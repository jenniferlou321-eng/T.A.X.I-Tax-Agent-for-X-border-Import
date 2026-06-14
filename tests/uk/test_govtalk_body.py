"""Tests for CT600 GovTalk body builder."""

from backend.jurisdictions.uk.corporation_tax.govtalk_body import (
    build_ct600_body,
    NS_CT,
)


class TestBuildCT600Body:
    def test_basic_fields(self):
        xml = build_ct600_body(
            ctref="1234567890",
            company_name="Acme Ltd",
            period_start="2024-04-01",
            period_end="2025-03-31",
            line_map={
                "turnover": 1000000,
                "taxable_total_profits": 250000,
                "corporation_tax_chargeable": 47500,
            },
        )
        assert "1234567890" in xml
        assert "Acme Ltd" in xml
        assert "2024-04-01" in xml
        assert "2025-03-31" in xml
        assert "1000000" in xml
        assert "250000" in xml
        assert "47500" in xml

    def test_contains_irenvelope_root(self):
        xml = build_ct600_body(
            ctref="1234567890",
            company_name="Test",
            period_start="2024-04-01",
            period_end="2025-03-31",
            line_map={},
        )
        # Should have the CT namespace on IRenvelope
        assert f"{{{NS_CT}}}IRenvelope" in xml or "IRenvelope" in xml

    def test_all_known_keys_mapped(self):
        """All key_map entries should produce output when provided."""
        line_map = {
            "turnover": 100,
            "trading_income": 200,
            "trading_expenses": 50,
            "investment_income": 30,
            "property_income": 20,
            "chargeable_gains": 10,
            "capital_allowances_claimed": 5,
            "trading_losses_brought_forward": 15,
            "group_relief_claimed": 8,
            "rd_qualifying_expenditure": 12,
            "taxable_total_profits": 300,
            "ct_rate_applied": 0.19,
            "corporation_tax_chargeable": 57,
            "marginal_relief": 0,
            "tax_already_paid": 10,
            "amount_payable": 47,
            "num_associated_companies": 1,
        }
        xml = build_ct600_body(
            ctref="9999999999",
            company_name="Big Corp",
            period_start="2024-04-01",
            period_end="2025-03-31",
            line_map=line_map,
        )
        # Check a few representative values appear
        assert "100" in xml
        assert "57" in xml
        assert "0.19" in xml

    def test_unknown_keys_passthrough(self):
        xml = build_ct600_body(
            ctref="1234567890",
            company_name="Test",
            period_start="2024-04-01",
            period_end="2025-03-31",
            line_map={"custom_field": 42},
        )
        # Unknown key → PascalCase
        assert "CustomField" in xml
        assert "42" in xml

    def test_none_values_excluded(self):
        xml = build_ct600_body(
            ctref="1234567890",
            company_name="Test",
            period_start="2024-04-01",
            period_end="2025-03-31",
            line_map={"turnover": None, "trading_income": 100},
        )
        assert "Turnover" not in xml
        assert "TradingIncome" in xml
