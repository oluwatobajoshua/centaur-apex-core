import importlib.util
from pathlib import Path


class VenueDiscoveryAgent:
    """
    Monitors venue connectivity and API documentation changes.
    Dynamically drafts, tests, and hot-swaps connector plugins when legacy venues die.
    """

    def __init__(self, plugins_dir: str = "adapters/adapters/venue_plugins"):
        self.plugins_dir = Path(plugins_dir)

    def load_active_plugins(self) -> dict:
        plugins = {}
        if not self.plugins_dir.exists():
            return plugins

        for file_path in self.plugins_dir.glob("*.py"):
            if file_path.name.startswith("__"):
                continue
            module_name = file_path.stem
            spec = importlib.util.spec_from_file_location(module_name, str(file_path))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "AdapterFactory"):
                    plugins[module_name] = module.AdapterFactory()
                    print(f"Loaded hot-swappable venue adapter plugin: {module_name}")
        return plugins
