import logging
import asyncio
import time
from fastapi import FastAPI, HTTPException
import httpx
from contextlib import asynccontextmanager

# Setting up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@asynccontextmanager
async def app_lifespan(app):
    # Startup logic
    async with httpx.AsyncClient() as client:
        app.state.http_client = client
        yield
        # Shutdown logic (if any)

app = FastAPI(lifespan=app_lifespan)

class DynamicLoadBalancer:
    def __init__(self, health_check_interval=5):
        self.servers = []
        self.health_check_interval = health_check_interval

    def register_server(self, server):
        if server not in [s['server'] for s in self.servers]:
            self.servers.append({"server": server, "healthy": True, "last_checked": time.time()})
            logging.info(f"Server {server} registered.")

    def remove_server(self, server):
        self.servers = [s for s in self.servers if s["server"] != server]
        logging.info(f"Server {server} deregistered.")

    async def check_server_health(self, client):
        for server_info in self.servers:
            server = server_info["server"]
            is_healthy = await self._check_health(client, server)
            server_info["healthy"] = is_healthy
            server_info["last_checked"] = time.time()

    async def _check_health(self, client, server):
        url = f"http://{server}/health-check"
        try:
            response = await client.get(url)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Health check failed for {server}: {e}")
            return False

    def get_next_server(self):
        available_servers = [s for s in self.servers if s["healthy"]]
        if not available_servers:
            raise ValueError("No healthy servers available.")
        # Round-robin selection
        server = available_servers.pop(0)
        available_servers.append(server)
        return server["server"]

load_balancer = DynamicLoadBalancer()

@app.post("/register")
def register_server(server: str):
    load_balancer.register_server(server)
    return {"status": "Server registered successfully"}

@app.delete("/deregister")
def deregister_server(server: str):
    load_balancer.remove_server(server)
    return {"status": "Server deregistered successfully"}

@app.get("/next")
def get_next_server():
    try:
        next_server = load_balancer.get_next_server()
        return {"next_server": next_server}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/list-workers")
def list_workers():
    registered_workers = [s["server"] for s in load_balancer.servers]
    return {"registered_workers": registered_workers}

async def periodic_health_check():
    while True:
        await load_balancer.check_server_health(app.state.http_client)
        await asyncio.sleep(load_balancer.health_check_interval)

if __name__ == "__main__":
    import uvicorn
    # Check if the script is run as the main module
    if asyncio.get_event_loop().is_running():
        asyncio.create_task(periodic_health_check())
    else:
        uvicorn.run(app, host="127.0.0.1", port=8000)
