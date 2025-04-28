import math
import time
import threading
from collections import deque
from core_node import CoreNode


class IngressNode(CoreNode):
    def __init__(self, cycle_duration_T, node_id=1):
        # Call the parent class constructor
        super().__init__(node_id, cycle_duration_T)
        
        # Additional attributes specific to IngressNode
        self.flow_queues = {}  # Dictionary to store queues for each flow
        self.flow_order = deque()  # Queue of flows to be processed
        self.flow_paths = {}  # Store the entire path for each flow
        self.flow_completed_callback = None  # Callback for flow completion

    def calculate_num_cycles(self, flow, shaping_parameter):
        num_cycles = math.ceil(flow.burst_size / shaping_parameter)
        return num_cycles

    def shape_flow(self, flow, shaping_parameter):
        """
        Shape the flow by scattering its burst into smaller chunks and assigning packets to queues.
        Each packet is assigned a label corresponding to the cycle in which it will be transmitted.
        """
        num_cycles = self.calculate_num_cycles(flow, shaping_parameter)
        with self.lock:
            self.flow_queues[flow.flow_id] = [deque() for _ in range(num_cycles)]  # Create queues for the flow
            self.flow_order.append((flow.flow_id, shaping_parameter))  # Add flow to the processing queue

        # Assign packets to queues based on the shaping parameter and assign labels
        for i, packet in enumerate(flow.packets):
            queue_index = i % num_cycles
            packet.label = queue_index  # Assign the label to the packet
            with self.lock:
                self.flow_queues[flow.flow_id][queue_index].append(packet)

    def set_flow_path(self, flow_id, path):
        """Set the path for a flow."""
        self.flow_paths[flow_id] = path
        if len(path) > 1:
            self.next_hop_map[flow_id] = path[1]  # Next hop is the second node in the path

    def transmit_packets(self):
        """
        Transmit packets from the open queues in the current cycle.
        Process one flow at a time, completing all its cycles before moving to the next flow.
        
        This overrides the CoreNode's transmit_packets method.
        """
        with self.lock:
            if not self.flow_order:
                return  # No flows to process

            # Get the current flow being processed
            flow_id, shaping_parameter = self.flow_order[0]
            flow_queues = self.flow_queues.get(flow_id, [])

            if flow_queues:
                queue_index = self.current_cycle % len(flow_queues)
                open_queue = flow_queues[queue_index]

                # Transmit all packets in the open queue for the current flow
                while open_queue:
                    packet = open_queue.popleft()
                    print(f"IngressNode {self.node_id}: Transmitting packet of size {packet.size} KB from flow {flow_id} with label {packet.label} in cycle {self.current_cycle}")
                    
                    # Forward packet to the next hop
                    next_hop = self.next_hop_map.get(flow_id)
                    if next_hop and next_hop in self.connected_nodes:
                        # Send packet to the next node
                        next_node = self.connected_nodes[next_hop]
                        print(f"IngressNode {self.node_id}: Forwarded packet from flow {flow_id} to node {next_hop}")
                        next_node.receive_packet(packet, self.node_id)
                    else:
                        print(f"IngressNode {self.node_id}: Unable to forward packet from flow {flow_id} - next hop not found or not connected")

                # Check if all cycles for the current flow are completed
                if queue_index == len(flow_queues) - 1:
                    completed_flow_id = flow_id
                    print(f"IngressNode {self.node_id}: Completed processing for flow {flow_id}")
                    self.flow_order.popleft()  # Remove the flow from the processing queue
                    self.current_cycle = 0  # Reset cycle counter for the next flow
                    
                    # Signal flow completion if callback is set
                    if self.flow_completed_callback:
                        # Call the callback in a separate thread to avoid blocking
                        threading.Thread(
                            target=self.flow_completed_callback, 
                            args=(completed_flow_id,), 
                            daemon=True
                        ).start()
                else:
                    self.current_cycle += 1  
        self.last_cycle_time = time.time()

    def receive_packet(self, packet, in_port):
        """
        Handle a packet when this ingress node is the destination.
        This method is called when packets are sent to this node from a core node.
        
        This overrides the CoreNode's receive_packet method.
        """
        with self.lock:
            flow_id = packet.flow_id
            
            # When receiving a packet as a destination, identify as egress node
            print(f"EgressNode {self.node_id}: Received packet from flow {flow_id} from in_port {in_port} - final destination reached for flow {flow_id}")
            # No further forwarding needed as this is the destination

    def add_flow(self, flow, shaping_parameter):
        """Add a new flow to the ingress node for processing."""
        flow.generate_packets()
        self.shape_flow(flow, shaping_parameter)

    def learn_mappings(self, upstream_node_id, in_port, out_port=None):
        """
        Override of CoreNode's learn_mappings to ensure IngressNodes always create mappings.
        """
        propagation_delay = self.link_delays.get(upstream_node_id, 0)
        cycles_to_shift = math.ceil(propagation_delay / self.cycle_duration_T)
        neighbors = list(self.connected_nodes.keys())
        
        # For IngressNodes, especially those that are destinations like node 1,
        # we need to make sure they create mappings even if they don't have many outports
        if out_port is not None:
            # Skip if in_port and out_port are the same - impossible to forward a packet back on the same port
            if in_port == out_port:
                return
            outports = [out_port]
        else:
            # Use all neighbors as potential outports except the inport itself
            outports = [n for n in neighbors if n != in_port]
            # If no valid outports found, don't create any mappings
            if not outports:
                return
        
        for out_port in outports:
            for in_label in range(3):
                out_label = (in_label + cycles_to_shift) % 3
                self.add_mapping(in_port, in_label, out_port, out_label)

    def set_flow_completed_callback(self, callback):
        """Set callback function to be called when a flow completes."""
        self.flow_completed_callback = callback 