"""Doomsday data-driven configuration (G6). Plans, cadence, and oracle wiring
are schema-validated data — the Evolution Sub-Agent owns their values, never
the mechanism."""

from enum import Enum

from pydantic import BaseModel, Field


class StepType(str, Enum):
    NOTIFY = "notify"
    HALT_PLACEMENTS = "halt_placements"
    REDUCE_EXPOSURE = "reduce_exposure"
    ACQUIRE_ASSETS = "acquire_assets"
    SEAL = "seal"


class EscalationStep(BaseModel):
    step: StepType
    channels: list[str] = Field(default_factory=list)
    target_percentage: float | None = Field(default=None, ge=0.0, le=100.0)
    via: str | None = None
    asset_out: str | None = None


class DeadManConfig(BaseModel):
    heartbeat_interval_s: float = Field(default=5.0, gt=0.0)
    grace_multiplier: int = Field(default=3, ge=1)
    escalation_multiplier: int = Field(default=6, ge=1)
    escalation_enabled: bool = True
    abortable_until_step: int = Field(default=2, ge=0)
    liquidation_grace_multiplier: int = Field(default=4, ge=1)
    plan: list[EscalationStep] = Field(default_factory=list)
    oracle: str = "simulation_oracle"
    strict_heartbeat_signing: bool = False
    max_journal_entries: int = Field(default=2048, ge=16)

    @property
    def grace_period(self) -> float:
        return self.heartbeat_interval_s * self.grace_multiplier

    @property
    def escalation_period(self) -> float:
        return self.heartbeat_interval_s * self.escalation_multiplier