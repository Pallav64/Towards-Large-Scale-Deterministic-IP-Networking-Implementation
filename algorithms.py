import numpy as np
import random
import networkx as nx
import math
from network import calculate_overall_delay


def possible_shaping_parameters(flow, T):
    """Compute possible shaping parameters for a flow."""
    import math
    MPS = flow.max_pkt_size  
    bf = flow.burst_size     
    rf = flow.arrival_rate * 0.000125  # conversion from Mbps to KB/µs
    n = 1
    B_f = set() 
    prev_ceil_value = float('inf')
    while True:
        ceil_value = math.ceil(bf / n)
        if ceil_value >= (rf * T):
            possible_param = MPS * math.ceil(bf / (n * MPS))
            B_f.add(possible_param)
        else:
            break  
        if ceil_value >= prev_ceil_value:
            break
        prev_ceil_value = ceil_value
        n += 1
    return sorted(B_f)


def larac_algorithm(graph, source, destination, delay_constraint, dual_costs):
    """LARAC algorithm for constrained shortest path (CSP)."""
    def lagrangian_relaxation(lambda_val):
        """Compute the Lagrangian relaxation for a given lambda."""
        def cost(u, v, edge_data):
            return dual_costs.get((u, v), 0) + lambda_val * edge_data['delay']
        path = nx.dijkstra_path(graph, source, destination, weight=cost)
        total_delay = sum(graph[u][v]['delay'] for u, v in zip(path[:-1], path[1:]))
        return path, total_delay

    # Binary search for the optimal lambda
    lambda_low = 0
    lambda_high = 1e6
    best_path = None
    for _ in range(50):  # Limit iterations for convergence
        lambda_mid = (lambda_low + lambda_high) / 2
        path, total_delay = lagrangian_relaxation(lambda_mid)
        if total_delay <= delay_constraint:
            best_path = path
            lambda_high = lambda_mid
        else:
            lambda_low = lambda_mid
    return best_path


def solve_rmp(columns, network, cycle_duration_T):
    """Solve the Restricted Master Problem (RMP) using linear programming."""
    if not columns:
        return {}, {e: 0 for e in network.graph.edges}
    c = np.array([-f.arrival_rate for (f, _, _) in columns], dtype=float)  # Negative for maximization
    A = []
    b = []
    for e in network.graph.edges:
        constraint = [0] * len(columns)
        for i, (f, p, b_prime) in enumerate(columns):
            if e in zip(p[:-1], p[1:]):
                constraint[i] = b_prime
        A.append(constraint)
        b.append(network.bandwidths[e] * cycle_duration_T)
    A = np.array(A, dtype=float)
    b = np.array(b, dtype=float)
    from scipy.optimize import linprog
    result = linprog(c, A_ub=A, b_ub=b, bounds=(0, 1), method='highs')
    solution = {(f, tuple(p), b): float(z) for (f, p, b), z in zip(columns, result.x)}
    dual_vars = {e: -float(dual) for e, dual in zip(network.graph.edges, result.ineqlin.marginals)}
    return solution, dual_vars


def solve_pricing_problem(flow, network, dual_vars, cycle_duration_T, queuing_delays):
    """Solve the pricing problem to find the best path and shaping parameter for a flow."""
    best_path = None
    best_b_prime = None
    best_cost = float('inf')
    for b_prime in possible_shaping_parameters(flow, cycle_duration_T):
        shaping_delay = math.ceil(flow.burst_size / b_prime) * cycle_duration_T + cycle_duration_T
        delay_constraint = flow.max_e2e_delay - shaping_delay
        
        if delay_constraint < 0:
            continue  
            
        path = larac_algorithm(network.graph, flow.src, flow.dest, delay_constraint, dual_vars)
        
        if path:
            # Calculate the actual path delay including propagation and queuing delays
            path_delay = calculate_overall_delay(network, path, cycle_duration_T, queuing_delays)
            
            # Check if the total delay (shaping delay + path delay) satisfies the max E2E delay constraint
            if shaping_delay + path_delay <= flow.max_e2e_delay:
                cost = sum(dual_vars.get((u, v), 0) for u, v in zip(path[:-1], path[1:]))
                if cost < best_cost:
                    best_path = path
                    best_b_prime = b_prime
                    best_cost = cost
    
    return best_path, best_b_prime


def add_new_columns(columns, dual_vars, network, flows, cycle_duration_T, queuing_delays):
    """Add new columns to the RMP based on the pricing problem."""
    new_columns_added = False
    for flow in flows:
        # Solve the pricing problem to find the best path and shaping parameter
        best_path, best_b_prime = solve_pricing_problem(flow, network, dual_vars, cycle_duration_T, queuing_delays)
        if best_path and best_b_prime:
            # Check if the new column improves the objective
            new_column = (flow, best_path, best_b_prime)
            if new_column not in columns:
                columns.append(new_column)
                new_columns_added = True
    return new_columns_added


def can_add_to_solution(current_solution, selected, network, cycle_duration_T):
    flow, path, b_prime = selected
    for u, v in zip(path[:-1], path[1:]):
        link_capacity = network.bandwidths.get((u, v), 0)
        used_capacity = sum(b for (f, p, b), z in current_solution.items() if z == 1 and (u, v) in zip(p[:-1], p[1:]))
        if used_capacity + b_prime > link_capacity * cycle_duration_T:
            return False
    return True


def calculate_objective(solution, flows):
    return sum(f.arrival_rate for (f, _, _), z in solution.items() if z == 1)


def cgrr_algorithm(network, flows, cycle_duration_T, queuing_delays, max_rounding_steps=100):
    """Column Generation with Randomized Rounding (CGRR) algorithm."""
    columns = []  # List of (flow, path, shaping_parameter) tuples
    dual_vars = {}  # Dual variables for capacity constraints
    while True:
        rmp_solution, dual_vars = solve_rmp(columns, network, cycle_duration_T)
        if not add_new_columns(columns, dual_vars, network, flows, cycle_duration_T, queuing_delays):
            break  # Exit the loop if no new columns are added
    base_solution = {(f, p, b): z for (f, p, b), z in rmp_solution.items() if z == 1}
    best_solution = base_solution.copy()
    for _ in range(max_rounding_steps):
        current_solution = base_solution.copy()
        fractional_vars = [(f, p, b) for (f, p, b), z in rmp_solution.items() if 0 < z < 1]
        for _ in range(len(fractional_vars)):
            total_fractional = sum(rmp_solution[(f, p, b)] for (f, p, b), z in rmp_solution.items() if 0 < z < 1)
            if total_fractional <= 0:
                break
            probabilities = {
                (f, p, b): rmp_solution[(f, p, b)] / total_fractional for (f, p, b), z in rmp_solution.items() if 0 < z < 1
            }
            selected = random.choices(list(probabilities.keys()), weights=probabilities.values(), k=1)[0]
            if can_add_to_solution(current_solution, selected, network, cycle_duration_T):
                current_solution[selected] = 1
        if calculate_objective(current_solution, flows) > calculate_objective(best_solution, flows):
            best_solution = current_solution
    return best_solution 