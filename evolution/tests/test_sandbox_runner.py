

from evolution.sandbox_runner import (
    SandboxShadowRunner,
    ShadowSimulationConfig,
    ShadowSimulationResult,
)


class TestSandboxShadowRunner:
    def test_stores_patch_id(self):
        runner = SandboxShadowRunner(patch_id="patch-001")
        assert runner.patch_id == "patch-001"

    def test_execute_returns_result_on_default_config(self):
        runner = SandboxShadowRunner(patch_id="patch-001")
        result = runner.execute_shadow_simulation()
        assert isinstance(result, ShadowSimulationResult)
        assert result.passed is True
        assert result.years_simulated == 1
        assert result.final_equity > 0.0
        assert result.worst_drawdown >= 0.0
        assert result.error is None

    def test_shadow_simulation_passes_with_hold_policy(self):
        """A no-op hold policy should survive the synthetic regimes."""
        runner = SandboxShadowRunner(patch_id="patch-002")
        result = runner.execute_shadow_simulation()
        assert result.passed is True
        assert result.years_simulated == 1
        assert result.final_equity > 0.0

    def test_shadow_simulation_fails_on_drawdown_breach(self):
        """A very strict drawdown threshold (0.01) should fail for normal vol."""
        runner = SandboxShadowRunner(patch_id="patch-003")
        result = runner.execute_shadow_simulation(
            config=ShadowSimulationConfig(
                simulated_years=5,
                max_acceptable_drawdown=0.01,
            ),
        )
        assert result.passed is False
        assert result.worst_drawdown > 0.01

    def test_shadow_simulation_fails_on_equity_exhaustion(self):
        """High volatility + low equity + many years should exhaust equity."""
        runner = SandboxShadowRunner(patch_id="patch-004")
        result = runner.execute_shadow_simulation(
            config=ShadowSimulationConfig(
                simulated_years=200,
                start_equity=1_000.0,
                volatility=0.05,
            ),
        )
        assert result.passed is False
        assert result.final_equity <= 0.0
        assert result.error is None

    def test_shadow_simulation_handles_exception(self):
        """An exception in the policy should be caught and reported, not raised."""
        runner = SandboxShadowRunner(patch_id="patch-005")

        def crashing_policy(equity: float):
            raise RuntimeError("candidate code crashed")

        result = runner.execute_shadow_simulation(
            config=ShadowSimulationConfig(simulated_years=1),
            candidate_policy=crashing_policy,
        )
        assert result.passed is False
        assert result.error is not None
        assert "candidate code crashed" in result.error

    def test_config_defaults_are_sane(self):
        cfg = ShadowSimulationConfig()
        assert cfg.simulated_years == 1
        assert cfg.confidence_threshold == 0.999
        assert cfg.start_equity == 1_000_000.0
        assert cfg.max_acceptable_drawdown == 0.99
        assert cfg.volatility == 0.01

    def test_config_supports_custom_parameters(self):
        cfg = ShadowSimulationConfig(
            simulated_years=3,
            start_equity=500_000.0,
            max_acceptable_drawdown=0.20,
        )
        assert cfg.simulated_years == 3
        assert cfg.start_equity == 500_000.0
        assert cfg.max_acceptable_drawdown == 0.20

    def test_elapsed_seconds_is_recorded(self):
        runner = SandboxShadowRunner(patch_id="patch-006")
        result = runner.execute_shadow_simulation()
        assert result.elapsed_seconds > 0.0
        assert result.elapsed_seconds < 60.0

    def test_candidate_policy_receives_equity(self):
        """The policy callable is invoked with the current equity each tick."""
        received = []

        def observer_policy(equity: float):
            received.append(equity)

        runner = SandboxShadowRunner(patch_id="patch-007")
        runner.execute_shadow_simulation(
            candidate_policy=observer_policy,
        )
        assert len(received) > 0
        assert all(eq > 0.0 for eq in received[:10])
