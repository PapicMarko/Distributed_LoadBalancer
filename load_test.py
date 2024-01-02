from locust import HttpUser, task, between

class LoadTester(HttpUser):
    wait_time = between(1, 2)  # Random wait time between requests from 1 to 2 seconds

    @task(5)
    def request_through_load_balancer(self):
        # Targeting the load balancer to test round-robin distribution
        self.client.get("http://localhost:8000/")

    # Uncomment and modify these tasks if you want to target specific endpoints or workers directly
    """
    @task(1)
    def request_specific_endpoint(self):
        # Replace with specific endpoints as needed
        self.client.get("http://localhost:8000/some-specific-endpoint")

    @task(1)
    def request_another_specific_endpoint(self):
        # Replace with other specific endpoints as needed
        self.client.get("http://localhost:8000/another-specific-endpoint")
    """
