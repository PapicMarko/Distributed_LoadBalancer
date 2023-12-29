import logging
import uvicorn
from fastapi import FastAPI, Request
import httpx
from contextlib import asynccontextmanager
import sys
import asyncio
from asyncio import Lock

# Configuration Parameters
LOAD_BALANCER_ADDRESS = "localhost:8000"
WORKER_PORT = sys.argv[1] if len(sys.argv) > 1 else "8001"
WORKER_ADDRESS = f"localhost:{WORKER_PORT}"
LOG_LEVEL = logging.INFO

logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()
active_requests = 0
lock = Lock()



async def report_load_to_balancer():
    global active_requests
    while True:
        async with lock:
            current_load = active_requests
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"http://{LOAD_BALANCER_ADDRESS}/report-load", 
                                             json={"server": WORKER_ADDRESS, "load": current_load})
                logging.info(f"Reported load {current_load} to load balancer, response status: {response.status_code}")
        except Exception as e:
            logging.error(f"Error reporting load to load balancer: {e}")
        await asyncio.sleep(10)  # Report every 10 seconds, adjust as needed


@app.middleware("http")
async def count_request(request: Request, call_next):
    global active_requests
    async with lock:
        active_requests += 1
    response = await call_next(request)
    async with lock:
        active_requests -= 1
    return response

@app.get("/health-check")
def health_check():
    logging.info(f"Health check: {active_requests} active requests")
    return {"status": "OK", "active_requests": active_requests}

async def startup_event():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"http://{LOAD_BALANCER_ADDRESS}/register-worker", json={"server": WORKER_ADDRESS})
            logging.info(f"Worker registration response: {response.status_code}")
        except Exception as e:
            logging.error(f"Failed to register with the load balancer: {e}")

async def app_startup():
    asyncio.create_task(report_load_to_balancer())

async def app_shutdown():
    # Add any cleanup logic here
    pass

app.add_event_handler("startup", app_startup)
app.add_event_handler("shutdown", lambda: logging.info("Worker shutdown"))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(WORKER_PORT))
