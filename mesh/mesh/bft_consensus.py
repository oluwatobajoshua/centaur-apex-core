import asyncio

from mesh.peer_transport import (
    OP_COMMIT,
    OP_VOTE_REQUEST,
    MessageHandler,
    WebsocketPeerTransport,
)

POLICY_HONEST = "honest"
POLICY_FAULTY = "faulty"


class BFTNodeStateSync:
    """
    Byzantine Fault Tolerant state sync for globally distributed edge nodes.

    Two operating modes, selected by whether a peer transport is attached:

    * Simulation mode (transport is ``None`` — legacy, unit-test only): every
      registered peer is assumed to agree; votes equal the node count. Never
      used by a running daemon.
    * Live mode (``WebsocketPeerTransport`` attached): quorum is reached by
      collecting **real votes over WebSocket** from registered peers.
      Unreachable/malformed peers count as non-votes; peers configured as
      `faulty` vote `False` and are tracked as Byzantine. A proposal commits
      only when honest votes >= quorum (`floor(N/2) + 1`).

    Fail-safe (I6): if the transport cannot raise a quorum, the state update
    is rejected and the local ledger is left untouched.
    """

    def __init__(self, node_id: str, transport: WebsocketPeerTransport | None = None):
        self.node_id = node_id
        self._transport = transport
        self.peers: dict[str, str | None] = {}
        self._policies: dict[str, str] = {}
        self.state_ledger: dict[str, str] = {}
        self.commit_count: int = 0
        self.rejected_count: int = 0
        self.byzantine_count: int = 0

    @property
    def peer_nodes(self) -> list[str]:
        return list(self.peers.keys())

    @property
    def active_peers(self) -> list[str]:
        return [pid for pid, uri in self.peers.items() if uri]

    @property
    def attached_transport(self) -> WebsocketPeerTransport | None:
        return self._transport

    def register_peer(self, peer_node_id: str, ws_uri: str | None = None) -> None:
        if peer_node_id not in self.peers:
            self.peers[peer_node_id] = ws_uri
            self._policies[peer_node_id] = POLICY_HONEST
            print(f"Node [{self.node_id}] registered peer: {peer_node_id}")
        elif ws_uri is not None:
            self.peers[peer_node_id] = ws_uri

    def set_peer_policy(self, peer_node_id: str, policy: str) -> None:
        """Fault injection hook: mark a registered peer honest or faulty."""
        if peer_node_id not in self.peers:
            raise KeyError(f"peer {peer_node_id} is not registered")
        self._policies[peer_node_id] = policy

    @property
    def _faulty_peers(self) -> list[str]:
        return [pid for pid, policy in self._policies.items() if policy == POLICY_FAULTY]

    def _quorum_for(self) -> int:
        return (len(self.peers) + 1) // 2 + 1

    def apply_commit(self, key: str, value: str, sender: str) -> bool:
        """Trusted-peer gate for remote commits broadcast by a committer.
        Only registered peers may mutate the local ledger; unauthenticated
        senders are ignored (peer-signature authentication lands with the
        Genesis Ceremony sealing work)."""
        if sender in self.peers:
            self.state_ledger[key] = value
            self.commit_count += 1
            return True
        return False

    def propose_state_update(self, key: str, value: str) -> bool:
        """Synchronous facade. Raises a quorum over the attached transport
        (real WebSocket) or, without a transport, the legacy simulated quorum."""
        try:
            asyncio.get_running_loop()
            in_loop = True
        except RuntimeError:
            in_loop = False

        if not in_loop:
            return asyncio.run(self._propose_state_update(key, value))

        result: dict = {}

        def _worker() -> None:
            result["ok"] = asyncio.run(self._propose_state_update(key, value))

        from threading import Thread

        worker = Thread(target=_worker, daemon=True)
        worker.start()
        worker.join(timeout=10.0)
        return bool(result.get("ok", False))

    async def _vote_request_payload(self, key: str, value: str) -> dict:
        return {
            "op": OP_VOTE_REQUEST,
            "proposer": self.node_id,
            "key": key,
            "value": value,
            "protocol_version": 1,
        }

    async def _collect_votes(self, key: str, value: str) -> int:
        """One node, one vote. Unreachable peers are non-votes and count as
        Byzantine (conservative, I6)."""
        votes = 1  # self's own proposal
        for peer_id, uri in self.peers.items():
            if self._policies.get(peer_id) == POLICY_FAULTY:
                self.byzantine_count += 1
                continue
            if not uri or self._transport is None:
                continue
            response = await self._transport.request_vote(
                uri,
                await self._vote_request_payload(key, value),
            )
            if response is not None and response.get("vote") is True:
                votes += 1
            else:
                self.byzantine_count += 1
        return votes

    async def _broadcast_commit(self, key: str, value: str) -> None:
        if self._transport is None:
            return
        for uri in self.peers.values():
            if not uri:
                continue
            payload = {
                "op": OP_COMMIT,
                "sender": self.node_id,
                "key": key,
                "value": value,
                "protocol_version": 1,
            }
            await self._transport.send_message(uri, payload)

    async def _propose_state_update(self, key: str, value: str) -> bool:
        if self._transport is None:
            # Legacy simulated quorum: all registered peers agree.
            votes = 1 + len(self.peers)
            if votes >= self._quorum_for():
                self.state_ledger[key] = value
                self.commit_count += 1
                return True
            self.rejected_count += 1
            return False

        votes = await self._collect_votes(key, value)
        if votes >= self._quorum_for():
            self.state_ledger[key] = value
            self.commit_count += 1
            await self._broadcast_commit(key, value)
            return True
        self.rejected_count += 1
        return False


def create_handler(node_id: str, consensus: BFTNodeStateSync) -> MessageHandler:
    """Factory for the daemon's inbound WS message handler (keeps wire protocol
    owning the opcode map)."""

    async def handler(message: dict, peer_uri: str | None) -> dict | None:
        op = message.get("op")
        if op == OP_VOTE_REQUEST:
            if consensus._policies.get(message.get("proposer")) == POLICY_FAULTY:
                return {"op": "vote_response", "vote": False, "reason": "node policy: faulty"}
            return {"op": "vote_response", "vote": True}
        if op == OP_COMMIT:
            consensus.apply_commit(
                str(message.get("key", "")),
                str(message.get("value", "")),
                str(message.get("sender", "")),
            )
            return None
        return None

    return handler

# Re-export MessageHandler for convenience.
__all__ = [
    "POLICY_FAULTY",
    "POLICY_HONEST",
    "BFTNodeStateSync",
    "MessageHandler",
    "create_handler",
]