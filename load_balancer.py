import logging
import asyncio
from fastapi import FastAPI, HTTPException, Request, Response
import httpx
from contextlib import asynccontextmanager
from pydantic import BaseModel
import subprocess
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse
import json
from collections import deque
from datetime import datetime, timedelta

#Loading the configuration from config.json
with open("config.json") as config_file:
    config = json.load(config_file)

#Configurable parameters from config.json
LOAD_BALANCER_HOST = config["load_balancer_host"]
LOAD_BALANCER_PORT = config["load_balancer_port"]
WORKER_HOST = config["worker_host"]
WORKER_PORT = config["worker_port"]
HEALTH_CHECK_INTERVAL = config["health_check_interval"]
LOG_LEVEL = config["log_level"]

# Convert log_level string from config to actual logging level
log_level_mapping = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}
LOG_LEVEL = log_level_mapping.get(LOG_LEVEL.upper(), logging.INFO)

# Setting up basic logging with the configured level
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')

class Worker(BaseModel):
    server: str
    healthy: bool = True
    active_requests: int = 0

class LoadReport(BaseModel):
    server: str
    load: int

#START OF CLASS
class DynamicLoadBalancer:
    def __init__(self, app, health_check_interval=HEALTH_CHECK_INTERVAL):
        self.app = app
        self.servers = []
        self.health_check_interval = health_check_interval
        self.shutdown_event = asyncio.Event()
        self.max_requests_per_worker = 5
        self.max_workers = 5
        self.current_worker_index = -1  # For round-robin
        self.active_workers = {}  # Track active workers
        self.worker_restart_history = deque(maxlen=10) # Keep last 10 restart times
        self.restart_threshold = timedelta(minutes=5)  # Time window for restart limit
        self.max_restarts_in_threshold = 3 # Max restarts allowed in the above time window

    def get_next_server(self):
        healthy_servers = [server for server in self.servers if server.healthy]
        if not healthy_servers:
            logging.error("No healthy servers available.")
            raise ValueError("No healthy servers available.")
        self.current_worker_index = (self.current_worker_index + 1) % len(healthy_servers)
        return healthy_servers[self.current_worker_index]

    async def start_new_worker(self):
        # Check if we have exceeded the restart threshold
        now = datetime.now()
        restarts_in_threshold = sum(1 for t in self.worker_restart_history if now - t < self.restart_threshold)
        if restarts_in_threshold >= self.max_restarts_in_threshold:
            logging.error(f"Worker restart limit reached. Not starting new worker.")
            return # Do not start new worker if restart limit reached
        
        existing_ports = [int(worker.server.split(":")[1]) for worker in self.servers]
        new_worker_port = max(existing_ports) + 1 if existing_ports else 8002
        new_worker_address = f"{WORKER_HOST}:{new_worker_port}"

        #Starting the worker and according terminal
        subprocess.Popen(f'start cmd /k python worker.py {new_worker_port}', shell=True)
        await asyncio.sleep(1)  # Wait for the worker to start
        self.register_server(new_worker_address)
        logging.info(f"New worker started and registered: {new_worker_address}")

        self.worker_restart_history.append(now)

    def get_next_available_port(self):
        existing_ports = [int(worker.server.split(':')[1]) for worker in self.servers]
        return max(existing_ports) + 1 if existing_ports else 8001

    def register_server(self, server: str):
        existing_worker = next((worker for worker in self.servers if worker.server == server), None)

        if existing_worker:
            existing_worker.healthy = True
            existing_worker.active_requests = 0
            logging.info(f"Updated registration for exisiting server: {server}")
        else:
            self.servers.append(Worker(server=server, active_requests=0))
            logging.info(f"New server registered: {server}")



    async def remove_server(self, server: str):
        #Sending a shutdown request before removing the server
        shutdown_url = f"http://{server}/shutdown"
        async with httpx.AsyncClient() as client:
            try:
                await client.post(shutdown_url)
                logging.info(f"Shutdown request sent to worker {server}")
            except Exception as exc:
                logging.error(f"Failed to send shutdown request to worker {server}: {exc}")
                              
        self.servers = [worker for worker in self.servers if worker.server != server]

    

    def should_scale_up(self):
        total_requests = sum(worker.active_requests for worker in self.servers)
        if total_requests > self.max_requests_per_worker * len(self.servers):
            logging.info("Scaling up due to high load...")
            return True
        return False
    
    def should_scale_down(self):
        total_requests = sum(worker.active_requests for worker in self.servers if worker.healthy)
        if len(self.servers) > 1 and total_requests < self.max_requests_per_worker * (len(self.servers) - 1):
            logging.info("Scaling down due to low load...")
            return True
        return False

    async def forward_request(self, path: str, request: Request):
        worker = self.get_next_server()
        url = f"http://{worker.server}{path}"
        client = request.app.state.http_client
        try:
            response = await client.request(
                method = request.method,
                url = url,
                headers = request.headers,
                data = await request.body(),
            )
            return Response(content=response.content, status_code=response.status_code, headers=response.headers)
        except httpx.RequestError as exc:
            #Handles the case where a worker could not handle the request
            logging.error(f"HTTP error occured: {exc}")
            raise HTTPException(status_code=503, detail = "Service Unavailable")
        except Exception as exc:
            logging.error(f"An error occured while forwarding the request: {exc}")
            raise HTTPException(status_code=500, detail = "Internal Server Error")
            

    async def perform_health_checks(self):
        while not self.shutdown_event.is_set():
            for server in self.servers:
                logging.info(f"Performing health check for {server.server}")
                await self.check_server_health(server)
            await asyncio.sleep(self.health_check_interval)

    async def scale_workers(self):

        active_requests_history = {worker.server: [] for worker in self.servers}

        while not self.shutdown_event.is_set():
            if self.should_scale_up():
                await self.start_new_worker()
            await asyncio.sleep(self.health_check_interval)

        for worker in self.servers:
            active_requests_history[worker.server].append(worker.active_requests)

            if len(active_requests_history[worker.server]) > 5:
                active_requests_history[worker.server].pop(0)

            if len(self.servers) > 1 and all(active_req < 2 for active_req in active_requests_history[worker.server]):
                self.remove_server(worker.server)
                active_requests_history.pop(worker.server, None)
                logging.info(f"Worker {worker.server} scaled down and removed due to low load")
                break

        await asyncio.sleep(self.health_check_interval)

    async def check_server_health(self, server):
        try:
            url = f"http://{server.server}/worker-health"
            client = self.app.state.http_client
            response = await client.get(url)
            if response.status_code == 200:
                try:
                    data = response.json()
                    server.healthy = data["status"] == "OK"
                    server.active_requests = data.get("active_requests", 0)
                    health_status = 'Healthy' if server.healthy else 'Unhealthy'
                    logging.info(f"Health check for {server.server}: {server.active_requests} active requests - {health_status}")
                except ValueError as json_error:
                # This block will execute if the response is not valid JSON
                    raise ValueError(f"Invalid JSON response: {json_error}")
            else:
                raise Exception(f"Health check failed with status code {response.status_code}")
        except (httpx.RequestError, ValueError, Exception) as e:
            server.healthy = False
            server.active_requests = 0  # Assuming no active requests if there's an error
            logging.error(f"Health check failed for {server.server}: {e}")

            # Remove the unhealthy server
            self.servers.remove(server)
            logging.info(f"Removed unhealthy worker: {server.server}")

            # Start a new worker
            await self.start_new_worker()
