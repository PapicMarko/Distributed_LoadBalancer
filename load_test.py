from locust import task, HttpUser
import logging

class MyUser(HttpUser):
    # ...

    @task
    def register_server(self):
        payload = {"server": "worker1"}  # Provide the "server" parameter
        headers = {"Content-Type": "application/json"}
        
        # Send the POST request with payload
        response = self.client.post("/register", json=payload, headers=headers)
        
        # Log the payload and response
        logging.info(f"Request Payload: {payload}")
        logging.info(f"Response: {response.status_code} - {response.text}")
