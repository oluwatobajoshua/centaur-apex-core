"""Live market-data adapter (G8 machinery): public Binance REST klines.

Fetches OHLCV history for a symbol without any credentials (I5: observation
only - this adapter can never route, sign or size). Converts the venue's
raw rows into our Genesis ``Candle`` type so every downstream engine
(aggregator, market-context, event watcher, sequence stats) can consume live
data transparently. Venue specifics stay scoped HERE - nothing downstream
knows (or cares) where the candles came from.
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

from cortex.cortex.market_context import Candle

BINANCE_KLINE_URL = "https://api.binance.com/api/v3/klines"
INTERVAL_MAP = {
    60: "1m",
    300: "5m",
    900: "15m",
    3600: "1h",
    14400: "4h",
    86400: "1d",
}
TIMEFRAME_MS = {k: k * 1000 for k in INTERVAL_MAP}


class LiveFeedError(Exception):
    pass


def _http_json(url: str, timeout_s: float = 15.0) -> dict[str, Any] | list[Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "centaur-apex-core/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            payload = resp.read()
    except Exception as exc:  # noqa: BLE001 - surface any transport failure to the caller
        raise LiveFeedError(f"request failed: {exc}") from exc
    try:
        return json.loads(payload)
    except ValueError as exc:
        raise LiveFeedError("malformed JSON response") from exc


def _to_float(v: Any, what: str) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError) as exc:
        raise LiveFeedError(f"invalid {what}: {v!r}") from exc
    if not (f > 0 and f == f):
        raise LiveFeedError(f"non-finite {what}: {f!r}")
    return f


def _parse_kline(row: list[Any]) -> Candle:
    open_ms, open_p, high, low, close, volume, close_ms = (
        row[0],
        row[1],
        row[2],
        row[3],
        row[4],
        row[5],
        row[6],
    )
    return Candle(
        open=_to_float(open_p, "open"),
        high=_to_float(high, "high"),
        low=_to_float(low, "low"),
        close=_to_float(close, "close"),
        t_open=float(open_ms) / 1000.0,
        t_close=float(close_ms) / 1000.0,
        volume=_to_float(volume, "volume"),
    )


def fetch_klines(
    symbol: str,
    timeframe_s: float,
    limit: int = 1000,
    end_ms: int | None = None,
) -> list[Candle]:
    """Fetch recent OHLCV candles (newest last) from Binance public REST."""
    interval = INTERVAL_MAP.get(int(timeframe_s))
    if interval is None:
        raise LiveFeedError(f"unsupported timeframe: {timeframe_s}")
    if not 1 <= limit <= 1000:
        raise LiveFeedError(f"limit must be 1..1000, got {limit}")
    params = f"symbol={symbol}&interval={interval}&limit={limit}"
    if end_ms is not None:
        params += f"&endTime={end_ms}"
    data = _http_json(f"{BINANCE_KLINE_URL}?{params}")
    if not isinstance(data, list):
        raise LiveFeedError("unexpected kline response shape")
    rows = [_parse_kline(r) for r in data]
    rows.sort(key=lambda c: c.t_open)
    return rows


def fetch_history(
    symbol: str,
    timeframe_s: float,
    history_ms: float,
    batch: int = 1000,
    end_ms: int | None = None,
) -> list[Candle]:
    """Paged bulk history fetch (newest last): walks endTime backwards in
    1000-row batches until ``history_ms`` of candles are covered.

    The system's own history for base-rate fitting: the more the model
    conditions on, the tighter the honest ceiling becomes.
    """
    out: list[Candle] = []
    cursor = int((time.time() * 1000) if end_ms is None else end_ms)
    oldest = cursor - int(history_ms)
    interval_s = TIMEFRAME_MS.get(int(timeframe_s), 60_000)
    while cursor > oldest:
        rows = fetch_klines(symbol, timeframe_s, limit=batch, end_ms=cursor)
        if not rows:
            break
        out = rows + out
        cursor = int(rows[0].t_open * 1000) - interval_s
    return out


def fetch_last_price(symbol: str) -> float:
    """A tiny live tick: latest BTC/USDT price. Nothing but observation."""
    data = _http_json(f"{BINANCE_KLINE_URL}?symbol={symbol}&interval=1m&limit=1")
    if not isinstance(data, list) or not data:
        raise LiveFeedError("empty kline response")
    close = data[-1][4]
    if not isinstance(close, (int, float)) or close <= 0:
        raise LiveFeedError("invalid price")
    return float(close)


def to_stream_tick(candle: Candle) -> dict[str, Any]:
    return {"price": candle.close, "timestamp": candle.t_close}