import math

from cortex.market_context import Candle
from cortex.sequence_stats import CandleSequenceStats, CondStats


def _candle(o: float, c: float, ts: float = 0.0) -> Candle:
    return Candle(
        t_open=ts,
        t_close=ts + 60.0,
        open=o,
        high=max(o, c) + 0.1,
        low=min(o, c) - 0.1,
        close=c,
        volume=1.0,
    )


def test_cond_stats_laplace_smoothing() -> None:
    s = CondStats()
    assert math.isclose(s.p_up(), 0.5)  # no data -> not 0/1
    s.up = 1
    assert s.p_up() > 0.5


def test_expectation_tracks_simple_alternation() -> None:
    stats = CandleSequenceStats()
    candles = [_candle(o, c) for o, c in ((100, 101), (101, 100), (100, 101), (101, 100))]
    stats.observe(candles, atr=2.0)
    e = stats.expectation(body_abs=1.0, atr=2.0, direction=1, streak=1)
    assert e.count >= 1
    assert 0.0 < e.p_down() < 1.0


def test_streak_extreme_reversal_base_rate_pathological() -> None:
    stats = CandleSequenceStats()
    closes = [100.0]
    for _ in range(20):  # streak of exactly 3 ups, then a down
        for _ in range(3):
            closes.append(closes[-1] + 1.0)
        closes.append(closes[-1] - 1.0)
    r = stats.observe_streak_extreme(closes, streak_n=3)
    assert r["n_bull_3"] == 20
    assert r["p_reverse_bull_3"] > 0.9  # ~ (20+1)/(20+2) Laplace-smoothed


def test_pullback_depth_percentile() -> None:
    stats = CandleSequenceStats()
    for d in (0.3, 0.5, 0.7):
        stats.record_alive_pullback_depth(d)
    assert math.isclose(stats.pullback_depth_percentile(0.2), 0.0)
    assert math.isclose(stats.pullback_depth_percentile(0.4), 1 / 3)
    assert math.isclose(stats.pullback_depth_percentile(0.9), 1.0)


def test_empty_percentile_fallback() -> None:
    assert CandleSequenceStats().pullback_depth_percentile(0.4) == 0.5