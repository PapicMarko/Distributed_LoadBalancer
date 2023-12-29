import logging
import asyncio
import time
from fastapi import FastAPI, HTTPException
import httpx
from contextlib import asynccontextmanager
from pydantic import BaseModel
import subprocess
import os

# Configurable Parameters
HEALTH_CHECK_INTERVAL = 2  # seconds
LOG_LEVEL = logging.INFO

# Setting up basic logging
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')

@asynccontextmanager
async def app_lifespan(app):
    # Startup logic
    async with httpx.AsyncClient() as client:
        app.state.http_client = client
        # Start the health check and scaling loops
        health_task = asyncio.create_task(app.state.load_balancer.check_server_health(client))
        scaling_task = asyncio.create_task(app.state.load_balancer.scale_workers())
        yield
        # Shutdown logic
        health_task.cancel()
        scaling_task.cancel()
        await app.state.load_balancer.shutdown()

app = FastAPI(lifespan=app_lifespan)

class DynamicLoadBalancer:
    def __init__(self, health_check_interval=HEALTH_CHECK_INTERVAL):
        self.servers = []
        self.health_check_interval = health_check_interval
        self.shutdown_event = asyncio.Event()
        self.active_workers = {}
        self.max_requests_per_worker = 10
        self.max_workers = 5
        self.worker_command_template = "python worker.py {}"  # Command template

    async def scale_workers(self):
        while not self.shutdown_event.is_set():
            if self.should_scale_up():
                await self.start_new_worker()
            elif self.should_scale_down():
                await self.stop_worker()
            await asyncio.sleep(10)

    def should_scale_up(self):
        total_requests = sum(worker['requests'] for worker in self.servers)
        if len(self.servers) < self.max_workers and total_requests / len(self.servers) > self.max_requests_per_worker:
            logging.info(f"Scaling up condition met. Total requests: {total_requests}, Servers: {len(self.servers)}")
            return True
        logging.info(f"Scaling up condition not met. Total requests: {total_requests}, Servers: {len(self.servers)}")
        return False

    async def start_new_worker(self):
        if len(self.active_workers) < self.max_workers:
            next_port = 8001 + len(self.active_workers) # Dynamically assign the next port
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




    def register_server(self, server):
        if server not in [s['server'] for s in self.servers]:
            self.servers.append({"server": server, "healthy": True, "last_checked": time.time()})
            logging.info(f"Server {server} registered.")

    def remove_server(self, server):
        self.servers = [s for s in self.servers if s["server"] != server]
        logging.info(f"Server {server} deregistered.")

    async def check_server_health(self, client):
        while not self.shutdown_event.is_set():
            for server_info in self.servers:
                server = server_info["server"]
                is_healthy = await self._check_health(client, server)
                server_info["healthy"] = is_healthy
                server_info["last_checked"] = time.time()
            await asyncio.sleep(self.health_check_interval)

    async def _check_health(self, client, server):
        url = f"http://{server}/health-check"
        try:
            response = await client.get(url)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Health check failed for {server}: {e}")
            return False

    def get_next_server(self):
        # Round-robin logic
        self.servers.append(self.servers.pop(0))
        for server in self.servers:
            if server["healthy"]:
                return server
        raise ValueError("No healthy servers available.")

    async def shutdown(self):
        self.shutdown_event.set()
        logging.info("Shutdown initiated for Load Balancer.")

class WorkerRegistration(BaseModel):
    server: str


# Create an instance of DynamicLoadBalancer with a health check interval of 10 seconds
load_balancer = DynamicLoadBalancer(health_check_interval=HEALTH_CHECK_INTERVAL)
app.state.load_balancer = load_balancer



#POST REQUESTS


@app.post("/register")
def register_server(server: str):
    DynamicLoadBalancer.register_server(server)
    return {"status": "Server registered successfully"}

@app.delete("/deregister")
def deregister_server(server: str):
    DynamicLoadBalancer.remove_server(server)
    return {"status": "Server deregistered successfully"}

@app.get("/next")
def get_next_server():
    try:
        next_server = app.state.load_balancer.get_next_server()
        logging.info(f"Selected worker: {next_server}")
        return {"next_server": next_server}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/list-workers")
def list_workers():
    registered_workers = [s["server"] for s in DynamicLoadBalancer.servers]
    return {"registered_workers": registered_workers}



# Endpoint for automatic worker registration
@app.post("/register-worker")
async def register_worker(worker: WorkerRegistration):
    app.state.load_balancer.register_server(worker.server)
    return {"message": f"Worker {worker.server} registered successfully."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
