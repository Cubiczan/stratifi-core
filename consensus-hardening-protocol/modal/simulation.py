"""
Consensus Hardening Protocol - Simulation at Scale
Deploy with: modal deploy modal/simulation.py
"""
import modal
from modal import App, Image

app = modal.App("consensus-simulation")

image = Image.debian_slim().pip_install("numpy", "cockroachdb")

@app.function(
    image=image,
    secrets=[modal.Secret.from_dotenv()],
    cpu=2.0,
    memory=4096
)
def simulate_consensus_round(num_nodes: int, fault_rate: float, protocol: str = "raft"):
    """
    Simulate consensus round with N nodes
    Test hardening protocol under various conditions
    """
    import random
    import time
    
    start_time = time.time()
    
    # Simulate voting
    votes = []
    for i in range(num_nodes):
        if random.random() > fault_rate:
            votes.append({'node_id': i, 'vote': 'accept'})
        else:
            votes.append({'node_id': i, 'vote': 'reject'})
    
    # Determine consensus (2/3 majority)
    accept_count = sum(1 for v in votes if v['vote'] == 'accept')
    consensus_reached = accept_count > (num_nodes * 2 / 3)
    
    latency = time.time() - start_time
    
    return {
        'round_id': f"sim-{int(time.time())}-{num_nodes}",
        'num_nodes': num_nodes,
        'fault_rate': fault_rate,
        'protocol': protocol,
        'consensus_reached': consensus_reached,
        'accept_votes': accept_count,
        'reject_votes': len(votes) - accept_count,
        'latency_ms': latency * 1000
    }

@app.function(image=image)
def run_simulation_suite():
    """Run comprehensive simulation suite"""
    results = []
    
    # Test different configurations
    for num_nodes in [10, 50, 100, 500]:
        for fault_rate in [0.0, 0.1, 0.2, 0.3]:
            result = simulate_consensus_round.remote(num_nodes, fault_rate)
            results.append(result)
    
    return results

@app.local_entrypoint()
def main():
    """Run test simulation"""
    print("🔐 Running consensus simulation...")
    
    result = simulate_consensus_round.remote(num_nodes=100, fault_rate=0.1)
    
    print(f"\n✅ Simulation complete!")
    print(f"📊 Nodes: {result['num_nodes']}")
    print(f"🎯 Consensus reached: {result['consensus_reached']}")
    print(f"✅ Accept votes: {result['accept_votes']}/{result['num_nodes']}")
    print(f"⏱️ Latency: {result['latency_ms']:.2f}ms")
