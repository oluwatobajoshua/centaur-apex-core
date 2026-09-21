"""Multi-node mesh integration: three real EdgeNodeDaemons over loopback
WebSocket, quorum replication, then fault injection (stop one node; mark one
peer Byzantine) and Byzantine-majority rejection.

Each daemon runs its own asyncio loop in a background thread; proposals are
driven from the test thread. Cleanup is guaranteed via ``finally``.
"""
import time

from mesh.bft_consensus import POLICY_FAULTY
from mesh.node_daemon import EdgeNodeDaemon


def _daemons(count: int = 3):
    nodes = [EdgeNodeDaemon(f"node-{i}") for i in range(1, count + 1)]
    for node in nodes:
        node.start_heartbeat()
    return nodes


def _fully_connect(nodes):
    for i, node in enumerate(nodes):
        for j, other in enumerate(nodes):
            if i != j:
                node.consensus.register_peer(other.node_id, other.ws_url)


def _stop_all(nodes):
    for node in nodes:
        try:
            node.stop_heartbeat()
        except Exception:  # noqa: BLE001,S110 - cleanup, best-effort
            pass


class TestMeshIntegration:
    def test_three_node_quorum_replication(self):
        nodes = _daemons(3)
        try:
            _fully_connect(nodes)
            leader = nodes[0]
            assert leader.consensus.propose_state_update("state/version", "v7") is True
            assert leader.consensus.state_ledger["state/version"] == "v7"
            for node in nodes:
                assert node.consensus.state_ledger.get("state/version") == "v7", (
                    f"{node.node_id} did not replicate"
                )
        finally:
            _stop_all(nodes)

    def test_fault_injection_stopped_node_does_not_block_majority(self):
        nodes = _daemons(3)
        try:
            _fully_connect(nodes)
            leader, peer_a, peer_b = nodes
            assert leader.consensus.propose_state_update("init", "1") is True

            peer_b.stop_heartbeat()
            # ensure peer_b's ws is closed before the next proposal
            time.sleep(0.2)

            # 2 live nodes + 1 dead: quorum = 2 <= honest votes {leader, peer_a}
            assert leader.consensus.propose_state_update("after-node-down", "ok") is True
            assert peer_a.consensus.state_ledger.get("after-node-down") == "ok"
            assert leader.consensus.byzantine_count >= 1
        finally:
            _stop_all(nodes)

    def test_byzantine_peer_handling(self):
        nodes = _daemons(3)
        try:
            _fully_connect(nodes)
            leader, peer_a, peer_b = nodes

            # Byzantine MINORITY tolerated: node-3 votes False to everything.
            peer_b.consensus.set_peer_policy(leader.node_id, POLICY_FAULTY)
            peer_b.consensus.set_peer_policy(peer_a.node_id, POLICY_FAULTY)
            assert leader.consensus.propose_state_update("k1", "v1") is True
            assert leader.consensus.byzantine_count >= 1

            # Byzantine MAJORITY rejects: node-2 + node-3 both refuse leader.
            leader.consensus.set_peer_policy(peer_a.node_id, POLICY_FAULTY)
            leader.consensus.set_peer_policy(peer_b.node_id, POLICY_FAULTY)
            assert leader.consensus.propose_state_update("bad", "x") is False
            assert "bad" not in leader.consensus.state_ledger
            assert leader.consensus.rejected_count >= 1
        finally:
            _stop_all(nodes)

    def test_telemetry_after_fault(self):
        nodes = _daemons(3)
        try:
            _fully_connect(nodes)
            leader = nodes[0]
            leader.consensus.propose_state_update("s", "v")
            leader.consensus.set_peer_policy("node-3", POLICY_FAULTY)
            telemetry = leader.health_telemetry()
            assert telemetry["status"] == "HEALTHY"
            assert telemetry["active_peers"] == 2
            assert telemetry["reachable_peers"] == 2
        finally:
            _stop_all(nodes)