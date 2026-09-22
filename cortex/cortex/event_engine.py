"""Event engine (G5 machinery): recognises durable market events and converts
them into structured, context-conditional observations.

Every event carries its own `thesis` and `invalidation` (from the data-driven
catalog in ``cortex/schemas/market_events.json``). This module only *interprets*
what the market is doing; it never decides to trade. Sizing, entry and exit
belong to system-written alpha (S2) gated by the Constitution (I5).

Pattern taxonomy is DATA: ``SEED_PATTERNS`` below is a plain declarative list,
and the matching engine interprets any spec without further code. The system's
evolution agent extends the catalog over the century - this file does not.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .market_context import Candle

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "market_events.json"


def load_catalog() -> dict[str, Any]:
    """Load the data-driven event taxonomy (families, events, principles)."""
    with SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# Bar anatomy: numeric features any pattern spec can reference.               #
# --------------------------------------------------------------------------- #

@dataclass
class BarFeatures:
    candle: Candle
    atr: float
    body: float = 0.0
    body_abs: float = 0.0
    rng: float = 0.0
    body_ratio: float = 0.0
    upper_wick: float = 0.0
    lower_wick: float = 0.0
    uw_ratio: float = 0.0
    lw_ratio: float = 0.0
    direction: int = 0
    atr_scale: float = 0.0

    def __post_init__(self) -> None:
        c = self.candle
        self.body = c.close - c.open
        self.body_abs = abs(self.body)
        hi, lo = max(c.open, c.close), min(c.open, c.close)
        self.rng = max(c.high - c.low, 1e-12)
        self.body_ratio = min(self.body_abs / self.rng, 1.0)
        self.upper_wick = max(c.high - hi, 0.0)
        self.lower_wick = max(lo - c.low, 0.0)
        self.uw_ratio = self.upper_wick / self.rng
        self.lw_ratio = self.lower_wick / self.rng
        self.direction = 1 if self.body > 0 else (-1 if self.body < 0 else 0)
        self.atr_scale = self.rng / self.atr if self.atr > 0 else 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "open": self.candle.open,
            "high": self.candle.high,
            "low": self.candle.low,
            "close": self.candle.close,
            "body": self.body,
            "body_abs": self.body_abs,
            "rng": self.rng,
            "body_ratio": self.body_ratio,
            "upper_wick": self.upper_wick,
            "lower_wick": self.lower_wick,
            "uw_ratio": self.uw_ratio,
            "lw_ratio": self.lw_ratio,
            "direction": float(self.direction),
            "atr_scale": self.atr_scale,
        }


def build_bar_features(candles: list[Candle], atr: float) -> list[BarFeatures]:
    return [BarFeatures(c, atr) for c in candles]


# --------------------------------------------------------------------------- #
# Schema-driven pattern interpreter.                                           #
# --------------------------------------------------------------------------- #

class PatternSpec(BaseModel):
    id: str
    direction: str = Field(default="Neutral", pattern="^(Bull|Bear|Neutral)$")
    candles: int = Field(default=1, ge=1, le=4, description="Bars the spec evaluates over.")
    conditions: list[dict[str, Any]] = Field(
        default_factory=list,
        description='Each condition: {"bar": -k, "feature": <name>, "op": gt/gte/lt/lte/eq/neq, "value": <n>}.',
    )


SEED_PATTERNS: list[dict[str, Any]] = [
    {"id": "doji", "direction": "Neutral", "candles": 1,
     "conditions": [{"bar": -1, "feature": "body_ratio", "op": "lt", "value": 0.1}]},
    {"id": "spinning_top", "direction": "Neutral", "candles": 1,
     "conditions": [{"bar": -1, "feature": "body_ratio", "op": "lt", "value": 0.3},
                    {"bar": -1, "feature": "uw_ratio", "op": "gt", "value": 0.2},
                    {"bar": -1, "feature": "lw_ratio", "op": "gt", "value": 0.2}]},
    {"id": "hammer", "direction": "Bull", "candles": 1,
     "conditions": [{"bar": -1, "feature": "body_ratio", "op": "lt", "value": 0.4},
                    {"bar": -1, "feature": "lw_ratio", "op": "gt", "value": 0.5},
                    {"bar": -1, "feature": "uw_ratio", "op": "lt", "value": 0.15}]},
    {"id": "inverted_hammer", "direction": "Bull", "candles": 1,
     "conditions": [{"bar": -1, "feature": "body_ratio", "op": "lt", "value": 0.4},
                    {"bar": -1, "feature": "uw_ratio", "op": "gt", "value": 0.5},
                    {"bar": -1, "feature": "lw_ratio", "op": "lt", "value": 0.15}]},
    {"id": "shooting_star", "direction": "Bear", "candles": 1,
     "conditions": [{"bar": -1, "feature": "body_ratio", "op": "lt", "value": 0.4},
                    {"bar": -1, "feature": "uw_ratio", "op": "gt", "value": 0.5},
                    {"bar": -1, "feature": "lw_ratio", "op": "lt", "value": 0.15}]},
    {"id": "hanging_man", "direction": "Bear", "candles": 1,
     "conditions": [{"bar": -1, "feature": "body_ratio", "op": "lt", "value": 0.4},
                    {"bar": -1, "feature": "lw_ratio", "op": "gt", "value": 0.5},
                    {"bar": -1, "feature": "uw_ratio", "op": "lt", "value": 0.15}]},
    {"id": "marubozu_bull", "direction": "Bull", "candles": 1,
     "conditions": [{"bar": -1, "feature": "body_ratio", "op": "gt", "value": 0.9},
                    {"bar": -1, "feature": "uw_ratio", "op": "lt", "value": 0.03},
                    {"bar": -1, "feature": "lw_ratio", "op": "lt", "value": 0.03},
                    {"bar": -1, "feature": "direction", "op": "eq", "value": 1}]},
    {"id": "marubozu_bear", "direction": "Bear", "candles": 1,
     "conditions": [{"bar": -1, "feature": "body_ratio", "op": "gt", "value": 0.9},
                    {"bar": -1, "feature": "uw_ratio", "op": "lt", "value": 0.03},
                    {"bar": -1, "feature": "lw_ratio", "op": "lt", "value": 0.03},
                    {"bar": -1, "feature": "direction", "op": "eq", "value": -1}]},
    {"id": "bull_engulfing", "direction": "Bull", "candles": 2,
     "conditions": [{"bar": -2, "feature": "direction", "op": "eq", "value": -1},
                    {"bar": -1, "feature": "direction", "op": "eq", "value": 1}]},
    {"id": "bear_engulfing", "direction": "Bear", "candles": 2,
     "conditions": [{"bar": -2, "feature": "direction", "op": "eq", "value": 1},
                    {"bar": -1, "feature": "direction", "op": "eq", "value": -1}]},
]


def _cmp(left: float, right: float, op: str) -> bool:
    if op == "gt":
        return left > right
    if op == "gte":
        return left >= right
    if op == "lt":
        return left < right
    if op == "lte":
        return left <= right
    if op == "eq":
        return abs(left - right) < 1e-9
    if op == "neq":
        return abs(left - right) >= 1e-9
    raise ValueError(f"unknown op: {op}")


class PatternMatcher:
    def __init__(self, specs: list[PatternSpec] | None = None) -> None:
        self.specs = specs or [PatternSpec.model_validate(s) for s in SEED_PATTERNS]

    def match(self, bars: list[BarFeatures]) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        for spec in self.specs:
            if len(bars) < spec.candles:
                continue
            window = bars[-spec.candles:]
            ok = True
            for cond in spec.conditions:
                fb = window[cond["bar"]].as_dict()
                if not _cmp(fb[cond["feature"]], float(cond["value"]), cond["op"]):
                    ok = False
                    break
            if ok:
                hits.append({"id": spec.id, "direction": spec.direction, "candles": spec.candles})
        return hits


# --------------------------------------------------------------------------- #
# Durable-event detectors (structure / volatility / exhaustion).              #
# --------------------------------------------------------------------------- #

@dataclass
class SweepEvent:
    side: str  # "BSL" swept (high side) or "SSL" swept (low side)
    level: float
    wick_extreme: float
    pierced_atr: float
    reclaimed: bool
    close: float


class SweepDetector:
    """Liquidity sweep / stop hunt: a bar wicks a fraction of ATR beyond a
    stop-cluster level, then closes back inside (the reclaim)."""

    def __init__(self, level_fraction: float = 0.3, reclaim_window: int = 3) -> None:
        self.level_fraction = level_fraction
        self.reclaim_window = reclaim_window

    def detect(self, bars: list[Candle], level: float, atr: float) -> SweepEvent | None:
        if len(bars) < 2 or atr <= 0:
            return None
        req = self.level_fraction * atr
        for b in reversed(bars[-self.reclaim_window:]):
            if b.low < level and (level - b.low) >= req and b.close > level:
                return SweepEvent("SSL", level, b.low, (level - b.low) / atr, True, b.close)
        last = bars[-1]
        if last.high > level and (last.high - level) >= req and last.close < level:
            return SweepEvent("BSL", level, last.high, (last.high - level) / atr, True, last.close)
        return None


@dataclass
class FakeoutEvent:
    side: str  # "Bull" break failed above / "Bear" break failed below
    level: float
    failure_extreme: float
    reclaimed: bool = True


class FakeoutDetector:
    """Classic failed break: price closes beyond a level, then closes back inside."""

    def __init__(self, check_back: int = 3) -> None:
        self.check_back = check_back

    def detect(self, bars: list[Candle], level: float) -> FakeoutEvent | None:
        if len(bars) < 2:
            return None
        for i in range(max(0, len(bars) - self.check_back), len(bars) - 1):
            if bars[i].close > level and bars[i + 1].close < level:
                return FakeoutEvent("Bull", level, bars[i].high)
            if bars[i].close < level and bars[i + 1].close > level:
                return FakeoutEvent("Bear", level, bars[i].low)
        return None


@dataclass
class SqueezeState:
    ratio: float  # short-window avg range / long-window avg range
    compressed: bool
    duration_bars: int


class SqueezeDetector:
    """Volatility compression: short-window average range well below the long
    window signals a coiled spring (expansion usually follows)."""

    def __init__(self, short: int = 10, long: int = 60, threshold: float = 0.7) -> None:
        self.short = short
        self.long = long
        self.threshold = threshold

    def detect(self, bars: list[Candle]) -> SqueezeState | None:
        if len(bars) < self.long:
            return None
        tail = bars[-self.long:]
        short_avg = sum(b.high - b.low for b in tail[-self.short:]) / self.short
        long_avg = sum(b.high - b.low for b in tail) / self.long
        ratio = short_avg / long_avg if long_avg > 0 else 1.0
        duration = 0
        for b in reversed(tail[:-1]):
            if (b.high - b.low) >= long_avg:
                break
            duration += 1
        return SqueezeState(ratio, ratio < self.threshold, duration)


@dataclass
class AccelReject:
    direction: str  # which direction was rejected
    accel_atr: float
    range_atr: float
    absorbed: float  # fraction of the impulse body reclaimed


def acceleration_rejection(
    bars: list[Candle],
    atr: float,
    accel_min: float = 1.0,
    range_min: float = 1.2,
    wick_factor: float = 0.5,
) -> AccelReject | None:
    """Speed-up-then-wick: an impulse bar is rejected by a wide-range wick bar
    closing back inside the impulse. The classic blowoff / failed acceleration."""
    if len(bars) < 2 or atr <= 0:
        return None
    first, last = bars[-2], bars[-1]
    impulse = first.close - first.open
    if abs(impulse) < accel_min * atr:
        return None
    rng = last.high - last.low
    if rng < range_min * atr:
        return None
    if impulse > 0:  # bullish impulse then rejection
        upper_wick = last.high - max(last.open, last.close)
        if last.close <= first.close and last.close >= first.open and upper_wick >= wick_factor * rng:
            return AccelReject("Bull", abs(impulse) / atr, rng / atr, (first.close - last.close) / abs(impulse))
    else:
        lower_wick = min(last.open, last.close) - last.low
        if last.close >= first.close and last.close <= first.open and lower_wick >= wick_factor * rng:
            return AccelReject("Bear", abs(impulse) / atr, rng / atr, (last.close - first.close) / abs(impulse))
    return None


@dataclass
class Divergence:
    kind: str  # "regular" | "hidden"
    side: str  # "Bull" | "Bear"
    strength: float


def _pivots(vals: list[float], window: int, is_high: bool) -> list[int]:
    out: list[int] = []
    for i in range(window, len(vals) - window):
        lo = i - window
        hi = i + window + 1
        v = vals[i]
        left = max(vals[lo:i])
        right = max(vals[i + 1:hi])
        if is_high and v > left and v > right:
            out.append(i)
        elif not is_high and v < min(vals[lo:i]) and v < min(vals[i + 1:hi]):
            out.append(i)
    return out


class DivergenceDetector:
    """Price vs momentum-swing divergence. A filter/context feature only - never
    a trade by itself (most standalone candlestick/divergence edges fade)."""

    def __init__(self, pivot_window: int = 3, roc_window: int = 5) -> None:
        self.pivot_window = pivot_window
        self.roc_window = roc_window

    def detect(self, closes: list[float]) -> list[Divergence]:
        if len(closes) < self.pivot_window * 2 + self.roc_window + 2:
            return []
        osc = [0.0] * len(closes)
        for i in range(self.roc_window, len(closes)):
            osc[i] = closes[i] - closes[i - self.roc_window]
        out: list[Divergence] = []
        price_highs = _pivots(closes, self.pivot_window, True)
        price_lows = _pivots(closes, self.pivot_window, False)
        for pivots, side in ((price_highs, "Bear"), (price_lows, "Bull")):
            if len(pivots) < 2:
                continue
            p1, p2 = pivots[-2], pivots[-1]
            price_dir = closes[p2] - closes[p1]
            osc_dir = osc[p2] - osc[p1]
            if side == "Bear" and price_dir > 0 and osc_dir < 0:
                out.append(Divergence("regular", "Bear", _strength(osc[p1], osc[p2])))
            elif side == "Bear" and price_dir < 0 and osc_dir > 0:
                out.append(Divergence("hidden", "Bull", _strength(osc[p1], osc[p2])))
            elif side == "Bull" and price_dir < 0 and osc_dir > 0:
                out.append(Divergence("regular", "Bull", _strength(osc[p1], osc[p2])))
            elif side == "Bull" and price_dir > 0 and osc_dir < 0:
                out.append(Divergence("hidden", "Bear", _strength(osc[p1], osc[p2])))
        return out


def _strength(a: float, b: float) -> float:
    scale = max(abs(a), abs(b), 1e-9)
    return min(abs(b - a) / scale, 2.0)


# --------------------------------------------------------------------------- #
# Composition: one report per update, thesis + invalidation from the catalog.  #
# --------------------------------------------------------------------------- #

@dataclass
class EventReport:
    asset_id: str
    closed_candles: int
    matched_patterns: list[dict[str, Any]]
    sweep: SweepEvent | None
    fakeout: FakeoutEvent | None
    squeeze: SqueezeState | None
    accel_reject: AccelReject | None
    divergences: list[Divergence]
    theses: list[dict[str, Any]]  # catalog knowledge attached to what fired

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "closed_candles": self.closed_candles,
            "patterns": self.matched_patterns,
            "sweep": None if self.sweep is None else vars(self.sweep),
            "fakeout": None if self.fakeout is None else vars(self.fakeout),
            "squeeze": None if self.squeeze is None else vars(self.squeeze),
            "accel_reject": None if self.accel_reject is None else vars(self.accel_reject),
            "divergences": [vars(d) for d in self.divergences],
            "theses": self.theses,
        }


class EventEngine:
    """Composes the detectors into one report. Pure observation machinery (I5)."""

    def __init__(
        self,
        asset_id: str,
        pattern_specs: list[PatternSpec] | None = None,
        matcher: PatternMatcher | None = None,
        sweep_detector: SweepDetector | None = None,
        fakeout_detector: FakeoutDetector | None = None,
        squeeze_detector: SqueezeDetector | None = None,
        divergence_detector: DivergenceDetector | None = None,
    ) -> None:
        self.asset_id = asset_id
        self.matcher = matcher or PatternMatcher(pattern_specs)
        self.sweep = sweep_detector or SweepDetector()
        self.fakeout = fakeout_detector or FakeoutDetector()
        self.squeeze = squeeze_detector or SqueezeDetector()
        self.divergence = divergence_detector or DivergenceDetector()
        self._catalog = load_catalog()
        self._by_id = {e["id"]: e for e in self._catalog["events"]}

    def analyze(
        self,
        candles: list[Candle],
        atr: float,
        liquidity_levels: list[float] | None = None,
    ) -> EventReport:
        bars = build_bar_features(candles, atr) if atr > 0 else []
        matched = self.matcher.match(bars) if bars else []
        actives: list[str] = [p["id"] for p in matched]

        sweep_event = fakeout_event = accel_reject = None
        squeeze_state = None
        divergences: list[Divergence] = []
        if len(candles) >= 2 and atr > 0:
            for level in (liquidity_levels or []):
                sweep_event = self.sweep.detect(candles, level, atr)
                if sweep_event:
                    actives.append("liquidity_sweep")
                    break
            for level in (liquidity_levels or []):
                fakeout_event = self.fakeout.detect(candles, level)
                if fakeout_event:
                    actives.append("fakeout_failed_break")
                    break
            accel_reject = acceleration_rejection(candles, atr)
            if accel_reject:
                actives.append("accel_to_wick_rejection")
            squeeze_state = self.squeeze.detect(candles)
            if squeeze_state and squeeze_state.compressed:
                actives.append("volatility_compression")
            divergences = self.divergence.detect([c.close for c in candles])
            for d in divergences:
                actives.append(f"divergence_{d.kind}")

        theses = [
            {"id": eid, **{k: self._by_id[eid][k] for k in ("mechanism", "thesis", "invalidation", "conversion", "family")}}
            for eid in dict.fromkeys(actives)
            if eid in self._by_id
        ]
        return EventReport(
            asset_id=self.asset_id,
            closed_candles=len(candles),
            matched_patterns=matched,
            sweep=sweep_event,
            fakeout=fakeout_event,
            squeeze=squeeze_state,
            accel_reject=accel_reject,
            divergences=divergences,
            theses=theses,
        )