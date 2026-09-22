#!/usr/bin/env python
"""Synthetic market tick generator — feeds the trading daemon over stdin JSON.

Genesis DNA (G7: Chronos framework): uses a regime-flavoured random walk to
produce realistic market data for the continuous trading loop. This is a
placeholder feed; production uses real venue feeds via the adapter layer (S1).

Cadence is configurable (default 5.0s) so the trading daemon's in-process
Doomsday (grace = 3x heartbeat) never degrades into escalation on slow feeds.
Emits one JSON tick per line, forever.
"""
import json
import os
import random
import sys
import time

_RNG = random.Random()
_TICK_INTERVAL_S = float(os.environ.get("MARKET_FEED_INTERVAL_S", "5.0"))


def generate_tick(asset="EURUSD", base_price=1.0800, rng=None):
    rng = rng or _RNG
    volatility = rng.uniform(0.005, 0.03)
    momentum = rng.choice([True, True, False])  # 2/3 bullish
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
    print(f"[MarketFeed] starting tick generator (interval={_TICK_INTERVAL_S}s, infinite)...", file=sys.stderr, flush=True)
    tick_index = 0
    while True:
        tick = generate_tick()
        tick_index += 1
        print(json.dumps(tick), flush=True)
        time.sleep(_TICK_INTERVAL_S)


if __name__ == "__main__":
    main()