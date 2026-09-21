import mesh.pqc_wrapper as pqc_module
import pytest
from mesh.pqc_wrapper import PostQuantumCryptoEngine


@pytest.fixture()
def placeholder():
    engine = PostQuantumCryptoEngine(provider=PostQuantumCryptoEngine.PROVIDER_PLACEHOLDER)
    yield engine
    engine.close()


class TestPostQuantumCryptoEngine:
    def test_signature_format(self):
        engine = PostQuantumCryptoEngine()
        sig = engine.generate_pqc_signature("test message")
        assert sig.startswith("pqc-dilithium3-")

    def test_signature_deterministic_placeholder(self, placeholder):
        sig1 = placeholder.generate_pqc_signature("hello")
        sig2 = placeholder.generate_pqc_signature("hello")
        assert sig1 == sig2

    def test_different_messages_different_signatures(self, placeholder):
        sig1 = placeholder.generate_pqc_signature("msg1")
        sig2 = placeholder.generate_pqc_signature("msg2")
        assert sig1 != sig2

    def test_verify_valid_signature(self, placeholder):
        msg = "important data"
        sig = placeholder.generate_pqc_signature(msg)
        assert placeholder.verify_pqc_signature(msg, sig) is True

    def test_verify_tampered_signature(self, placeholder):
        sig = placeholder.generate_pqc_signature("data")
        assert placeholder.verify_pqc_signature("data", sig + "x") is False

    def test_verify_wrong_message(self, placeholder):
        sig = placeholder.generate_pqc_signature("msg1")
        assert placeholder.verify_pqc_signature("msg2", sig) is False

    def test_different_seeds_different_signatures(self):
        e1 = PostQuantumCryptoEngine(master_seed="seed-a", provider=PostQuantumCryptoEngine.PROVIDER_PLACEHOLDER)
        e2 = PostQuantumCryptoEngine(master_seed="seed-b", provider=PostQuantumCryptoEngine.PROVIDER_PLACEHOLDER)
        sig1 = e1.generate_pqc_signature("msg")
        sig2 = e2.generate_pqc_signature("msg")
        assert sig1 != sig2

    def test_placeholder_reports_false_post_quantum(self, placeholder):
        assert placeholder.is_post_quantum is False
        assert "PLACEHOLDER" in placeholder.get_algorithm().upper()

    def test_placeholder_prefix_is_explicit(self, placeholder):
        assert placeholder.generate_pqc_signature("x").startswith("pqc-dilithium3-placeholder-")

    def test_garbage_signature_never_verifies(self, placeholder):
        for bad in ("", "not-a-sig", "pqc-dilithium3-", None, "pqc-other-abc"):
            assert placeholder.verify_pqc_signature("msg", bad) is False

    def test_can_verify_signature_from_other_engine_deterministic(self):
        # Placeholder signatures are deterministic and keyless by design.
        e1 = PostQuantumCryptoEngine(provider=PostQuantumCryptoEngine.PROVIDER_PLACEHOLDER)
        e2 = PostQuantumCryptoEngine(provider=PostQuantumCryptoEngine.PROVIDER_PLACEHOLDER)
        sig = e1.generate_pqc_signature("shared")
        assert e2.verify_pqc_signature("shared", sig) is True
        e1.close()
        e2.close()

    def test_requesting_liboqs_without_binding_fails_closed(self):
        # Fail-closed: never silently downgrade requested real crypto.
        if pqc_module._LIBOQS_AVAILABLE:  # pragma: no cover
            pytest.skip("liboqs present on this interpreter")
        with pytest.raises(RuntimeError):
            PostQuantumCryptoEngine(provider=PostQuantumCryptoEngine.PROVIDER_LIBOQS)

    def test_liboqs_real_signing_roundtrip(self):
        pytest.importorskip("oqs", reason="liboqs absent; placeholder path covered elsewhere")
        engine = PostQuantumCryptoEngine(provider=PostQuantumCryptoEngine.PROVIDER_LIBOQS)
        try:
            assert engine.is_post_quantum is True
            assert "Dilithium3" in engine.get_algorithm()
            msg = "governance-state-v1"
            sig = engine.generate_pqc_signature(msg)
            assert sig.startswith("pqc-dilithium3-")
            assert "." in sig
            assert engine.verify_pqc_signature(msg, sig) is True
            assert engine.verify_pqc_signature(msg + "x", sig) is False
            assert engine.verify_pqc_signature("different", sig) is False
        finally:
            engine.close()

    def test_liboqs_signature_self_verifies_across_engines(self):
        pytest.importorskip("oqs", reason="liboqs absent")
        signer = PostQuantumCryptoEngine(provider=PostQuantumCryptoEngine.PROVIDER_LIBOQS)
        verifier = PostQuantumCryptoEngine(provider=PostQuantumCryptoEngine.PROVIDER_LIBOQS)
        try:
            sig = signer.generate_pqc_signature("cross-node")
            assert verifier.verify_pqc_signature("cross-node", sig) is True
        finally:
            signer.close()
            verifier.close()