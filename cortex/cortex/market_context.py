"""Market Context Engine — Genesis machinery (G5 framework), not a strategy.

Reads raw price action into machine-readable *structure* so autonomous
strategies (S2, system-written) can reason like a professional trader:

* Multi-timeframe candle aggregation (one timeframe per engine instance;
  daily -> lowest TF is covered by stacking instances).
* Swing / pivot structure with an ATR-scaled reversal threshold.
* Regime classification: TREND_UP / TREND_DOWN / RANGE / EXPANSION.
* Phase anticipation: COIL (contracting range, pending breakout), TREND
  (impulse), EXHAUSTION (extended move, decaying momentum);
  `expected_remaining_candles` estimates how long the current move has left.
* Integrity primitive: `integrity=False` + `break_level` exactly when price
  violates the structure that defined the active thesis — the machine
  equivalent of "exit immediately when I sense something is wrong."

This module is a *context provider only*. It computes features and labels.
It never proposes, sizes, or executes (I5: only the Iron Constitution may
adjudicate, and only the Cortex strategy layer - never this file - decides
what to trade). All thresholds live in `MarketContextParams` (data-driven),
so the Evolution Sub-Agent can tune the machinery without touching code.
"""

from __future__ import annotations

import math
import random
import statistics
import time
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class Candle:
    """One OHLCV candle. All prices finite and > 0 by construction."""

    open: float
    high: float
    low: float
    close: float
    t_open: float
    t_close: float
    volume: float = 0.0


@dataclass(frozen=True)
class Swing:
    """A confirmed pivot. kind is 'High' or 'Low'."""

    kind: str
    price: float
    candle_index: int


class MarketContextParams(BaseModel):
    """Data-driven machinery tuning. Modify here or via the schedule, never by
    replacing the computation underneath."""

    timeframe_s: float = Field(default=300.0, gt=0.0, description="Candle aggregation window in seconds.")
    atr_period: int = Field(default=14, ge=2, description="ATR lookback in candles.")
    swing_atr_multiple: float = Field(default=1.5, gt=0.0, description="Min reversal to confirm a swing, in ATR units.")
    range_height_atr: float = Field(default=1.2, gt=0.0, description="Range/coil band, in ATR units.")
    extension_atr_multiple: float = Field(default=3.0, gt=0.0, description="Move length that counts as EXHAUSTION, in ATR.")
    min_swings: int = Field(default=3, ge=2, description="Swings required before regime classification begins.")
    lookback_swings: int = Field(default=8, ge=2, description="Swings used for polarity scoring.")
    max_candles: int = Field(default=400, ge=30, description="Bounded candle history (constant-memory).")
    impulse_atr_multiple: float = Field(default=2.5, gt=0.0, description="Single-bar displacement that counts as EXPANSION, in ATR units.")


class MarketContext(BaseModel):
    """Snapshot of structure at the last fully-closed candle."""

    asset_id: str
    timeframe_s: float
    closed_candles: int = Field(ge=0)
    atr: float = 0.0
    regime: str = "SEEDING"
    phase: str = "SEEDING"
    bias: str = "Flat"
    momentum: float = 0.0
    swing_high: float | None = None
    swing_low: float | None = None
    coil_bounds: tuple[float, float] | None = None
    structure_age_candles: int = 0
    expected_remaining_candles: float | None = None
    expansion_potential_candles: float | None = None
    integrity: bool = True
    break_level: float | None = None


