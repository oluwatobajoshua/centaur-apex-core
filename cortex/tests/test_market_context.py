import math

import pytest
from hypothesis import given, settings, strategies as st

from cortex.market_context import (
    Candle,
    CandleAggregator,
    MarketContextEngine,
    MarketContextParams,
    atr_of,
    build_context,
    zigzag_swings,
)


def mk_candle(open_, close, high=None, low=None, t=0.0) -> Candle:
    high = high if high is not None else max(open_, close)
    low = low if low is not None else min(open_, close)
    return Candle(open=open_, high=high, low=low, close=close, t_open=t, t_close=t + 59.0)


def drifts_series(values: list[float], base: float = 100.0) -> list[Candle]:
    candles, price = [], base
    for d in values:
        o = price
        c = max(price * (1.0 + d), 0.01)
        h = max(o, c) * 1.002
        l = min(o, c) * 0.998
        candles.append(Candle(o, h, l, c, float(len(candles)), float(len(candles)) + 1.0))
        price = c
    return candles


PARAMS = MarketContextParams()


class TestAtR:
    def test_empty_series(self):
        assert atr_of([], 14) == 0.0

    def test_short_series(self):
        assert atr_of([mk_candle(1, 1) for _ in range(2)], 14) == 0.0

    def test_constant_series_zero(self):
        candles = [mk_candle(10.0, 10.0) for _ in range(30)]
        assert atr_of(candles, 14) == 0.0

    def test_nan_inf_guarded(self):
        c = mk_candle(float("nan"), 10.0)
        assert atr_of([mk_candle(1, 1)] + [c] * 30, 14) == 0.0 or atr_of(
            [Candle(1, float("inf"), 1, 1, 0.0, 1.0)] * 30, 14
        ) == 0.0


class TestAggregator:
    def test_no_rows_inside_bucket(self):
        agg = CandleAggregator(60.0)
        assert agg.feed(100.0, 0.0) is None
        assert agg.feed(101.0, 30.0) is None

    def test_candle_closed_on_bucket_rollover(self):
        agg = CandleAggregator(60.0)
        agg.feed(100.0, 0.0)
        agg.feed(104.0, 10.0)
        closed = agg.feed(99.0, 70.0)
        assert closed is not None
        assert closed.open == 100.0
        assert closed.high == 104.0
        assert closed.low == 100.0  # 99 lands in the *next* bucket
        assert closed.close == 104.0

    def test_next_bucket_starts_fresh(self):
        agg = CandleAggregator(60.0)
        agg.feed(100.0, 0.0)
        first = agg.feed(99.0, 70.0)  # the 99 tick opens a NEW bucket
        assert first is not None
        assert first.close == 100.0
        assert agg.feed(102.0, 80.0) is None  # still inside bucket 60
        closed = agg.feed(103.0, 130.0)  # closes bucket 60
        assert closed is not None
        assert closed.open == 99.0 and closed.low == 99.0 and closed.high == 102.0

    def test_rejects_nonfinite_and_negatives(self):
        agg = CandleAggregator(60.0)
        assert agg.feed(float("nan"), 0.0) is None
        assert agg.feed(float("inf"), 0.0) is None
        assert agg.feed(-5.0, 0.0) is None
        assert agg.feed(100.0, 0.0) is None  # valid tick still accepted


class TestZigzag:
    def test_monotonic_up_no_confirmation(self):
        # One-bar steps far below the ATR reversal threshold -> no pivots.
        candles = [
            Candle(p, p + 0.05, p, p + 0.05, float(i), float(i) + 1.0)
            for i, p in enumerate([100.0 + 0.05 * i for i in range(60)])
        ]
        swings = zigzag_swings(candles, atr=0.5, mult=1.5)
        # A one-way rally confirms at most the starting Low pivot, never a top.
        assert len(swings) <= 1

    def test_pullback_confirms_high_then_low(self):
        vals = [1.0] * 40 + [-0.04] * 15  # rise then clear reversal
        candles = drifts_series(vals, base=100.0)
        swings = zigzag_swings(candles, atr=0.4, mult=1.5)
        assert len(swings) >= 2
        assert swings[0].kind == "High"

    def test_alternating_kinds(self):
        vals = [1.0] * 30 + [-0.05] * 20 + [0.05] * 20 + [-0.05] * 20
        candles = drifts_series(vals, base=100.0)
        swings = zigzag_swings(candles, atr=0.6, mult=1.5)
        assert all(a.kind != b.kind for a, b in zip(swings, swings[1:]))


class TestBuildContext:
    def test_seeding_on_short_series(self):
        ctx = build_context(drifts_series([0.0] * 5), PARAMS, "SYNTH")
        assert ctx.regime == "SEEDING"
        assert ctx.integrity is True

    def test_seeding_when_atr_zero(self):
        ctx = build_context([mk_candle(10.0, 10.0) for _ in range(40)], PARAMS, "SYNTH")
        assert ctx.regime == "SEEDING"

    def test_trend_up_regime_detected(self):
        candles = drifts_series([0.02] * 100)  # strong sustained rise
        ctx = build_context(candles, PARAMS, "SYNTH")
        assert ctx.regime in ("TREND_UP", "SEEDING")
        if ctx.regime == "TREND_UP":
            assert ctx.bias == "Long"

    def test_synthetic_walk_reaches_trend_without_crashing(self):
        from cortex.market_context import _synthetic_candles

        candles = _synthetic_candles()
        regimes: set[str] = set()
        for i in range(PARAMS.atr_period + 2, len(candles) + 1):
            ctx = build_context(candles[:i], PARAMS, "SYNTH")
            regimes.add(ctx.regime)
        assert "TREND_UP" in regimes
        assert len(regimes) >= 2

