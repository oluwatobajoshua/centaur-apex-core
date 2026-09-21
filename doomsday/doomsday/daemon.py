"""Dead-man switch daemon (Phase 14.2, G6).

Deterministic liveness watchdog: when heartbeats stop, it walks a pre-registered
escalation path and can drive the AssetConversionOracle. Reverse of a human
dead-man switch — the system watches itself, and humans cannot disarm it (I7);
only the cryptographic governance path may. Every transition is journaled."""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from doomsday.config import DeadManConfig, EscalationStep, StepType
from doomsday.oracle import AssetConversionOracle, oracle_factory


class EscalationState(str, Enum):
    ARMED = "ARMED"
    WATCHING = "WATCHING"
    ESCALATING = "ESCALATING"
    LIQUIDATING = "LIQUIDATING"
    DORMANT = "DORMANT"


_TRANSITIONS: dict[EscalationState, frozenset[EscalationState]] = {
    EscalationState.ARMED: {EscalationState.WATCHING},
    EscalationState.WATCHING: {EscalationState.ESCALATING, EscalationState.ARMED},
    EscalationState.ESCALATING: {EscalationState.ARMED, EscalationState.LIQUIDATING},
    EscalationState.LIQUIDATING: {EscalationState.DORMANT},
    EscalationState.DORMANT: frozenset(),
}


@dataclass
class Transition:
    frm: str
    to: str
    t: float
    detail: str = ""


