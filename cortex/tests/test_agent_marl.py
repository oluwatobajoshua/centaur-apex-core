
from cortex.agent_marl import AdaptiveCortexAgent
from cortex.proposal_api import OrderDirection


class TestAdaptiveCortexAgent:
    def setup_method(self):
        self.agent = AdaptiveCortexAgent(agent_id="test-agent")

    def test_positive_signal_buy(self):
        proposal = self.agent.evaluate_market_and_propose(
            asset_id="BTC-PERP", market_signal_strength=0.03, current_equity=10000
        )
        assert proposal.direction == OrderDirection.BUY

    def test_negative_signal_sell(self):
        proposal = self.agent.evaluate_market_and_propose(
            asset_id="BTC-PERP", market_signal_strength=-0.03, current_equity=10000
        )
        assert proposal.direction == OrderDirection.SELL

    def test_signal_clamped_to_min(self):
        proposal = self.agent.evaluate_market_and_propose(
            asset_id="BTC-PERP", market_signal_strength=0.001, current_equity=10000
        )
        expected_notional = round(max(10000 * 0.01, 1.0), 2)
        assert proposal.target_notional == expected_notional

    def test_signal_clamped_to_max(self):
        proposal = self.agent.evaluate_market_and_propose(
            asset_id="BTC-PERP", market_signal_strength=0.5, current_equity=10000
        )
        expected_notional = round(max(10000 * 0.05, 1.0), 2)
        assert proposal.target_notional == expected_notional

    def test_proposal_id_contains_agent_id(self):
        proposal = self.agent.evaluate_market_and_propose(
            asset_id="BTC-PERP", market_signal_strength=0.03, current_equity=10000
        )
        assert proposal.proposal_id.startswith("test-agent-")

    def test_min_notional_floor(self):
        proposal = self.agent.evaluate_market_and_propose(
            asset_id="BTC-PERP", market_signal_strength=0.03, current_equity=0.01
        )
        assert proposal.target_notional >= 1.0

    def test_default_slippage(self):
        proposal = self.agent.evaluate_market_and_propose(
            asset_id="BTC-PERP", market_signal_strength=0.03, current_equity=10000
        )
        assert proposal.max_acceptable_slippage == 0.001

    def test_zero_signal_direction(self):
        proposal = self.agent.evaluate_market_and_propose(
            asset_id="BTC-PERP", market_signal_strength=0.0, current_equity=10000
        )
        assert proposal.direction == OrderDirection.SELL
