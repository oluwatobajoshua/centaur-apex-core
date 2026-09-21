import json
from pathlib import Path

from adapters.base import AbstractExchangeAdapter
from adapters.discovery_agent import VenueDiscoveryAgent

REAL_PLUGINS_DIR = Path(__file__).resolve().parent.parent / "adapters" / "venue_plugins"


class TestVenueDiscoveryAgent:
    def test_load_schema_conformant_plugins(self):
        agent = VenueDiscoveryAgent(plugins_dir=str(REAL_PLUGINS_DIR))
        plugins = agent.load_active_plugins()
        assert "mock_exchange" in plugins
        assert "mt5_adapter" in plugins
        assert all(isinstance(p, AbstractExchangeAdapter) for p in plugins.values())

    def test_nonexistent_dir_returns_empty(self):
        agent = VenueDiscoveryAgent(plugins_dir="/nonexistent/path")
        plugins = agent.load_active_plugins()
        assert plugins == {}

    def test_adapter_factory_returns_instances(self):
        agent = VenueDiscoveryAgent(plugins_dir=str(REAL_PLUGINS_DIR))
        plugins = agent.load_active_plugins()
        for adapter in plugins.values():
            assert hasattr(adapter, "connect")
            assert hasattr(adapter, "execute_order")
            assert hasattr(adapter, "health_check")

    def test_schema_invalid_manifest_plugin_rejected(self, tmp_path, capsys):
        plugin_dir = tmp_path / "rogue"
        plugin_dir.mkdir()
        (plugin_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "name": "rogue",
                    "version": "0.1.0",
                    "api_version": 1,
                    "entry_point": "AdapterFactory",
                    "methods": ["connect", "execute_order", "health_check"],
                    "sides": ["Buy"],
                    "order_types": [{"type": "MARKET_ALL", "time_in_force": "GTC"}],
                }
            ),
            encoding="utf-8",
        )
        (plugin_dir / "adapter.py").write_text(
            "class _Rogue:\n"
            "    def connect(self):\n        return True\n"
            "    def execute_order(self, intent):\n        return None\n"
            "    def health_check(self):\n        return True\n"
            "def AdapterFactory():\n    return _Rogue()\n",
            encoding="utf-8",
        )

        from adapters.discovery_agent import SCHEMAS_DIR

        agent = VenueDiscoveryAgent(plugins_dir=str(tmp_path), schemas_dir=str(SCHEMAS_DIR))
        plugins = agent.load_active_plugins()
        assert "rogue" not in plugins
        assert plugins == {}
        captured = capsys.readouterr().out
        assert "REJECTED venue plugin 'rogue'" in captured
        assert "MARKET_ALL" in captured

    def test_missing_manifest_plugin_rejected(self, tmp_path):
        plugin_dir = tmp_path / "ghost"
        plugin_dir.mkdir()
        (plugin_dir / "adapter.py").write_text(
            "from adapters.base import AbstractExchangeAdapter\n"
            "class GhostAdapter(AbstractExchangeAdapter):\n"
            "    def connect(self):\n        return True\n"
            "    def execute_order(self, intent):\n        return None\n"
            "    def health_check(self):\n        return True\n"
            "def AdapterFactory():\n    return GhostAdapter()\n",
            encoding="utf-8",
        )

        from adapters.discovery_agent import SCHEMAS_DIR

        agent = VenueDiscoveryAgent(plugins_dir=str(tmp_path), schemas_dir=str(SCHEMAS_DIR))
        plugins = agent.load_active_plugins()
        assert plugins == {}

    def test_missing_entry_point_rejected(self, tmp_path):
        plugin_dir = tmp_path / "noentry"
        plugin_dir.mkdir()
        (plugin_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "name": "noentry",
                    "version": "0.1.0",
                    "api_version": 1,
                    "entry_point": "AdapterFactory",
                    "methods": ["connect", "execute_order", "health_check"],
                    "sides": ["Buy"],
                    "order_types": [{"type": "MARKET", "time_in_force": "IOC"}],
                }
            ),
            encoding="utf-8",
        )
        (plugin_dir / "adapter.py").write_text("pass\n", encoding="utf-8")

        from adapters.discovery_agent import SCHEMAS_DIR

        agent = VenueDiscoveryAgent(plugins_dir=str(tmp_path), schemas_dir=str(SCHEMAS_DIR))
        plugins = agent.load_active_plugins()
        assert plugins == {}


class TestVenueContractSchema:
    def test_all_schema_files_load(self):
        agent = VenueDiscoveryAgent(plugins_dir=str(REAL_PLUGINS_DIR))
        registry = agent._schema_registry()
        from adapters.discovery_agent import ORDER_TYPES_SCHEMA, VENUE_CONTRACT_SCHEMA

        for name in (VENUE_CONTRACT_SCHEMA, ORDER_TYPES_SCHEMA):
            assert name in {p.name for p in (agent.schemas_dir).glob("*.jsonschema")}
        assert registry is not None

    def test_mt5_manifest_conforms_to_schema(self):
        mt5_manifest = json.loads(
            (REAL_PLUGINS_DIR / "mt5_adapter" / "manifest.json").read_text(encoding="utf-8")
        )
        agent = VenueDiscoveryAgent(plugins_dir=str(REAL_PLUGINS_DIR))
        assert agent._validate_manifest(mt5_manifest) == []

    def test_missing_required_field_fails(self):
        agent = VenueDiscoveryAgent(plugins_dir=str(REAL_PLUGINS_DIR))
        bad_manifest = {
            "name": "bad",
            "version": "0.1.0",
            "api_version": 1,
            "entry_point": "AdapterFactory",
            "methods": ["connect", "execute_order"],
            "sides": ["Buy"],
            "order_types": [],
        }
        assert agent._validate_manifest(bad_manifest) != []