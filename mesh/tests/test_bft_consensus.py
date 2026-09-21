import pytest
from mesh.bft_consensus import BFTNodeStateSync
from mesh.peer_transport import WebsocketPeerTransport


class StubTransport(WebsocketPeerTransport):
    """Deterministic transport stand-in: returns scripted vote responses by URI
    and records outbound traffic. No sockets are opened."""

    def __init__(self, per_peer: dict | None = None, default: dict | None = None):
        super().__init__()
        self.per_peer = per_peer or {}
        self.default = default
        self.outbound = []

    async def request_vote(self, uri, payload, timeout=3.0):
        self.outbound.append(("vote", uri, payload))
        if uri in self.per_peer:
            return self.per_peer[uri]
        return self.default

    async def send_message(self, uri, payload, timeout=3.0):
        self.outbound.append(("commit", uri, payload))


@pytest.fixture()
def node():
    return BFTNodeStateSync("node-1")


class TestBFTLegacySimulatedMode:
    def test_register_peer(self, node):
        node.register_peer("node-2")
        assert "node-2" in node.peer_nodes

    def test_no_duplicate_peers(self, node):
        node.register_peer("node-2")
        node.register_peer("node-2")
        assert node.peer_nodes.count("node-2") == 1

    def test_consensus_with_enough_peers(self, node):
        node.register_peer("node-2")
        node.register_peer("node-3")
        result = node.propose_state_update("key1", "val1")
        assert result is True
        assert node.state_ledger["key1"] == "val1"

    def test_consensus_with_minimum_peers(self, node):
        node.register_peer("node-2")
        result = node.propose_state_update("key1", "val1")
        assert result is True

    def test_consensus_solo_node(self, node):
        result = node.propose_state_update("solo_key", "solo_val")
        assert result is True
        assert node.state_ledger["solo_key"] == "solo_val"

    def test_multiple_state_updates(self, node):
        node.register_peer("node-2")
        node.propose_state_update("k1", "v1")
        node.propose_state_update("k2", "v2")
        assert node.state_ledger == {"k1": "v1", "k2": "v2"}


class TestBFTLiveQuorum:
    def test_honest_quorum_commits(self):
        transport = StubTransport(default={"vote": True})
        node = BFTNodeStateSync("node-1", transport=transport)
        node.register_peer("node-2", "ws://stub/node-2")
        node.register_peer("node-3", "ws://stub/node-3")
        assert node.propose_state_update("k", "v") is True
        assert node.state_ledger["k"] == "v"
        assert node.commit_count == 1
        assert any(op == "vote" and p["key"] == "k" for op, _, p in transport.outbound)
        assert any(op == "commit" and p["op"] == "commit" for op, _, p in transport.outbound)

    def test_byzantine_minority_still_commits(self):
        transport = StubTransport(
            per_peer={"ws://stub/node-2": {"vote": False}},
            default={"vote": True},
        )
        node = BFTNodeStateSync("node-1", transport=transport)
        node.register_peer("node-2", "ws://stub/node-2")
        node.register_peer("node-3", "ws://stub/node-3")
        assert node.propose_state_update("k", "v") is True
        assert node.byzantine_count >= 1

    def test_byzantine_majority_rejects(self):
        transport = StubTransport(default={"vote": False})
        node = BFTNodeStateSync("node-1", transport=transport)
        node.register_peer("node-2", "ws://stub/node-2")
        node.register_peer("node-3", "ws://stub/node-3")
        assert node.propose_state_update("k", "v") is False
        assert "k" not in node.state_ledger
        assert node.rejected_count == 1
        assert node.byzantine_count == 2

    def test_unreachable_peers_are_non_votes(self):
        transport = StubTransport(default=None)
        node = BFTNodeStateSync("node-1", transport=transport)
        node.register_peer("node-2", "ws://stub/unreachable-a")
        node.register_peer("node-3", "ws://stub/unreachable-b")
        assert node.propose_state_update("k", "v") is False
        assert "k" not in node.state_ledger

    def test_honest_majority_with_one_unreachable_commits(self):
        transport = StubTransport(
            per_peer={"ws://stub/node-2": {"vote": True}},
            default=None,
        )
        node = BFTNodeStateSync("node-1", transport=transport)
        node.register_peer("node-2", "ws://stub/node-2")
        node.register_peer("node-3", "ws://stub/gone")
        assert node.propose_state_update("k", "v") is True
        assert node.state_ledger["k"] == "v"

    def test_policy_faulty_peer_vote_skipped(self):
        transport = StubTransport(default={"vote": True})
        node = BFTNodeStateSync("node-1", transport=transport)
        node.register_peer("node-2", "ws://stub/node-2")
        node.set_peer_policy("node-2", "faulty")
        # 2 nodes, quorum 2: skipping the faulty peer leaves 1 vote -> reject.
        assert node.propose_state_update("k", "v") is False
        assert "k" not in node.state_ledger
        assert node.byzantine_count == 1

    def test_policy_requires_registered_peer(self, node):
        with pytest.raises(KeyError):
            node.set_peer_policy("ghost", "faulty")

    def test_apply_commit_trusted_gate(self, node):
        node.register_peer("node-2", "ws://stub/node-2")
        assert node.apply_commit("k", "v", "node-2") is True
        assert node.apply_commit("k", "v", "attacker") is False
        assert node.state_ledger == {"k": "v"}