"""Pytest wrapper for the full-stack integration test.

Cortex → Constitution → Adapter → Mock Exchange.
Delegates to the standalone harness in integration_full_pipeline.py but
asserts on the result dict so failures are caught in CI.
"""
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
TESTS_DIR = os.path.join(ROOT, "simulation", "tests")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "cortex"))
sys.path.insert(0, os.path.join(ROOT, "adapters"))
sys.path.insert(0, os.path.join(ROOT, "simulation"))
sys.path.insert(0, TESTS_DIR)

import integration_full_pipeline

run_full_pipeline = integration_full_pipeline.run_full_pipeline

DAEMON_NAME = "constitutiond.exe" if os.name == "nt" else "constitutiond"
CONSTITUTIOND = os.path.join(ROOT, "constitution", "target", "debug", DAEMON_NAME)


def test_constitutiond_built():
    """The integration test requires a compiled constitutiond binary."""
    if not os.path.exists(CONSTITUTIOND):
        pytest.fail(
            f"constitutiond binary not found at {CONSTITUTIOND}. "
            "Run `cargo build` in constitution/ first."
        )


@pytest.mark.skipif(
    not os.path.exists(CONSTITUTIOND),
    reason="constitutiond binary not built (run: cargo build in constitution/)",
)
def test_full_pipeline_integration():
    """Exercise the full Cortex → Constitution → MockExchange pipeline."""
    report = run_full_pipeline()

    assert report["passed"], f"Pipeline failed: {report}"
    assert report["proposals"] > 0, "Should have generated at least one proposal"
    assert report["approved"] > 0, "At least one proposal should be approved"
    assert report["executions"] == report["approved"], (
        "Every approved proposal must be executed"
    )
    assert report["emergency"] == 0, "No emergency liquidations expected in normal scenarios"
    assert "Normal" in report["states_seen"], "System should remain in Normal state"


@pytest.mark.skipif(
    not os.path.exists(CONSTITUTIOND),
    reason="constitutiond binary not built (run: cargo build in constitution/)",
)
def test_constitution_adjudicates_concentration_limit():
    """The Constitution must reject proposals that breach the concentration limit (I3)."""
    report = run_full_pipeline()

    if report["rejected"] > 0:
        reasons = report["rejections_by_reason"]
        assert any(
            "Concentration" in reason for reason in reasons
        ), f"Expected concentration rejection, got: {reasons}"
