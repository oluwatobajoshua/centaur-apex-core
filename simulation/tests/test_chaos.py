"""Pytest tests for the chaos engineering engine.

Validates that the system handles three failure scenarios correctly:
1. Daemon crash — connection loss detected
2. Corrupted packets — malformed frames handled gracefully
3. Flash crash — EmergencyHalt + two-phase recovery
"""
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TESTS_DIR = os.path.join(ROOT, "simulation", "tests")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "simulation"))
sys.path.insert(0, TESTS_DIR)

import chaos_engine

ChaosEngine = chaos_engine.ChaosEngine

DAEMON_NAME = "constitutiond.exe" if os.name == "nt" else "constitutiond"
CONSTITUTIOND = os.path.join(ROOT, "constitution", "target", "debug", DAEMON_NAME)

REQUIRES_DAEMON = pytest.mark.skipif(
    not os.path.exists(CONSTITUTIOND),
    reason="constitutiond binary not built (run: cargo build in constitution/)",
)


@REQUIRES_DAEMON
def test_corrupted_packets_handled():
    """Malformed IPC frames must be rejected without crashing the daemon."""
    engine = ChaosEngine()
    result = engine.scenario_corrupted_packets()

    assert result.passed, f"Corrupted packet handling failed: {result.details}"
    assert result.metrics["daemon_alive_after_attacks"] is True, (
        "daemon must survive all packet corruption attacks"
    )


@REQUIRES_DAEMON
def test_daemon_crash_detected():
    """Killing the daemon must be detectable by the IPC client."""
    engine = ChaosEngine()
    result = engine.scenario_daemon_crash()

    assert result.passed, (
        f"Daemon crash detection failed: {result.details}. "
        "IPC client must detect the connection loss when the daemon dies."
    )


@REQUIRES_DAEMON
def test_flash_crash_triggers_recovery():
    """Extreme market regimes must trigger EmergencyHalt + two-phase recovery."""
    engine = ChaosEngine()
    result = engine.scenario_flash_crash()

    assert result.passed, (
        f"Flash crash scenario failed: {result.details}. "
        f"Metrics: {result.metrics}"
    )
    assert result.metrics["emergency_halt_triggered"] is True
    assert result.metrics["recovery_phase1"] is True
    assert result.metrics["recovery_phase2"] is True
    assert result.metrics["daemon_alive_after_flash_crash"] is True


@REQUIRES_DAEMON
def test_all_scenarios_pass():
    """All chaos scenarios must pass together."""
    engine = ChaosEngine()
    results = engine.run_all()

    for r in results:
        assert r.passed, f"{r.scenario} failed: {r.details}"

    # Verify all three scenarios ran
    scenario_names = {r.scenario for r in results}
    assert "corrupted_packets" in scenario_names
    assert "daemon_crash" in scenario_names
    assert "flash_crash" in scenario_names
