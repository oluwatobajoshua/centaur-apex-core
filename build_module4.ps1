# ==============================================================================
# CENTAUR-APEX: Module 4 Automation Script (Protocol-Agnostic Execution Adapters)
# Generates the schema-first scaffold: JSON-Schema venue contract + order-type
# vocabulary, manifest-gated plugin directories, and the Discovery Agent that
# rejects non-conforming plugins. Mirrors the canonical tracked files exactly.
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "Building Module 4: Protocol-Agnostic Execution Adapters..." -ForegroundColor Cyan

$adapterDirs = @(
    "adapters/adapters/venue_plugins/mock_exchange",
    "adapters/adapters/venue_plugins/mt5_adapter",
    "adapters/schemas",
    "adapters/tests"
)

foreach ($dir in $adapterDirs) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "Created directory: $dir" -ForegroundColor Green
    }
}

Write-Host "Writing adapters/schemas/order_types.jsonschema..." -ForegroundColor Yellow
$orderTypesSchemaContent = @'
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://centaur-apex.core/schemas/order-types/v1",
  "title": "Universal Order Intent Vocabulary",
  "description": "Canonical vocabulary governing order intents that flow through the protocol-agnostic execution layer. Referenced by venue_contract.jsonschema and enforced by adapters/base.py. Genesis DNA (G3).",
  "$defs": {
    "side": { "enum": ["Buy", "Sell"] },
    "orderType": { "enum": ["MARKET", "LIMIT", "STOP", "STOP_LIMIT"] },
    "timeInForce": { "enum": ["GTC", "IOC", "FOK", "DAY"] },
    "executionStatus": { "enum": ["FILLED", "PARTIAL_FILL", "REJECTED", "PENDING", "DRY_RUN"] },
    "orderIntent": {
      "type": "object",
      "additionalProperties": false,
      "required": ["intent_id", "asset_id", "side", "quantity", "max_slippage"],
      "properties": {
        "intent_id": { "type": "string", "minLength": 1 },
        "asset_id": { "type": "string", "minLength": 1 },
        "side": { "$ref": "#/$defs/side" },
        "quantity": { "type": "number", "exclusiveMinimum": 0 },
        "max_slippage": { "type": "number", "minimum": 0 },
        "order_type": { "$ref": "#/$defs/orderType" },
        "time_in_force": { "$ref": "#/$defs/timeInForce" }
      }
    },
    "executionReceipt": {
      "type": "object",
      "additionalProperties": false,
      "required": ["intent_id", "execution_id", "filled_price", "filled_quantity", "status"],
      "properties": {
        "intent_id": { "type": "string", "minLength": 1 },
        "execution_id": { "type": "string", "minLength": 1 },
        "filled_price": { "type": "number", "minimum": 0 },
        "filled_quantity": { "type": "number", "minimum": 0 },
        "status": { "$ref": "#/$defs/executionStatus" }
      }
    }
  }
}
'@
Set-Content -Path "adapters/schemas/order_types.jsonschema" -Value $orderTypesSchemaContent -Encoding UTF8

Write-Host "Writing adapters/schemas/venue_contract.jsonschema..." -ForegroundColor Yellow
$venueContractSchemaContent = @'
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://centaur-apex.core/schemas/venue-contract/v1",
  "title": "Venue Plugin Contract",
  "description": "Manifest contract every venue connector plugin MUST satisfy before the Discovery Agent may load it. Venue plugins (AGENTS.md S1/S6) are system-owned artifacts; this schema is the Genesis-mandated rejection gate.",
  "type": "object",
  "additionalProperties": false,
  "required": ["name", "version", "api_version", "entry_point", "methods", "sides", "order_types"],
  "properties": {
    "name": { "type": "string", "minLength": 1, "pattern": "^[a-z][a-z0-9_]*$" },
    "version": { "type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$" },
    "api_version": { "const": 1 },
    "venue_kind": { "enum": ["exchange", "broker", "custodian"] },
    "entry_point": { "const": "AdapterFactory" },
    "methods": {
      "type": "array",
      "items": { "enum": ["connect", "execute_order", "health_check"] },
      "minItems": 3,
      "uniqueItems": true,
      "contains": { "const": "execute_order" }
    },
    "sides": {
      "type": "array",
      "items": { "$ref": "https://centaur-apex.core/schemas/order-types/v1#/$defs/side" },
      "minItems": 1,
      "uniqueItems": true
    },
    "order_types": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["type", "time_in_force"],
        "properties": {
          "type": { "$ref": "https://centaur-apex.core/schemas/order-types/v1#/$defs/orderType" },
          "time_in_force": { "$ref": "https://centaur-apex.core/schemas/order-types/v1#/$defs/timeInForce" }
        }
      },
      "minItems": 1
    },
    "configuration": { "type": "object" },
    "sandboxed": { "type": "boolean" }
  }
}
'@
Set-Content -Path "adapters/schemas/venue_contract.jsonschema" -Value $venueContractSchemaContent -Encoding UTF8

