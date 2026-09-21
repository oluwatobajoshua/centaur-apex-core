import pytest
from doomsday.config import DeadManConfig, StepType
from pydantic import ValidationError


def test_minimal_config_loads_with_defaults():
    cfg = DeadManConfig()
    assert cfg.heartbeat_interval_s == 5.0
    assert cfg.grace_period == 15.0
    assert cfg.escalation_enabled is True
    assert cfg.plan == []


def test_full_plan_loads_from_dict():
    cfg = DeadManConfig.model_validate(
        {
            "heartbeat_interval_s": 2.0,
            "plan": [
                {"step": "notify", "channels": ["ops"]},
                {"step": "halt_placements"},
                {"step": "reduce_exposure", "target_percentage": 50},
                {"step": "acquire_assets", "via": "simulation_oracle", "asset_out": "USDT"},
                {"step": "seal"},
            ],
        }
    )
    assert [s.step for s in cfg.plan] == [
        StepType.NOTIFY,
        StepType.HALT_PLACEMENTS,
        StepType.REDUCE_EXPOSURE,
        StepType.ACQUIRE_ASSETS,
        StepType.SEAL,
    ]
    assert cfg.grace_period == 6.0
    assert cfg.abortable_until_step == 2


def test_unknown_step_type_rejected():
    with pytest.raises(ValidationError):
        DeadManConfig.model_validate({"plan": [{"step": "panic"}]})


def test_negative_cadence_rejected():
    with pytest.raises(ValidationError):
        DeadManConfig(heartbeat_interval_s=-1.0)


def test_target_percentage_out_of_range_rejected():
    with pytest.raises(ValidationError):
        DeadManConfig.model_validate({"plan": [{"step": "reduce_exposure", "target_percentage": 150}]})


def test_closed_vocabulary_via_enum():
    assert set(StepType.__members__) == {
        "NOTIFY",
        "HALT_PLACEMENTS",
        "REDUCE_EXPOSURE",
        "ACQUIRE_ASSETS",
        "SEAL",
    }