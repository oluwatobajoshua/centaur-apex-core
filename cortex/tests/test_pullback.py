from cortex.market_context import Candle
from cortex.pullback import ALIGNED, ARMED, BROKEN, RESUMED, PullbackTracker


def _can(o: float, c: float, h: float, l: float) -> Candle:
    return Candle(t_open=0.0, t_close=60.0, open=o, high=h, low=l, close=c, volume=1.0)


def _uptrend() -> list[Candle]:
    # leg: 100 -> 110 (size 10 >= 1.0*2 ATR), then pullbacks and a resume.
    return [
        _can(100.0, 105.0, 106.0, 99.5),   # first candle sets direction up
        _can(105.0, 110.0, 111.0, 104.5),  # extend leg to 110
    ]


def test_aligned_to_armed_to_resumed_to_broken() -> None:
    atr = 2.0
    tr = PullbackTracker(min_impulse_atr=1.0, min_depth=0.25, max_depth=0.65, buffer_atr=0.3)
    for c in _uptrend():
        tr.update(c, atr)
    assert tr.state == ALIGNED

    # retrace 5.5 points (0.5 of the 11-point leg) -> healthy zone 0.25-0.65
    assert tr.update(_can(110.0, 106.0, 110.5, 105.5), atr) == "armed"
    assert tr.state == ARMED
    assert tr.current_depth is not None and 0.49 <= tr.current_depth <= 0.51

    # resume: high beyond extreme (111.0) + buffer (0.6)
    assert tr.update(_can(106.0, 111.0, 112.0, 105.5), atr) == "resumed"
    assert tr.state == ALIGNED
    assert tr.alive_pullbacks >= 0

    # deep pullback closes below the re-anchored origin -> broken (reversal)
    assert tr.update(_can(111.0, 99.0, 111.5, 98.5), atr) == "broken"
    assert tr.state == BROKEN


def test_shallow_pullback_does_not_arm() -> None:
    atr = 2.0
    tr = PullbackTracker(min_impulse_atr=1.0, min_depth=0.25, max_depth=0.65)
    for c in _uptrend():
        tr.update(c, atr)
    # only 0.2 points off the extreme -> far shallower than 0.25*2 ATR floor
    assert tr.update(_can(110.0, 109.9, 110.2, 109.8), atr) is None
    assert tr.state == ALIGNED


def test_direction_established_on_first_body() -> None:
    atr = 2.0
    tr = PullbackTracker()
    assert tr.update(_can(100.0, 99.9, 100.1, 99.8), atr) is None  # 0.1 body << 0.5*ATR
    assert tr.update(_can(99.9, 103.0, 103.2, 99.5), atr) is None  # 3.1 body >= 0.5*ATR sets direction
    assert tr.snapshot()["direction"] == "Bull"


def test_bear_symmetry() -> None:
    atr = 2.0
    tr = PullbackTracker(min_impulse_atr=1.0, min_depth=0.25, max_depth=0.65, buffer_atr=0.3)
    tr.update(_can(110.0, 105.0, 111.0, 104.5), atr)
    tr.update(_can(105.0, 100.0, 105.5, 99.5), atr)  # leg 110 -> 100
    assert tr.state == ALIGNED
    assert tr.update(_can(100.0, 104.0, 104.5, 99.7), atr) == "armed"  # pullback up 4 (0.4)
    assert tr.state == ARMED
    assert tr.update(_can(104.0, 99.0, 104.3, 98.7), atr) == "resumed"
    assert tr.update(_can(99.0, 111.0, 111.3, 98.5), atr) == "broken"  # close above origin 110-ish