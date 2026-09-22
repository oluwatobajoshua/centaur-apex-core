import math

from cortex.event_engine import (
    AccelReject,
    BarFeatures,
    DivergenceDetector,
    EventEngine,
    FakeoutDetector,
    PatternMatcher,
    SqueezeDetector,
    SweepDetector,
    acceleration_rejection,
    load_catalog,
)
from cortex.market_context import Candle


def mk(open_, high, low, close, t):
    return Candle(open_, high, low, close, float(t), float(t) + 1.0)


class TestBarAnatomy:
    def test_doji_shapes_attributes(self):
        bf = BarFeatures(mk(100.0, 101.0, 99.0, 100.03, 0), atr=1.0)
        d = bf.as_dict()
        assert d["body_ratio"] < 0.1
        assert abs(d["body"]) < 0.1
        assert d["atr_scale"] > 0

    def test_hammer_has_big_lower_wick(self):
        bf = BarFeatures(mk(100.0, 100.2, 98.0, 100.1, 0), atr=1.0)
        d = bf.as_dict()
        assert d["lw_ratio"] > 0.5
        assert d["uw_ratio"] < 0.15

    def test_shooting_star_has_big_upper_wick(self):
        bf = BarFeatures(mk(100.0, 102.0, 99.8, 100.05, 0), atr=1.0)
        d = bf.as_dict()
        assert d["uw_ratio"] > 0.5

    def test_marubozu_full_body(self):
        bf = BarFeatures(mk(100.0, 103.0, 100.1, 102.9, 0), atr=1.0)
        d = bf.as_dict()
        assert d["body_ratio"] > 0.9
        assert d["direction"] == 1


class TestPatternMatcher:
    def test_default_seeds_include_doji(self):
        matcher = PatternMatcher()
        bars = [BarFeatures(mk(100.0, 100.5, 99.5, 100.01, i), atr=1.0) for i in range(3)]
        hits = matcher.match(bars)
        assert any(h["id"] == "doji" for h in hits)

    def test_hammer_only_matches_with_shape(self):
        matcher = PatternMatcher()
        bars = [BarFeatures(mk(100.0, 100.2, 98.0, 100.1, 0), atr=1.0)]
        hits = matcher.match(bars)
        assert any(h["id"] == "hammer" for h in hits)
        bars2 = [BarFeatures(mk(100.0, 103.0, 100.1, 102.9, 0), atr=1.0)]
        assert not any(h["id"] == "hammer" for h in matcher.match(bars2))


class TestSweep:
    def test_sellside_sweep_reclaimed(self):
        det = SweepDetector(level_fraction=0.3)
        candles = [mk(100.0, 100.3, 99.7, 100.1, i) for i in range(10)]
        candles.append(mk(100.0, 100.2, 99.1, 100.3, 10))  # pierce 0.4 ATR below level
        evt = det.detect(candles, level=99.5, atr=1.0)
        assert evt is not None and evt.side == "SSL" and evt.reclaimed

    def test_no_sweep_when_no_pierce(self):
        det = SweepDetector(level_fraction=0.3)
        candles = [mk(100.0, 100.3, 99.7, 100.1, i) for i in range(10)]
        evt = det.detect(candles, level=99.8, atr=1.0)  # low never reaches 99.8-0.3
        assert evt is None

    def test_buyside_sweep(self):
        det = SweepDetector(level_fraction=0.3)
        candles = [mk(100.0, 100.3, 99.7, 100.1, i) for i in range(10)]
        candles.append(mk(100.0, 101.0, 99.9, 99.6, 10))
        evt = det.detect(candles, level=100.4, atr=1.0)
        assert evt is not None and evt.side == "BSL"


class TestFakeout:
    def test_bull_fakeout_closes_back_inside(self):
        det = FakeoutDetector()
        candles = [mk(101.8, 102.2, 101.6, 102.1, 0)]   # already inside/neutral above level
        candles.append(mk(102.0, 102.6, 101.9, 102.3, 1))  # closes beyond level
        candles.append(mk(102.2, 102.3, 100.4, 100.6, 2))  # closes back inside
        evt = det.detect(candles, level=101.5)
        assert evt is not None and evt.side == "Bull" and evt.reclaimed