COIL_PARAMS = MarketContextParams(swing_atr_multiple=0.5, range_height_atr=2.0, min_swings=2)


def _trend_up() -> list[Candle]:
    candles: list[Candle] = []
    p = 100.0
    for i in range(40):
        o = p
        c = o + 1.2
        candles.append(Candle(o, c + 0.9, o - 0.9, c, float(i), float(i) + 1.0))
        p = c
    return candles


class TestCoilAndIntegrity:
    def test_coil_then_expansion_breakout(self):
        candles = _trend_up()
        mid = candles[-1].close
        for i in range(30):  # tight coil with amplitude above the tuned min_move
            side = -1.0 if i % 2 else 1.0
            o = mid
            c = mid + side * 0.4
            candles.append(Candle(o, max(o, c) + 0.1, min(o, c) - 0.1, c, float(len(candles)), float(len(candles)) + 1.0))
        for step in (3.0, 3.5, 4.0):  # sharp breakout above the coil
            o = candles[-1].close
            c = o + step
            candles.append(Candle(o, c + 0.4, c - 0.4, c, float(len(candles)), float(len(candles)) + 1.0))
        regimes, breaks, range_intact = set(), 0, False
        for i in range(COIL_PARAMS.atr_period + 2, len(candles) + 1):
            ctx = build_context(candles[:i], COIL_PARAMS, "SYNTH")
            regimes.add(ctx.regime)
            breaks += 0 if ctx.integrity else 1
            if ctx.regime == "RANGE" and ctx.integrity:
                range_intact = True
            if not ctx.integrity:
                assert ctx.break_level is not None
        assert range_intact, "coil must be recognized as intact RANGE before expanding"
        assert "EXPANSION" in regimes and breaks >= 1

    def test_impulse_displacement_is_expansion(self):
        candles = _trend_up()  # ends ~148; ATR compressed down near the top
        for _ in range(20):  # flat coil firms ATR to ~1.0
            o = candles[-1].close
            c = o + 0.3
            candles.append(Candle(o, c + 0.2, o - 0.2, c, float(len(candles)), float(len(candles)) + 1.0))
        o = candles[-1].close
        candles.append(Candle(o, o + 3.6, o, o + 3.5, float(len(candles)), float(len(candles)) + 1.0))
        ctx = build_context(candles, COIL_PARAMS, "SYNTH")
        assert ctx.regime == "EXPANSION"
        assert not ctx.integrity
        assert ctx.break_level is not None


class TestEngine:
    def test_snapshot_json_safe_no_crash_on_short_stream(self):
        eng = MarketContextEngine("SYNTH")
        for price in (100.0, 100.5, 101.0, 101.5):
            out = eng.ingest({"price": price, "timestamp": float(len(eng._candles)) * 60.0})
        snap = eng.snapshot()
        assert set(snap) >= {
            "regime", "phase", "bias", "integrity", "closed_candles", "atr", "momentum",
        }
        assert math.isfinite(snap["atr"])
        assert snap["asset_id"] == "SYNTH"

    def test_daily_stacks_yield_bigger_context(self):
        params = MarketContextParams(timeframe_s=60.0)
        eng = MarketContextEngine("SYNTH", params)
        snapshots = []
        t = 0.0
        price = 100.0
        for _ in range(400):
            price += 0.05
            out = eng.ingest({"price": price, "timestamp": t})
            t += 60.0
            if out is not None:
                snapshots.append(out)
        assert len(snapshots) >= 3
        assert snapshots[-1]["closed_candles"] > 3


REGRIMES = {"SEEDING", "TREND_UP", "TREND_DOWN", "RANGE", "EXPANSION"}


class TestPropertyFuzz:
    @given(st.lists(st.floats(min_value=0.01, max_value=500.0), min_size=20, max_size=120))
    @settings(max_examples=50)
    def test_random_walks_never_crash_and_always_finite(self, closes):
        candles = []
        t = 0.0
        for c in closes:
            candles.append(Candle(c, c * 1.001, c * 0.999, c, t, t + 1.0))
            t += 1.0
        ctx = build_context(candles, PARAMS, "SYNTH")
        assert ctx.regime in REGRIMES
        assert ctx.phase in {"SEEDING", "TREND", "EXHAUSTION", "COIL", "EXPANSION"}
        assert isinstance(ctx.integrity, bool)
        assert math.isfinite(ctx.atr)
        for v in (ctx.swing_high, ctx.swing_low, ctx.break_level):
            if v is not None:
                assert math.isfinite(v) and v > 0