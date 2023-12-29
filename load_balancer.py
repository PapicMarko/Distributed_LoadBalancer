import logging
import asyncio
import time
from fastapi import FastAPI, HTTPException
import httpx
from contextlib import asynccontextmanager
from pydantic import BaseModel
import subprocess

# Configurable Parameters
HEALTH_CHECK_INTERVAL = 2  # seconds
LOG_LEVEL = logging.INFO

# Setting up basic logging
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')

class Worker(BaseModel):
    server: str
    healthy: bool = True
    last_checked: float = 0
    active_requests: int = 0

class DynamicLoadBalancer:
    def __init__(self, health_check_interval=HEALTH_CHECK_INTERVAL):
        self.servers = []
        self.health_check_interval = health_check_interval
        self.shutdown_event = asyncio.Event()
        self.active_workers = {}
        self.max_requests_per_worker = 10
        self.max_workers = 5
        self.worker_command_template = "python worker.py {}"

    async def scale_workers(self):
        while not self.shutdown_event.is_set():
            if self.should_scale_up():
                await self.start_new_worker()
            elif self.should_scale_down():
                await self.stop_worker()
            await asyncio.sleep(self.health_check_interval)

    def should_scale_up(self):
        total_requests = sum(worker.active_requests for worker in self.servers)
        average_requests = total_requests / len(self.servers) if self.servers else 0
        logging.info(f"Scale up check: total {total_requests}, average {average_requests}")
        return len(self.servers) < self.max_workers and average_requests > self.max_requests_per_worker

    def should_scale_down(self):
        # Implement your logic to determine if scaling down is needed
        # For example, if the load is consistently low for a certain period
        return False

    async def start_new_worker(self):
        if len(self.active_workers) < self.max_workers:
            next_port = 8001 + len(self.active_workers)
            worker_command = self.worker_command_template.format(next_port)
            try:
                logging.info(f"Attempting to start new worker: {worker_command}")
                process = subprocess.Popen(worker_command, shell=True)
                self.active_workers[process.pid] = process
                logging.info(f"Started new worker on port {next_port} with PID: {process.pid}")
            except Exception as e:
                logging.error(f"Failed to start new worker on port {next_port}: {e}")

    async def stop_worker(self):
        if self.active_workers:
            pid, process = self.active_workers.popitem()
            process.terminate()
            logging.info(f"Stopped worker with PID: {pid}")

    def register_server(self, server: str):
        self.servers.append(Worker(server=server))

    def remove_server(self, server: str):
        self.servers = [s for s in self.servers if s.server != server]

    def get_next_server(self):
        # Implement round-robin logic to select the next server
        healthy_servers = [server for server in self.servers if server.healthy]
        if not healthy_servers:
            raise ValueError("No healthy servers available.")

        # Move the first server to the end of the list to rotate them
        selected_server = healthy_servers.pop(0)
        self.servers.append(selected_server)
        return selected_server

    async def check_server_health(self, client):
        while not self.shutdown_event.is_set():
            for server_info in self.servers:
                server = server_info["server"]
                is_healthy = await self._check_health(client, server)
                server_info["healthy"] = is_healthy
                server_info["last_checked"] = time.time()
            await asyncio.sleep(self.health_check_interval)

    async def _check_health(self, client: httpx.AsyncClient, server: Worker):
        url = f"http://{server.server}/health-check"
        try:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                server.healthy = data["status"] == "OK"
                server.active_requests = data.get("active_requests", 0)
                logging.info(f"Health check for {server.server}: {server.active_requests} active requests")
            else:
                server.healthy = False
        except Exception as e:
            logging.error(f"Health check failed for {server.server}: {e}")
            server.healthy = False

    async def shutdown(self):
        self.shutdown_event.set()
        logging.info("Shutdown initiated for Load Balancer.")

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient()
    app.state.load_balancer = DynamicLoadBalancer()
    health_task = asyncio.create_task(app.state.load_balancer.check_server_health(app.state.http_client))
    scaling_task = asyncio.create_task(app.state.load_balancer.scale_workers())
    yield
    health_task.cancel()
    scaling_task.cancel()
    await app.state.load_balancer.shutdown()
    await app.state.http_client.aclose()

app = FastAPI(lifespan=app_lifespan)

@app.post("/register-worker")
async def register_worker(worker: Worker):
    app.state.load_balancer.register_server(worker.server)
    return {"message": f"Worker {worker.server} registered successfully."}

@app.post("/report-load")
async def report_load(data: dict):
    server = data.get("server")
    load = data.get("load")
    for worker in app.state.load_balancer.servers:
        if worker.server == server:
            worker.active_requests = load
            break
    logging.info(f"Load reported for {server}: {load}")

@app.get("/next")
def get_next_server():
    try:
        next_server = app.state.load_balancer.get_next_server()
        return {"next_server": next_server.server}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/list-workers")
def list_workers():
    registered_workers = [s.server for s in app.state.load_balancer.servers]
    return {"registered_workers": registered_workers}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
