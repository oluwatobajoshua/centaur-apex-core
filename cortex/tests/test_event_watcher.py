import io
import json
import sys

from cortex.event_watcher import EventWatcher
from cortex.market_context import CandleAggregator


class TestAggregatorForming:
    def test_forming_none_when_idle(self):
        agg = CandleAggregator(60.0)
        assert agg.forming(0.0) is None

    def test_forming_snapshots_intrabar(self):
        agg = CandleAggregator(60.0)
        agg.feed(100.0, 0.0)
        agg.feed(101.0, 10.0)
        agg.feed(99.5, 20.0)
        form = agg.forming(20.0)
        assert form is not None
        assert (form.open, form.high, form.low, form.close) == (100.0, 101.0, 99.5, 99.5)


class TestEventWatcherRt:
    @staticmethod
    def _feed_history(watcher, count=21, spread=(99.8, 100.2)):
        reports = []
        for i in range(count):
            price = 100.0 if i % 2 else 100.0
            price = 99.9 + 0.2 * (i % 3 - 1)
            rep = watcher.watch_tick({"price": price, "timestamp": float(i * 300 + 1)})
            if rep is not None:
                reports.append(rep)
        return reports

    def test_sweep_detected_realtime_before_close(self):
        watcher = EventWatcher("EURUSD", timeframe_s=300.0, levels=[99.5], rt_interval_ms=0.0)
        self._feed_history(watcher)
        rt_reports = []
        for ts, price in ((6100.0, 100.0), (6150.0, 99.1), (6200.0, 100.3)):
            rep = watcher.watch_tick({"price": price, "timestamp": ts})
            if rep is not None:
                rt_reports.append(rep)
        sweep_rt = [
            r for r in rt_reports
            if any(t["id"] == "liquidity_sweep" for t in r["theses"]) and r["phase"] == "rt"
        ]
        assert sweep_rt, "sweep must be struck in real time, before the candle closes"
        assert sweep_rt[0]["preview_price"] in (99.1, 100.3)
        assert set(sweep_rt[0]["context"]) >= {"regime", "integrity", "bias"}
        json.dumps(sweep_rt[0], sort_keys=True)

    def test_heartbeat_proves_aliveness(self, monkeypatch):
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buf)
        watcher = EventWatcher("EURUSD", rt_interval_ms=0.0)
        watcher.run(["", " ", ""], heartbeat_s=0.0)
        out = buf.getvalue()
        assert '"watcher":"alive"' in out.replace(" ", "")

    def test_quiet_ticks_do_not_spam(self):
        watcher = EventWatcher("EURUSD", timeframe_s=300.0, rt_interval_ms=0.0)
        self._feed_history(watcher)
        stable_sig = None
        spammy_events = 0
        for ts in range(6400, 6600):
            rep = watcher.watch_tick({"price": 100.0, "timestamp": float(ts)})
            if rep is not None:
                sig = tuple(sorted(t["id"] for t in rep["theses"]))
                if sig == stable_sig:
                    spammy_events += 1
                stable_sig = sig
        assert spammy_events < 3  # dedup: repeated same signature is not re-emitted