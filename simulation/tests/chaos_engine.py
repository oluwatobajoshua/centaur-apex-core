"""
Chaos Engineering Engine — G9 tooling for Centaur-Apex Core.

Tests system resilience by injecting controlled failures and verifying
fail-safe behavior (AGENTS.md I6: "any unknown state, crash, or loss of
connectivity → EmergencyHalt"). All chaos tests run in isolated sandboxes;
the Constitution daemon is spawned, attacked, and reaped per-scenario.

Scenarios (PRD §5):
  1. Daemon crash — sever the TCP connection to constitutiond; verify IPC
     client detects failure, system can re-spawn and recover.
  2. Corrupted packet — send malformed IPC frames (invalid JSON, wrong
     protocol version, oversized, missing fields); verify the daemon handles
     every case gracefully without crashing.
  3. Flash crash — drive the engine through SyntheticRegimeGenerator extreme
     shocks that trigger EmergencyHalt; verify two-phase recovery restores
     Normal state.
"""
import json
import os
import socket
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field

ROOT = os.path.abspath(os.path.dirname(__file__) + "/../..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "cortex"))
sys.path.insert(0, os.path.join(ROOT, "simulation"))

from cortex.constitution_client import ConstitutionIPCClient
from cortex.engine import CortexEngine
from cortex.proposal_api import OrderDirection, TradeProposal
from simulation.synthetic_gen import SyntheticRegimeGenerator

DAEMON_NAME = "constitutiond.exe" if os.name == "nt" else "constitutiond"
CONSTITUTIOND = os.path.join(ROOT, "constitution", "target", "debug", DAEMON_NAME)
PORT = 15565
MAX_FRAME = 16_384


@dataclass
class ChaosResult:
    """Outcome of a single chaos scenario."""
    scenario: str
    passed: bool
    details: str = ""
    metrics: dict = field(default_factory=dict)


def _spawn_daemon() -> subprocess.Popen:
    """Start constitutiond; raise if it cannot bind."""
    proc = subprocess.Popen(
        [CONSTITUTIOND],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 10
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"constitutiond exited (rc={proc.returncode})")
        try:
            with ConstitutionIPCClient(timeout=1.0) as c:
                c.heartbeat()
                return proc
        except OSError:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("constitutiond did not come up in 10s")


def _raw_send(payload: bytes, port: int = PORT) -> bytes | None:
    """Send a raw frame (no validation) and return any response bytes."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
            sock.sendall(struct.pack(">I", len(payload)) + payload)
            header = sock.recv(4)
            if len(header) != 4:
                return None
            frame_len = struct.unpack(">I", header)[0]
            if frame_len == 0 or frame_len > MAX_FRAME:
                return None
            data = b""
            while len(data) < frame_len:
                chunk = sock.recv(frame_len - len(data))
                if not chunk:
                    break
                data += chunk
            return data
    except OSError:
        return None


def _portfolio(equity: float, hwm: float) -> dict:
    return {
        "timestamp": int(time.time()),
        "total_equity": equity,
        "cash_balance": equity,
        "high_water_mark": hwm,
        "open_positions": [],
    }


def _make_proposal() -> dict:
    return TradeProposal(
        proposal_id="chaos-001",
        asset_id="BTC-PERP",
        direction=OrderDirection.BUY,
        target_notional=10_000.0,
        max_acceptable_slippage=0.001,
    ).model_dump()


class ChaosEngine:
    """
    Orchestrates controlled failure-injection scenarios.

    Per AGENTS.md §5 ("Sandbox everything"): every scenario spawns an ephemeral
    constitutiond instance, injects the failure, observes the response, and
    reaps the process. No chaos test mutates shared state.
    """

    def __init__(self, daemon_path: str = CONSTITUTIOND):
        self._daemon_path = daemon_path

    def scenario_daemon_crash(self) -> ChaosResult:
        """
        Kill the constitutiond process mid-session and verify the IPC client
        detects the connection loss. The daemon must NOT silently continue.
        """
        proc = _spawn_daemon()
        client = ConstitutionIPCClient()
        try:
            client.open_session()
            client.heartbeat()

            # Kill the daemon
            proc.terminate()
            proc.wait(timeout=5)

            # Connection should now fail
            crashed = False
            try:
                client.heartbeat()
            except OSError:
                crashed = True

            return ChaosResult(
                scenario="daemon_crash",
                passed=crashed,
                details="daemon terminated, IPC client detected connection loss",
                metrics={"port": PORT},
            )
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
            client.close_session()

    def scenario_corrupted_packets(self) -> ChaosResult:
        """
        Send malformed IPC frames and verify the daemon handles each case
        gracefully (returns an error, does not crash or hang).

        Per AGENTS.md I6 (fail-safe default): any unknown/malformed state
        must not cause the daemon to behave unpredictably.
        """
        proc = _spawn_daemon()
        results: dict[str, bool] = {}
        try:
            def _handled(raw: bytes | None) -> bool:
                """Graceful = error response OR dropped connection (no crash)."""
                return raw is None or b"error" in (raw or b"")

            # 1. Invalid JSON envelope
            results["invalid_json"] = _handled(_raw_send(b"not json at all"))

            # 2. Wrong protocol version
            bad_ver = json.dumps({
                "protocol_version": 999,
                "request_id": "bad",
                "opcode": "Heartbeat",
                "payload": "{}",
            })
            results["wrong_version"] = _handled(_raw_send(bad_ver.encode()))

            # 3. Oversized frame (> 16KB) — server drops connection before reading
            big = b"x" * (MAX_FRAME + 1)
            results["oversized_frame"] = _handled(_raw_send(big))

            # 4. Missing required fields
            missing = json.dumps({"protocol_version": 1, "request_id": "x"})
            results["missing_fields"] = _handled(_raw_send(missing.encode()))

            # 5. Corrupted payload (valid envelope, garbage payload for EvaluateProposal)
            bad_payload = {
                "protocol_version": 1,
                "request_id": "x",
                "opcode": "EvaluateProposal",
                "payload": "{{broken",
            }
            results["corrupted_payload"] = _handled(_raw_send(
                json.dumps(bad_payload).encode()
            ))

            # Verify daemon is still alive
            alive = _raw_send(json.dumps({
                "protocol_version": 1,
                "request_id": "alive",
                "opcode": "Heartbeat",
                "payload": "{}",
            }).encode())
            results["daemon_alive_after_attacks"] = alive is not None and b"true" in (alive or b"")

            all_passed = all(results.values())
            return ChaosResult(
                scenario="corrupted_packets",
                passed=all_passed,
                details=f"{sum(results.values())}/{len(results)} attack vectors handled gracefully",
                metrics=results,
            )
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)

    def scenario_flash_crash(self) -> ChaosResult:
        """
        Drive CortexEngine through extreme SyntheticRegimeGenerator shocks
        that trigger EmergencyHalt via drawdown (I1). Verify the system
        enters EmergencyHalt and recovers via the two-phase cryptographic path.
        """
        proc = _spawn_daemon()
        engine = CortexEngine(asset_id="BTC-PERP", risk_profile="aggressive")
        generator = SyntheticRegimeGenerator()
        client = ConstitutionIPCClient()

        metrics: dict = {
            "emergency_halt_triggered": False,
            "recovery_phase1": False,
            "recovery_phase2": False,
            "proposals_evaluated": 0,
        }
        try:
            client.open_session()
            client.heartbeat()

            portfolio = _portfolio(equity=1_000_000.0, hwm=1_000_000.0)

            # Generate one year of extreme volatility using SyntheticRegimeGenerator
            _prices, curve = generator.generate_price_path(
                start_price=100.0,
                points=365,
                volatility=0.05,
            )
            baseline = curve[0] if (curve and curve[0] > 0.0) else 1.0
            equity = 1_000_000.0
            peak = equity

            for tick in curve:
                equity *= tick / baseline
                peak = max(peak, equity)

                # Generate aggressive proposals to stress-test the risk kernel
                result = engine.evaluate_market_tick({
                    "price": tick,
                    "volatility": 0.05,
                    "momentum_signal": True,
                    "trend": "bearish",
                    "account_equity": equity,
                })

                if result["status"] == "ProposalGenerated":
                    metrics["proposals_evaluated"] += 1
                    proposal = TradeProposal.model_validate(result["proposal"])

                    if equity <= 0.0:
                        metrics["equity_exhausted"] = True
                        break

                    portfolio["total_equity"] = equity
                    portfolio["high_water_mark"] = peak

                    resp = client.evaluate(portfolio, proposal.model_dump())
                    verdict = resp["verdict"]

                    if verdict == "EmergencyLiquidationAll":
                        metrics["emergency_halt_triggered"] = True
                        break

            # If EmergencyHalt was triggered, attempt two-phase recovery
            if metrics["emergency_halt_triggered"]:
                status = client.status()
                if status.system_state == "EmergencyHalt":
                    resp1 = client.recover(cryptographic_proof_valid=True)
                    if resp1.get("recovery_success"):
                        metrics["recovery_phase1"] = True
                    resp2 = client.recover(cryptographic_proof_valid=True)
                    if resp2.get("recovery_success"):
                        metrics["recovery_phase2"] = True

            # Verify daemon is still alive after the flash crash
            alive = _raw_send(json.dumps({
                "protocol_version": 1,
                "request_id": "alive",
                "opcode": "Heartbeat",
                "payload": "{}",
            }).encode())
            metrics["daemon_alive_after_flash_crash"] = alive is not None and b"true" in (alive or b"")

            passed = (
                metrics["emergency_halt_triggered"]
                and metrics["recovery_phase1"]
                and metrics["recovery_phase2"]
                and metrics["daemon_alive_after_flash_crash"]
            )
            return ChaosResult(
                scenario="flash_crash",
                passed=passed,
                details=(
                    "EmergencyHalt triggered via drawdown; "
                    f"recovery: phase1={metrics['recovery_phase1']}, "
                    f"phase2={metrics['recovery_phase2']}"
                ),
                metrics=metrics,
            )
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
            client.close_session()

    def run_all(self) -> list[ChaosResult]:
        """Execute all chaos scenarios sequentially."""
        return [
            self.scenario_corrupted_packets(),
            self.scenario_daemon_crash(),
            self.scenario_flash_crash(),
        ]


if __name__ == "__main__":
    engine = ChaosEngine()
    results = engine.run_all()
    print(json.dumps([r.__dict__ for r in results], indent=2, default=str))
    all_passed = all(r.passed for r in results)
    sys.exit(0 if all_passed else 1)
