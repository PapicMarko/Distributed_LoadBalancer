class RoundRobinLoadBalancer:
    def __init__(self, servers):
        self.servers = servers
        self.current_index = 0

    def get_next_server(self):
        server = self.servers[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.servers)
        return server
    
class DynamicLoadBalancer:
    def __init__(self):
        self.servers = []
        self.current_index = 0

    def add_server(self, server):
        self.servers.append(server)

    def remove_server(self, server):
        if server in self.servers:
            self.servers.remove(server)

    def get_next_server(self):
        if not self.servers:
            raise ValueError("No servers available in the server pool")
        
        server = self.servers[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.servers)
        return server

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


