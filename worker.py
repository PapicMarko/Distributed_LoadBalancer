import logging
import uvicorn
from fastapi import FastAPI, Request
import httpx
import sys
import asyncio
from datetime import datetime, timedelta
import json

with open("config.json") as config_file:
    config = json.load(config_file)

LOAD_BALANCER_ADDRESS = config["load_balancer_address"]
WORKER_HOST = config["worker_host"]
WORKER_PORT = sys.argv[1] if len(sys.argv) > 1 else config["worker_port"]
LOG_LEVEL = config["log_level"]
REPORT_TIMEOUT = config["report_timeout"]
REPORT_INTERVAL = timedelta(seconds=config["report_interval"])

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

app = FastAPI()
active_requests = 0
worker_lock = asyncio.Lock()  # Lock for thread-safe operation on active_requests
last_report_time = datetime.now()  # Track the last time the load was reported
is_registered_with_load_balancer = False #Global flag to check registration with load balancer

async def report_current_load():
    async with worker_lock:
        current_load = active_requests

    try:
        async with httpx.AsyncClient(timeout=REPORT_TIMEOUT) as client:
            worker_address = f"{WORKER_HOST}:{WORKER_PORT}"
            await client.post(
                f"http://{LOAD_BALANCER_ADDRESS}/report-load",
                json={"server": worker_address, "load": current_load}
            )
    except Exception as e:
        logging.error(f"Error reporting load to load balancer: {e}")


async def register_with_load_balancer():
    global is_registered_with_load_balancer
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"http://{LOAD_BALANCER_ADDRESS}/register-worker", json={"server": f"{WORKER_HOST}:{WORKER_PORT}"})
            if response.status_code == 200:
                logging.info(f"Successfully registered with load balancer at {LOAD_BALANCER_ADDRESS}")
                is_registered_with_load_balancer = True  # Set flag to True after successful registration
            else:
                logging.error(f"Failed to register with load balancer: Status code {response.status_code}")
        except Exception as e:
            logging.error(f"Exception occurred while registration with load balancer: {e}")

async def check_load_balancer_alive():
    global is_registered_with_load_balancer
    while True:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://{LOAD_BALANCER_ADDRESS}/load-balancer-health")
                if response.status_code == 200:
                    logging.info(f"Load balancer is alive")
                    if not is_registered_with_load_balancer:
                        await register_with_load_balancer()  # Attempt to register if not already registered
                else:
                    logging.error(f"Load balancer health check failed.")
                    is_registered_with_load_balancer = False  # Reset flag if load balancer is not healthy
        except Exception as e:
            logging.error(f"Error contacting load balancer: {e}")
            is_registered_with_load_balancer = False  # Reset flag if there's an error contacting load balancer
            
        await asyncio.sleep(30)  # Wait for 30 seconds before the next health check

@app.middleware("http")
async def count_request(request: Request, call_next):
    global active_requests, last_report_time
    current_time = datetime.now()

    async with worker_lock:
        active_requests += 1
        logging.info(f"Request received. Active requests: {active_requests}")

    response = await call_next(request)

    async with worker_lock:
        active_requests -= 1
        # logging.info(f"Request completed. Active requests: {active_requests}")

    # Report load if the interval has elapsed
    if current_time - last_report_time > REPORT_INTERVAL:
        await report_current_load()
        last_report_time = current_time

    return response

@app.get("/worker-health")
def health_check():
    logging.info(f"Health check: {active_requests} active requests")
    return {"status": "OK", "active_requests": active_requests}

@app.get("/")
def worker_info():
    logging.info(f"This is the worker {WORKER_HOST}")
    return {"status": "OK", "active_requests": active_requests}

@app.get("/test")
def test_endpoint():
    return {"message": "Test endpoint in worker reached successfully."}

@app.post("/test")
def test_endpoint_post():
    return {"message": "Test endpoint in worker reached successfully."}

@app.post("/shutdown")
async def shutdown(request: Request):
    #Endpoint to shutdown the worker
    func = request.app.extra["shutdown"]
    if func is not None:
        await func()
    return {"message": "Shutting down worker."}

async def startup_event():
    await register_with_load_balancer()  # Attempt initial registration with the load balancer

    # Always start the task to check load balancer health
    asyncio.create_task(check_load_balancer_alive())

app.add_event_handler("startup", startup_event)

if __name__ == "__main__":
    uvicorn.run(app, host=WORKER_HOST, port=int(WORKER_PORT))
