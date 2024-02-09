from locust import HttpUser, task, between
import json

with open("config.json") as config_file:
    config = json.load(config_file)

#Extract the load balancer address from the configuration
LOAD_BALANCER_ADDRESS = config["load_balancer_address"]

class LoadTester(HttpUser):
    wait_time = between(1, 2)  # Random wait time between requests from 1 to 2 seconds

    @task(5)
    def request_through_load_balancer(self):
        # Targeting the load balancer to test round-robin distribution
        self.client.get(f"http://{LOAD_BALANCER_ADDRESS}/test")
