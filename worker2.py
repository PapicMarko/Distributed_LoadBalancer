import logging
import uvicorn
from fastapi import FastAPI
import httpx
from contextlib import asynccontextmanager

# Configurable Parameters
LOAD_BALANCER_ADDRESS = "localhost:8000"  # Address of the load balancer
WORKER_ADDRESS = "localhost:8002"  # Address of this worker
LOG_LEVEL = logging.INFO

# Configure logging
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic: Register with the load balancer
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
        yield  # Yield for the context manager

    # Shutdown logic (if any)


app = FastAPI(lifespan=lifespan)

@app.get("/")
async def worker2_endpoint():
    logging.info("Received request in worker2")
    response_data = {
        "worker_id": "worker2",
        "message": "This is the response from worker 2."
    }
    return response_data


@app.get("/health-check")
def health_check():
    # Health check endpoint
    return {"status": "OK"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8002)