@dataclass
class CandleAggregator:
    """Folds a tick stream into closed OHLCV candles on a fixed clock."""

    timeframe_s: float
    _bucket_open: float | None = field(default=None, init=False)
    _o: float = field(default=0.0, init=False)
    _h: float = field(default=0.0, init=False)
    _l: float = field(default=0.0, init=False)
    _c: float = field(default=0.0, init=False)
    _v: float = field(default=0.0, init=False)

    def _bucket(self, ts: float) -> float:
        return math.floor(ts / self.timeframe_s) * self.timeframe_s

    def feed(self, price: float, ts: float) -> Candle | None:
        """Feed one price tick; returns the just-closed candle (or None)."""
        price = float(price)
        if not math.isfinite(price) or price <= 0.0:
            return None
        bucket = self._bucket(ts)
        closed: Candle | None = None
        if self._bucket_open is None:
            self._bucket_open = bucket
            self._o = self._h = self._l = self._c = price
            self._v = 0.0
        elif bucket != self._bucket_open:
            closed = Candle(
                open=self._o,
                high=self._h,
                low=self._l,
                close=self._c,
                t_open=self._bucket_open,
                t_close=bucket,
                volume=self._v,
            )
            self._bucket_open = bucket
            self._o = self._h = self._l = self._c = price
            self._v = 0.0
        self._h = max(self._h, price)
        self._l = min(self._l, price)
        self._c = price
        self._v += 1.0
        return closed

    def forming(self, ts: float) -> Candle | None:
        """Snapshot of the currently-forming (unclosed) candle, None if idle.

        Enables real-time, intra-candle event analysis for split-second strikes.
        Does not mutate state; t_close is the observation time.
        """
        bucket = self._bucket(ts)
        if self._bucket_open is None or bucket != self._bucket_open:
            return None
        return Candle(
            open=self._o,
            high=self._h,
            low=self._l,
            close=self._c,
            t_open=self._bucket_open,
            t_close=ts,
            volume=self._v,
        )


def atr_of(candles: list[Candle], period: int) -> float:
    """Wilder-smoothed Average True Range over the trailing window.

    GUI-safe: zero/short series and NaN inputs yield 0.0, never NaN/inf.
    """
    if not candles:
        return 0.0
    window = candles[-(period + 1):]
    if len(window) <= 1:
        return 0.0
    trs: list[float] = []
    prev_close = window[0].close
    for c in window[1:]:
        tr = max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close))
        if math.isfinite(tr):
            trs.append(tr)
        prev_close = c.close
    if not trs:
        return 0.0
    return sum(trs) / len(trs)


def zigzag_swings(candles: list[Candle], atr: float, mult: float) -> list[Swing]:
    """Confirm pivots when price reverses by `mult * ATR` from an extreme."""
    if not candles:
        return []
    min_move = max(atr * mult, 1e-12)
    swings: list[Swing] = []
    direction = 0
    pivot_high = pivot_low = None
    for i, c in enumerate(candles):
        if direction >= 0:
            if pivot_high is None or c.high > pivot_high:
                pivot_high = c.high
            if pivot_high - c.low >= min_move:
                swings.append(Swing("High", pivot_high, i))
                direction = -1
                pivot_low = c.low
                pivot_high = None
        if direction <= 0:
            if pivot_low is None or c.low < pivot_low:
                pivot_low = c.low
            if c.high - pivot_low >= min_move:
                swings.append(Swing("Low", pivot_low, i))
                direction = 1
                pivot_high = c.high
                pivot_low = None
    return swings


def _polarity(swings: list[Swing]) -> int:
    """Net higher-high/higher-low (+1) minus lower-high/lower-low (-1)."""
    vals = swings[-8:]
    highs = [s.price for s in vals if s.kind == "High"]
    lows = [s.price for s in vals if s.kind == "Low"]
    score = 0
    if len(highs) >= 2 and highs[-1] > highs[-2]:
        score += 1
    elif len(highs) >= 2 and highs[-1] < highs[-2]:
        score -= 1
    if len(lows) >= 2 and lows[-1] > lows[-2]:
        score += 1
    elif len(lows) >= 2 and lows[-1] < lows[-2]:
        score -= 1
    return score


def _cycle_median(swings: list[Swing], recent: int = 6) -> float | None:
    idxs = [s.candle_index for s in swings[-recent:]]
    if len(idxs) < 3:
        return None
    deltas = [b - a for a, b in pairwise(idxs)]
    return float(statistics.median(deltas))


