import logging
import uvicorn
from fastapi import FastAPI, Request
import httpx
import sys
import asyncio
import os

# Configuration Parameters
LOAD_BALANCER_ADDRESS = "localhost:8000"
WORKER_PORT = sys.argv[1] if len(sys.argv) > 1 else "8001"
WORKER_ADDRESS = f"localhost:{WORKER_PORT}"
LOG_LEVEL = logging.INFO
LOG_FILE = f"worker_{WORKER_PORT}.log"

# Setting up basic logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()
active_requests = 0
worker_lock = asyncio.Lock()  # Lock for thread-safe operation on active_requests

async def report_current_load():
    async with worker_lock:
        current_load = active_requests
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"http://{LOAD_BALANCER_ADDRESS}/report-load",
                json={"server": WORKER_ADDRESS, "load": current_load},
            )
    except Exception as e:
        logging.error(f"Error reporting load to load balancer: {e}")

@app.middleware("http")
async def count_request(request: Request, call_next):
    global active_requests
    async with worker_lock:
        active_requests += 1
        logging.info(f"Request received. Active requests: {active_requests}")
    
    # Report load at the start of handling a request
    await report_current_load()
    
    response = await call_next(request)
    
    async with worker_lock:
        active_requests -= 1
        logging.info(f"Request completed. Active requests: {active_requests}")
    
    # Report load at the end of handling a request
    await report_current_load()
    
    return response

@app.get("/health-check")
def health_check():
    logging.info(f"Health check: {active_requests} active requests")
    return {"status": "OK", "active_requests": active_requests}

async def startup_event():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"http://{LOAD_BALANCER_ADDRESS}/register-worker", json={"server": WORKER_ADDRESS})
            if response.status_code == 200:
                logging.info(f"Successfully registered with load balancer at {LOAD_BALANCER_ADDRESS}")
            else:
                logging.error(f"Failed to register with load balancer: Status code {response.status_code}")
        except Exception as e:
            logging.error(f"Exception occurred while registering with load balancer: {e}")

app.add_event_handler("startup", startup_event)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(WORKER_PORT))
