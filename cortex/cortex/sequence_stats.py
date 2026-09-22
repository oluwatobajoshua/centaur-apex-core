"""Sequence base-rate machinery (G5): self-measured conditional probabilities.

The system measures its OWN history - no textbook assumptions. Colour sequencing
alone is a coin flip (~50/50): the edges that survive are contextual base rates
(e. g. reversal odds after long same-direction streaks, extension exhaustion).
This module tracks those probabilities empirically, Laplace-smoothed, so the
calibration layer can quote honest numbers instead of guesses.

I5: pure observation. No orders, no sizing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .market_context import Candle


@dataclass
class CondStats:
    up: int = 0
    down: int = 0

    @property
    def count(self) -> int:
        return self.up + self.down

    def p_up(self, alpha: float = 1.0) -> float:
        return (self.up + alpha) / (self.count + 2.0 * alpha)

    def p_down(self, alpha: float = 1.0) -> float:
        return (self.down + alpha) / (self.count + 2.0 * alpha)


def _sign(v: float) -> int:
    return (v > 0) - (v < 0)


class CandleSequenceStats:
    """Fits conditional next-bar-direction probabilities from observed candles.

    Context = (body-size bucket vs ATR, streak length bucket). Also tracks
    streak-extreme reversal base rates (the ~87% family) and P75 pullback-depth
    survival.
    """

    def __init__(self) -> None:
        self._table: dict[tuple[int, int, int], CondStats] = {}
        self._streak_rev: dict[tuple[bool, int], CondStats] = {}
        self._alive_pullback_depths: list[float] = []

    def _body_bucket(self, body_abs: float, atr: float, buckets: tuple[float, float] = (0.5, 2.0)) -> int:
        if atr <= 0:
            return 0
        ratio = body_abs / atr
        if ratio < buckets[0]:
            return 0
        if ratio < buckets[1]:
            return 1
        return 2

    def _streak_bucket(self, streak: int) -> int:
        return 0 if streak <= 1 else (1 if streak == 2 else 2)

    def observe(self, candles: list[Candle], atr: float) -> None:
        if len(candles) < 3 or atr <= 0:
            return
        streak = 0
        last_dir: int | None = None
        for i in range(1, len(candles)):
            prev = candles[i - 1]
            cur = candles[i]
            d = _sign(cur.close - cur.open)
            if d == 0:
                continue
            if last_dir is not None and d == last_dir:
                streak += 1
            else:
                streak = 1
            last_dir = d
            bucket = (self._body_bucket(abs(cur.close - cur.open), atr), d, self._streak_bucket(streak))
            if i + 1 < len(candles):
                nxt = candles[i + 1]
                nd = _sign(nxt.close - nxt.open)
                if nd == 0:
                    continue
                s = self._table.setdefault(bucket, CondStats())
                s.up += 1 if nd > 0 else 0
                s.down += 1 if nd < 0 else 0
            else:
                continue

    def expectation(self, body_abs: float, atr: float, direction: int, streak: int) -> CondStats:
        bucket = (self._body_bucket(body_abs, atr), direction, self._streak_bucket(streak))
        return self._table.get(bucket, CondStats())

    # -- streak-extreme reversal base rates ---------------------------------- #

    def observe_streak_extreme(self, hist: list[float], streak_n: int = 3) -> dict[str, float]:
        """P(opposite candle after N straight closes in the previous direction)."""
        self._streak_rev: dict[tuple[bool, int], CondStats] = {}
        run = 0
        last: int | None = None
        for i in range(1, len(hist)):
            d = _sign(hist[i] - hist[i - 1])
            if d == 0:
                run = 0
                last = None
                continue
            if last is not None and d == last:
                run += 1
            else:
                run = 1
            last = d
            if run >= streak_n and i + 1 < len(hist):
                nd = _sign(hist[i + 1] - hist[i])
                if nd == 0:
                    continue
                key = (d > 0, run)
                s = self._streak_rev.setdefault(key, CondStats())
                if nd > 0:
                    s.up += 1
                else:
                    s.down += 1
        out: dict[str, float] = {}
        for (bullish, run), s in self._streak_rev.items():
            label = f"{'bull' if bullish else 'bear'}_{run}"
            out[f"p_reverse_{label}"] = s.p_down() if bullish else s.p_up()
            out[f"n_{label}"] = float(s.count)
        return out

    # -- pullback-depth survival percentiles --------------------------------- #

    def record_alive_pullback_depth(self, depth_ratio: float, cap: int = 200) -> None:
        if not (0.0 < depth_ratio < 1.0):
            return
        self._alive_pullback_depths.append(depth_ratio)
        if len(self._alive_pullback_depths) > cap:
            self._alive_pullback_depths = self._alive_pullback_depths[-cap:]

    def pullback_depth_percentile(self, depth_ratio: float) -> float:
        """Share of survived pullbacks shallower than this one (0..1)."""
        if not self._alive_pullback_depths:
            return 0.5
        data = sorted(self._alive_pullback_depths)
        return sum(1.0 for d in data if d < depth_ratio) / len(data)

    def reset(self) -> None:
        self._table.clear()
        self._streak_rev.clear()
        self._alive_pullback_depths.clear()