import time
import httpx


class RoundRobinLoadBalancer:
    def __init__(self, servers):
        self.servers = servers
        self.current_index = 0

    def get_next_server(self):
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
        for s in self.servers:
            if s["server"] == server:
                self.servers.remove(s)

    def check_server_health(self, server):
        #Simulation of a health check, for example by attempting a connection
        
        #Health check logic
        url = f"http://{server}/health-check"
        try:
            with httpx.Client() as client:
                response = client.get(url)
                return response.status_code == 200
        except Exception as e:
            print(f"Health check failed for {server}: {e}")
        return False
    

    def get_next_server(self):
        self._perform_health_checks()

        available_servers = [s for s in self.servers if s["healthy"]]
        if not available_servers:
            raise ValueError("No healthy servers available in the server pool.")

        if not self.servers:
            raise ValueError("No servers available in the server pool")
        
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

# Example usage (RoundRobin)
servers = ["Server1", "Server2", "Server3", "Server4", "Server5"]
load_balancer = RoundRobinLoadBalancer(servers)

# Get the next server for each request
for _ in range(10):
    next_server = load_balancer.get_next_server()
    print(f"Request directed to: {next_server}")


# Example usage (DynamicLoadBalancer)
load_balancer = DynamicLoadBalancer()

# Add servers dynamically
load_balancer.add_server("Server1")
load_balancer.add_server("Server2")
load_balancer.add_server("Server3")

# Get the next server for each request
for _ in range(10):
    next_server = load_balancer.get_next_server()
    print(f"Request directed to: {next_server}")

# Remove a server dynamically
load_balancer.remove_server("Server2")

# Get the next server after removal
next_server_after_removal = load_balancer.get_next_server()
print(f"Request directed to: {next_server_after_removal}")


# Example usage
load_balancer = DynamicLoadBalancer(health_check_interval=5)

# Add servers dynamically
load_balancer.add_server("Server7")
load_balancer.add_server("Server8")
load_balancer.add_server("Server9")

# Get the next server for each request
for _ in range(10):
    next_server = load_balancer.get_next_server()
    print(f"Request directed to: {next_server}")

# Simulate a server becoming unhealthy
unhealthy_server = "Server8"
load_balancer.remove_server(unhealthy_server)

# Wait for a health check interval
time.sleep(6)

# Get the next server after health check
next_server_after_health_check = load_balancer.get_next_server()
print(f"Request directed to: {next_server_after_health_check}")