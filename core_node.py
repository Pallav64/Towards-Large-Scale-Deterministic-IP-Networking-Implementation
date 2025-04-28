import threading
import time
import math
from collections import deque


class CoreNode:
    def __init__(self, node_id, cycle_duration_T):
        self.node_id = node_id
        self.cycle_duration_T = cycle_duration_T
        self.queues = [{}, {}, {}]  # 3 FIFO queues per interface (indexed 0, 1, 2)
        self.current_cycle = 0
        self.last_cycle_time = time.time()-(cycle_duration_T / 1e6)
        self.lock = threading.Lock()
        self.mapping_table = {} # Mapping table: maps (in_port, in_label) to (out_port, out_label)
        self.link_delays = {}  # Store delays for each link to neighbors
        self.queuing_delay = 0.0  # Default queuing delay (ms)
        self.active_queue_index = 0   # Track active queue (0, 1, or 2) during each cycle
        self.connected_nodes = {}   # Connect to other nodes
        self.next_hop_map = {}      # Track which node is the next hop for each flow
        self.packet_flow_map = {}   # Store the flow ID for each packet (needed for forwarding)
        self.routing_table = {}     # Routing table: maps flow_id to next hop

    def add_mapping(self, in_port, in_label, out_port, out_label):
        """
        Add an entry to the mapping table.
        For each (in_port, in_label) pair, we store a list of possible (out_port, out_label) tuples.
        This allows us to support multiple outport options for the same incoming packet.
        """
        if (in_port, in_label) in self.mapping_table:
            # If this inport-label pair already has mappings, add the new one
            # Avoid duplicates
            if (out_port, out_label) not in self.mapping_table[(in_port, in_label)]:
                self.mapping_table[(in_port, in_label)].append((out_port, out_label))
        else:
            # Create a new list of outport options
            self.mapping_table[(in_port, in_label)] = [(out_port, out_label)]

    def set_link_delay(self, neighbor_node, delay):
        self.link_delays[neighbor_node] = delay

    def set_queuing_delay(self, delay):
        """Set the queuing delay for this node."""
        self.queuing_delay = delay

    def connect_to_node(self, node_id, node):
        self.connected_nodes[node_id] = node

    def set_routing_entry(self, flow_id, next_hop):
        self.routing_table[flow_id] = next_hop

    def learn_mappings(self, upstream_node_id, in_port, out_port=None):
        """
        Learn the mappings between input labels from an upstream node and output labels.
        The mapping depends on the propagation delay between nodes.
        If out_port is not specified, create mappings for all possible outports other than the inport.
        """
        propagation_delay = self.link_delays.get(upstream_node_id, 0)
        
        # Calculate the cycle shift based on propagation delay to determine how many cycles the packet will take to arrive
        cycles_to_shift = math.ceil(propagation_delay / self.cycle_duration_T)
        
        # Get all neighbors of this node
        neighbors = list(self.connected_nodes.keys())
        
        # If out_port is specified, use only that outport otherwise, create mappings for all possible outports
        if out_port is not None:
            # Skip if in_port and out_port are the same - impossible to forward a packet back on the same port
            if in_port == out_port:
                return
            outports = [out_port]
        else:
            # Use all neighbors except the inport as potential outports
            outports = [n for n in neighbors if n != in_port]
        
        # Map each possible input label (0, 1, 2) to the appropriate output label for each possible outport
        for out_port in outports:
            for in_label in range(3):
                # The output label depends on the input label and the cycle shift
                out_label = (in_label + cycles_to_shift) % 3
                
                # Store the mapping with outport information
                self.add_mapping(in_port, in_label, out_port, out_label)

    def receive_packet(self, packet, in_port):
        """
        Process an incoming packet:
        1. Determine the output port and new label based on the mapping table
        2. Enqueue the packet in the appropriate queue
        3. Store the flow ID for later forwarding
        """
        with self.lock:
            in_label = packet.label
            flow_id = packet.flow_id
            # Store the flow ID for this packet
            self.packet_flow_map[id(packet)] = flow_id
            
            # Check if this node is the final destination for this flow
            if flow_id in self.routing_table:
                next_hop = self.routing_table.get(flow_id)
                
                # Check if mapping exists
                if (in_port, in_label) in self.mapping_table:
                    # Find the appropriate mapping entry that matches the next_hop
                    mapping_options = self.mapping_table[(in_port, in_label)]
                    
                    # Use the first mapping option by default
                    out_port, out_label = mapping_options[0]
                    
                    # But if we have a next_hop from the routing table, use that specific outport
                    if next_hop:
                        for port, label in mapping_options:
                            if port == next_hop:
                                out_port = port
                                out_label = label
                                break
                    
                    # Assign the new label to the packet
                    packet.label = out_label
                    
                    # Determine which queue to place the packet in
                    queue_index = out_label % 3
                    
                    # Create queue for this port if it doesn't exist
                    if out_port not in self.queues[queue_index]:
                        self.queues[queue_index][out_port] = deque()
                    
                    # Enqueue the packet
                    self.queues[queue_index][out_port].append(packet)
                    
                    # Use node role in the log message
                    node_role = "CoreNode"
                    print(f"{node_role} {self.node_id}: Received packet from flow {packet.flow_id} from in_port {in_port} with label {in_label}, enqueued for out_port {out_port} with new label {out_label} in queue {queue_index}")
                else:
                    print(f"Node {self.node_id}: No mapping found for packet from in_port {in_port} with label {in_label}")
            else:
                # This node is the final destination for this flow
                print(f"EgressNode {self.node_id}: Received packet from flow {flow_id} from in_port {in_port} - final destination reached for flow {flow_id}")

    def transmit_packets(self):
        """
        Transmit packets from the active queue for the current cycle.
        Only one queue is open (active) at any time, following round-robin scheduling.
        """
        with self.lock:
            # Get the currently active queue
            active_queue = self.queues[self.active_queue_index]
            
            # Process packets in all output ports for this queue
            for out_port, queue in list(active_queue.items()):  # Create a copy of items to avoid mutation during iteration
                while queue:
                    packet = queue.popleft()
                    print(f"CoreNode {self.node_id}: Transmitting packet from flow {packet.flow_id} with label {packet.label} to port {out_port} in cycle {self.current_cycle}")
                    
                    # Forward packet to the next node
                    flow_id = self.packet_flow_map.get(id(packet))
                    if flow_id is not None:
                        next_hop = self.routing_table.get(flow_id)
                        if next_hop and next_hop in self.connected_nodes:
                            next_node = self.connected_nodes[next_hop]
                            print(f"CoreNode {self.node_id}: Forwarded packet from flow {flow_id} to node {next_hop}")
                            next_node.receive_packet(packet, self.node_id)
                        else:
                            print(f"CoreNode {self.node_id}: Packet destination reached or routing not available for flow {flow_id}")
                            # Clean up the packet flow mapping
                            if id(packet) in self.packet_flow_map:
                                del self.packet_flow_map[id(packet)]
                    else:
                        print(f"CoreNode {self.node_id}: Unable to determine flow ID for packet")
            
            # Move to the next queue (round-robin)
            self.active_queue_index = (self.active_queue_index + 1) % 3
            self.current_cycle += 1
        self.last_cycle_time = time.time()
        
    def run(self):
        """Simulate the core node's operation over time. """
       
        while True:
            # Check if it's time to start a new cycle
            current_time = time.time()
            if current_time - self.last_cycle_time >= self.cycle_duration_T / 1e6:  # Convert to seconds
                self.transmit_packets()
                self.last_cycle_time = current_time

            # Simulate some delay between cycles
            time.sleep(0.1) 