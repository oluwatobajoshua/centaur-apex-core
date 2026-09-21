
from compliance.tax_parser import GlobalTaxRegulatoryParser


class TestGlobalTaxRegulatoryParser:
    def setup_method(self):
        self.parser = GlobalTaxRegulatoryParser()

    def test_known_jurisdiction_rates(self):
        assert self.parser.fetch_current_tax_rate("GLOBAL_STANDARD") == 0.15
        assert self.parser.fetch_current_tax_rate("RESTRICTED_ZONE_A") == 0.35
        assert self.parser.fetch_current_tax_rate("TAX_HAVEN_OPTIMIZED") == 0.05

    def test_unknown_jurisdiction_default(self):
        assert self.parser.fetch_current_tax_rate("UNKNOWN_ZULU") == 0.20

    def test_compliance_passes_for_normal_asset(self):
        assert self.parser.audit_compliance_status("BTC", "GLOBAL_STANDARD") is True

    def test_compliance_fails_for_restricted_asset(self):
        assert self.parser.audit_compliance_status("BANNED_TOKEN_X", "GLOBAL_STANDARD") is False

    def test_compliance_fails_for_sanctioned_asset(self):
        assert self.parser.audit_compliance_status("SANCTIONED_ASSET_Y", "TAX_HAVEN_OPTIMIZED") is False

    def test_compliance_passes_for_non_restricted(self):
        assert self.parser.audit_compliance_status("ETH", "RESTRICTED_ZONE_A") is True
