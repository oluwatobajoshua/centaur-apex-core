

from simulation.chronic_stress import ChronosStressHarness


class TestChronosStressHarness:
    def test_short_run_passes(self):
        harness = ChronosStressHarness(simulated_years=2)
        result = harness.run()
        assert result is True

    def test_policy_called(self):
        calls = []
        harness = ChronosStressHarness(simulated_years=1)
        result = harness.run(policy=lambda eq: calls.append(eq))
        assert result is True
        assert len(calls) > 0

    def test_harness_stores_years(self):
        harness = ChronosStressHarness(simulated_years=500)
        assert harness.simulated_years == 500

    def test_generator_initialized(self):
        harness = ChronosStressHarness()
        assert harness.generator is not None
