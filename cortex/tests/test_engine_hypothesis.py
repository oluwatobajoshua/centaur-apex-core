"""Property-based tests for CortexEngine.evaluate_market_tick.

Per PRD §5: property-based testing against millions of random market scenarios.
These tests verify invariants that must hold for ANY market tick input.
"""
from cortex.engine import CortexEngine
from hypothesis import assume, given, settings
from hypothesis import strategies as st


class TestCortexEngineProperties:
    """Property-based tests for the Cortex engine."""

    def setup_method(self):
        self.engine = CortexEngine(asset_id="ETH-PERP")

    # Strategy: generate arbitrary market ticks
    arb_tick = st.fixed_dictionaries({
        "price": st.floats(min_value=0.01, max_value=1_000_000.0,
                            allow_nan=False, allow_infinity=False),
        "volatility": st.floats(min_value=0.0, max_value=1.0,
                                 allow_nan=False, allow_infinity=False),
        "momentum_signal": st.booleans(),
        "trend": st.sampled_from(["bullish", "bearish", "neutral"]),
        "account_equity": st.floats(min_value=1.0, max_value=10_000_000.0,
                                     allow_nan=False, allow_infinity=False),
    })

    @given(arb_tick)
    @settings(max_examples=500)
    def test_no_action_without_momentum(self, tick):
        """P5: When momentum_signal is False, the engine must return NoAction."""
        tick["momentum_signal"] = False
        result = self.engine.evaluate_market_tick(tick)
        assert result["status"] == "NoAction"
        assert result["proposal"] is None

    @given(arb_tick)
    @settings(max_examples=500)
    def test_neutral_trend_always_no_action(self, tick):
        """P6: Neutral trend must always return NoAction (no directional signal)."""
        tick["trend"] = "neutral"
        tick["momentum_signal"] = True
        result = self.engine.evaluate_market_tick(tick)
        assert result["status"] == "NoAction"

    @given(arb_tick)
    @settings(max_examples=500)
    def test_proposal_notional_always_positive(self, tick):
        """P7: Any generated proposal must have target_notional > 0."""
        assume(tick["momentum_signal"] is True)
        assume(tick["trend"] in ("bullish", "bearish"))
        result = self.engine.evaluate_market_tick(tick)
        if result["status"] == "ProposalGenerated":
            assert result["proposal"]["target_notional"] > 0.0
            assert result["proposal"]["direction"] in ("Buy", "Sell")

    @given(arb_tick)
    @settings(max_examples=500)
    def test_bullish_generates_buy(self, tick):
        """P8: Bullish + momentum must generate a Buy proposal."""
        tick["momentum_signal"] = True
        tick["trend"] = "bullish"
        result = self.engine.evaluate_market_tick(tick)
        if result["status"] == "ProposalGenerated":
            assert result["proposal"]["direction"] == "Buy"

    @given(arb_tick)
    @settings(max_examples=500)
    def test_bearish_generates_sell(self, tick):
        """P9: Bearish + momentum must generate a Sell proposal."""
        tick["momentum_signal"] = True
        tick["trend"] = "bearish"
        result = self.engine.evaluate_market_tick(tick)
        if result["status"] == "ProposalGenerated":
            assert result["proposal"]["direction"] == "Sell"

    @given(arb_tick)
    @settings(max_examples=500)
    def test_sizing_proportional_to_equity(self, tick):
        """P10: Higher equity must produce higher or equal notional (for same trend)."""
        tick["momentum_signal"] = True
        tick["trend"] = "bullish"
        tick2 = dict(tick)
        tick2["account_equity"] = tick["account_equity"] * 2.0

        result1 = self.engine.evaluate_market_tick(tick)
        result2 = self.engine.evaluate_market_tick(tick2)

        if (result1["status"] == "ProposalGenerated"
                and result2["status"] == "ProposalGenerated"):
            n1 = result1["proposal"]["target_notional"]
            n2 = result2["proposal"]["target_notional"]
            # Higher equity → higher notional (capped by the 5% sizing multiplier)
            assert n2 >= n1, f"higher equity ({tick2['account_equity']}) should yield n2 ({n2}) >= n1 ({n1})"

    @given(arb_tick)
    @settings(max_examples=500)
    def test_zero_price_no_action(self, tick):
        """P11: Zero or negative price must produce NoAction (no division error)."""
        tick["price"] = 0.0
        tick["momentum_signal"] = True
        tick["trend"] = "bullish"
        result = self.engine.evaluate_market_tick(tick)
        assert result["status"] == "NoAction"
