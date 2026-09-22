"""Event Watcher daemon (G5/G8 machinery): the permanent microscope.

Consumes a tick stream (JSON lines on stdin by default, same framing as
``market_feed``) and reacts in REAL TIME: every few milliseconds it re-analyses
the currently-forming candle, so a split-second event (a sweep, an impulse, a
fakeout reclaim) is detected the instant it becomes identifiable - not when the
candle closes. Closed candles confirm the reading. It never sizes, signs or
routes a trade (I5): it only observes, warns, and proves it is alive with
heartbeats (Doomsday-compatible).
"""

from __future__ import annotations

import json
import random
import sys
import time
from collections import deque
from collections.abc import Callable, Iterable
from typing import Any

from .event_engine import EventEngine
from .market_context import CandleAggregator, MarketContextParams, build_context
from .pullback import PullbackTracker


class EventWatcher:
    def __init__(
        self,
        asset_id: str,
        timeframe_s: float = 300.0,
        params: MarketContextParams | None = None,
        levels: list[float] | None = None,
        levels_provider: Callable[[], list[float]] | None = None,
        max_candles: int = 400,
        event_engine: EventEngine | None = None,
        rt_interval_ms: float = 0.0,
    ) -> None:
        self.asset_id = asset_id
        self.timeframe_s = timeframe_s
        self.params = params or MarketContextParams(timeframe_s=timeframe_s)
        self.aggregator = CandleAggregator(timeframe_s)
        self.candles: deque[Any] = deque(maxlen=max_candles)
        self.levels = levels or []
        self.levels_provider = levels_provider
        self.engine = event_engine or EventEngine(asset_id)
        self.pullback = PullbackTracker()
        self.rt_interval_ms = rt_interval_ms
        self._watch_start = time.monotonic()
        self._last_rt_at = 0.0
        self._last_rt_sig: tuple[Any, ...] | None = None

    def _current_levels(self) -> list[float]:
        if self.levels_provider is not None:
            return self.levels_provider()
        return self.levels

    def watch_tick(self, tick: dict[str, Any]) -> dict[str, Any] | None:
        """Feed one tick; returns the freshest report (real-time or close).

        Every tick is analysed - the watcher never blinks. The real-time path
        re-reads the forming candle on each update so a split-second event is
        struck the instant it is identifiable.
        """
        price = tick.get("price")
        ts = tick.get("timestamp")
        if price is None or ts is None:
            return None
        now = time.monotonic()
        price = float(price)
        ts = float(ts)
        if not self._finite_positive(price):
            return None

        closed = self.aggregator.feed(price, ts)
        if closed is not None:
            self.candles.append(closed)
            close_report = self._analyze_closed()
            self._last_rt_sig = None  # fresh state after a closed candle
            return close_report

        if now - self._last_rt_at >= self.rt_interval_ms / 1000.0:
            self._last_rt_at = now
            rt = self._analyze_rt(ts)
            if rt is not None:
                sig = self._signature(rt)
                if sig != self._last_rt_sig:
                    self._last_rt_sig = sig
                    return rt
        return None

    @staticmethod
    def _finite_positive(price: float) -> bool:
        try:
            return price > 0 and price == price  # reject NaN, inf, <= 0
        except Exception:
            return False

    def _analyze_rt(self, ts: float) -> dict[str, Any] | None:
        if not self.candles or len(self.candles) < self.params.atr_period + 1:
            return None
        forming = self.aggregator.forming(ts)
        if forming is None:
            return None
        candles = list(self.candles) + [forming]
        ctx = build_context(candles, self.params, self.asset_id)
        report = self.engine.analyze(candles, ctx.atr, self._current_levels())
        transition = self.pullback.update(forming, ctx.atr)
        data = report.to_dict()
        self._merge_pullback(data, transition)
        data["phase"] = "rt"
        data["fired_at"] = time.time()
        data["latency_ms"] = 0.0  # live strike
        data["preview_price"] = forming.close
        data["context"] = self._context_dict(ctx)
        return data

    def _analyze_closed(self) -> dict[str, Any]:
        candles = list(self.candles)
        ctx = build_context(candles, self.params, self.asset_id)
        report = self.engine.analyze(candles, ctx.atr, self._current_levels())
        transition = self.pullback.update(candles[-1], ctx.atr)
        data = report.to_dict()
        self._merge_pullback(data, transition)
        data["phase"] = "close"
        data["fired_at"] = time.time()
        data["latency_ms"] = self._latency_ms()
        data["context"] = self._context_dict(ctx)
        return data

    def _merge_pullback(self, data: dict[str, Any], transition: str | None) -> None:
        thesis: dict[str, Any] | None = None
        if transition == "armed":
            thesis = {
                "id": "pullback_armed",
                "family": "structure",
                "mechanism": "price retraced into the healthy 0.25-0.65 ATR-normalised zone",
                "thesis": "The impulse is intact; what was obtainable is being banked and the re-entry lay-up is forming.",
                "invalidation": "retrace deepens beyond 0.65 of the impulse (the correction becomes a reversal)",
                "conversion": "re-enter when the impulse confirms resumption",
            }
        elif transition == "resumed":
            thesis = {
                "id": "pullback_resumed",
                "family": "structure",
                "mechanism": "impulse resumed past its extreme after an ATR-normalised pullback",
                "thesis": "The healthy pullback resolved in favour of the impulse: re-enter with the move.",
                "invalidation": "close back through the pullback low (bull) / high (bear)",
                "conversion": "re-enter with the impulse; trail under the resumption pivot",
            }
        elif transition == "broken":
            thesis = {
                "id": "pullback_broken",
                "family": "structure",
                "mechanism": "structure anchor violated: the correction has become a reversal",
                "thesis": "The red-after-green event: stand out with profits banked; the impulse is over.",
                "invalidation": "price reclaims the anchor within this candle",
                "conversion": "stand out; the move is done",
            }
        if thesis is not None:
            data["theses"] = [t for t in data["theses"] if t.get("id") != thesis["id"]]
            data["theses"].insert(0, thesis)
        snap = self.pullback.snapshot()
        snap["transition"] = transition
        data["pullback"] = snap

    @staticmethod
    def _context_dict(ctx: Any) -> dict[str, Any]:
        return {
            "regime": ctx.regime,
            "phase": ctx.phase,
            "bias": ctx.bias,
            "integrity": ctx.integrity,
            "break_level": ctx.break_level,
        }

    @staticmethod
    def _signature(data: dict[str, Any]) -> tuple[Any, ...]:
        actives = tuple(sorted(t["id"] for t in data["theses"]))
        c = data["context"]
        return (actives, c["regime"], c["phase"], c["integrity"])

    def _latency_ms(self) -> float:
        closed = self.candles[-1]
        return max(0.0, (time.time() - closed.t_close) * 1000.0)

    def run(self, stream: Iterable[str], heartbeat_s: float = 10.0) -> None:
        """Consume JSON-line ticks from ``stream`` and write JSON-line reports out."""
        out = sys.stdout
        last_pulse = time.monotonic()
        for line in stream:
            line = line.strip()
            now = time.monotonic()
            if line:
                try:
                    tick = json.loads(line)
                except json.JSONDecodeError:
                    tick = None
                report = self.watch_tick(tick) if tick else None
                if report is not None:
                    last_pulse = now
                    self._emit(out, report)
                    continue
            if now - last_pulse >= heartbeat_s:
                last_pulse = now
                self._emit(out, self._heartbeat())

    @staticmethod
    def _emit(out: Any, payload: dict[str, Any]) -> None:
        out.write(json.dumps(payload, sort_keys=True) + "\n")
        out.flush()

    def _heartbeat(self) -> dict[str, Any]:
        return {
            "watcher": "alive",
            "asset_id": self.asset_id,
            "closed_candles": len(self.candles),
            "uptime_s": round(time.monotonic() - self._watch_start, 3),
            "fired_at": time.time(),
        }