#CLASS END
            


#FASTAPI APP           
app = FastAPI()

load_balancer = DynamicLoadBalancer(app = app)

@asynccontextmanager
async def app_lifespan(app_context: FastAPI):
    app_context.state.http_client = httpx.AsyncClient()
    app_context.state.load_balancer = DynamicLoadBalancer(app_context)
    health_task = asyncio.create_task(app_context.state.load_balancer.perform_health_checks())
    scaling_task = asyncio.create_task(app_context.state.load_balancer.scale_workers())
    try:
        yield
    finally:
        health_task.cancel()
        scaling_task.cancel()
        await asyncio.gather(health_task, scaling_task, return_exceptions=True)
        await app_context.state.http_client.aclose()


app = FastAPI(lifespan = app_lifespan)


#EXCEPTION HANDLER
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(exc: RequestValidationError):
    logging.error(f"Validation error: {exc.body}")
    return PlainTextResponse(str(exc), status_code=422)

#ROOT ENDPOINT
@app.get("/")
async def root():
    return {"message": "This is the load balancer!"}

#REGISTER WORKER
@app.post("/register-worker")
async def register_worker(worker: Worker):
    app.state.load_balancer.register_server(worker.server)
    logging.info(f"Worker {worker.server} connected to load balancer.")
    return {"message": f"Worker {worker.server} registered successfully."}       


#REPORT LOAD
@app.post("/report-load")
async def report_load(report: LoadReport):
    logging.info(f"Received load report: {report.model_dump_json()}")
    found = False
    for worker in app.state.load_balancer.servers:
        if worker.server == report.server:
            worker.active_requests = report.load
            logging.info(f"Load updated for worker {report.server}: {report.load} active requests")
            found = True
            break
    if not found:
        logging.warning(f"Worker {report.server} not found in registered servers")
    return {"message": "Load updated"}

#LOAD BALANCER HEALTH
@app.get("/load-balancer-health")
def load_balancer_health():
    worker_statuses = []
    for worker in app.state.load_balancer.servers:
        status = "healthy" if worker.healthy else "unhealthy"
        worker_statuses.append(f"  {{'worker_address': '{worker.server}', 'status': '{status}'}}")
    formatted_response = "\n".join([
        "{",
        "  'status': 'OK',",
        "  'load_balancer_message': 'Load Balancer is operational.',",
        "  'workers': [",
        ",\n".join(worker_statuses),
        "  ]",
        "}"
    ])
    return Response(content=formatted_response, media_type="application/json")


#NEXT SERVER - GETS THE NEXT WORKING SERVER
@app.get("/next")
def get_next_server():
    try:
        next_server = app.state.load_balancer.get_next_server()
        return {"next_server": next_server.server}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

#LIST WORKERS - LISTS AVALIABLE WORKERS
@app.get("/list-workers")
def list_workers():
    registered_workers = [s.server for s in app.state.load_balancer.servers]
    return {"registered_workers": registered_workers}


#TEST ENDPOINT - FOR TESTING PURPOSES
@app.route("/test", methods=["GET", "POST"])
async def test_endpoint(request: Request):
    return await app.state.load_balancer.forward_request(request.url.path, request)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=LOAD_BALANCER_HOST, port=LOAD_BALANCER_PORT)
