from abc import ABC, abstractmethod

from pydantic import BaseModel


class UniversalOrderIntent(BaseModel):
    intent_id: str
    asset_id: str
    side: str
    quantity: float
    max_slippage: float


class ExecutionReceipt(BaseModel):
    intent_id: str
    execution_id: str
    filled_price: float
    filled_quantity: float
    status: str


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
