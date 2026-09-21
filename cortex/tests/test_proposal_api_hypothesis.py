"""Property-based tests for TradeProposal (Cortex proposal API).

Per PRD §5: "property-based Python testing against millions of random market
scenarios." These tests verify invariants that must hold for ANY input, not
just the hand-picked examples in test_proposal_api.py.
"""
import pytest
from cortex.proposal_api import OrderDirection, TradeProposal
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

# Strategy: generate arbitrary valid proposal dicts
arb_valid_proposal = st.fixed_dictionaries({
    "proposal_id": st.text(min_size=1, max_size=64),
    "asset_id": st.text(min_size=1, max_size=32),
    "direction": st.sampled_from(["Buy", "Sell"]),
    "target_notional": st.floats(min_value=0.01, max_value=1_000_000.0,
                                  exclude_min=True, allow_nan=False, allow_infinity=False),
    "max_acceptable_slippage": st.floats(min_value=0.0, max_value=0.5,
                                          allow_nan=False, allow_infinity=False),
})


# Strategy: generate arbitrary invalid notional values (non-positive + NaN)
arb_invalid_notional = st.one_of(
    st.floats(min_value=-1.0, max_value=0.0, allow_nan=False, allow_infinity=False),
    st.just(float("nan")),
)


class TestTradeProposalProperties:
    """Property-based tests for TradeProposal validation."""

    @given(arb_valid_proposal)
    @settings(max_examples=500)
    def test_valid_proposal_always_parses(self, proposal_dict):
        """P1: Any dict with a positive notional must construct a valid TradeProposal."""
        proposal = TradeProposal(**proposal_dict)
        assert proposal.target_notional > 0.0
        assert proposal.direction in OrderDirection

    @given(arb_valid_proposal)
    @settings(max_examples=500)
    def test_roundtrip_is_identity(self, proposal_dict):
        """P2: model_dump() → model_validate() must round-trip cleanly."""
        original = TradeProposal(**proposal_dict)
        dumped = original.model_dump()
        restored = TradeProposal.model_validate(dumped)
        assert restored.proposal_id == original.proposal_id
        assert restored.asset_id == original.asset_id
        assert restored.direction == original.direction
        assert restored.target_notional == pytest.approx(original.target_notional)
        assert restored.max_acceptable_slippage == pytest.approx(original.max_acceptable_slippage)

    @given(arb_invalid_notional)
    @settings(max_examples=100)
    def test_non_positive_notional_rejected(self, notional):
        """P3: Any non-positive notional (including 0 and negative) must raise."""
        assume(notional <= 0.0)
        with pytest.raises(ValidationError):
            TradeProposal(
                proposal_id="test",
                asset_id="BTC-PERP",
                direction=OrderDirection.BUY,
                target_notional=notional,
            )

    @given(
        st.text(min_size=1, max_size=64),
        st.text(min_size=1, max_size=32),
        st.sampled_from(["Buy", "Sell"]),
        st.floats(min_value=0.01, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
        st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=500)
    def test_json_payload_always_serializable(self, pid, asset, direction, notional, slippage):
        """P4: Any valid proposal must serialize to valid JSON."""
        p = TradeProposal(
            proposal_id=pid,
            asset_id=asset,
            direction=direction,
            target_notional=notional,
            max_acceptable_slippage=slippage,
        )
        import json
        parsed = json.loads(p.to_json_payload())
        assert parsed["proposal_id"] == pid
        assert parsed["target_notional"] == notional
        assert parsed["direction"] == direction
