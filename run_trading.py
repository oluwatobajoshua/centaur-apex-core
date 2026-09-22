#!/usr/bin/env python
"""Production trading loop — starts TradingDaemon with a synthetic tick feed.

Run: python run_trading.py
Stop: Ctrl+C
"""
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
for pkg in ["cortex", "adapters", "doomsday", "mesh", "compliance", "simulation", "evolution"]:
    sys.path.insert(0, os.path.join(ROOT, pkg))
sys.path.insert(0, ROOT)

from cortex.trading_daemon import TradingDaemon


def generate_tick(asset="EURUSD", base_price=1.0800):
    rng = random.Random()
    volatility = rng.uniform(0.005, 0.03)
    momentum = rng.choice([True, True, False])
    price = base_price * (1 + rng.gauss(0, volatility))
    return {
        "asset_id": asset,
        "price": round(price, 5),
        "volatility": round(volatility, 6),
        "momentum_signal": momentum,
        "trend": "bullish" if momentum else "neutral",
        "timestamp": int(time.time()),
    }


def main():
    daemon = TradingDaemon(
        asset_id=os.environ.get("TRADING_ASSET", "EURUSD"),
        constitution_host=os.environ.get("CONSTITUTION_HOST", "127.0.0.1"),
        constitution_port=int(os.environ.get("CONSTITUTION_PORT", "15565")),
        equity=float(os.environ.get("TRADING_EQUITY", "100000")),
        heartbeat_interval_s=5.0,
        tick_interval_s=5.0,
    )
    daemon.start()

    tick_count = 0
    try:
        while daemon._running:
            tick = generate_tick()
            tick_count += 1
            print(f"\n[Tick #{tick_count}] {tick['price']} vol={tick['volatility']} momentum={tick['momentum_signal']}", flush=True)
            daemon._process_tick(tick)
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n[TradingDaemon] Shutdown requested...", flush=True)
    finally:
        daemon._dormant.stop()
        daemon.client.close_session()
        print("[TradingDaemon] Stopped.", flush=True)


if __name__ == "__main__":
    main()
