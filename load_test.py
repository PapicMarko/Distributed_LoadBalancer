from locust import HttpUser, task, between

class LoadTester(HttpUser):
    wait_time = between(1, 2)  # Random wait time between requests from 1 to 2 seconds

    @task
    def request_next_worker(self):
        # Sending a GET request to the load balancer's /next endpoint
        self.client.get("http://localhost:8000")
