import time
import httpx
import logging

# Setting up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RoundRobinLoadBalancer:
    def __init__(self, servers):
        self.servers = servers
        self.current_index = 0

    def get_next_server(self):
        if not self.servers:
            raise ValueError("No servers available in the server pool.")
        server = self.servers[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.servers)
        return server
    
class DynamicLoadBalancer:
    def __init__(self, health_check_interval=5):
        self.servers = []
        self.current_index = 0
        self.health_check_interval = health_check_interval

    def add_server(self, server):
        self.servers.append({"server": server, "healthy": True, "last_checked": time.time()})

    def remove_server(self, server):
        self.servers = [s for s in self.servers if s["server"] != server]

    def check_all_servers_health(self):
        for server_info in self.servers:
            server = server_info["server"]
            is_healthy = self.check_server_health(server)
            server_info["healthy"] = is_healthy

    def check_server_health(self, server):
        url = f"http://{server}/health-check"
        try:
            with httpx.Client() as client:
                response = client.get(url)
                return response.status_code == 200
        except Exception as e:
            logging.error(f"Health check failed for {server}: {e}")
            return False

    def get_next_server(self):
        self._perform_health_checks()

        available_servers = [s for s in self.servers if s["healthy"]]
        if not available_servers:
            logging.warning("No healthy servers available in the server pool.")
            raise ValueError("No healthy servers available in the server pool.")

        server = available_servers[self.current_index]["server"]
        self.current_index = (self.current_index + 1) % len(available_servers)
        return server
    
    def _perform_health_checks(self):
        current_time = time.time()
        for server_info in self.servers:
            if current_time - server_info["last_checked"] >= self.health_check_interval:
                server = server_info["server"]
                is_healthy = self.check_server_health(server)
                server_info["healthy"] = is_healthy
                server_info["last_checked"] = current_time

# Example usage (commented out for production use)
"""
# RoundRobin
servers = ["Server1", "Server2", "Server3"]
load_balancer = RoundRobinLoadBalancer(servers)
for _ in range(10):
    next_server = load_balancer.get_next_server()
    print(f"Request directed to: {next_server}")

# DynamicLoadBalancer
dynamic_load_balancer = DynamicLoadBalancer()
dynamic_load_balancer.add_server("Server4")
dynamic_load_balancer.add_server("Server5")
for _ in range(10):
    next_server = dynamic_load_balancer.get_next_server()
    print(f"Request directed to: {next_server}")
"""