def build_context(candles: list[Candle], params: MarketContextParams, asset_id: str) -> MarketContext:
    """Compute the structure snapshot for the candle history provided."""
    ctx = MarketContext(asset_id=asset_id, timeframe_s=params.timeframe_s, closed_candles=len(candles))
    if len(candles) < params.atr_period + 2:
        return ctx

    atr = atr_of(candles, params.atr_period)
    ctx.atr = atr
    if atr <= 0.0:
        return ctx

    # Impulse/breakout expansion: a single-bar displacement many ATR wide is the
    # market telling us the old structure just broke (or is beginning to extend).
    last = candles[-1].close
    if len(candles) >= 2:
        move = last - candles[-2].close
        if abs(move) >= params.impulse_atr_multiple * atr:
            ctx.regime = "EXPANSION"
            ctx.phase = "EXPANSION"
            ctx.bias = "Long" if move > 0 else "Short"
            ctx.momentum = move / (atr * params.atr_period)
            ctx.integrity = False
            ctx.break_level = candles[-2].close
            return ctx

    swings = zigzag_swings(candles, atr, params.swing_atr_multiple)
    if len(swings) < params.min_swings:
        return ctx

    last = candles[-1].close
    highs = [s.price for s in swings if s.kind == "High"]
    lows = [s.price for s in swings if s.kind == "Low"]
    ctx.swing_high = max(highs[-params.lookback_swings // 2:], default=None)
    ctx.swing_low = min(lows[-params.lookback_swings // 2:], default=None)

    bias = "Long" if swings[-1].kind == "Low" else "Short"
    ctx.bias = bias

    # Range/coil band over recent swings
    recent_high = max(highs[-params.lookback_swings // 2:], default=None)
    recent_low = min(lows[-params.lookback_swings // 2:], default=None)
    if recent_high is not None and recent_low is not None and (recent_high - recent_low) < params.range_height_atr * atr:
        ctx.coil_bounds = (recent_low, recent_high)

    score = _polarity(swings)
    trend_polarized = abs(score) >= 1 and len(swings) >= params.min_swings

    # Momentum: closes travelled over ATR_Period candles, in ATR/candle units.
    prev_close = candles[-params.atr_period].close
    ctx.momentum = (last - prev_close) / (atr * params.atr_period)

    if ctx.coil_bounds is not None:
        lo, hi = ctx.coil_bounds
        if last > hi or last < lo:
            ctx.regime = "EXPANSION"
            ctx.phase = "EXPANSION"
            ctx.bias = "Long" if last > hi else "Short"
            ctx.integrity = False
            ctx.break_level = hi if last > hi else lo
            ctx.expansion_potential_candles = None
            ctx.expected_remaining_candles = _cycle_median(swings) or None
            return ctx

    if trend_polarized:
        if score > 0:
            ctx.regime = "TREND_UP"
            ctx.bias = "Long"
        else:
            ctx.regime = "TREND_DOWN"
            ctx.bias = "Short"
        # structure age & duration anticipation
        age = len(candles) - 1 - swings[-1].candle_index
        ctx.structure_age_candles = max(age, 0)
        cycle = _cycle_median(swings)
        if cycle is not None:
            ctx.expected_remaining_candles = max(0.0, cycle - ctx.structure_age_candles)
        # exhaustion: overextended leg + momentum decelerating
        ref = ctx.swing_low if score > 0 else ctx.swing_high
        leg = abs(last - ref) if ref is not None else 0.0
        if leg >= params.extension_atr_multiple * atr and abs(ctx.momentum) < 0.25:
            ctx.phase = "EXHAUSTION"
        else:
            ctx.phase = "TREND"
        # integrity: thesis holds unless the defining structure breaks
        break_level = ctx.swing_low if score > 0 else ctx.swing_high
        if break_level is not None and (last < break_level if score > 0 else last > break_level):
            ctx.integrity = False
            ctx.break_level = break_level
        return ctx

    # Ambiguous polarity with a coil -> pristine range
    if ctx.coil_bounds is not None:
        ctx.regime = "RANGE"
        ctx.phase = "COIL"
        lo, hi = ctx.coil_bounds
        dist = min(last - lo, hi - last)
        ctx.expansion_potential_candles = max(dist / atr, 0.0) if atr > 0 else None
        ctx.expected_remaining_candles = None
        ctx.integrity = True
        ctx.break_level = None
        return ctx

    ctx.regime = "SEEDING"
    ctx.phase = "SEEDING"
    return ctx


class MarketContextEngine:
    """Incremental engine: ticks in, structure snapshots out (context only)."""

    def __init__(self, asset_id: str = "SYNTH", params: MarketContextParams | None = None):
        self.asset_id = asset_id
        self.params = params or MarketContextParams()
        self._aggregator = CandleAggregator(self.params.timeframe_s)
        self._candles: list[Candle] = []
        self._context = MarketContext(asset_id=asset_id, timeframe_s=self.params.timeframe_s, closed_candles=0)

    def ingest(self, tick: dict[str, Any]) -> dict[str, Any] | None:
        """Consume one tick. Returns the latest structure snapshot dict when a
        candle closes, else None."""
        price = float(tick.get("price", 0.0) or 0.0)
        ts = float(tick.get("timestamp", time.time()))
        closed = self._aggregator.feed(price, ts)
        if closed is None:
            return None
        self._candles.append(closed)
        if len(self._candles) > self.params.max_candles:
            self._candles = self._candles[-self.params.max_candles:]
        self._context = build_context(self._candles, self.params, self.asset_id)
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        """JSON-safe structure snapshot for the S2 strategy layer and logs."""
        ctx = self._context
        bounds = list(ctx.coil_bounds) if ctx.coil_bounds else None
        return {
            "asset_id": ctx.asset_id,
            "timeframe_s": ctx.timeframe_s,
            "closed_candles": ctx.closed_candles,
            "atr": round(ctx.atr, 8),
            "regime": ctx.regime,
            "phase": ctx.phase,
            "bias": ctx.bias,
            "momentum": round(ctx.momentum, 6),
            "swing_high": ctx.swing_high,
            "swing_low": ctx.swing_low,
            "coil_bounds": bounds,
            "structure_age_candles": ctx.structure_age_candles,
            "expected_remaining_candles": (
                round(ctx.expected_remaining_candles, 2) if ctx.expected_remaining_candles is not None else None
            ),
            "expansion_potential_candles": (
                round(ctx.expansion_potential_candles, 2) if ctx.expansion_potential_candles is not None else None
            ),
            "integrity": ctx.integrity,
            "break_level": ctx.break_level,
        }


# ---------------------------------------------------------------------------
# Self-test / demo: deterministic synthetic market walk that visits every
# structural event (trend -> range/coil -> expansion -> exhaustion tail).
# This is G7-style demonstration machinery, not alpha.
# ---------------------------------------------------------------------------
def _synthetic_candles(total: int = 220) -> list[Candle]:
    rng = random.Random(42)
    price = 100.0
    candles: list[Candle] = []
    regime_script: list[tuple[int, float]] = [  # (candles, drift)
        (70, 0.06),   # TREND_UP impulse
        (50, -0.004), # range / coil
        (2, -0.08),   # EXPANSION (impulse breakdown)
        (40, -0.012), # trend down, decelerating -> EXHAUSTION
        (45, -0.004), # range again
        (15, 0.005),  # coil again
    ]
    t = 1_700_000_000.0
    for count, drift in regime_script:
        for _ in range(count):
            o = price
            gap = rng.uniform(-0.15, 0.15)
            c = price + drift * price + gap
            c = max(c, 0.5)
            h = max(o, c) * (1 + rng.uniform(0.0005, 0.004))
            l = min(o, c) * (1 - rng.uniform(0.0005, 0.004))
            candles.append(Candle(o, h, l, c, t, t + 1.0))
            price = c
            t += 1.0
    return candles


def _demo() -> int:
    params = MarketContextParams()
    candles = _synthetic_candles()
    print(f"MarketContextEngine demo — {len(candles)} synthetic candles "
          f"({int(params.timeframe_s)}s TF), structure only (no trading decisions).")
    print(f"{'bar':>5} | {'regime':<10} | {'phase':<11} | {'bias':<5} | {'mom':>6} | "
          f"{'remain':>6} | {'expand':>6} | integrity | break_level")
    last: tuple[str, str, str] = ("", "", "")
    for i in range(1, len(candles) + 1):
        ctx = build_context(candles[:i], params, "SYNTH")
        key = (ctx.regime, ctx.phase, ctx.bias)
        if key == last:
            continue
        last = key
        remain = f"{ctx.expected_remaining_candles:.1f}" if ctx.expected_remaining_candles is not None else "-"
        expand = f"{ctx.expansion_potential_candles:.1f}" if ctx.expansion_potential_candles is not None else "-"
        print(f"{i:>5} | {ctx.regime:<10} | {ctx.phase:<11} | {ctx.bias:<5} | {ctx.momentum:>6.3f} | "
              f"{remain:>6} | {expand:>6} | {ctx.integrity!s:<9} | {ctx.break_level}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_demo())