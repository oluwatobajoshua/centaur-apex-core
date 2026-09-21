import json
from enum import Enum

from pydantic import BaseModel, Field


class OrderDirection(str, Enum):
    BUY = "Buy"
    SELL = "Sell"


class TradeProposal(BaseModel):
    proposal_id: str = Field(..., description="Unique deterministic hash of the trade strategy")
    asset_id: str = Field(..., description="Target asset identifier e.g., BTC-PERP")
    direction: OrderDirection
    target_notional: float = Field(..., gt=0.0, description="Proposed absolute notional value in USD")
    max_acceptable_slippage: float = Field(default=0.001, ge=0.0)

    def to_json_payload(self) -> str:
        """Serializes the proposal into the exact byte schema expected by the Iron Constitution IPC."""
        return self.model_dump_json()


def parse_constitution_verdict(response_json: str) -> dict:
    """Parses the absolute verdict returned by the Iron Constitution core."""
    return json.loads(response_json)
