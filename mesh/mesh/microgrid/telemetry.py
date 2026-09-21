import math
from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator

GRID_ONGRID = "ON_GRID"
GRID_ISLANDED = "ISLANDED"
GRID_OFFLINE = "OFFLINE"

# Constitutional guardrails for a single power sample (voltage in V, current in A).
VOLT_NOMINAL_V = 238.0
VOLT_TOLERANCE = 0.15
CURRENT_MAX_A = 200.0
VOLT_MIN_V = VOLT_NOMINAL_V * (1.0 - VOLT_TOLERANCE)
VOLT_MAX_V = VOLT_NOMINAL_V * (1.0 + VOLT_TOLERANCE)


class PowerSample(BaseModel):
    node_id: str = Field(min_length=1)
    voltage_v: float = Field(gt=0.0)
    current_a: float = Field(ge=0.0)
    grid_state: str = Field(pattern="^(ON_GRID|ISLANDED|OFFLINE)$")
    timestamp: int = Field(ge=0)

    @field_validator("voltage_v", "current_a")
    @classmethod
    def _finite(cls, value: float) -> float:
        # I4: no NaN / Inf in telemetry.
        if math.isnan(value) or value in (float("inf"), float("-inf")):
            raise ValueError("power telemetry must be finite")
        return value


@dataclass
class GridHealth:
    under_voltage: bool = False
    over_voltage: bool = False
    over_current: bool = False
    islanded: bool = False

    @property
    def is_degraded(self) -> bool:
        return any((self.under_voltage, self.over_voltage, self.over_current, self.islanded))

    def to_dict(self) -> dict[str, object]:
        return {
            "under_voltage": self.under_voltage,
            "over_voltage": self.over_voltage,
            "over_current": self.over_current,
            "islanded": self.islanded,
            "degraded": self.is_degraded,
        }


class MicrogridTelemetryHook:
    """Bounded, guardrailed power telemetry ring for one edge node.

    `snapshot()` derives a health assessment from the latest sample and prunes
    stale memory so a 100-year node never grows unbounded state (cf. the
    Constitution's bounded transition journal)."""

    def __init__(self, max_samples: int = 4096, voltage_nominal_v: float = VOLT_NOMINAL_V):
        self._samples: list[PowerSample] = []
        self.max_samples = max(1, max_samples)
        self.voltage_nominal_v = voltage_nominal_v

    def record(self, node_id: str, voltage_v: float, current_a: float, grid_state: str = GRID_ONGRID) -> PowerSample:
        """Record a power telemetry sample (validated, finite, guardrailed)."""
        sample = PowerSample(
            node_id=node_id,
            voltage_v=voltage_v,
            current_a=current_a,
            grid_state=grid_state,
            timestamp=self._now(),
        )
        self._samples.append(sample)
        if len(self._samples) > self.max_samples:
            self._samples = list(self._samples[-self.max_samples :])
        return sample

    def snapshot(self) -> dict[str, object]:
        """Latest sample + derived health + bounded ring stats."""
        if not self._samples:
            return {
                "samples": 0,
                "grid_state": GRID_OFFLINE,
                "power_w": 0.0,
                "health": GridHealth(islanded=False).to_dict(),
            }
        latest: PowerSample = self._samples[-1]
        return {
            "samples": len(self._samples),
            "last_voltage_v": latest.voltage_v,
            "last_current_a": latest.current_a,
            "power_w": round(latest.voltage_v * latest.current_a, 3),
            "grid_state": latest.grid_state,
            "health": self._assess(latest).to_dict(),
        }

    def _assess(self, sample: PowerSample) -> GridHealth:
        volt_min = self.voltage_nominal_v * (1.0 - VOLT_TOLERANCE)
        volt_max = self.voltage_nominal_v * (1.0 + VOLT_TOLERANCE)
        return GridHealth(
            under_voltage=sample.voltage_v < volt_min,
            over_voltage=sample.voltage_v > volt_max,
            over_current=sample.current_a > CURRENT_MAX_A,
            islanded=sample.grid_state == GRID_ISLANDED,
        )

    def _now(self) -> int:
        import time

        return int(time.time() * 1000)

    def __len__(self) -> int:
        return len(self._samples)