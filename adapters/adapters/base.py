from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel

# Canonical vocabulary — must stay in lock-step with
# adapters/schemas/order_types.jsonschema (schema over code, AGENTS.md §7).
Side = Literal["Buy", "Sell"]
OrderType = Literal["MARKET", "LIMIT", "STOP", "STOP_LIMIT"]
TimeInForce = Literal["GTC", "IOC", "FOK", "DAY"]
ExecutionStatus = Literal["FILLED", "PARTIAL_FILL", "REJECTED", "PENDING", "DRY_RUN"]


class UniversalOrderIntent(BaseModel):
    intent_id: str
    asset_id: str
    side: Side
    quantity: float
    max_slippage: float
    order_type: OrderType = "MARKET"
    time_in_force: TimeInForce = "IOC"


class ExecutionReceipt(BaseModel):
    intent_id: str
    execution_id: str
    filled_price: float
    filled_quantity: float
    status: ExecutionStatus


class AbstractExchangeAdapter(ABC):
    """
    Universal abstract interface for asset transfer and order routing.
    Ensures that venue-specific APIs are completely decoupled from core logic.
    """

    @abstractmethod
    def connect(self) -> bool:
        ...

    @abstractmethod
    def execute_order(self, intent: UniversalOrderIntent) -> ExecutionReceipt:
        ...

    @abstractmethod
    def health_check(self) -> bool:
        ...
