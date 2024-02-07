# Distributed_LoadBalancer


##Table of Contents


- [Overview](#overview)
- [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)
- [Links](#links)


##Overview
A load balancer made for my college course Distributed Systems and for my use to improve my Python and learn about FastAPI...

"Load Balancer" is an application for processing and distributing web requests to worker services. FastAPI is used to build RESTful APIs in Python. The load balancer receives requests to its endpoints and distributes those requests to available workers. A round robin algorithm is used for distributed management of requests - the load balancer distributes the processes that alternate in execution, one after the other in a repeating sequence, and each of them is turned off when it spends its time slice. For example, if there are two "services" running, the round-robin algorithm will use both of them alternately, or if more workers are used, it will do it in a round-robin fashion. Dynamic worker registration, health checks for load balancer and workers, load-reporting mechanism for worker scaling, etc. are implemented. Locust 2.20.0 - web framework for load testing is used for testing, but it is possible use any other framework.


##Installation

1. Clone the repository
```bash
   git clone https://github.com/PapicMarko/Distributed_LoadBalancer.git


2. Install dependencies 
pip install -r requirements.txt


##Usage

1. Run the load balancer using the terminal window 
    python load_balancer.py:8000
    "OR"
   Run it by running script

2. Run a worker service
    python worker.py:port (for example: python worker.py 8001)


3. Run "localhost:8000/docs" for overview, or run locust for stress testing
     locust -f load_test.py  
     !IMPORTANT! - if locust is not working make sure it is added to your path!

4. Use ThunderboltClient or any other service for quick usage.