def _demo_ticks(total: int = 260) -> Iterable[dict[str, Any]]:
    """Synthetic tick generator: a walk that visits trends, a coil, an impulse
    breakdown and a range so the watcher has real events to report."""
    # Reuse the market_context synthetic candle walk, expanded to ticks.
    from .market_context import _synthetic_candles

    rng = random.Random(7)
    t = 1_700_000_000.0
    for candle in _synthetic_candles():
        o, c, h, l = candle.open, candle.close, candle.high, candle.low
        steps = rng.randint(2, 5)
        for k in range(steps):
            frac = (k + 1) / steps
            price = o + (c - o) * frac + rng.uniform(-0.02, 0.02) * (h - l)
            yield {"price": price, "timestamp": t + k * 60.0}
        t += 60.0 * steps
        yield {"price": c, "timestamp": t}


def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Event Watcher - the permanent microscope.")
    parser.add_argument("--asset", default="SYNTH", help="Instrument id.")
    parser.add_argument("--tf", type=float, default=300.0, help="Candle timeframe in seconds.")
    parser.add_argument("--heartbeat", type=float, default=10.0, help="Heartbeat interval in seconds.")
    parser.add_argument("--demo", action="store_true", help="Feed the synthetic walk instead of stdin.")
    args = parser.parse_args()

    watcher = EventWatcher(args.asset, timeframe_s=args.tf)
    if args.demo:
        watcher.run((json.dumps(t) + "\n" for t in _demo_ticks()), heartbeat_s=args.heartbeat)
    else:
        watcher.run(sys.stdin, heartbeat_s=args.heartbeat)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())