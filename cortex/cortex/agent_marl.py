# SYSTEM-OWNED STUB (S2): Bootstrap MARL scaffolding. Per AGENTS.md §3, real
# sizing/signal heuristics are meta-learned by the Adaptive Cortex; this stub only
# proves the proposal contract end-to-end and will be replaced by the system.
import uuid

from cortex.proposal_api import OrderDirection, TradeProposal


class AdaptiveCortexAgent:
    """
    The probabilistic intelligence layer. Analyzes market macro flows and
    emits structured TradeProposals to the Iron Constitution. It has zero
    direct execution privileges.
    """

    def __init__(self, agent_id: str = "alpha-sentinel-01"):
        self.agent_id = agent_id

    def evaluate_market_and_propose(
        self,
        asset_id: str,
        market_signal_strength: float,
        current_equity: float,
    ) -> TradeProposal:
        conviction_multiplier = min(max(market_signal_strength, 0.01), 0.05)
        target_notional = max(current_equity * conviction_multiplier, 1.0)

        direction = OrderDirection.BUY if market_signal_strength > 0 else OrderDirection.SELL
        proposal_id = f"{self.agent_id}-{uuid.uuid4().hex[:8]}"

        return TradeProposal(
            proposal_id=proposal_id,
            asset_id=asset_id,
            direction=direction,
            target_notional=round(target_notional, 2),
            max_acceptable_slippage=0.001,
        )
