import importlib.util
import json
from pathlib import Path

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
        schemas_dir: str | None = None,
    ):
        self.plugins_dir = Path(plugins_dir)
        self.schemas_dir = Path(schemas_dir) if schemas_dir else SCHEMAS_DIR

    def _schema_registry(self) -> Registry:
        registry = Registry()
        for schema_file in (ORDER_TYPES_SCHEMA, VENUE_CONTRACT_SCHEMA):
            doc = json.loads((self.schemas_dir / schema_file).read_text(encoding="utf-8"))
            registry = registry.with_resource(doc["$id"], Resource.from_contents(doc))
        return registry

    def _validate_manifest(self, manifest: dict) -> list[str]:
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