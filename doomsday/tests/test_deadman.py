import pytest
from doomsday.config import DeadManConfig, StepType
from doomsday.daemon import DeadManSwitchDaemon, EscalationState


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


PLAN = [
    {"step": "notify", "channels": ["ops"]},
    {"step": "halt_placements"},
    {"step": "reduce_exposure", "target_percentage": 50},
    {"step": "acquire_assets", "via": "simulation_oracle", "asset_out": "USDT"},
    {"step": "seal"},
]


def make_daemon(clock=None, cadence=1.0, hooks=None, governance_key=None, **overrides):
    cfg = DeadManConfig(heartbeat_interval_s=cadence, plan=list(PLAN), **overrides)
    return DeadManSwitchDaemon(
        config=cfg, clock=clock or FakeClock(), hooks=hooks, governance_key=governance_key
    )


def test_starts_armed_and_does_not_escalate_before_first_beat():
    clock = FakeClock()
    d = make_daemon(clock)
    clock.advance(60.0)
    assert d.tick() is EscalationState.ARMED


def test_regular_beats_keep_armed():
    clock = FakeClock()
    d = make_daemon(clock)
    for i in range(20):
        d.beat()
        clock.advance(0.5)
        assert d.tick() is EscalationState.ARMED


def test_missed_beats_escalate_through_the_ladder():
    clock = FakeClock()
    d = make_daemon(clock)
    d.beat()
    clock.advance(3.5)  # grace = 3s
    assert d.tick() is EscalationState.WATCHING
    clock.advance(6.5)  # grace + escalation = 9s
    assert d.tick() is EscalationState.ESCALATING
    d.tick()  # first escalation execution window
    assert len([t for t in d.journal() if t.detail.startswith("execute")]) == 1
    clock.advance(6.0)
    d.tick()
    assert len([t for t in d.journal() if t.detail.startswith("execute")]) == 2


def test_plan_completes_into_dormant():
    clock = FakeClock()
    d = make_daemon(clock)
    d.beat()
    clock.advance(3.5)
    d.tick()
    clock.advance(60.0)
    d.tick()
    assert d.tick() is EscalationState.LIQUIDATING
    orders = getattr(d, "_orders", [])
    assert len(orders) == 1 and orders[0].asset_out == "USDT"
    clock.advance(60.0)
    assert d.tick() is EscalationState.DORMANT


def test_recovery_before_abort_threadhold_rearms():
    clock = FakeClock()
    d = make_daemon(clock)
    d.beat()
    clock.advance(3.5)
    assert d.tick() is EscalationState.WATCHING
    d.beat()  # heartbeat resumes
    assert d.tick() is EscalationState.ARMED
    assert d._step_index == 0


def test_past_abort_threshold_recovery_is_refused():
    clock = FakeClock()
    d = make_daemon(clock, abortable_until_step=0)
    d.beat()
    clock.advance(3.5)
    d.tick()
    clock.advance(9.0)
    assert d.tick() is EscalationState.ESCALATING
    d.beat()
    assert d.tick() is not EscalationState.ARMED  # irreversible now


def test_zero_human_override_disarm():
    clock = FakeClock()
    d = make_daemon(clock, governance_key=None)
    with pytest.raises(PermissionError):
        d.disarm("hacker")
    d2 = make_daemon(clock, governance_key="multisig-proof-001")
    d2.beat()
    clock.advance(3.5)
    d2.tick()
    assert d2.state is EscalationState.WATCHING
    d2.disarm("multisig-proof-001")
    assert d2.state is EscalationState.ARMED


def test_strict_signing_refuses_unsigned_beat():
    clock = FakeClock()
    d = make_daemon(clock, strict_heartbeat_signing=True)
    with pytest.raises(PermissionError):
        d.beat()
    d.beat(signed=True)
    assert d.state is EscalationState.ARMED


def test_escaling_disabled_is_fail_safe_armed():
    clock = FakeClock()
    d = make_daemon(clock, escalation_enabled=False)
    d.beat()
    clock.advance(999.0)
    assert d.tick() is EscalationState.ARMED


def test_hooks_are_invoked_in_order():
    clock = FakeClock()
    seen = []

    def hook(step, daemon):
        seen.append(step.step)

    hooks = {s: hook for s in StepType}
    d = make_daemon(clock, hooks=hooks)
    d.beat()
    clock.advance(3.5)
    d.tick()
    clock.advance(9.0)
    d.tick()
    d.tick()
    clock.advance(30.0)
    d.tick()
    assert seen == list(StepType)


def test_background_thread_runs_and_stops():
    import time

    clock = FakeClock()
    d = make_daemon(clock)
    d.beat()
    d.start(tick_interval_s=0.01)
    time.sleep(0.05)
    d.stop()
    assert not d._thread.is_alive()