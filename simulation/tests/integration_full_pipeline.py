"""
CHRONOS × CORTEX × CONSTITUTION × ADAPTER — full-stack integration test.

Spawns the Rust constitutiond daemon, opens a persistent IPC session, then
drives the complete live pipeline:

    CortexEngine → TradeProposal → Constitution verdict
        → [if Approved] proposal_to_intent → MockExchangeAdapter → ExecutionReceipt

Validates the full cross-module contract: the Constitution's verdict is the
sole authority on whether an order may be placed (Invariant I5), and the
adapter layer executes only approved intents.
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "cortex"))
sys.path.insert(0, os.path.join(ROOT, "adapters"))
sys.path.insert(0, os.path.join(ROOT, "simulation"))

from adapters.base import AbstractExchangeAdapter, ExecutionReceipt
from adapters.discovery_agent import VenueDiscoveryAgent
from adapters.proposal_bridge import verdict_to_order_action
from cortex.constitution_client import ConstitutionIPCClient
from cortex.engine import CortexEngine
from cortex.proposal_api import TradeProposal

DAEMON_NAME = "constitutiond.exe" if os.name == "nt" else "constitutiond"
CONSTITUTIOND = os.path.abspath(
    os.path.join(ROOT, "constitution", "target", "debug", DAEMON_NAME)
)

PLUGINS_DIR = os.path.join(ROOT, "adapters", "adapters", "venue_plugins")


def spawn_daemon() -> subprocess.Popen:
    """Start constitutiond in debug mode; fail fast if the port is already bound."""
    proc = subprocess.Popen([CONSTITUTIOND], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 10
    while time.time() < deadline:
        if proc.poll() is not None:
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


def _portfolio(equity: float, hwm: float, asset: str = "EURUSD") -> dict:
    return {
        "timestamp": int(time.time()),
        "total_equity": round(equity, 2),
        "cash_balance": round(equity * 0.9, 2),
        "high_water_mark": round(hwm, 2),
        "open_positions": [
            {"asset_id": asset, "notional_value": 5_000.0, "entry_price": 1.0820}
        ],
    }


def _market_scenarios():
    """Yield (scenario_name, tick_dict, price) tuples."""
    return [
        ("bullish-low-vol",  {"price": 1.0850, "volatility": 0.005,
                              "momentum_signal": True, "trend": "bullish"}, 1.0850),
        ("bearish-high-vol", {"price": 1.0720, "volatility": 0.025,
                              "momentum_signal": True, "trend": "bearish"}, 1.0720),
        ("bullish-high-vol", {"price": 1.0900, "volatility": 0.030,
                              "momentum_signal": True, "trend": "bullish"}, 1.0900),
        ("no-momentum",      {"price": 1.0800, "volatility": 0.005,
                              "momentum_signal": False, "trend": "neutral"}, 1.0800),
        ("bearish-low-vol",  {"price": 1.0650, "volatility": 0.008,
                              "momentum_signal": True, "trend": "bearish"}, 1.0650),
    ]


def run_full_pipeline() -> dict:
    """Execute the full Cortex → Constitution → Adapter pipeline.

    Returns a summary dict with proposal/approval/rejection/execution counts.
    """
    proc = spawn_daemon()
    engine = CortexEngine(asset_id="EURUSD", risk_profile="dynamic")
    discovery = VenueDiscoveryAgent(plugins_dir=PLUGINS_DIR)
    plugins = discovery.load_active_plugins()

    assert "mock_exchange" in plugins, "MockExchangeAdapter must be discoverable"
    adapter: AbstractExchangeAdapter = plugins["mock_exchange"]
    assert adapter.connect(), "Mock exchange adapter must connect"
    assert adapter.health_check(), "Mock exchange adapter must be healthy"

    portfolio = _portfolio(equity=50_000.0, hwm=52_000.0)
    results = {
        "proposals": 0,
        "approved": 0,
        "rejected": 0,
        "emergency": 0,
        "executions": 0,
        "rejections_by_reason": {},
        "states_seen": set(),
    }

    try:
        with ConstitutionIPCClient() as client:
            for name, tick, price in _market_scenarios():
                tick["account_equity"] = portfolio["total_equity"]

                cortex_result = engine.evaluate_market_tick(tick)

                if cortex_result["status"] != "ProposalGenerated":
                    continue

                proposal = TradeProposal.model_validate(cortex_result["proposal"])
                results["proposals"] += 1

                resp = client.evaluate(portfolio, proposal.model_dump())
                verdict = resp["verdict"]
                results["states_seen"].add(resp["system_state"])

                if "Approved" in verdict:
                    results["approved"] += 1
                    adjusted = verdict["Approved"]["adjusted_notional"]

                    intent = verdict_to_order_action(
                        verdict, proposal, price=price
                    )
                    assert intent is not None, "Approved verdict must yield an intent"
                    assert intent.asset_id == proposal.asset_id
                    assert intent.side == proposal.direction.value

                    receipt: ExecutionReceipt = adapter.execute_order(intent)
                    assert receipt.status == "FILLED"
                    assert receipt.filled_price > 0
                    assert receipt.filled_quantity > 0
                    results["executions"] += 1

                    portfolio["open_positions"].append({
                        "asset_id": intent.asset_id,
                        "notional_value": adjusted,
                        "entry_price": receipt.filled_price,
                    })
                elif "Rejected" in verdict:
                    results["rejected"] += 1
                    reason = verdict["Rejected"]["reason_code"]
                    results["rejections_by_reason"][reason] = (
                        results["rejections_by_reason"].get(reason, 0) + 1
                    )
                elif verdict == "EmergencyLiquidationAll":
                    results["emergency"] += 1
                    portfolio["total_equity"] = max(
                        portfolio["total_equity"] * 0.98, 50_000.0
                    )
                    portfolio["high_water_mark"] = portfolio["total_equity"]

    finally:
        proc.terminate()
        proc.wait(timeout=5)

    return {
        "passed": results["proposals"] > 0 and results["executions"] > 0,
        "proposals": results["proposals"],
        "approved": results["approved"],
        "rejected": results["rejected"],
        "emergency": results["emergency"],
        "executions": results["executions"],
        "rejections_by_reason": results["rejections_by_reason"],
        "states_seen": sorted(results["states_seen"]),
    }


if __name__ == "__main__":
    report = run_full_pipeline()
    print(json.dumps(report, indent=2, default=str))
    sys.exit(0 if report["passed"] else 1)
