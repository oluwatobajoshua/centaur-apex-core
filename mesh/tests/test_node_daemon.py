import pytest
from mesh.node_daemon import EdgeNodeDaemon
from mesh.pqc_wrapper import PostQuantumCryptoEngine


class TestEdgeNodeDaemon:
    def test_start_stop(self):
        daemon = EdgeNodeDaemon("node-1")
        assert daemon.is_running is False
        daemon.start_heartbeat()
        assert daemon.is_running is True
        daemon.stop_heartbeat()
        assert daemon.is_running is False

    def test_health_telemetry_offline_before_start(self):
        daemon = EdgeNodeDaemon("node-1")
        telemetry = daemon.health_telemetry()
        assert telemetry["node_id"] == "node-1"
        assert telemetry["status"] == "OFFLINE"
        assert "grid" in telemetry

    def test_health_telemetry_online_after_start(self):
        daemon = EdgeNodeDaemon("node-1")
        daemon.start_heartbeat()
        try:
            telemetry = daemon.health_telemetry()
            assert telemetry["status"] == "HEALTHY"
            assert telemetry["reachable_peers"] == 0
        finally:
            daemon.stop_heartbeat()

    def test_health_after_registering_peers(self):
        daemon = EdgeNodeDaemon("node-1")
        daemon.consensus.register_peer("node-2")
        daemon.consensus.register_peer("node-3")
        telemetry = daemon.health_telemetry()
        assert telemetry["active_peers"] == 2

    def test_daemon_has_consensus_and_pqc(self):
        daemon = EdgeNodeDaemon("node-1")
        assert daemon.consensus.node_id == "node-1"
        assert daemon.pqc is not None

    def test_pqc_secured_reflects_provider(self):
        daemon = EdgeNodeDaemon("node-1", pqc_provider=PostQuantumCryptoEngine.PROVIDER_PLACEHOLDER)
        telemetry = daemon.health_telemetry()
        assert telemetry["pqc_secured"] == daemon.pqc.is_post_quantum

    def test_placeholder_provider_disables_pqc_flag(self):
        engine = PostQuantumCryptoEngine(provider=PostQuantumCryptoEngine.PROVIDER_PLACEHOLDER)
        assert engine.is_post_quantum is False
        sig = engine.generate_pqc_signature("msg")
        assert sig.startswith("pqc-dilithium3-placeholder-")


class TestMicrogridTelemetry:
    def test_record_and_snapshot(self):
        daemon = EdgeNodeDaemon("node-1")
        daemon.record_microgrid(voltage_v=238.0, current_a=5.0)
        snapshot = daemon.microgrid.snapshot()
        assert snapshot["samples"] == 1
        assert snapshot["power_w"] == 1190.0
        assert snapshot["grid_state"] == "ON_GRID"

    def test_over_current_is_degraded(self):
        daemon = EdgeNodeDaemon("node-1")
        daemon.record_microgrid(voltage_v=238.0, current_a=999.0)
        health = daemon.microgrid.snapshot()["health"]
        assert health["over_current"] is True
        assert health["degraded"] is True

    def test_bad_voltage_is_degraded(self):
        daemon = EdgeNodeDaemon("node-1")
        daemon.record_microgrid(voltage_v=20.0, current_a=1.0)
        health = daemon.microgrid.snapshot()["health"]
        assert health["under_voltage"] is True

    def test_nan_voltage_rejected(self):
        daemon = EdgeNodeDaemon("node-1")
        with pytest.raises(Exception):  # noqa: B017 - validation error
            daemon.record_microgrid(voltage_v=float("nan"), current_a=1.0)

    def test_bounded_ring(self):
        daemon = EdgeNodeDaemon("node-1")
        hook = daemon.microgrid
        for i in range(hook.max_samples + 50):
            hook.record("node-1", 238.0, float(i % 10))
        assert len(hook) == hook.max_samples