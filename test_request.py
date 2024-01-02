import requests
import time

while True:
    response = requests.get("http://localhost:8000/test")
    print(response.status_code)
    time.sleep(0.25)  # Wait for 1 second between requests
