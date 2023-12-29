from locust import HttpUser, task, between

class LoadTester(HttpUser):
    wait_time = between(1, 2)  # Random wait time between requests from 1 to 2 seconds

    @task(5)
    def request_next_worker(self):
        self.client.get("http://localhost:8000/next")

    @task(1)
    def request_other_endpoint(self):
        # Replace with other endpoints as needed
        self.client.get("http://localhost:8002/health-check")
