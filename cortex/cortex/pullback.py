"""Pullback lifecycle machinery (G5): exit before the evil, re-enter on the dip.

State machine over an impulse leg:
  ALIGNED  - trending, no pullback deep enough yet
  ARMED    - price has retraced into the HEALTHY zone (ATR-normalised,
             0.25-0.65 of the impulse; deeper = turning into a reversal)
  RESUMED  - impulse resumed past its extreme -> re-entry opportunity fired
  BROKEN   - structure anchor violated -> the 'red after green' event: stand
             out, the correction has become a reversal

Miroslav-inspired honesty: pullback/base-rate numbers are measured from THIS
instrument's history (see ``sequence_stats``), never assumed from a textbook.
Pure observation machinery - I5, features only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .market_context import Candle

ALIGNED = "ALIGNED"
ARMED = "ARMED"
RESUMED = "RESUMED"
BROKEN = "BROKEN"


@dataclass
class PullbackTracker:
    min_impulse_atr: float = 1.0
    min_depth: float = 0.25
    max_depth: float = 0.65
    buffer_atr: float = 0.3
    _direction: int = field(default=0, init=False)
    _origin: float = field(default=0.0, init=False)
    _extreme: float = field(default=0.0, init=False)
    _retrace: float | None = field(default=None, init=False)
    state: str = field(default=ALIGNED, init=False)
    _alive_depths: list[float] = field(default_factory=list, init=False, repr=False)
    _atr: float = field(default=0.0, init=False)

    def update(self, c: Candle, atr: float) -> str | None:
        """Advance with one (closed or forming) candle; returns a transition."""
        self._atr = atr
        if atr <= 0:
            return None
        if self._direction == 0:
            body = c.close - c.open
            if abs(body) >= 0.5 * atr:
                self._direction = 1 if body > 0 else -1
                self._origin = c.open
                self._extreme = c.high if body > 0 else c.low
            return None

        transition: str | None = None
        if self._direction > 0:
            transition = self._step_bull(c, atr)
        else:
            transition = self._step_bear(c, atr)
        return transition

    def _depth(self, price: float) -> float:
        leg = abs(self._extreme - self._origin)
        if leg <= 0:
            return 0.0
        return (self._extreme - price) / leg if self._direction > 0 else (price - self._extreme) / leg

    def _step_bull(self, c: Candle, atr: float) -> str | None:
        leg = self._extreme - self._origin
        if c.close < self._origin:
            self.state = BROKEN
            return "broken"
        if c.high > self._extreme + self.buffer_atr * atr:
            if self.state == ARMED and self._retrace is not None:
                self._record_alive(self._depth(self._retrace))
                self.state = ALIGNED
                self._origin = self._retrace
                self._extreme = max(self._extreme, c.high)
                self._retrace = None
                return "resumed"
            self.state = ALIGNED
            self._extreme = max(self._extreme, c.high)
            self._retrace = None
            return None

        if self.state == ALIGNED and c.low < self._extreme and leg >= self.min_impulse_atr * atr:
            depth = self._depth(c.low)
            if self.min_depth <= depth < self.max_depth:
                self.state = ARMED
                self._retrace = c.low
                return "armed"
        elif self.state == ARMED:
            if self._retrace is None:
                self._retrace = c.low
            elif c.low < self._retrace:
                self._retrace = c.low
        return None

    def _step_bear(self, c: Candle, atr: float) -> str | None:
        leg = self._origin - self._extreme
        if c.close > self._origin:
            self.state = BROKEN
            return "broken"
        if c.low < self._extreme - self.buffer_atr * atr:
            if self.state == ARMED and self._retrace is not None:
                self._record_alive(self._depth(self._retrace))
                self.state = ALIGNED
                self._origin = self._retrace
                self._extreme = min(self._extreme, c.low)
                self._retrace = None
                return "resumed"
            self.state = ALIGNED
            self._extreme = min(self._extreme, c.low)
            self._retrace = None
            return None

        if self.state == ALIGNED and c.high > self._extreme and leg >= self.min_impulse_atr * atr:
            depth = self._depth(c.high)
            if self.min_depth <= depth < self.max_depth:
                self.state = ARMED
                self._retrace = c.high
                return "armed"
        elif self.state == ARMED:
            if self._retrace is None:
                self._retrace = c.high
            elif c.high > self._retrace:
                self._retrace = c.high
        return None

    def _record_alive(self, depth_ratio: float, cap: int = 200) -> None:
        if 0.0 < depth_ratio < 1.0:
            self._alive_depths.append(depth_ratio)
            if len(self._alive_depths) > cap:
                self._alive_depths = self._alive_depths[-cap:]

    def percentile(self, depth_ratio: float) -> float:
        """Share of survived pullbacks shallower than this one (0..1)."""
        if not self._alive_depths:
            return 0.5
        data = sorted(self._alive_depths)
        return sum(1.0 for d in data if d < depth_ratio) / len(data)

    @property
    def alive_pullbacks(self) -> int:
        return len(self._alive_depths)

    @property
    def current_depth(self) -> float | None:
        if self.state != ARMED or self._retrace is None:
            return None
        return self._depth(self._retrace)

    def snapshot(self) -> dict:
        leg = abs(self._extreme - self._origin)
        return {
            "state": self.state,
            "direction": "Bull" if self._direction > 0 else ("Bear" if self._direction < 0 else "Flat"),
            "impulse_atr": round(leg / self._atr, 3) if getattr(self, "_atr", 0) else "n/a",
            "current_depth": None if self.current_depth is None else round(self.current_depth, 3),
            "alive_pullbacks": len(self._alive_depths),
        }

    def reset(self) -> None:
        self._direction = 0
        self._origin = 0.0
        self._extreme = 0.0
        self._retrace = None
        self.state = ALIGNED
        self._alive_depths.clear()