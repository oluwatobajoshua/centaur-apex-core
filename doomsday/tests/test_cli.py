import json

import pytest
from doomsday.cli import (
    _default_config,
    _load_config,
    build_parser,
    cmd_self_test,
    main,
)
from doomsday.config import StepType
from doomsday.daemon import DeadManSwitchDaemon, EscalationState


class TestDoomsdayCLI:
    def test_self_test_passes(self):
        """The CLI self-test must validate the full FSM in both directions."""
        assert cmd_self_test() == 0

    def test_build_parser_has_all_subcommands(self):
        parser = build_parser()
        args = parser.parse_args(["--self-test"])
        assert args.self_test is True

        args = parser.parse_args(["--run"])
        assert args.run is True

        args = parser.parse_args(["--beat"])
        assert args.beat is True

        args = parser.parse_args(["--status"])
        assert args.status is True

        args = parser.parse_args(["--disarm", "my-key"])
        assert args.disarm == "my-key"

    def test_no_args_prints_help(self):
        assert main([]) == 0  # no subcommands → prints help

    def test_disarm_wrong_key_raises(self):
        config = _default_config()
        daemon = DeadManSwitchDaemon(config=config, governance_key="secret-key")
        with pytest.raises(PermissionError):
            daemon.disarm("wrong-key")

    def test_disarm_correct_key_accepted(self):
        config = _default_config()
        daemon = DeadManSwitchDaemon(config=config, governance_key="secret-key")
        daemon.disarm("secret-key")
        assert daemon.state == EscalationState.ARMED

    def test_default_config_has_escalation_plan(self):
        cfg = _default_config()
        assert cfg.escalation_enabled is True
        assert len(cfg.plan) == 5
        step_types = [s.step for s in cfg.plan]
        assert StepType.SEAL in step_types
        assert StepType.ACQUIRE_ASSETS in step_types

    def test_load_config_from_json(self, tmp_path):
        cfg_file = tmp_path / "doomsday.json"
        cfg_file.write_text(
            json.dumps({
                "heartbeat_interval_s": 2.0,
                "grace_multiplier": 2,
                "escalation_multiplier": 3,
                "plan": [],
                "oracle": "simulation_oracle",
                "strict_heartbeat_signing": False,
                "max_journal_entries": 1024,
                "abortable_until_step": 1,
                "liquidation_grace_multiplier": 2,
            })
        )
        cfg = _load_config(str(cfg_file), 5.0)
        assert cfg.heartbeat_interval_s == 2.0
        assert cfg.grace_multiplier == 2
        assert cfg.escalation_multiplier == 3

    def test_load_config_fallback_to_default(self):
        cfg = _load_config("/nonexistent/path.json", 3.0)
        assert cfg.heartbeat_interval_s == 3.0
        assert cfg.escalation_enabled is True

    def test_main_self_test_invocation(self):
        assert main(["--self-test"]) == 0

    def test_heartbeat_interval_arg(self):
        parser = build_parser()
        args = parser.parse_args(["--run", "--heartbeat-interval", "1.5"])
        assert args.heartbeat_interval == 1.5
