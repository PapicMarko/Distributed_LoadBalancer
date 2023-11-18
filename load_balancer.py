class RoundRobinLoadBalancer:
    def __init__(self, servers):
        self.servers = servers
        self.current_index = 0

    def get_next_server(self):
        server = self.servers[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.servers)
        return server

# Example usage
servers = ["Server1", "Server2", "Server3", "Server4", "Server5"]
load_balancer = RoundRobinLoadBalancer(servers)

# Get the next server for each request
for _ in range(10):
    next_server = load_balancer.get_next_server()
    print(f"Request directed to: {next_server}")