Write-Host "Writing adapters/pyproject.toml..." -ForegroundColor Yellow
$pyprojectContent = @"
[project]
name = "protocol_agnostic_adapters"
version = "0.1.0"
description = "Universal intent routing and exchange abstraction layer for Centaur-Apex"
dependencies = [
    "pydantic>=2.0.0",
    "requests>=2.31.0",
    "websockets>=11.0",
    "jsonschema>=4.18.0"
]
requires-python = ">=3.10"
"@
Set-Content -Path "adapters/pyproject.toml" -Value $pyprojectContent -Encoding UTF8

Write-Host "Writing adapters/adapters/base.py..." -ForegroundColor Yellow
$baseAdapterContent = @'
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
'@
Set-Content -Path "adapters/adapters/base.py" -Value $baseAdapterContent -Encoding UTF8

Write-Host "Writing adapters/adapters/discovery_agent.py..." -ForegroundColor Yellow
$discoveryAgentContent = @'
import importlib.util
import json
from pathlib import Path
from typing import List, Optional

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from adapters.base import AbstractExchangeAdapter

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"
VENUE_CONTRACT_SCHEMA = "venue_contract.jsonschema"
ORDER_TYPES_SCHEMA = "order_types.jsonschema"


class VenueDiscoveryAgent:
    """
    Monitors venue connectivity and API documentation changes. Dynamically
    drafts, tests, and hot-swaps connector plugins when legacy venues die.

    Genesis gate (G3 / AGENTS.md §3, §7): a venue plugin is loaded ONLY when
    its `manifest.json` validates against `venue_contract.jsonschema`. Manifests
    are JSON — validated WITHOUT executing plugin code (sandbox-first). Only a
    conformant plugin is imported, its `AdapterFactory` instantiated, and the
    result type-checked against `AbstractExchangeAdapter`. Non-conforming
    plugins are rejected with the schema errors.
    """

    def __init__(
        self,
        plugins_dir: str = "adapters/adapters/venue_plugins",
        schemas_dir: Optional[str] = None,
    ):
        self.plugins_dir = Path(plugins_dir)
        self.schemas_dir = Path(schemas_dir) if schemas_dir else SCHEMAS_DIR

    def _schema_registry(self) -> Registry:
        registry = Registry()
        for schema_file in (ORDER_TYPES_SCHEMA, VENUE_CONTRACT_SCHEMA):
            doc = json.loads((self.schemas_dir / schema_file).read_text(encoding="utf-8"))
            registry = registry.with_resource(doc["$id"], Resource.from_contents(doc))
        return registry

    def _validate_manifest(self, manifest: dict) -> List[str]:
        doc = json.loads((self.schemas_dir / VENUE_CONTRACT_SCHEMA).read_text(encoding="utf-8"))
        validator = Draft202012Validator(doc, registry=self._schema_registry())
        return sorted({error.message for error in validator.iter_errors(manifest)})

    def load_active_plugins(self) -> dict:
        plugins = {}
        if not self.plugins_dir.exists():
            return plugins

        for manifest_path in sorted(self.plugins_dir.glob("*/manifest.json")):
            plugin_name = manifest_path.parent.name
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                errors = self._validate_manifest(manifest)
                if errors:
                    print(f"REJECTED venue plugin '{plugin_name}': {errors}")
                    continue
            except (json.JSONDecodeError, KeyError, OSError) as exc:
                print(f"REJECTED venue plugin '{plugin_name}': invalid manifest ({exc})")
                continue

            module_path = manifest_path.parent / "adapter.py"
            spec = importlib.util.spec_from_file_location(plugin_name, str(module_path))
            if spec is None or spec.loader is None:
                print(f"REJECTED venue plugin '{plugin_name}': adapter.py not importable")
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            factory = getattr(module, "AdapterFactory", None)
            if not callable(factory):
                print(f"REJECTED venue plugin '{plugin_name}': missing AdapterFactory entry point")
                continue

            adapter = factory()
            if not isinstance(adapter, AbstractExchangeAdapter):
                print(
                    f"REJECTED venue plugin '{plugin_name}': "
                    "AdapterFactory() must return an AbstractExchangeAdapter"
                )
                continue

            plugins[plugin_name] = adapter
            print(f"Loaded schema-conformant venue adapter plugin: {plugin_name}")
        return plugins
