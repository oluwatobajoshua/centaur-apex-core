"""Real WebSocket peer transport for the BFT mesh (G4).

Genesis: the transport is the mechanism; topology, quorum policy, and
fault-models are injected/data-driven. Production deploys bind the daemon's
`WebsocketPeerTransport` to real interfaces; tests bind to loopback.
"""
import asyncio
import json
from collections.abc import Awaitable, Callable

import websockets

# Canonical wire ops (schema-over-code; keep in sync with node protocol).
OP_VOTE_REQUEST = "vote_request"
OP_VOTE_RESPONSE = "vote_response"
OP_COMMIT = "commit"
OP_HEARTBEAT = "heartbeat"
OP_STATUS = "status"

MessageHandler = Callable[[dict, str | None], Awaitable[dict | None]]


class WebsocketPeerTransport:
    """
    Minimal WebSocket peer transport: hosts a server for inbound peer traffic
    and issues outbound vote solicitations / commit broadcasts.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self.port = port
        self._server = None

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    async def serve(self, handler: MessageHandler) -> None:
        if self._server is not None:
            return

        async def _dispatch(ws):
            peer_uri = None
            try:
                peer_uri = ws.remote_address[0] if ws.remote_address else None
            except Exception:  # noqa: BLE001,S110 - peer address is best-effort
                pass
            async for raw in ws:
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    await ws.send(json.dumps({"op": OP_VOTE_RESPONSE, "vote": False, "reason": "malformed"}))
                    continue
                if not isinstance(message, dict):
                    await ws.send(json.dumps({"op": OP_VOTE_RESPONSE, "vote": False, "reason": "malformed"}))
                    continue
                response = await handler(message, peer_uri)
                if response is not None:
                    await ws.send(json.dumps(response))

        self._server = await websockets.serve(_dispatch, self.host, self.port)
        socket = self._server.sockets[0]
        self.port = socket.getsockname()[1]

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def request_vote(
        self, uri: str, payload: dict, timeout: float = 3.0
    ) -> dict | None:
        """Solicit a single peer's vote. Returns the peer's response dict, or
        None when the peer is unreachable / non-responsive (counted as a
        (possibly Byzantine) non-vote by the caller)."""
        try:
            async with asyncio.timeout(timeout):
                async with websockets.connect(uri) as ws:
                    await ws.send(json.dumps(payload))
                    raw = await ws.recv()
                    response = json.loads(raw)
            return response if isinstance(response, dict) else None
        except Exception:  # noqa: BLE001 - unreachable, timeout, malformed -> non-vote
            return None

    async def send_message(self, uri: str, payload: dict, timeout: float = 3.0) -> None:
        """Fire-and-forget message (best-effort)."""
        try:
            async with asyncio.timeout(timeout):
                async with websockets.connect(uri) as ws:
                    await ws.send(json.dumps(payload))
        except Exception:  # noqa: BLE001 - best-effort; failures surface as missing peer acks
            return