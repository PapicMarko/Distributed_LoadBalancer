from locust import HttpUser, task, between

class MyUser(HttpUser):
    wait_time = between(1, 3)  # Time between consecutive requests in seconds

    @task
    def get_next_server(self):
        self.client.get("/next")

