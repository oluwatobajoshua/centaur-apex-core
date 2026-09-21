
from cortex.engine import CortexEngine


class TestCortexEngine:
    def setup_method(self):
        self.engine = CortexEngine(asset_id="ETH-PERP")

    def test_no_action_without_momentum(self):
        result = self.engine.evaluate_market_tick({"price": 100.0})
        assert result["status"] == "NoAction"
        assert result["proposal"] is None

    def test_no_action_with_zero_price(self):
        result = self.engine.evaluate_market_tick(
            {"price": 0.0, "momentum_signal": True, "trend": "bullish"}
        )
        assert result["status"] == "NoAction"

    def test_no_action_neutral_trend(self):
        result = self.engine.evaluate_market_tick(
            {"price": 100.0, "momentum_signal": True, "trend": "neutral"}
        )
        assert result["status"] == "NoAction"

    def test_bullish_generates_buy(self):
        result = self.engine.evaluate_market_tick(
            {"price": 100.0, "momentum_signal": True, "trend": "bullish", "account_equity": 10000}
        )
        assert result["status"] == "ProposalGenerated"
        assert result["proposal"]["direction"] == "Buy"

    def test_bearish_generates_sell(self):
        result = self.engine.evaluate_market_tick(
            {"price": 100.0, "momentum_signal": True, "trend": "bearish", "account_equity": 10000}
        )
        assert result["status"] == "ProposalGenerated"
        assert result["proposal"]["direction"] == "Sell"

    def test_sizing_base_equity(self):
        result = self.engine.evaluate_market_tick(
            {"price": 100.0, "momentum_signal": True, "trend": "bullish", "account_equity": 10000}
        )
        expected = round(10000 * CortexEngine.SIZING_MULTIPLIER, 2)
        assert result["proposal"]["target_notional"] == expected

    def test_high_volatility_halves_sizing(self):
        result = self.engine.evaluate_market_tick(
            {"price": 100.0, "momentum_signal": True, "trend": "bullish",
             "account_equity": 10000, "volatility": 0.05}
        )
        expected = round(10000 * CortexEngine.SIZING_MULTIPLIER * 0.5, 2)
        assert result["proposal"]["target_notional"] == expected

    def test_low_volatility_full_sizing(self):
        result = self.engine.evaluate_market_tick(
            {"price": 100.0, "momentum_signal": True, "trend": "bullish",
             "account_equity": 10000, "volatility": 0.01}
        )
        expected = round(10000 * CortexEngine.SIZING_MULTIPLIER, 2)
        assert result["proposal"]["target_notional"] == expected

    def test_invalid_volatility_fallback(self):
        result = self.engine.evaluate_market_tick(
            {"price": 100.0, "momentum_signal": True, "trend": "bullish",
             "account_equity": 10000, "volatility": "not_a_number"}
        )
        expected = round(10000 * CortexEngine.SIZING_MULTIPLIER, 2)
        assert result["proposal"]["target_notional"] == expected

    def test_proposal_has_timestamp(self):
        result = self.engine.evaluate_market_tick(
            {"price": 100.0, "momentum_signal": True, "trend": "bullish", "account_equity": 10000}
        )
        assert isinstance(result["timestamp"], int)
        assert result["timestamp"] > 0

    def test_proposal_asset_id_matches_engine(self):
        result = self.engine.evaluate_market_tick(
            {"price": 100.0, "momentum_signal": True, "trend": "bullish", "account_equity": 10000}
        )
        assert result["proposal"]["asset_id"] == "ETH-PERP"

    def test_minimum_notional_floor(self):
        result = self.engine.evaluate_market_tick(
            {"price": 100.0, "momentum_signal": True, "trend": "bullish", "account_equity": 1.0}
        )
        assert result["proposal"]["target_notional"] >= 1.0

    def test_missing_account_equity_defaults(self):
        result = self.engine.evaluate_market_tick(
            {"price": 100.0, "momentum_signal": True, "trend": "bullish"}
        )
        assert result["status"] == "ProposalGenerated"