class TestSqueeze:
    def test_compression_detected(self):
        det = SqueezeDetector(short=10, long=30, threshold=0.7)
        rng = 3.0
        candles = [mk(100.0, 100.0 + rng, 100.0, 100.0 + rng / 2, i) for i in range(20)]
        rng = 1.0
        candles += [mk(100.0, 100.0 + rng, 100.0, 100.0 + rng / 2, 20 + i) for i in range(20)]
        st = det.detect(candles)
        assert st is not None and st.compressed and st.ratio < 0.7

    def test_uniform_no_compression(self):
        det = SqueezeDetector(short=10, long=30, threshold=0.7)
        candles = [mk(100.0, 100.0 + 2.0, 100.0, 101.0, i) for i in range(30)]
        st = det.detect(candles)
        assert st is None or not st.compressed


class TestAccelReject:
    def test_bull_impulse_rejected_by_wick(self):
        candles = [mk(100.0, 99.9, 99.9, 99.9, 0) for _ in range(10)]
        candles.append(mk(100.0, 103.2, 99.9, 103.0, 10))  # fast up impulse
        candles.append(mk(103.0, 106.0, 101.0, 102.5, 11))  # wide wick closes back
        evt = acceleration_rejection(candles, atr=1.0)
        assert evt is not None and evt.direction == "Bull"
        assert isinstance(evt, AccelReject)

    def test_continuation_bar_is_not_rejection(self):
        candles = [mk(100.0, 99.9, 99.9, 99.9, 0) for _ in range(10)]
        candles.append(mk(100.0, 103.2, 99.9, 103.0, 10))
        candles.append(mk(103.0, 104.0, 102.5, 103.7, 11))  # strong follow-through
        assert acceleration_rejection(candles, atr=1.0) is None


class TestDivergence:
    def test_regular_bear_price_hh_osc_ll(self):
        closes = [100.0]
        for _ in range(12):
            closes.append(closes[-1] + 0.5)        # steep rise -> H1 = 106
        for _ in range(5):
            closes.append(closes[-1] - 1.0)        # pullback to 101
        for _ in range(25):
            closes.append(closes[-1] + 0.3)        # slow grind -> H2 = 108.5 (higher high)
        for _ in range(4):
            closes.append(108.0)                   # flat tail below H2 so it stays a pivot
        divs = DivergenceDetector().detect(closes)
        assert any(d.kind == "regular" and d.side == "Bear" for d in divs)

    def test_divergence_needs_enough_history(self):
        assert DivergenceDetector().detect([100.0] * 8) == []


class TestCatalogAndEngine:
    def test_catalog_is_data_driven(self):
        cat = load_catalog()
        ids = {e["id"] for e in cat["events"]}
        assert {"liquidity_sweep", "fakeout_failed_break", "accel_to_wick_rejection",
                "impulse_expansion", "surprise_drift", "coil_expansion"} <= ids
        assert len(cat["principles"]) >= 4

    def test_engine_attaches_thesis_knowledge(self):
        candles = [mk(100.0, 100.4, 99.6, 100.1, i) for i in range(20)]
        candles.append(mk(100.0, 100.3, 99.1, 100.5, 20))  # SSL sweep of 99.5
        eng = EventEngine("EURUSD")
        rep = eng.analyze(candles, atr=1.0, liquidity_levels=[99.5])
        thesis_ids = [t["id"] for t in rep.theses]
        assert "liquidity_sweep" in thesis_ids
        sweep_thesis = next(t for t in rep.theses if t["id"] == "liquidity_sweep")
        assert sweep_thesis["thesis"] and sweep_thesis["invalidation"]
        assert math.isfinite(rep.closed_candles)
        out = rep.to_dict()
        assert out["sweep"] is not None