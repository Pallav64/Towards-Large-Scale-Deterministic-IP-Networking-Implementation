import json
import sys
import threading
import time
from collections import deque

# Import custom modules
from models import Flow, generate_random_flows, display_flows
from network import Network, calculate_overall_delay
from core_node import CoreNode
from ingress_node import IngressNode
from algorithms import cgrr_algorithm


def main():
    # Check for random flow generation flag
    use_random_flows = False
    random_flow_count = 0
    output_json_file = None
    
    # Process command line arguments
    config_file = 'network_config.json'
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == '--random':
            use_random_flows = True
            # Check if next argument is a number for flow count
            if i < len(sys.argv) - 1 and sys.argv[i+1].isdigit():
                random_flow_count = int(sys.argv[i+1])
            else:
                # Prompt user for flow count if not provided
                random_flow_count = int(input("Enter the number of random flows to generate: "))
        elif arg == '--output':
            # Check if next argument is the output file name
            if i < len(sys.argv) - 1:
                output_json_file = sys.argv[i+1]
            else:
                # Default output file name
                output_json_file = 'simulation_results.json'
        elif not arg.startswith('--') and i == 1:
            # First non-flag argument is the config file
            config_file = arg
    
    # If no output file specified but user wants JSON output, set a default
    if output_json_file is None:
        output_json_file = 'simulation_results.json'
    
    # Load configuration from JSON file
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # Extract simulation parameters
        cycle_duration_T = config['simulation_parameters']['cycle_duration_T']
        
        # Set up network from config
        network = Network()
        network_config = config['network']
        
        # Add links from config
        for link in network_config['links']:
            network.add_link(
                link['node1'], 
                link['node2'], 
                delay=link['delay'], 
                bandwidth=link['bandwidth']
            )
        
        # Extract queuing delays if available
        queuing_delays = {}
        if 'queuing_delays' in network_config:
            for node_id, delay in network_config['queuing_delays'].items():
                queuing_delays[int(node_id)] = delay
        
        # Either load flows from config or generate random flows
        if use_random_flows:
            flows = generate_random_flows(random_flow_count, network_config['nodes'])
            print(f"Generated {random_flow_count} random flows")
        else:
            # Load flows from config
            flows = []
            for flow_config in config['flows']:
                flows.append(Flow(
                    flow_id=flow_config['flow_id'],
                    arrival_rate=flow_config['arrival_rate'],
                    burst_size=flow_config['burst_size'],
                    max_e2e_delay=flow_config['max_e2e_delay'],
                    max_pkt_size=flow_config['max_pkt_size'],
                    src=flow_config['src'],
                    dest=flow_config['dest']
                ))
            print(f"Loaded {len(flows)} flows from configuration")
        
        # Display loaded flows
        display_flows(flows)
        
        # Run the CGRR algorithm to find the best solution
        best_solution = cgrr_algorithm(network, flows, cycle_duration_T, queuing_delays)
        
        # Dictionary to store all nodes (both ingress and core)
        nodes = {}
        
        # Create ingress nodes for each unique source node in flows
        for flow in flows:
            if flow.src not in nodes:
                nodes[flow.src] = IngressNode(cycle_duration_T, node_id=flow.src)
        
        # Create core nodes for nodes that aren't already ingress nodes
        for node_id in network_config['nodes']:
            if node_id not in nodes:
                nodes[node_id] = CoreNode(node_id, cycle_duration_T)
        
        # Connect nodes to each other based on the network topology
        for node1, node2 in network.graph.edges():
            nodes[node1].connect_to_node(node2, nodes[node2])
            nodes[node2].connect_to_node(node1, nodes[node1])
        
        # Set link delays for each node
        for node1, node2, data in network.graph.edges(data=True):
            # Check if the node is a CoreNode before calling set_link_delay
            if isinstance(nodes[node1], CoreNode):
                nodes[node1].set_link_delay(node2, network.delays[(node1, node2)])
            if isinstance(nodes[node2], CoreNode):
                nodes[node2].set_link_delay(node1, network.delays[(node1, node2)])
        
        # Set queuing delays for each node
        for node_id, delay in queuing_delays.items():
            if node_id in nodes:
                nodes[node_id].set_queuing_delay(delay)
        
        admitted_flows = set()
        flow_paths = {}
        flow_shaping_parameters = {}
        
        # Set up flow paths and routing entries
        for (flow, path, shaping_parameter), z in best_solution.items():
            if z == 1: 
                flow_id = flow.flow_id
                admitted_flows.add(flow_id)
                flow_paths[flow_id] = path
                flow_shaping_parameters[flow_id] = shaping_parameter
                
                # Set the flow path in the source node (which is the ingress node for this flow)
                source_node = nodes[flow.src]
                source_node.set_flow_path(flow_id, path)
                
                # Set up routing entries for core nodes along the path
                for i in range(len(path) - 1): 
                    current_node = path[i]
                    next_node = path[i + 1]
                    # Only set routing entries for core nodes
                    if isinstance(nodes[current_node], CoreNode):
                        nodes[current_node].set_routing_entry(flow_id, next_node)
        
        # Learn mappings for each core node
        for (node1, node2) in network.graph.edges():
            # For each edge, have both nodes learn mappings from the other node
            nodes[node1].learn_mappings(node2, in_port=node2)
            nodes[node2].learn_mappings(node1, in_port=node1)
        
        # Prepare data for JSON output
        simulation_results = {
            "simulation_parameters": {
                "cycle_duration_T": cycle_duration_T
            },
            "network": {
                "nodes": network_config["nodes"],
                "links": network_config["links"],
                "queuing_delays": {str(node): delay for node, delay in queuing_delays.items()}
            },
            "flows": [
                {
                    "flow_id": flow.flow_id,
                    "arrival_rate": flow.arrival_rate,
                    "burst_size": flow.burst_size,
                    "max_e2e_delay": flow.max_e2e_delay,
                    "max_pkt_size": flow.max_pkt_size,
                    "src": flow.src,
                    "dest": flow.dest,
                    "admitted": flow.flow_id in admitted_flows,
                    "path": flow_paths.get(flow.flow_id, []),
                    "shaping_parameter": flow_shaping_parameters.get(flow.flow_id, None)
                }
                for flow in flows
            ],
            "admitted_flows_count": len(admitted_flows),
            "total_flows_count": len(flows)
        }
        
        # Write results to JSON file
        with open(output_json_file, 'w') as f:
            json.dump(simulation_results, f, indent=2)
        
        print(f"\nSimulation results have been saved to {output_json_file}")
        
        # Start all nodes in separate threads
        threads = {}
        for node_id, node in nodes.items():
            threads[node_id] = threading.Thread(target=node.run, daemon=True)
            threads[node_id].start()
        
        # Setup flow completion tracking
        if admitted_flows:
            flow_completion_status = {flow_id: False for flow_id in admitted_flows}
            all_flows_completed = threading.Event()
            
            # Callback function for flow completion
            def flow_completed_callback(flow_id):
                flow_id = int(flow_id)  # Ensure flow_id is an integer
                if flow_id in flow_completion_status:
                    flow_completion_status[flow_id] = True
                    print(f"✓ Flow {flow_id} has fully completed processing")
                    
                    # Check if all flows have completed
                    if all(flow_completion_status.values()):
                        all_flows_completed.set()
            
            # Set the callback on all ingress nodes
            for node_id, node in nodes.items():
                if isinstance(node, IngressNode):
                    node.set_flow_completed_callback(flow_completed_callback)
        else:
            print("No flows were admitted. Exiting.")
            return
        
        # Add admitted flows to their respective source nodes
        for (flow, path, shaping_parameter), z in best_solution.items():
            if z == 1: 
                print(f"✅ Flow {flow.flow_id} is admitted with shaping parameter {shaping_parameter} KB")
                print(f"   📍 Path: {' -> '.join(map(str, path))}")
                # Add the flow to its source node (which is the ingress node for this flow)
                nodes[flow.src].add_flow(flow, shaping_parameter)
        
        # Check for flows that were not admitted
        for flow in flows:
            if flow.flow_id not in admitted_flows:
                print(f"❌ Flow {flow.flow_id} is NOT admitted due to constraints.")
        
        # Keep the main thread alive to allow nodes to process flows
        try:
            # Wait for all flows to complete or timeout after a reasonable duration
            timeout_seconds = 60  # Adjust as needed based on expected flow completion time
            flows_completed = all_flows_completed.wait(timeout_seconds)
            
            if flows_completed:
                print("\nAll flows have completed processing. Simulation successful!")
                
                # Update completion status in the JSON file
                simulation_results["simulation_complete"] = True
                simulation_results["completion_status"] = {
                    str(flow_id): completed for flow_id, completed in flow_completion_status.items()
                }
                with open(output_json_file, 'w') as f:
                    json.dump(simulation_results, f, indent=2)
                print(f"Updated simulation results with completion status in {output_json_file}")
            else:
                print(f"\nTimeout reached after {timeout_seconds} seconds. Some flows did not complete:")
                incomplete_flows = []
                for flow_id, completed in flow_completion_status.items():
                    if not completed:
                        print(f"- Flow {flow_id} did not complete")
                        incomplete_flows.append(flow_id)
                
                # Update timeout status in the JSON file
                simulation_results["simulation_complete"] = False
                simulation_results["timeout_reached"] = True
                simulation_results["incomplete_flows"] = incomplete_flows
                with open(output_json_file, 'w') as f:
                    json.dump(simulation_results, f, indent=2)
                print(f"Updated simulation results with timeout information in {output_json_file}")
        except KeyboardInterrupt:
            print("Stopping the nodes early due to keyboard interrupt.")
            
            # Update keyboard interrupt status in the JSON file
            simulation_results["simulation_complete"] = False
            simulation_results["keyboard_interrupt"] = True
            with open(output_json_file, 'w') as f:
                json.dump(simulation_results, f, indent=2)
            print(f"Updated simulation results with interruption information in {output_json_file}")
    
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Configuration file '{config_file}' contains invalid JSON.")
        sys.exit(1)
    except KeyError as e:
        print(f"Error: Missing required field in configuration: {e}")
        sys.exit(1)



if __name__ == "__main__":
    main() 