from locust import HttpUser, task, between

class LoadTester(HttpUser):
    wait_time = between(1, 2)  # Random wait time between requests from 1 to 2 seconds

    @task(5)
    def request_through_load_balancer(self):
        # Targeting the load balancer to test round-robin distribution
        self.client.get("http://localhost:8001/worker-health")
