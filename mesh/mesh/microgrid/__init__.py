"""Microgrid telemetry hooks for the edge mesh (G4).

Genesis: these are *hooks* — data-driven measurement, guardrail, and health
derivation machinery. Node-specific power hardware integration is the system's
job (S7 asset/handling expansion), not ours.
"""
from mesh.microgrid.telemetry import (
    GRID_ISLANDED,
    GRID_OFFLINE,
    GRID_ONGRID,
    GridHealth,
    MicrogridTelemetryHook,
)

__all__ = [
    "GRID_ISLANDED",
    "GRID_OFFLINE",
    "GRID_ONGRID",
    "GridHealth",
    "MicrogridTelemetryHook",
]