import math

from adapters.adapters.live_feed import LiveFeedError, _parse_kline, fetch_klines
from cortex.market_context import Candle


def test_parse_kline_string_prices() -> None:
    row = [1700000000000, "100.5", "101.0", "99.5", "100.8", "12.3", 1700000059999]
    c = _parse_kline(row)
    assert (c.open, c.high, c.low, c.close) == (100.5, 101.0, 99.5, 100.8)
    assert c.t_open == 1_700_000_000.0
    assert c.t_close == 1_700_000_059.999


def test_parse_kline_rejects_bad_rows() -> None:
    try:
        _parse_kline([0, "x", "y", "z", "w", "v", 0])
    except LiveFeedError:
        return
    raise AssertionError("expected LiveFeedError")


def test_unsupported_timeframe_raises() -> None:
    try:
        fetch_klines("BTCUSDT", 777)
    except LiveFeedError as exc:
        assert "unsupported" in str(exc)
        return
    raise AssertionError("expected LiveFeedError")