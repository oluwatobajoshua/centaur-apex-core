"""Next-candle colour drill (empirical base-rate measurement, not alpha).

Answers an honest question: 'how often can the system correctly call the colour
of the NEXT candle before it closes?' The literature ceiling is ~54-65%; any
claim of 99.99% is regression overfit or marketing. This module walks live
Binance candles forward, fits context-conditional probabilities on the history
seen SO FAR (point-in-time, no lookahead), then scores the colour call.

Contexts conditioned on:
  * colour of the just-closed candle (momentum persistence vs reversal)
  * consecutive same-colour streak (streak-extreme reversal base rates)
  * body size vs ATR (strong/weak candle)

Everything is measured and reported: coverage, accuracy, and the confidence
curve wins the user's trust - not a magic percentage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from adapters.adapters.live_feed import fetch_klines
from .market_context import Candle
from .sequence_stats import CondStats


def _colour(c: Candle) -> int:
    return (c.close > c.open) - (c.close < c.open)


def _streak(hist: list[Candle], i: int) -> int:
    """Length of the consecutive same-colour run ending at index i (colour of bar i)."""
    if i < 0:
        return 0
    col = _colour(hist[i])
    if col == 0:
        return 0
    n = 1
    j = i - 1
    while j >= 0 and _colour(hist[j]) == col:
        n += 1
        j -= 1
    return n


def _atr(candles: list[Candle], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    trs: list[float] = []
    for i in range(1, len(candles)):
        p = candles[i - 1]
        c = candles[i]
        trs.append(max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close)))
    window = trs[-period:]
    return sum(window) / len(window)


@dataclass
class NextCandleDrill:
    """Point-in-time walk-forward colour predictor with honest scoring."""

    confidence_min: float = 0.52
    _table: dict[tuple[int, int, int], CondStats] = field(default_factory=dict)
    _decisions: list[tuple[bool, str]] = field(default_factory=list)
    _all_calls: int = 0
    _all_right: int = 0

    def fit_accumulate(self, hist: list[Candle], i: int) -> None:
        """Add one historical (bar i -> bar i+1) observation to the table."""
        if i + 1 >= len(hist):
            return
        cur = hist[i]
        col = _colour(cur)
        if col == 0:
            return
        atr = _atr(hist[: i + 1])
        size_bucket = 2 if abs(cur.close - cur.open) >= 2 * atr else (1 if abs(cur.close - cur.open) >= atr else 0)
        key = (col, _streak(hist, i), size_bucket)
        nxt = _colour(hist[i + 1])
        stat = self._table.setdefault(key, CondStats())
        if nxt > 0:
            stat.up += 1
        elif nxt < 0:
            stat.down += 1

    def predict(self, hist: list[Candle]) -> int | None:
        """Colour call for the next candle: +1 (green), -1 (red), None = abstain."""
        if not hist:
            return None
        last = hist[-1]
        col = _colour(last)
        if col == 0:
            return None
        atr = _atr(hist)
        size_bucket = 2 if abs(last.close - last.open) >= 2 * atr else (1 if abs(last.close - last.open) >= atr else 0)
        key = (col, _streak(hist, len(hist) - 1), size_bucket)
        stat = self._table.get(key)
        if stat is None or stat.count == 0:
            return None
        p_green = stat.p_up()
        if p_green >= self.confidence_min:
            return 1
        if p_green <= 1 - self.confidence_min:
            return -1
        return None

    def on_realised(self, call: int | None, actual: int) -> None:
        self._all_calls += 1
        if actual == 0:
            return
        if call is not None:
            self._decisions.append((call == actual, "green" if call > 0 else "red"))

    def score(self) -> dict[str, float]:
        right = sum(1 for ok, _ in self._decisions if ok)
        n = len(self._decisions)
        return {
            "decisions": float(n),
            "accuracy": right / n if n else 0.0,
            "coverage": n / self._all_calls if self._all_calls else 0.0,
            "green_calls": float(sum(1 for _, c in self._decisions if c == "green")),
            "red_calls": float(sum(1 for _, c in self._decisions if c == "red")),
            "base_rate_green": self._base_rate(),
        }

    def _base_rate(self) -> float:
        total = self._table
        ups = sum(s.up for s in total.values())
        downs = sum(s.down for s in total.values())
        if ups + downs == 0:
            return 0.0
        return ups / (ups + downs)


def run_live_drill(
    symbol: str = "BTCUSDT",
    timeframe_s: float = 300,
    history_candles: int = 600,
    score_candles: int = 200,
) -> dict[str, Any]:
    """Walk live Binance data forward: fit on history-so-far, call next colour."""
    candles = fetch_klines(symbol, timeframe_s, limit=history_candles + score_candles)
    if len(candles) < history_candles + 30:
        return {"error": "not enough live candles"}

    drill = NextCandleDrill(confidence_min=0.54)
    for i in range(30, history_candles - 1):
        drill.fit_accumulate(candles, i)

    for i in range(history_candles - 1, len(candles) - 1):
        hist = candles[: i + 1]
        drill.fit_accumulate(hist, i)
        call = drill.predict(hist)
        drill.on_realised(call, _colour(candles[i + 1]))

    out: dict[str, Any] = {
        "symbol": symbol,
        "timeframe_s": timeframe_s,
        "scored_candles": len(candles) - history_candles,
        "result": drill.score(),
    }
    return out