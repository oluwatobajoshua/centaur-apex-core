# SYSTEM-OWNED STUB (S1): Reference venue connector. Per AGENTS.md §3, venue
# connectors are artifacts the system writes. This mock exists only to exercise
# the universal execution interface in tests/sandbox; not a permanent asset.
from adapters.base import (
    AbstractExchangeAdapter,
    ExecutionReceipt,
    UniversalOrderIntent,
)


class MockExchangeAdapter(AbstractExchangeAdapter):
    """Reference implementation of an exchange connector conforming to the universal interface."""

    def connect(self) -> bool:
        print("Connected to Mock Execution Venue.")
        return True

    def execute_order(self, intent: UniversalOrderIntent) -> ExecutionReceipt:
        print(f"Executing intent {intent.intent_id} on Mock Venue for {intent.asset_id}")
        return ExecutionReceipt(
            intent_id=intent.intent_id,
            execution_id="exec-mock-9988",
            filled_price=50000.0,
            filled_quantity=intent.quantity,
            status="FILLED",
        )

    def health_check(self) -> bool:
        return True


def AdapterFactory() -> AbstractExchangeAdapter:
    return MockExchangeAdapter()