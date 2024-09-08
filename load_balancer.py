from flask import Flask, request
import requests

app = Flask(__name__)

class RoundRobinLoadBalancer:
    def __init__(self, servers):
        self.servers = servers
        self.index = -1

    def get_next_server(self):
        self.index = (self.index + 1) % len(self.servers)
        return self.servers[self.index]

servers = []  # http://ipv4:port

load_balancer = RoundRobinLoadBalancer(servers)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>', methods=['GET', 'POST'])
def handle_request(path):
    target_server = load_balancer.get_next_server()
    target_url = f"{target_server}/{path}"

    if request.method == 'GET':
        response = requests.get(target_url, params=request.args)
    elif request.method == 'POST':
        response = requests.post(target_url, data=request.data)
    
    return (response.content, response.status_code, response.headers.items())

if __name__ == "__main__":
    app.run(port=5020)
