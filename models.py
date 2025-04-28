class Packet:
    def __init__(self, size, flow_id, label=None):
        self.size = size  # Size of the packet in KB
        self.flow_id = flow_id  # Identifier for the flow
        self.label = label  # Cycle label for transmission


class Flow:
    def __init__(self, flow_id, arrival_rate, burst_size, max_e2e_delay, max_pkt_size, src, dest):
        self.flow_id = flow_id  # Identifier for the flow
        self.arrival_rate = arrival_rate  # Rate at which packets arrive (e.g., Mbps)
        self.burst_size = burst_size  # Maximum burst size (e.g., KB)
        self.max_e2e_delay = max_e2e_delay  # Maximum end-to-end delay (e.g., ms)
        self.max_pkt_size = max_pkt_size  # Maximum packet size (e.g., KB)
        self.src = src  # Source node
        self.dest = dest  # Destination node
        self.packets = []  # Queue of packets in the flow
    
    def __repr__(self):
        return f"Flow-{self.flow_id}" 
    
    def __str__(self):
        return f"Flow-{self.flow_id}"

    def generate_packets(self):
        """Simulate packet generation for the flow based on the burst size."""
        from collections import deque
        self.packets = deque()
        remaining_burst = self.burst_size
        while remaining_burst > 0:
            packet_size = min(self.max_pkt_size, remaining_burst)
            self.packets.append(Packet(packet_size, self.flow_id))
            remaining_burst -= packet_size


def generate_random_flows(num_flows, network_nodes):
    """
    Generate random flows based on the network topology.
    
    Args:
        num_flows: Number of flows to generate
        network_nodes: List of node IDs from the network configuration
        
    Returns:
        List of Flow objects with random parameters
    """
    import random
    flows = []
    for i in range(1, num_flows + 1):
        # Randomly select source node
        src = random.choice(network_nodes)
        
        # Create a list of possible destinations (all nodes except source)
        possible_destinations = [node for node in network_nodes if node != src]
        
        # If no valid destinations available (should not happen with normal networks)
        if not possible_destinations:
            print(f"Warning: Cannot generate flow {i} - no valid destinations for source {src}")
            continue
            
        # Randomly select destination node
        dest = random.choice(possible_destinations)
        
        # Generate random flow parameters
        arrival_rate = random.uniform(5, 15)
        max_pkt_size = random.uniform(1, 2)
        num_packets = random.randint(3, 8)
        burst_size = num_packets * max_pkt_size
        max_e2e_delay = random.uniform(30, 70)
        
        flows.append(Flow(
            flow_id=i,
            arrival_rate=arrival_rate,
            burst_size=burst_size,
            max_e2e_delay=max_e2e_delay,
            max_pkt_size=max_pkt_size,
            src=src,
            dest=dest
        ))
    
    return flows


def display_flows(flows):
    print("\n" + "="*100)
    print("{:^80}".format("FLOW INFORMATION"))
    print("="*100)
    print("{:<5} | {:<10} | {:<10} | {:<15} | {:<10} | {:<10} | {:<5}".format("ID", "Rate (Mbps)", "Burst (KB)", "Max Delay (ms)", "Pkt Size (KB)", "Source", "Dest"))
    print("-"*100)
    
    for flow in flows:
        print("{:<5} | {:<10.2f} | {:<10.2f} | {:<15.2f} | {:<10.2f} | {:<10} | {:<5}".format(
            flow.flow_id, 
            flow.arrival_rate, 
            flow.burst_size, 
            flow.max_e2e_delay, 
            flow.max_pkt_size, 
            flow.src, 
            flow.dest))
    print("="*100 + "\n") 