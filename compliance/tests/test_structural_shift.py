
from compliance.structural_shift import JurisdictionalRoutingEngine


class TestJurisdictionalRoutingEngine:
    def setup_method(self):
        self.engine = JurisdictionalRoutingEngine()

    def test_default_jurisdiction(self):
        assert self.engine.current_jurisdiction == "TAX_HAVEN_OPTIMIZED"

    def test_low_pressure_stays_in_haven(self):
        result = self.engine.evaluate_and_shift(0.5)
        assert result == "TAX_HAVEN_OPTIMIZED"

    def test_high_pressure_shifts_to_global(self):
        result = self.engine.evaluate_and_shift(0.9)
        assert result == "GLOBAL_STANDARD"

    def test_boundary_pressure_shifts(self):
        result = self.engine.evaluate_and_shift(0.86)
        assert result == "GLOBAL_STANDARD"

    def test_exactly_at_threshold_no_shift(self):
        result = self.engine.evaluate_and_shift(0.85)
        assert result == "TAX_HAVEN_OPTIMIZED"

    def test_shift_is_persistent(self):
        self.engine.evaluate_and_shift(0.9)
        assert self.engine.current_jurisdiction == "GLOBAL_STANDARD"
        # Second call with low pressure — jurisdiction remains changed
        result = self.engine.evaluate_and_shift(0.1)
        assert result == "GLOBAL_STANDARD"
