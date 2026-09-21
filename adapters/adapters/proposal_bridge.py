"""Proposal-to-intent bridge — G3 Genesis DNA (protocol-agnostic abstraction layer).

Defines the single conversion point between the Cortex domain model
(`TradeProposal`) and the adapter domain model (`UniversalOrderIntent`).
Per AGENTS.md §3 (G3), this is the universal intent routing mechanism — it
contains no venue-specific or strategy-specific logic. The specific price
reference and routing decisions are injected; this module only enforces the
type-correct shape crossing the Cortex → Adapter boundary.
"""

from cortex.proposal_api import TradeProposal

from adapters.base import UniversalOrderIntent


def proposal_to_intent(
    proposal: TradeProposal,
    price: float,
    intent_id: str | None = None,
) -> UniversalOrderIntent:
    """Convert a Cortex TradeProposal into an adapter UniversalOrderIntent.

    Args:
        proposal: The approved TradeProposal from the Adaptive Cortex.
        price: The reference market price for converting notional to quantity.
        intent_id: Optional explicit intent ID; defaults to the proposal's ID.

    Returns:
        A UniversalOrderIntent ready for `AbstractExchangeAdapter.execute_order`.

    Raises:
        ValueError: If price is zero or negative (cannot compute quantity).
    """
    if price <= 0.0:
        raise ValueError(f"price must be positive, got {price}")

    return UniversalOrderIntent(
        intent_id=intent_id or proposal.proposal_id,
        asset_id=proposal.asset_id,
        side=proposal.direction.value,
        quantity=proposal.target_notional / price,
        max_slippage=proposal.max_acceptable_slippage,
        order_type="MARKET",
        time_in_force="IOC",
    )


def verdict_to_order_action(
    verdict: dict,
    proposal: TradeProposal,
    price: float,
) -> UniversalOrderIntent | None:
    """Convert a Constitution verdict + approved proposal into an execution intent.

    Returns None if the proposal was rejected or triggered an emergency liquidation
    (the Constitution's verdict is the sole authority on whether an order may be
    placed — Invariant I5: no code outside constitution/ routes or signs orders).
    """
    if not isinstance(verdict, dict):
        return None

    if "Approved" in verdict:
        approved = verdict["Approved"]
        adjusted_notional = approved.get("adjusted_notional", proposal.target_notional)
        approved_proposal = proposal.model_copy(
            update={"target_notional": adjusted_notional}
        )
        return proposal_to_intent(approved_proposal, price, intent_id=proposal.proposal_id)

    # Rejected or EmergencyLiquidationAll — no order to route
    return None
