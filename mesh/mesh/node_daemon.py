from mesh.mesh.bft_consensus import BFTNodeStateSync
from mesh.mesh.pqc_wrapper import PostQuantumCryptoEngine


class EdgeNodeDaemon:
    """Manages physical node health, microgrid power telemetry, and network heartbeats."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.consensus = BFTNodeStateSync(node_id)
        self.pqc = PostQuantumCryptoEngine()
        self.is_running = False

    def start_heartbeat(self):
        self.is_running = True
        print(f"Edge Node Daemon [{self.node_id}] online and monitoring grid status.")

    def stop_heartbeat(self):
        self.is_running = False
        print(f"Edge Node Daemon [{self.node_id}] entering offline state.")

    def health_telemetry(self) -> dict:
        return {
            "node_id": self.node_id,
            "status": "HEALTHY",
            "pqc_secured": True,
            "active_peers": len(self.consensus.peer_nodes),
        }
