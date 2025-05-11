# Time-Deterministic Network Simulation

This simulation implements a time-deterministic network with cycle-based scheduling for deterministic packet delivery. The program simulates network nodes, flows, and packet transmission with guaranteed timely delivery.

## Project Structure

The project has been organized into multiple files for better maintainability:

- `models.py` - Basic data structures (Packet, Flow) and flow-related utility functions
- `network.py` - Network graph representation and helper functions
- `core_node.py` - CoreNode implementation for packet forwarding
- `ingress_node.py` - IngressNode implementation for packet injection
- `algorithms.py` - CGRR algorithm and associated functions for path computation
- `main.py` - Main program entry point and simulation orchestration
- `__init__.py` - Package definition file

## Configuration File

The simulation can be configured using a JSON file:

`network_config.json` - Network with predefined flows and configuration

### Running the Simulation

To run the simulation with the configuration file:

```bash
python main.py network_config.json
```

If no configuration file is specified, it defaults to `network_config.json`.

### Random Flow Generation

Alternatively, you can run the simulation with randomly generated flows:

```bash
# Generate random flows with a prompt for the number of flows
python main.py --random

# Generate a specific number of random flows
python main.py --random 5

# Use a specific config file for network settings but generate random flows
python main.py custom_network.json --random 3
```

When using random flow generation, the network topology and other settings are still loaded from the configuration file, but the flows are randomly generated instead of loaded from the file.

### Dynamic Tau (τ) Calculation

The simulation dynamically calculates tau values based on network topology and propagation delays according to the formulas from the paper. This accurately models the real waiting time between reception and transmission at each node.

For each pair of nodes, the tau value is calculated as:

- Reception end time = Propagation delay + T
- Next cycle start time = ⌈Reception end time / T⌉ × T
- tau = Next cycle start time - Reception end time

### JSON Output

The simulation can output results to a JSON file for further analysis or visualization:

```bash
# Save results to a specified JSON file
python main.py --output results.json

# Combine with random flow generation
python main.py --random 5 --output results.json

# Use custom config and specify output file
python main.py custom_network.json --output results.json
```

If no output file is specified but the `--output` flag is used, results will be saved to `simulation_results.json` by default.

#### JSON Output Structure

The output JSON file contains comprehensive information about the simulation:

```json
{
  "simulation_parameters": {
    "cycle_duration_T": 10
  },
  "network": {
    "nodes": [1, 2, 3, 4],
    "links": [...]
  },
  "flows": [
    {
      "flow_id": 1,
      "arrival_rate": 10,
      "burst_size": 7.5,
      "max_e2e_delay": 50,
      "max_pkt_size": 1.5,
      "src": 1,
      "dest": 4,
      "admitted": true,
      "path": [1, 2, 4],
      "shaping_parameter": 3.75
    },
    ...
  ],
  "admitted_flows_count": 2,
  "total_flows_count": 3,
  "simulation_complete": true,
  "completion_status": {
    "1": true,
    "2": true
  }
}
```

The JSON file is updated at multiple points during the simulation:

- Initially after flow admission decisions are made
- When all flows complete successfully
- If there's a timeout with some incomplete flows
- If the simulation is interrupted with keyboard interrupt

## JSON Configuration Format

### Example Configuration

```json
{
  "simulation_parameters": {
    "cycle_duration_T": 10
  },
  "network": {
    "nodes": [1, 2, 3, 4],
    "links": [
      {
        "node1": 1,
        "node2": 2,
        "delay": 1.0,
        "bandwidth": 100
      },
      ...
    ]
  },
  "flows": [
    {
      "flow_id": 1,
      "arrival_rate": 10,
      "burst_size": 7.5,
      "max_e2e_delay": 50,
      "max_pkt_size": 1.5,
      "src": 1,
      "dest": 4
    },
    ...
  ]
}
```

### Configuration Options

#### Simulation Parameters

- `cycle_duration_T`: Duration of each cycle in microseconds

#### Network

- `nodes`: List of node IDs in the network
- `links`: List of links connecting nodes
  - `node1`: First node ID in the undirected link
  - `node2`: Second node ID in the undirected link
  - `delay`: Propagation delay in milliseconds
  - `bandwidth`: Bandwidth in Mbps

#### Flows

- `flow_id`: Unique identifier for the flow
- `arrival_rate`: Rate at which packets arrive (Mbps),
- `burst_size`: Maximum burst size (KB)
- `max_e2e_delay`: Maximum end-to-end delay (ms)
- `max_pkt_size`: Maximum packet size (KB)
- `src`: Source node for the flow
- `dest`: Destination node for the flow

## Output

The simulation outputs information about flow paths, admitted flows, and packet transmissions. Each node acts as one of:

- **IngressNode**: Source node generating traffic
- **CoreNode**: Forwarding node in the network
- **EgressNode**: Destination node receiving traffic

The simulation tracks each packet through the network, showing the cycle-based scheduling and transmission times.
