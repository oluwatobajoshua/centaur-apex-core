
from compliance.governance.multisig_dao import CryptographicGovernanceDAO


class TestCryptographicGovernanceDAO:
    def test_default_threshold(self):
        dao = CryptographicGovernanceDAO()
        assert dao.threshold == 5
        assert dao.human_override_locked is True

    def test_denied_when_below_threshold(self):
        dao = CryptographicGovernanceDAO(threshold_signatures_required=3)
        result = dao.request_human_emergency_override(["sig1", "sig2"])
        assert result is False

    def test_approved_when_threshold_met(self):
        dao = CryptographicGovernanceDAO(threshold_signatures_required=3)
        result = dao.request_human_emergency_override(["s1", "s2", "s3"])
        assert result is True

    def test_approved_when_above_threshold(self):
        dao = CryptographicGovernanceDAO(threshold_signatures_required=3)
        result = dao.request_human_emergency_override(["s1", "s2", "s3", "s4"])
        assert result is True

    def test_empty_signatures_denied(self):
        dao = CryptographicGovernanceDAO()
        result = dao.request_human_emergency_override([])
        assert result is False

    def test_human_override_permanently_locked(self):
        dao = CryptographicGovernanceDAO()
        assert dao.human_override_locked is True
        # Even with enough sigs, the override is allowed (threshold met)
        # but human_override_locked remains True — it's a permanent flag
        result = dao.request_human_emergency_override(["s1", "s2", "s3", "s4", "s5"])
        assert result is True
        assert dao.human_override_locked is True
