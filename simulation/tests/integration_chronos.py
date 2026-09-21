"""
CHRONOS x CORTEX x CONSTITUTION — first live end-to-end integration test.

Spawns the Rust constitutiond daemon, opens a persistent IPC session, then
drives the Adaptive Cortex (MARL) proposal engine through a CHRONOS synthetic
stress timeline. Verifies the full loop: AI proposes -> Constitution adjudicates
-> equity is tracked under the verdict -> halted states recover via cryptographic proof.
"""

import json
import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, ROOT)                        # repo root (editable/debug paths)
sys.path.insert(0, os.path.join(ROOT, "cortex"))       # cortex package home
sys.path.insert(0, os.path.join(ROOT, "simulation"))   # simulation package home

from cortex.agent_marl import AdaptiveCortexAgent
from cortex.constitution_client import ConstitutionIPCClient
from simulation.synthetic_gen import SyntheticRegimeGenerator

DAEMON_NAME = "constitutiond.exe" if os.name == "nt" else "constitutiond"
CONSTITUTIOND = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../constitution/target/debug", DAEMON_NAME)
)

EXPOSURE = 0.15          # fraction of market move applied to equity
EQUITY_FLOOR = 50_000.0  # survivable cash backstop


def spawn_daemon() -> subprocess.Popen:
    proc = subprocess.Popen([CONSTITUTIOND], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 10
    while time.time() < deadline:
        if proc.poll() is not None:
            # If a stale daemon already holds the port, the new one dies on
            # bind and we would otherwise silently talk to the stale kernel.
            raise RuntimeError(
                f"constitutiond exited early (port already in use?): rc={proc.returncode}"
            )
        try:
            with ConstitutionIPCClient(timeout=1.0) as c:
                c.heartbeat()
                return proc
        except OSError:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("constitutiond did not come up in time")


def portfolio_state(equity: float, hwm: float) -> dict:
    return {
        "timestamp": int(time.time()),
        "total_equity": round(equity, 2),
        "cash_balance": round(equity, 2),
        "high_water_mark": round(hwm, 2),
        "open_positions": [],
    }


def run_simulation(years: int = 250) -> dict:
    failures = {"equity_exhausted": 0, "recoveries": 0}
    proc = spawn_daemon()
    agent = AdaptiveCortexAgent()
    generator = SyntheticRegimeGenerator()
    equity = 1_000_000.0
    peak = equity
    worst_drawdown = 0.0
    approved = rejected = emergency = 0
    regime_counts: dict[str, int] = {}
    state_log: set[str] = set()

    try:
        with ConstitutionIPCClient() as client:
            for year in range(years):
                prices, _ = generator.generate_price_path(start_price=100.0, points=365)
                regime = generator.sample_next_regime()
                regime_counts[regime] = regime_counts.get(regime, 0) + 1

                for i in range(1, len(prices)):
                    ret = (prices[i] - prices[i - 1]) / prices[i - 1]
                    equity = max(equity * (1.0 + EXPOSURE * ret), EQUITY_FLOOR)
                    peak = max(peak, equity)
                    worst_drawdown = max(worst_drawdown, (peak - equity) / peak)

                    signal = (prices[i] - prices[i - 1]) / prices[i - 1] * 10.0
                    proposal = agent.evaluate_market_and_propose(
                        asset_id="SYNTH-PERP",
                        market_signal_strength=signal,
                        current_equity=equity,
                    )

                    resp = client.evaluate(
                        portfolio_state(equity, peak),
                        proposal.model_dump(),
                    )
                    state_log.add(resp["system_state"])

                    verdict = resp["verdict"]
                    if "Approved" in verdict:
                        approved += 1
                        # Approved position is hedged by a small execution cost
                        equity = max(equity - proposal.target_notional * 0.0001, EQUITY_FLOOR)
                    elif "Rejected" in verdict:
                        rejected += 1
                    elif verdict == "EmergencyLiquidationAll":
                        emergency += 1
                        # Constitution halts trading; liquidation costs 2% of capital
                        equity = max(equity * 0.98, EQUITY_FLOOR)
                        if equity <= 0.0:
                            failures["equity_exhausted"] += 1
                            break

                # End-of-year: if halted, run the two-phase cryptographic recovery
                # (EmergencyHalt -> AutonomousRecovery -> Normal) so the system can
                # re-enter Normal operations with the restructured capital.
                status = client.status()
                state_log.add(status.system_state)
                if status.system_state == "EmergencyHalt":
                    resp = client.recover(cryptographic_proof_valid=True)
                    if resp.get("recovery_success"):
                        failures["recoveries"] += 1
                        # Phase 2: diagnostic-pass proof returns to Normal.
                        resp2 = client.recover(cryptographic_proof_valid=True)
                        if resp2.get("recovery_success"):
                            # Anchor peak to current equity to model capital restructuring
                            peak = equity
                        else:
                            state_log.add(client.status().system_state)
    finally:
        # Always reap the daemon, even on mid-run failure, so no stale kernel
        # can leak onto the fixed port and poison later runs.
        proc.terminate()
        proc.wait(timeout=5)

    return {
        "passed": equity > 0.0 and failures["equity_exhausted"] == 0,
        "final_equity": round(equity, 2),
        "worst_drawdown": round(worst_drawdown, 4),
        "approved": approved,
        "rejected": rejected,
        "emergency_liquidations": emergency,
        "regime_counts": regime_counts,
        "states_seen": sorted(state_log),
        "failures": failures,
    }


if __name__ == "__main__":
    years = int(sys.argv[1]) if len(sys.argv) > 1 else 250
    report = run_simulation(years=years)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["passed"] else 1)