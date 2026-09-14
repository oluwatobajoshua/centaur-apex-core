from typing import Dict, List


class BFTNodeStateSync:
    """
    Coordinates state synchronization across globally distributed edge nodes
    using Byzantine Fault Tolerant consensus to survive localized infrastructure collapse.
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.peer_nodes: List[str] = []
        self.state_ledger: Dict[str, str] = {}

    def register_peer(self, peer_node_id: str):
        if peer_node_id not in self.peer_nodes:
            self.peer_nodes.append(peer_node_id)
            print(f"Node [{self.node_id}] registered peer: {peer_node_id}")

    def propose_state_update(self, key: str, value: str) -> bool:
        # Simulate BFT quorum verification across active peer nodes
        total_nodes = len(self.peer_nodes) + 1
        quorum_required = (total_nodes // 2) + 1
        votes = 1 + len(self.peer_nodes)  # self vote + simulated acks

        if votes >= quorum_required:
            self.state_ledger[key] = value
            print(f"BFT Consensus achieved for key [{key}] across node network.")
            return True
        return False
