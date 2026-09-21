import os
import sys

ROOT = os.path.abspath(os.path.dirname(__file__))

for package_home in ("cortex", "adapters", "evolution", "mesh", "compliance", "simulation", "doomsday"):
    home = os.path.join(ROOT, package_home)
    if home not in sys.path:
        sys.path.insert(0, home)