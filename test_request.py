import requests
import time

while True:
    response = requests.get("http://localhost:8001/health-check")
    print(response.status_code)
    time.sleep(0.25)  # Wait for 1 second between requests
