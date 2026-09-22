import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "cortex"))
sys.path.insert(0, os.path.join(ROOT, "adapters"))

from cortex.constitution_client import ConstitutionIPCClient
from cortex.engine import CortexEngine

DAEMON_NAME = "constitutiond.exe" if os.name == "nt" else "constitutiond"
CONSTITUTIOND = os.path.abspath(
    os.path.join(ROOT, os.path.normpath(f"constitution/target/debug/{DAEMON_NAME}"))
)


def _portfolio(equity: float, hwm: float) -> dict:
    return {
        "timestamp": 1789450800,
        "total_equity": round(equity, 2),
        "cash_balance": round(equity * 0.9, 2),
        "high_water_mark": round(hwm, 2),
        "open_positions": [
            {"asset_id": "EURUSD", "notional_value": 5000.0, "entry_price": 1.0820}
        ],
    }


def main() -> None:
    print("Initializing Centaur-Apex Core pipeline simulation...")

    proc = None
    try:
        client = ConstitutionIPCClient(timeout=2.0)
        client.open_session()
        client.heartbeat()
    except OSError:
        print("Starting constitutiond daemon...")
        proc = subprocess.Popen(
            [CONSTITUTIOND], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(1.5)
        client = ConstitutionIPCClient(timeout=2.0)
        client.open_session()

    ENGINE_ASSET = "EURUSD"
    engine = CortexEngine(asset_id=ENGINE_ASSET, risk_profile="dynamic")

    portfolio = _portfolio(equity=50_000.0, hwm=52_000.0)

    scenarios = [
        {"price": 1.0850, "volatility": 0.007, "momentum_signal": True, "trend": "bullish"},
        {"price": 1.0720, "volatility": 0.028, "momentum_signal": True, "trend": "bearish"},
        {"price": 1.0800, "volatility": 0.005, "momentum_signal": False, "trend": "neutral"},
    ]

    try:
        for idx, tick in enumerate(scenarios, start=1):
            tick["account_equity"] = portfolio["total_equity"]

            result = engine.evaluate_market_tick(tick)

            if result["status"] != "ProposalGenerated":
                print(f"[{idx}] Cortex: NoAction (no momentum) -> skipped")
                continue

            proposal = result["proposal"]
            resp = client.evaluate(portfolio, proposal)
            verdict = resp["verdict"]
            state = resp["system_state"]

            print(f"[{idx}] Cortex proposal -> Constitution verdict: {verdict} [{state}]")

            if "Approved" in verdict:
                notional = next(iter(verdict.values()))["adjusted_notional"]
                portfolio["open_positions"].append(
                    {"asset_id": ENGINE_ASSET, "notional_value": notional, "entry_price": tick["price"]}
                )

        print(f"\nFinal status: {client.status()}")
        print("\n[SUCCESS] End-to-End pipeline (Cortex -> Rust Constitution) complete!")
    finally:
        client.close_session()
        if proc is not None:
            proc.terminate()


if __name__ == "__main__":
    main()