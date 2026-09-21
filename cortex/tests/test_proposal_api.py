import json
from typing import ClassVar

import pytest
from cortex.proposal_api import (
    OrderDirection,
    TradeProposal,
    parse_constitution_verdict,
)
from pydantic import ValidationError


class TestOrderDirection:
    def test_buy_value(self):
        assert OrderDirection.BUY == "Buy"

    def test_sell_value(self):
        assert OrderDirection.SELL == "Sell"

    def test_roundtrip_from_string(self):
        assert OrderDirection("Buy") is OrderDirection.BUY
        assert OrderDirection("Sell") is OrderDirection.SELL

    def test_invalid_direction_raises(self):
        with pytest.raises(ValueError):
            OrderDirection("hold")


class TestTradeProposal:
    VALID: ClassVar[dict] = {
        "proposal_id": "abc-123",
        "asset_id": "BTC-PERP",
        "direction": "Buy",
        "target_notional": 500.0,
    }

    def test_valid_construction(self):
        p = TradeProposal(**self.VALID)
        assert p.proposal_id == "abc-123"
        assert p.asset_id == "BTC-PERP"
        assert p.direction == OrderDirection.BUY
        assert p.target_notional == 500.0

    def test_default_slippage(self):
        p = TradeProposal(**self.VALID)
        assert p.max_acceptable_slippage == 0.001

    def test_custom_slippage(self):
        p = TradeProposal(**self.VALID, max_acceptable_slippage=0.01)
        assert p.max_acceptable_slippage == 0.01

    def test_invalid_notional_rejected(self):
        for bad in (-100.0, 0.0):
            with pytest.raises(ValidationError):
                kwargs = {k: v for k, v in self.VALID.items() if k != "target_notional"}
                TradeProposal(**kwargs, target_notional=bad)

    def test_negative_slippage_rejected(self):
        with pytest.raises(ValidationError):
            TradeProposal(**self.VALID, max_acceptable_slippage=-0.01)

    def test_to_json_payload_roundtrip(self):
        p = TradeProposal(**self.VALID)
        raw = p.to_json_payload()
        parsed = json.loads(raw)
        assert parsed["proposal_id"] == "abc-123"
        assert parsed["direction"] == "Buy"
        assert parsed["target_notional"] == 500.0

    def test_missing_required_field_rejected(self):
        with pytest.raises(ValidationError):
            TradeProposal(asset_id="X", direction="Buy", target_notional=1.0)


class TestParseConstitutionVerdict:
    def test_valid_json(self):
        raw = json.dumps({"verdict": "Approved", "system_state": "Normal"})
        result = parse_constitution_verdict(raw)
        assert result["verdict"] == "Approved"
        assert result["system_state"] == "Normal"

    def test_nested_payload(self):
        raw = json.dumps({"inner": {"key": "value"}})
        result = parse_constitution_verdict(raw)
        assert result["inner"]["key"] == "value"

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_constitution_verdict("{not json")
