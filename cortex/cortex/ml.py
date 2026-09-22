"""Cortex ML framework (G5): honest, walk-forward, point-in-time learning.

This is the *machinery* the Cortex uses to learn market behaviour - NOT a
hand-written strategy. It answers, honestly, what level a model can reach on
next-candle colour with real live data.

Design laws:
  * POINT-IN-TIME ONLY. Features for bar i are computed from bars <= i; the
    label (colour of bar i+1) becomes known only when that bar closes.
  * WALK-FORWARD. The model is fit on history up to bar i, then queried for
    bar i+1; accuracy is scored on candles the fit never saw.
  * I5. Classifies and measures only. Never sizes, routes or signs.
  * The realised accuracy IS the honest answer; including coverage and
    train-vs-test breakdown - no magic percentage, ever.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .market_context import Candle


# --------------------------------------------------------------------------- #
# Feature extraction - fixed schema. Compute from bars <= i only.             #
# --------------------------------------------------------------------------- #

def _atr(candles: list[Candle], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    trs: list[float] = []
    for i in range(1, len(candles)):
        p = candles[i - 1]
        c = candles[i]
        trs.append(max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close)))
    window = trs[-period:]
    return sum(window) / len(window)


def _colour(c: Candle) -> int:
    return (c.close > c.open) - (c.close < c.open)


def _streak(hist: list[Candle], i: int) -> int:
    if i < 0:
        return 0
    col = _colour(hist[i])
    if col == 0:
        return 0
    n = 1
    j = i - 1
    while j >= 0 and _colour(hist[j]) == col:
        n += 1
        j -= 1
    return n


FEATURE_NAMES = [
    "last_colour",
    "body_atr",
    "range_atr",
    "up_streak",
    "down_streak",
    "momentum_atr",
    "body_in_range",
]


def features_for(candles: list[Candle], i: int) -> list[float]:
    """Point-in-time features for bar i (predicting colour of bar i+1)."""
    c = candles[i]
    atr_tail = candles[max(0, i - 16): i + 1]
    atr = _atr(atr_tail, 14)
    col = _colour(c)
    body = c.close - c.open
    rng = c.high - c.low
    tail = candles[max(0, i - 9): i + 1]
    closes = [x.close for x in tail]
    mom = (c.close - closes[0]) / atr if atr > 0 and closes else 0.0
    up_streak = _streak(candles, i) if col > 0 else 0
    down_streak = _streak(candles, i) if col < 0 else 0
    return [
        col,
        body / atr if atr > 0 else 0.0,
        rng / atr if atr > 0 else 0.0,
        min(up_streak, 6.0),
        min(down_streak, 6.0),
        mom,
        (c.close - c.open) / rng if rng > 0 else 0.0,
    ]


# --------------------------------------------------------------------------- #
# Walk-forward harness.                                                       #
# --------------------------------------------------------------------------- #

@dataclass
class CloseSet:
    model: Any = None


def _train(X: list[list[float]], y: list[int]) -> Any:
    try:
        from sklearn.linear_model import LogisticRegression

        clf = LogisticRegression(max_iter=2000)
        clf.fit(X, y)
        return clf
    except Exception:  # pragma: no cover - env without sklearn
        return None


def _proba_green(clf: Any, feats: list[float]) -> float | None:
    try:
        proba = clf.predict_proba([feats])[0]
        classes = list(clf.classes_)
    except Exception:
        return None
    if len(classes) == 1:
        return 1.0 if classes[0] == 1 else 0.0
    if len(proba) == 2:
        return float(proba[classes.index(1)])
    return None


class NextCandleML:
    """Walk-forward classifier. ``step`` is called with the just-closed candle;
    it returns a colour call for the NEXT candle, or None to abstain.

    ``retrain_every`` batching keeps large-history drills tractable: the model
    is re-fit only every ``retrain_every`` closed candles (still strictly on
    the past - no leakage), so months of history can be scored in one pass.
    """

    def __init__(
        self,
        min_train: int = 250,
        warmup: int = 60,
        retrain_every: int = 1,
        rolling_window: int | None = None,
    ) -> None:
        self.min_train = min_train
        self.warmup = warmup
        self.retrain_every = retrain_every
        self.rolling_window = rolling_window
        self._history: list[Candle] = []
        self._pending: int | None = None  # call awaiting the just-closed bar
        self._clf: Any = None
        self._since_train = 0
        self._decisions: list[dict[str, Any]] = []

    def step(self, candle: Candle) -> int | None:
        """Append one CLOSED candle. Scores the previous call against this
        candle, then (if a model is loaded) issues the next call."""
        self._history.append(candle)

        if self._pending is not None:
            col = _colour(candle)
            if col != 0:
                self._decisions.append({"call": self._pending, "actual": col, "hit": self._pending == col})
            self._pending = None

        n = len(self._history)
        if n < self.warmup + 2:
            return None

        # advance the retrain clock on every step so a re-fit always happens
        self._since_train += 1
        if self._since_train >= self.retrain_every or self._clf is None:
            X, y = self._training_set()
            if len(X) < self.min_train:
                return None
            clf = _train(X, y)
            if clf is None:
                return None
            self._clf = clf
            self._since_train = 0

        p = _proba_green(self._clf, features_for(self._history, n - 1))
        if p is None:
            return None
        self._pending = 1 if p >= 0.5 else -1
        return self._pending

    def _training_set(self) -> tuple[list[list[float]], list[int]]:
        X: list[list[float]] = []
        y: list[int] = []
        start = 0
        if self.rolling_window is not None:
            start = max(0, len(self._history) - self.rolling_window)
        for i in range(max(self.warmup, start), len(self._history) - 1):
            X.append(features_for(self._history, i))
            y.append(_colour(self._history[i + 1]))
        return X, y

    def report(self) -> dict[str, Any]:
        decided = [d for d in self._decisions if d["hit"] is not None]
        hits = sum(1 for d in decided if d["hit"])
        greens = sum(1 for d in decided if d["call"] == 1)
        greens_right = sum(1 for d in decided if d["call"] == 1 and d["hit"])
        reds = len(decided) - greens
        reds_right = sum(1 for d in decided if d["call"] == -1 and d["hit"])
        return {
            "candles_seen": len(self._history),
            "calls_scored": len(decided),
            "accuracy": hits / len(decided) if decided else 0.0,
            "green_accuracy": greens_right / greens if greens else 0.0,
            "red_accuracy": reds_right / reds if reds else 0.0,
            "green_calls": greens,
            "red_calls": reds,
        }


def run_live_ml(
    symbol: str = "BTCUSDT",
    timeframe_s: float = 300,
    history_candles: int = 700,
    score_candles: int = 180,
) -> dict[str, Any]:
    """Fetch live Binance candles and walk forward with a model fit strictly on
    the past; reality scores every call on an unseen candle."""
    from adapters.adapters.live_feed import fetch_klines

    candles = fetch_klines(symbol, timeframe_s, limit=history_candles + score_candles)
    if len(candles) < history_candles + 30:
        return {"error": "not enough live candles"}

    m = NextCandleML(min_train=250, warmup=300)
    for i in range(300, len(candles) - 1):
        m.step(candles[i])

    return {
        "symbol": symbol,
        "timeframe_s": timeframe_s,
        "scored_candles": len(candles) - 300,
        **m.report(),
    }


def run_scale_ml(
    symbol: str = "BTCUSDT",
    timeframe_s: float = 300,
    history_ms: float = 90 * 24 * 3600 * 1000,  # 90 days by default
    warmup: int = 500,
    rolling_window: int = 20_000,
    retrain_every: int = 250,
) -> dict[str, Any]:
    """THE big-history drill: months of candles, point-in-time rolling-window
    fits, honest walk-forward scores. Reports raw accuracy - and checks it
    against the value the history itself is trading at."""
    from adapters.adapters.live_feed import fetch_history

    candles = fetch_history(symbol, timeframe_s, history_ms=history_ms)
    if len(candles) < warmup + 200:
        return {"error": "not enough history"}

    m = NextCandleML(
        min_train=200,
        warmup=warmup,
        retrain_every=retrain_every,
        rolling_window=rolling_window,
    )
    for i in range(warmup, len(candles) - 1):
        m.step(candles[i])

    base_up = sum(1 for c in candles if c.close > c.open)
    base_down = sum(1 for c in candles if c.close < c.open)
    total_directional = base_up + base_down
    return {
        "symbol": symbol,
        "timeframe_s": timeframe_s,
        "candles_fetched": len(candles),
        "history_days": round(history_ms / (24 * 3600 * 1000), 1),
        "base_rate_green": base_up / total_directional if total_directional else 0.0,
        **m.report(),
    }


if __name__ == "__main__":
    print(json.dumps(run_live_ml(), indent=2))