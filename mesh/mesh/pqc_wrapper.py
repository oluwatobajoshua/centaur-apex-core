import base64
import hashlib
import hmac

try:
    from oqs import Signature

    _LIBOQS_AVAILABLE = True
except ImportError:  # pragma: no cover - native wheel absent in some sandboxes
    Signature = None  # type: ignore[assignment]
    _LIBOQS_AVAILABLE = False


class PostQuantumCryptoEngine:
    """
    Post-quantum signature engine (G4 distributed cryptographic backbone).

    Primary path: CRYSTALS-Dilithium3 via liboqs (`oqs-python`) — a real
    lattice-based NIST PQC signature scheme. When the native `oqs` binding is
    absent (pure-Python sandbox, no wheel for the platform/ABI), the engine
    degrades to a clearly-labelled deterministic HMAC-SHA3-512 PLACEHOLDER so
    protocols can be exercised end-to-end. `is_post_quantum` reports which path
    is live; fail-safe consumers should refuse to trust artifacts produced by
    the placeholder (DRY_RUN semantics, invariant I6).

    Genesis-by-design: provider/algorithm selection is data-driven and the
    placeholder path never claims to be real cryptography.
    """

    PROVIDER_PLACEHOLDER = "placeholder-hmac-sha3-512"
    PROVIDER_LIBOQS = "liboqs-crystals-dilithium3"
    ALGORITHM_LIBOQS = "Dilithium3"
    SIG_PREFIX = "pqc-dilithium3-"

    def __init__(
        self,
        master_seed: str = "genesis-quantum-seed-secure",
        provider: str | None = None,
    ):
        self._master_secret = master_seed.encode("utf-8")
        self._requested_provider = provider or (
            type(self).PROVIDER_LIBOQS if _LIBOQS_AVAILABLE else type(self).PROVIDER_PLACEHOLDER
        )
        self._public_key = b""
        self._secret_key = b""
        self._signer = None

        if self._requested_provider == type(self).PROVIDER_LIBOQS and _LIBOQS_AVAILABLE:
            self.provider = type(self).PROVIDER_LIBOQS
            self._init_liboqs()
        elif self._requested_provider == type(self).PROVIDER_LIBOQS:
            # Requested real crypto but the binding is unavailable: fail safe
            # by refusing to masquerade as post-quantum.
            raise RuntimeError(
                "liboqs (oqs-python) requested but not importable on this platform; "
                "refusing to silently fall back to placeholder cryptography."
            )
        else:
            self.provider = type(self).PROVIDER_PLACEHOLDER

    @property
    def is_post_quantum(self) -> bool:
        return self.provider == type(self).PROVIDER_LIBOQS

    def get_algorithm(self) -> str:
        if self.is_post_quantum:
            return f"CRYSTALS-{type(self).ALGORITHM_LIBOQS} ({type(self).PROVIDER_LIBOQS})"
        return type(self).PROVIDER_PLACEHOLDER.upper()

    def _init_liboqs(self) -> None:
        self._signer = Signature(type(self).ALGORITHM_LIBOQS)
        self._public_key = self._signer.generate_keypair()
        self._secret_key = self._signer.export_secret_key()

    def generate_pqc_signature(self, message: str) -> str:
        """Sign `message`; returns a self-contained (pubkey-embedded) signature string."""
        if self.is_post_quantum and self._signer is not None:
            raw_sig = self._signer.sign(message.encode("utf-8"), self._secret_key)
            return (
                type(self).SIG_PREFIX
                + base64.b64encode(self._public_key).decode("ascii")
                + "."
                + base64.b64encode(raw_sig).decode("ascii")
            )
        sig = hmac.new(self._master_secret, message.encode("utf-8"), hashlib.sha3_512).hexdigest()
        return f"{type(self).SIG_PREFIX}placeholder-{sig}"

    def verify_pqc_signature(self, message: str, signature: str) -> bool:
        """Verify `signature` for `message`. Placeholder artifacts verify only
        against the placeholder scheme; real artifacts only against Dilithium3."""
        if not isinstance(signature, str) or not signature.startswith(type(self).SIG_PREFIX):
            return False
        if self.is_post_quantum and self._signer is not None:
            body = signature[len(type(self).SIG_PREFIX) :]
            try:
                pub_b64, sig_b64 = body.split(".", 1)
                raw_sig = base64.b64decode(sig_b64, validate=True)
                pub_key = base64.b64decode(pub_b64, validate=True)
            except Exception:  # noqa: BLE001 - malformed envelope never verifies
                return False
            verifier = Signature(type(self).ALGORITHM_LIBOQS)
            try:
                return verifier.verify(message.encode("utf-8"), raw_sig, pub_key)
            except Exception:  # noqa: BLE001 - liboqs raises on signature mismatch
                return False
        expected_sig = self.generate_pqc_signature(message)
        return hmac.compare_digest(expected_sig, signature)

    def close(self) -> None:
        """Release native signer state. No-op for the placeholder provider."""
        if self._signer is not None:
            self._signer.free()
            self._signer = None
        del self._secret_key
        self._secret_key = b""