'@
Set-Content -Path "adapters/adapters/discovery_agent.py" -Value $discoveryAgentContent -Encoding UTF8

Write-Host "Writing adapters/adapters/venue_plugins/mock_exchange/..." -ForegroundColor Yellow
$mockExchangeManifest = @'
{
  "name": "mock_exchange",
  "version": "0.1.0",
  "api_version": 1,
  "venue_kind": "exchange",
  "entry_point": "AdapterFactory",
  "methods": ["connect", "execute_order", "health_check"],
  "sides": ["Buy", "Sell"],
  "order_types": [
    { "type": "MARKET", "time_in_force": "IOC" },
    { "type": "MARKET", "time_in_force": "GTC" }
  ],
  "sandboxed": true
}
'@
Set-Content -Path "adapters/adapters/venue_plugins/mock_exchange/manifest.json" -Value $mockExchangeManifest -Encoding UTF8

$mockExchangeAdapterContent = @'
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
'@
Set-Content -Path "adapters/adapters/venue_plugins/mock_exchange/adapter.py" -Value $mockExchangeAdapterContent -Encoding UTF8

Write-Host "Writing adapters/adapters/venue_plugins/mt5_adapter/..." -ForegroundColor Yellow
$mt5AdapterManifest = @'
{
  "name": "mt5_adapter",
  "version": "0.1.0",
  "api_version": 1,
  "venue_kind": "broker",
  "entry_point": "AdapterFactory",
  "methods": ["connect", "execute_order", "health_check"],
  "sides": ["Buy", "Sell"],
  "order_types": [
    { "type": "MARKET", "time_in_force": "IOC" },
    { "type": "MARKET", "time_in_force": "GTC" }
  ],
  "sandboxed": true
}
'@
Set-Content -Path "adapters/adapters/venue_plugins/mt5_adapter/manifest.json" -Value $mt5AdapterManifest -Encoding UTF8

$mt5AdapterContent = @'
# SYSTEM-OWNED STUB (S1): Dynamic venue connector. Per AGENTS.md §3, concrete
# venue adapters are artifacts the system writes (Discovery Agent + Evolution
# Sub-Agent) as venues die or change APIs. This bootstrap stub exists ONLY to
# prove the AbstractExchangeAdapter contract and run integration tests. It is
# replaceable, hot-swappable, and not a permanent 100-year asset.
from typing import Any, Dict, Optional

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
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
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
        if self.login and self.password and self.server:
            if not mt5.login(self.login, password=self.password, server=self.server):
                print(f"Failed to connect to account #{self.login}, error = {mt5.last_error()}")
                mt5.shutdown()
                return False
        self.is_connected = True
        return True

    def get_account_state(self) -> Dict[str, Any]:
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

    def get_live_tick(self, symbol: str) -> Dict[str, Any]:
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
'@
Set-Content -Path "adapters/adapters/venue_plugins/mt5_adapter/adapter.py" -Value $mt5AdapterContent -Encoding UTF8

Set-Content -Path "adapters/adapters/__init__.py" -Value "" -Encoding UTF8

# PowerShell 5.1 Set-Content -Encoding UTF8 writes a BOM, which poisons TOML/JSON
# parsers (pytest rootdir detection). Strip the BOM from every generated file.
$generatedFiles = Get-ChildItem "adapters" -Recurse -File | Where-Object {
    $_.Extension -in ".toml", ".json", ".jsonschema", ".py"
}
foreach ($f in $generatedFiles) {
    $bytes = [System.IO.File]::ReadAllBytes($f.FullName)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        [System.IO.File]::WriteAllBytes($f.FullName, $bytes[3..($bytes.Length - 1)])
        Write-Host "Stripped BOM: $($f.FullName)" -ForegroundColor DarkGray
    }
}

Write-Host "[SUCCESS] Module 4 (Protocol-Agnostic Execution Adapters) generated successfully!" -ForegroundColor Green
Write-Host "Schema-gated venue plugins (mock_exchange, mt5_adapter) + Discovery Agent ready." -ForegroundColor Cyan