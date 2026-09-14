# ==============================================================================
# CENTAUR-APEX: Module 2 Automation Script (Adaptive Cortex & IPC Bridge)
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "Building Module 2: The Adaptive Cortex (Python Layer)..." -ForegroundColor Cyan

# 1. Ensure Cortex directory structure exists
$cortexDirs = @(
    "cortex/cortex",
    "cortex/models",
    "cortex/tests"
)

foreach ($dir in $cortexDirs) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "Created directory: $dir" -ForegroundColor Green
    }
}

# 2. Write Python Project Configuration (pyproject.toml)
Write-Host "Writing cortex/pyproject.toml..." -ForegroundColor Yellow
$pyprojectContent = @"
[project]
name = "adaptive_cortex"
version = "0.1.0"
description = "Probabilistic AI Layer for Centaur-Apex Autonomous Trading Ecosystem"
dependencies = [
    "pydantic>=2.0.0",
    "numpy>=1.24.0",
    "requests>=2.31.0"
]
requires-python = ">=3.10"
"@
Set-Content -Path "cortex/pyproject.toml" -Value $pyprojectContent -Encoding UTF8

# 3. Write Data Proposal Schema & IPC Serialization Bridge
Write-Host "Writing cortex/cortex/proposal_api.py..." -ForegroundColor Yellow
$proposalApiContent = @'
import json
from enum import Enum
from pydantic import BaseModel, Field


class OrderDirection(str, Enum):
    BUY = "Buy"
    SELL = "Sell"


class TradeProposal(BaseModel):
    proposal_id: str = Field(..., description="Unique deterministic hash of the trade strategy")
    asset_id: str = Field(..., description="Target asset identifier e.g., BTC-PERP")
    direction: OrderDirection
    target_notional: float = Field(..., gt=0.0, description="Proposed absolute notional value in USD")
    max_acceptable_slippage: float = Field(default=0.001, ge=0.0)

    def to_json_payload(self) -> str:
        """Serializes the proposal into the exact byte schema expected by the Iron Constitution IPC."""
        return self.model_dump_json()


def parse_constitution_verdict(response_json: str) -> dict:
    """Parses the absolute verdict returned by the Iron Constitution core."""
    return json.loads(response_json)
'@
Set-Content -Path "cortex/cortex/proposal_api.py" -Value $proposalApiContent -Encoding UTF8

# 4. Write the Multi-Agent Reinforcement Learning Engine
Write-Host "Writing cortex/cortex/agent_marl.py..." -ForegroundColor Yellow
$agentMarlContent = @'
import uuid

from cortex.proposal_api import OrderDirection, TradeProposal


class AdaptiveCortexAgent:
    """
    The probabilistic intelligence layer. Analyzes market macro flows and
    emits structured TradeProposals to the Iron Constitution. It has zero
    direct execution privileges.
    """

    def __init__(self, agent_id: str = "alpha-sentinel-01"):
        self.agent_id = agent_id

    def evaluate_market_and_propose(
        self,
        asset_id: str,
        market_signal_strength: float,
        current_equity: float,
    ) -> TradeProposal:
        # Dynamic position sizing proportional to conviction and equity
        conviction_multiplier = min(max(market_signal_strength, 0.01), 0.05)
        target_notional = current_equity * conviction_multiplier

        direction = OrderDirection.BUY if market_signal_strength > 0 else OrderDirection.SELL
        proposal_id = f"{self.agent_id}-{uuid.uuid4().hex[:8]}"

        return TradeProposal(
            proposal_id=proposal_id,
            asset_id=asset_id,
            direction=direction,
            target_notional=round(target_notional, 2),
            max_acceptable_slippage=0.001,
        )
'@
Set-Content -Path "cortex/cortex/agent_marl.py" -Value $agentMarlContent -Encoding UTF8

# 5. Write the IPC client wrapper so Python talks to the Rust constitutiond boundary
Write-Host "Writing cortex/cortex/constitution_client.py..." -ForegroundColor Yellow
$clientContent = @'
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

    def _build_envelope(self, opcode: str, payload: str) -> bytes:
        envelope = {
            "protocol_version": self.PROTOCOL_VERSION,
            "request_id": "cortex-0001",
            "opcode": opcode,
            "payload": payload,
        }
        return json.dumps(envelope).encode("utf-8")

    def _send_frame(self, payload: bytes) -> str:
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.sendall(struct.pack(">I", len(payload)) + payload)
            header = sock.recv(4)
            if len(header) != 4:
                raise ConnectionError("Constitution closed connection early")
            frame_len = struct.unpack(">I", header)[0]
            if frame_len == 0 or frame_len > self.MAX_FRAME_BYTES:
                raise ValueError(f"Invalid response frame length: {frame_len}")
            chunks = []
            remaining = frame_len
            while remaining > 0:
                chunk = sock.recv(remaining)
                if not chunk:
                    raise ConnectionError("Truncated response frame")
                chunks.append(chunk)
                remaining -= len(chunk)
            return b"".join(chunks).decode("utf-8")

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
'@
Set-Content -Path "cortex/cortex/constitution_client.py" -Value $clientContent -Encoding UTF8

# 6. Write cortex/__init__.py
Set-Content -Path "cortex/cortex/__init__.py" -Value "" -Encoding UTF8

Write-Host "[SUCCESS] Module 2 (Adaptive Cortex) generated successfully via PowerShell automation!" -ForegroundColor Green
Write-Host "Python AI layer is fully wired to structure trade intents for the Rust Iron Constitution." -ForegroundColor Cyan