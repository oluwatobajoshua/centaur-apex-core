from abc import ABC

import pytest
from adapters.base import (
    AbstractExchangeAdapter,
    ExecutionReceipt,
    UniversalOrderIntent,
)


class TestUniversalOrderIntent:
    def test_valid_construction(self):
        intent = UniversalOrderIntent(
            intent_id="i-001",
            asset_id="BTC-PERP",
            side="Buy",
            quantity=1.5,
            max_slippage=0.001,
        )
        assert intent.intent_id == "i-001"
        assert intent.quantity == 1.5

    def test_missing_field_raises(self):
        with pytest.raises(Exception):  # noqa: B017 - schema validation errors
            UniversalOrderIntent(intent_id="i-001")

    @pytest.mark.parametrize("bad_side", ["both", "BUY", "HOLD", ""])
    def test_invalid_side_rejected(self, bad_side):
        with pytest.raises(Exception):  # noqa: B017 - schema validation errors
            UniversalOrderIntent(
                intent_id="i-1",
                asset_id="BTC-PERP",
                side=bad_side,
                quantity=1.0,
                max_slippage=0.001,
            )

    def test_vocabulary_defaults(self):
        intent = UniversalOrderIntent(
            intent_id="i-1", asset_id="BTC-PERP", side="Sell", quantity=1.0, max_slippage=0.001
        )
        assert intent.order_type == "MARKET"
        assert intent.time_in_force == "IOC"

    @pytest.mark.parametrize("bad_status", ["DONE", "FAILED", "", "executed"])
    def test_invalid_execution_status_rejected(self, bad_status):
        with pytest.raises(Exception):  # noqa: B017 - schema validation errors
            ExecutionReceipt(
                intent_id="i-1",
                execution_id="e-1",
                filled_price=100.0,
                filled_quantity=1.0,
                status=bad_status,
            )


class TestExecutionReceipt:
    def test_valid_construction(self):
        receipt = ExecutionReceipt(
            intent_id="i-001",
            execution_id="e-001",
            filled_price=50000.0,
            filled_quantity=1.5,
            status="FILLED",
        )
        assert receipt.status == "FILLED"
        assert receipt.filled_price == 50000.0


class TestAbstractExchangeAdapter:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            AbstractExchangeAdapter()

    def test_is_abc(self):
        assert issubclass(AbstractExchangeAdapter, ABC)

    def test_subclass_must_implement_all(self):
        class Incomplete(AbstractExchangeAdapter):
            pass

        with pytest.raises(TypeError):
            Incomplete()