@dataclass
class DeadManSwitchDaemon:
    config: DeadManConfig
    oracle: AssetConversionOracle | None = None
    governance_key: str | None = None
    hooks: dict[StepType, Callable[[EscalationStep, DeadManSwitchDaemon], None]] | None = None
    clock: Callable[[], float] = time.monotonic

    _state: EscalationState = field(default=EscalationState.ARMED, init=False)
    _last_beat: float | None = field(default=None, init=False)
    _step_index: int = field(default=0, init=False)
    _journal: deque[Transition] = field(init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _last_error: str | None = field(default=None, init=False)
    _orders: list = field(default_factory=list, init=False)
    _liquidating_since: float | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._journal = deque(maxlen=self.config.max_journal_entries)
        self.oracle = self.oracle or oracle_factory(self.config.oracle)
        self._hooks = {k: v for k, v in (self.hooks or {}).items()}

    @property
    def state(self) -> EscalationState:
        with self._lock:
            return self._state

    def beat(self, signed: bool = False) -> None:
        """Emit a liveness heartbeat. In strict mode, unsigned beats are refused."""
        if self.config.strict_heartbeat_signing and not signed:
            raise PermissionError("unsigned heartbeat refused in strict mode")
        with self._lock:
            self._last_beat = self.clock()
            if self._state in (EscalationState.ARMED,):
                self._note("armed heartbeat")

    def disarm(self, governance_key: str) -> None:
        """Zero-human-override (I7): only the governance multi-sig path disarms."""
        if self.governance_key is None or governance_key != self.governance_key:
            raise PermissionError("governance override rejected — key mismatch/unset")
        with self._lock:
            self._move(EscalationState.ARMED, "governance disarmed")
            self._step_index = 0
            self._liquidating_since = None
            self._last_beat = self.clock()

    def _move(self, target: EscalationState, detail: str) -> bool:
        allowed = _TRANSITIONS[self._state]
        if target not in allowed:
            return False
        self._journal.append(Transition(self._state.value, target.value, self.clock(), detail))
        self._state = target
        return True

    def _note(self, detail: str) -> None:
        self._journal.append(Transition(self._state.value, self._state.value, self.clock(), detail))

    def _can_abort(self) -> bool:
        return self._step_index < self.config.abortable_until_step

    def _record_order(self, order) -> None:
        self._orders.append(order)

    def _execute_step(self, step: EscalationStep) -> None:
        self._note(f"execute {step.step.value}")
        hook = self._hooks.get(step.step)
        if step.step is StepType.NOTIFY:
            self._note(f"notify:{','.join(step.channels) or 'none'}")
        elif step.step is StepType.HALT_PLACEMENTS:
            self._note("placements halted at gateway boundary")
        elif step.step is StepType.REDUCE_EXPOSURE:
            self._note(f"reduce_exposure target={step.target_percentage}%")
        elif step.step is StepType.ACQUIRE_ASSETS:
            quote = self.oracle.quote("PORTFOLIO", step.asset_out, 1.0)
            order = self.oracle.submit_conversion_request(quote)
            self._record_order(order)
            self._note(f"acquire_assets order={order.order_id} via={step.via or self.config.oracle}")
        elif step.step is StepType.SEAL:
            self._note("journal sealed for audit")
        if hook is not None:
            hook(step, self)

    def tick(self) -> EscalationState:
        """Advance the state machine one step for the current clock time."""
        now = self.clock()
        with self._lock:
            last = self._last_beat if self._last_beat is not None else now
            elapsed = now - last
            cfg = self.config
            if not cfg.escalation_enabled:
                self._state = EscalationState.ARMED
                return self._state

            if self._state is EscalationState.ARMED:
                if elapsed > cfg.grace_period:
                    self._move(EscalationState.WATCHING, "heartbeat lost")
                return self._state

            if self._state is EscalationState.WATCHING:
                if elapsed <= cfg.grace_period:
                    if self._move(EscalationState.ARMED, "heartbeat resumed"):
                        self._step_index = 0
                        self._liquidating_since = None
                elif elapsed > cfg.grace_period + cfg.escalation_period:
                    self._move(EscalationState.ESCALATING, "plan armed")
                return self._state

            if self._state is EscalationState.ESCALATING:
                if last is not None and elapsed <= cfg.grace_period and self._can_abort():
                    if self._move(EscalationState.ARMED, "heartbeat resumed"):
                        self._step_index = 0
                    return self._state
                step_no = int((elapsed - cfg.grace_period) // cfg.escalation_period)
                if step_no <= self._step_index:
                    return self._state
                plan = cfg.plan
                step_index = min(step_no, len(plan))
                for i in range(self._step_index + 1, step_index + 1):
                    try:
                        self._step_index = i
                        if i - 1 < len(plan):
                            self._execute_step(plan[i - 1])
                            if i - 1 == len(plan) - 1:
                                self._liquidating_since = now
                                self._move(EscalationState.LIQUIDATING, "plan complete")
                    except Exception as exc:  # noqa: BLE001 - fail-safe per design (I6)
                        self._last_error = f"step {i} failed: {exc}"
                        self._move(EscalationState.LIQUIDATING, f"plan failed: {exc}")
                        return self._state
                return self._state

            if self._state is EscalationState.LIQUIDATING:
                if self._liquidating_since is None:
                    self._liquidating_since = now
                orders = getattr(self, "_orders", []) or []
                pending = any(o.status.value == "SUBMITTED" for o in orders)
                grace = cfg.grace_period * cfg.liquidation_grace_multiplier
                if not pending or now - self._liquidating_since > grace:
                    detail = (
                        "conversions settled or none required"
                        if not pending
                        else "liquidation grace elapsed (orders unsettled, evidence sealed)"
                    )
                    self._move(EscalationState.DORMANT, detail)
                return self._state

            return self._state

    def journal(self) -> list[Transition]:
        return list(self._journal)

    # -- background thread lifetime (integration parity) ---------------------

    def start(self, tick_interval_s: float = 0.05) -> None:
        if getattr(self, "_thread", None) is not None and self._thread.is_alive():
            return
        self._stop_requested = False
        self._thread = threading.Thread(target=self._run_loop, args=(tick_interval_s,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_requested = True
        if getattr(self, "_thread", None) is not None:
            self._thread.join(timeout=2.0)

    def _run_loop(self, tick_interval_s: float) -> None:
        while not getattr(self, "_stop_requested", False):
            time.sleep(tick_interval_s)
            self.tick()