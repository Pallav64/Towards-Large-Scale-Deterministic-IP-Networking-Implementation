import networkx as nx
import math


class Network:
    def __init__(self):
        self.graph = nx.Graph()  # Graph G(V, E)
        self.delays = {}  # Delay for each link e in E
        self.bandwidths = {}  # Bandwidth for each link e in E

    def add_link(self, node1, node2, delay, bandwidth):
        self.graph.add_edge(node1, node2, delay=delay)
        self.delays[(node1, node2)] = delay
        self.bandwidths[(node1, node2)] = bandwidth
    
    def calculate_tau(self, upstream_node, downstream_node, cycle_duration_T):
        """
        Calculate τ (tau) for a specific upstream-downstream node pair.
        
        Args:
            upstream_node: The ID of the upstream node
            downstream_node: The ID of the downstream node
            cycle_duration_T: The cycle duration in μs
            
        Returns:
            tau: The τ value in ms (waiting time between packet reception and transmission)
        """
        # Get the propagation delay between the nodes (in ms)
        edge = (upstream_node, downstream_node)
        reversed_edge = (downstream_node, upstream_node)
        
        if edge in self.delays:
            propagation_delay = self.delays[edge]
        elif reversed_edge in self.delays:
            propagation_delay = self.delays[reversed_edge]
        else:
            # No direct connection
            return None
            
        # Convert propagation delay from ms to μs for consistency
        propagation_delay_us = propagation_delay * 1000
        
        # Calculate when the packet reception ends (Pe)
        # Pe = Pb + T where Pb is when the first bit arrives
        # Pb is determined by the propagation delay
        reception_end_time = propagation_delay_us + cycle_duration_T
        
        # Calculate which cycle this corresponds to
        cycle_number = math.ceil(reception_end_time / cycle_duration_T)
        
        # Calculate the start time of the next available cycle (Tb)
        next_cycle_start = cycle_number * cycle_duration_T
        
        # Calculate τ = Tb - Pe
        # This is the waiting time between packet reception end and next transmission cycle
        tau_us = next_cycle_start - reception_end_time
        
        # Ensure τ is in the range [0, T)
        if tau_us < 0:
            tau_us += cycle_duration_T
        
        # Convert back to ms for consistency with other delay values
        tau_ms = tau_us / 1000
        
        return tau_ms
    
    def calculate_tau_values(self, cycle_duration_T):
        """
        Calculate τ (tau) values for all nodes in the network.
        
        Args:
            cycle_duration_T: The cycle duration in μs
            
        Returns:
            tau_values: Dictionary mapping node IDs to their τ values in ms
        """
        tau_values = {}
        
        # For each node in the graph
        for node in self.graph.nodes():
            # Get all neighbors (upstream nodes)
            neighbors = list(self.graph.neighbors(node))
            
            # Calculate tau for each upstream-downstream pair
            node_taus = {}
            for upstream in neighbors:
                tau = self.calculate_tau(upstream, node, cycle_duration_T)
                if tau is not None:
                    node_taus[upstream] = tau
            
            # If node has tau values, use the average as its tau value
            if node_taus:
                avg_tau = sum(node_taus.values()) / len(node_taus)
                tau_values[node] = avg_tau
            else:
                tau_values[node] = 0.0
                
        return tau_values


def calculate_overall_delay(network, path, T, delay_values):
    """Calculate the total delay for a path, including propagation and tau values."""
    total_delay = 0.0
    for i in range(len(path) - 1):
        current_node = path[i]
        next_node = path[i + 1]
        link = (current_node, next_node)
        propagation_delay = network.delays.get(link, 0.0)
        tau = delay_values.get(next_node, 0.0)
        total_delay += propagation_delay + tau + T/1000  # Convert T from μs to ms
    return total_delay
