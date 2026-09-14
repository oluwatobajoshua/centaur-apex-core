import json
import socket
import struct
from dataclasses import dataclass


@dataclass
class ConstitutionStatus:
    system_state: str
    proposals_seen: int
    emergencies: int


class ConstitutionIPCClient:
    """Length-prefixed TCP framing client for the Iron Constitution daemon."""

    PROTOCOL_VERSION = 1
    MAX_FRAME_BYTES = 16_384

    def __init__(self, host: str = "127.0.0.1", port: int = 15565, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._session_sock: socket.socket | None = None

    # ------------------------------------------------------------------ framing
    def _build_envelope(self, opcode: str, payload: str) -> bytes:
        envelope = {
            "protocol_version": self.PROTOCOL_VERSION,
            "request_id": "cortex-0001",
            "opcode": opcode,
            "payload": payload,
        }
        return json.dumps(envelope).encode("utf-8")

    @staticmethod
    def _read_exact(sock: socket.socket, length: int) -> bytes:
        chunks = []
        remaining = length
        while remaining > 0:
            chunk = sock.recv(remaining)
            if not chunk:
                raise ConnectionError("Connection closed early by Constitution daemon")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _send_frame(self, payload: bytes) -> str:
        if self._session_sock is None:
            raise ConnectionError("No active session. Use open_session() first.")
        sock = self._session_sock

        sock.sendall(struct.pack(">I", len(payload)) + payload)
        header = sock.recv(4)
        if len(header) != 4:
            raise ConnectionError("Constitution closed connection early")
        frame_len = struct.unpack(">I", header)[0]
        if frame_len == 0 or frame_len > self.MAX_FRAME_BYTES:
            raise ValueError(f"Invalid response frame length: {frame_len}")
        return self._read_exact(sock, frame_len).decode("utf-8")

    # ------------------------------------------------------------------ session
    def open_session(self) -> "ConstitutionIPCClient":
        """Opens a persistent TCP connection so kernel state survives across calls."""
        if self._session_sock is None:
            self._session_sock = socket.create_connection(
                (self.host, self.port), timeout=self.timeout
            )
        return self

    def close_session(self) -> None:
        if self._session_sock is not None:
            self._session_sock.close()
            self._session_sock = None

    def __enter__(self) -> "ConstitutionIPCClient":
        return self.open_session()

    def __exit__(self, *exc) -> None:
        self.close_session()

    # ------------------------------------------------------------------- RPCs
    def evaluate(self, portfolio: dict, proposal: dict) -> dict:
        payload = json.dumps({"portfolio": portfolio, "proposal": proposal})
        raw = self._build_envelope("EvaluateProposal", payload)
        resp = self._send_frame(raw)
        return json.loads(resp)

    def status(self) -> ConstitutionStatus:
        raw = self._build_envelope("GetStatus", "{}")
        resp = json.loads(self._send_frame(raw))
        return ConstitutionStatus(
            system_state=resp["system_state"],
            proposals_seen=resp["proposals_seen"],
            emergencies=resp["emergencies"],
        )

    def heartbeat(self) -> dict:
        raw = self._build_envelope("Heartbeat", "{}")
        return json.loads(self._send_frame(raw))

    def recover(self, cryptographic_proof_valid: bool = True) -> dict:
        payload = json.dumps({"cryptographic_proof_valid": cryptographic_proof_valid})
        raw = self._build_envelope("AttemptRecovery", payload)
        return json.loads(self._send_frame(raw))