import asyncio
import threading

from mesh.bft_consensus import BFTNodeStateSync, create_handler
from mesh.microgrid import MicrogridTelemetryHook
from mesh.peer_transport import WebsocketPeerTransport
from mesh.pqc_wrapper import PostQuantumCryptoEngine


class EdgeNodeDaemon:
    """Physical edge node: BFT state sync over a real WebSocket transport,
    microgrid power telemetry hooks, and post-quantum identity."""
    def __init__(
        self,
        node_id: str,
        transport: WebsocketPeerTransport | None = None,
        pqc_provider: str | None = None,
    ):
        self.node_id = node_id
        self.transport = transport or WebsocketPeerTransport()
        self.consensus = BFTNodeStateSync(node_id, transport=self.transport)
        self.pqc = PostQuantumCryptoEngine(provider=pqc_provider)
        self.microgrid = MicrogridTelemetryHook()
        self.is_running = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._serve_task: asyncio.Future | None = None

    @property
    def ws_url(self) -> str:
        return self.transport.url

    def record_microgrid(self, voltage_v: float, current_a: float, grid_state: str = "ON_GRID"):
        """Telemetry hook: record one power sample and expose derived health."""
        return self.microgrid.record(self.node_id, voltage_v, current_a, grid_state)

    def start_heartbeat(self) -> None:
        """Start the peer transport server and mark the node online."""
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, name=f"mesh-{self.node_id}", daemon=True
        )
        self._thread.start()

        served = asyncio.run_coroutine_threadsafe(
            self.transport.serve(create_handler(self.node_id, self.consensus)),
            self._loop,
        )
        served.result(timeout=10.0)
        self.is_running = True
        print(f"Edge Node Daemon [{self.node_id}] online at {self.ws_url}.")

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def stop_heartbeat(self) -> None:
        """Best-effort graceful shutdown of the transport server."""
        if not self.is_running:
            return
        if self._loop is not None:
            async def _shutdown() -> None:
                await self.transport.close()
                self._loop.stop()

            self._loop.call_soon_threadsafe(
                lambda: self._loop.create_task(_shutdown())
            )
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self.is_running = False
        print(f"Edge Node Daemon [{self.node_id}] entering offline state.")

    def health_telemetry(self) -> dict:
        grid = self.microgrid.snapshot()
        return {
            "node_id": self.node_id,
            "status": "HEALTHY" if self.is_running else "OFFLINE",
            "pqc_secured": self.pqc.is_post_quantum,
            "pqc_algorithm": self.pqc.get_algorithm(),
            "active_peers": len(self.consensus.peer_nodes),
            "reachable_peers": len(self.consensus.active_peers),
            "byzantine_rejections": self.consensus.byzantine_count,
            "state_entries": len(self.consensus.state_ledger),
            "grid": grid,
        }