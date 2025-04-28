import networkx as nx


class Network:
    def __init__(self):
        self.graph = nx.Graph()  # Graph G(V, E)
        self.delays = {}  # Delay for each link e in E
        self.bandwidths = {}  # Bandwidth for each link e in E

    def add_link(self, node1, node2, delay, bandwidth):
        self.graph.add_edge(node1, node2, delay=delay)
        self.delays[(node1, node2)] = delay
        self.bandwidths[(node1, node2)] = bandwidth


def calculate_overall_delay(network, path, T, queuing_delays):
    """Calculate the total delay for a path, including propagation and queuing delays."""
    total_delay = 0.0
    for i in range(len(path) - 1):
        current_node = path[i]
        next_node = path[i + 1]
        link = (current_node, next_node)
        propagation_delay = network.delays.get(link, 0.0)
        queuing_delay = queuing_delays.get(next_node, 0.0)
        total_delay += propagation_delay + queuing_delay + T
    return total_delay 