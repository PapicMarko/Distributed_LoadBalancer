import logging
import uvicorn
from fastapi import FastAPI, Request
import httpx
from contextlib import asynccontextmanager
import sys

# Configuration Parameters
LOAD_BALANCER_ADDRESS = "localhost:8000"  # Address of the load balancer

# Read worker's unique port from command line arguments (default to 8001 if not provided)
WORKER_PORT = sys.argv[1] if len(sys.argv) > 1 else "8001"
WORKER_ADDRESS = f"localhost:{WORKER_PORT}"  # Address of this worker

LOG_LEVEL = logging.INFO

# Configure logging
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()

active_requests = 0

@app.middleware("http")
async def count_request(request: Request, call_next):
    global active_requests
    active_requests += 1
    response = await call_next(request)
    active_requests -= 1
    return response

@app.get("/")
async def worker_endpoint():
    logging.info(f"Received request in worker on port {WORKER_PORT}")
    response_data = {
        "worker_id": f"worker_{WORKER_PORT}",
        "message": f"This is the response from worker on port {WORKER_PORT}."
    }
    return response_data

@app.get("/health-check")
def health_check():
    return {"status": "OK", "active_requests": active_requests}

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"http://{LOAD_BALANCER_ADDRESS}/register-worker", 
                json={"server": WORKER_ADDRESS}
            )
            if response.status_code == 200:
                logging.info("Successfully registered with the load balancer.")
            else:
                logging.error(f"Failed to register with the load balancer: Status code {response.status_code}")
        except Exception as e:
            logging.error(f"Failed to register with the load balancer: {e}")
        yield

app.add_event_handler("startup", lifespan(app).__aenter__)
app.add_event_handler("shutdown", lifespan(app).__aexit__)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(WORKER_PORT))
