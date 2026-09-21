# SYSTEM-OWNED STUB (S1): Dynamic venue connector. Per AGENTS.md §3, concrete
# venue adapters are artifacts the system writes (Discovery Agent + Evolution
# Sub-Agent) as venues die or change APIs. This bootstrap stub exists ONLY to
# prove the AbstractExchangeAdapter contract and run integration tests. It is
# replaceable, hot-swappable, and not a permanent 100-year asset.
from typing import Any

from adapters.base import (
    AbstractExchangeAdapter,
    ExecutionReceipt,
    UniversalOrderIntent,
)

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - MT5 terminal may be absent in CI/sandbox
    mt5 = None


class MT5VenueAdapter(AbstractExchangeAdapter):
    """MetaTrader 5 connector conforming to the universal execution interface."""

    def __init__(
        self,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
    ):
        self.login = login
        self.password = password
        self.server = server
        self.is_connected = False

    def connect(self) -> bool:
        if mt5 is None:
            print("MT5 package not installed; adapter in dry-run mode.")
            self.is_connected = True
            return True
        if not mt5.initialize():
            print(f"MT5 initialization failed, error code = {mt5.last_error()}")
            return False
        if self.login and self.password and self.server and not mt5.login(
            self.login, password=self.password, server=self.server
        ):
                print(f"Failed to connect to account #{self.login}, error = {mt5.last_error()}")
                mt5.shutdown()
                return False
        self.is_connected = True
        return True

    def get_account_state(self) -> dict[str, Any]:
        if not self.is_connected:
            raise ConnectionError("MT5 Adapter is not connected.")
        if mt5 is None:
            return {"total_equity": 0.0, "cash_balance": 0.0, "margin_free": 0.0, "leverage": 0}
        acc_info = mt5.account_info()
        if acc_info is None:
            return {}
        return {
            "total_equity": acc_info.equity,
            "cash_balance": acc_info.balance,
            "margin_free": acc_info.margin_free,
            "leverage": acc_info.leverage,
        }

    def get_live_tick(self, symbol: str) -> dict[str, Any]:
        if mt5 is None:
            return {"symbol": symbol, "bid": 0.0, "ask": 0.0, "time": 0}
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {}
        return {"symbol": symbol, "bid": tick.bid, "ask": tick.ask, "time": tick.time}

    def execute_order(self, intent: UniversalOrderIntent) -> ExecutionReceipt:
        if not self.is_connected:
            raise ConnectionError("MT5 not connected.")
        if mt5 is None:
            return ExecutionReceipt(
                intent_id=intent.intent_id,
                execution_id="mt5-dryrun",
                filled_price=0.0,
                filled_quantity=0.0,
                status="DRY_RUN",
            )
        return self._send_order(intent)

    def _send_order(self, intent: UniversalOrderIntent) -> ExecutionReceipt:
        symbol_info = mt5.symbol_info(intent.asset_id)
        if symbol_info is None or not symbol_info.visible:
            mt5.symbol_select(intent.asset_id, True)
        tick = mt5.symbol_info_tick(intent.asset_id)
        order_type = (
            mt5.ORDER_TYPE_BUY if intent.side.lower() == "buy" else mt5.ORDER_TYPE_SELL
        )
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": intent.asset_id,
            "volume": float(intent.quantity),
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 20260901,
            "comment": "CentaurApex-Core-Execution",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        filled = getattr(result, "price", 0.0) or 0.0
        return ExecutionReceipt(
            intent_id=intent.intent_id,
            execution_id=str(getattr(result, "deal", "none")),
            filled_price=filled,
            filled_quantity=float(getattr(result, "volume", intent.quantity) or 0.0),
            status="FILLED" if getattr(result, "retcode", -1) == mt5.TRADE_RETCODE_DONE else "REJECTED",
        )

    def health_check(self) -> bool:
        return self.is_connected

    def disconnect(self) -> None:
        if self.is_connected and mt5 is not None:
            mt5.shutdown()
        self.is_connected = False


def AdapterFactory() -> AbstractExchangeAdapter:
    return MT5VenueAdapter()