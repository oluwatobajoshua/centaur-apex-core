"""Next-candle ML drill - run EXTERNALLY in your own terminal so long model
fits never hit the agent shell timeout.

Usage (from the repo root, any stable terminal):
    C:\\Python314\\python.exe cortex\\scripts\\next_candle_drill.py --days 365 --tf 300 --symbol BTCUSDT --out reports\\drill_btc_5m_1y.json

Streams progress to stdout and writes the JSON result to ``--out``. Run it in
its own PowerShell/cmd window and let it grind - the honest answer is written
to disk, not to a chat buffer.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--tf", type=int, default=300, help="Candle timeframe in seconds.")
    parser.add_argument("--days", type=int, default=90, help="How much history to fetch (days).")
    parser.add_argument("--warmup", type=int, default=500)
    parser.add_argument("--rolling", type=int, default=20_000, help="Rolling training window (candles).")
    parser.add_argument("--retrain", type=int, default=250, help="Re-fit the model every N candles.")
    parser.add_argument("--out", default="reports/next_candle_drill.json")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from cortex.cortex.ml import run_scale_ml  # noqa: E402

    history_ms = args.days * 24 * 3600 * 1000
    t0 = time.monotonic()
    print(f"[drill] fetching {args.days}d of {args.symbol} {args.tf}s candles...", flush=True)
    result = run_scale_ml(
        symbol=args.symbol,
        timeframe_s=args.tf,
        history_ms=history_ms,
        warmup=args.warmup,
        rolling_window=args.rolling,
        retrain_every=args.retrain,
    )
    result["duration_s"] = round(time.monotonic() - t0, 1)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    print(f"[drill] written to {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())