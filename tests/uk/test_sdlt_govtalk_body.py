"""Tests for SDLT GovTalk body builder."""

from backend.jurisdictions.uk.stamp_duty.govtalk_body import (
    build_sdlt_body,
    NS_SDLT,
)


class TestBuildSDLTBody:
    def test_basic_fields(self):
        xml = build_sdlt_body(
            utr="1234567890123",
            transaction_id="TX-001",
            effective_date="2024-06-15",
            line_map={
                "property_value": 500000,
                "property_type": "residential",
                "buyer_type": "individual",
                "sdlt_payable": 12500,
                "effective_rate": 0.025,
            },
        )
        assert "1234567890123" in xml
        assert "TX-001" in xml
        assert "2024-06-15" in xml
        assert "500000" in xml
        assert "12500" in xml
        assert "residential" in xml

    def test_contains_irenvelope_root(self):
        xml = build_sdlt_body(
            utr="1234567890123",
            transaction_id="TX-001",
            effective_date="2024-06-15",
            line_map={},
        )
        assert "IRenvelope" in xml
        assert "SDLTReturn" in xml

    def test_property_section(self):
        xml = build_sdlt_body(
            utr="1234567890123",
            transaction_id="TX-001",
            effective_date="2024-06-15",
            line_map={
                "property_value": 750000,
                "property_type": "non-residential",
                "buyer_type": "company",
            },
        )
        assert "Property" in xml
        assert "non-residential" in xml
        assert "company" in xml

    def test_additional_dwelling_surcharge(self):
        xml = build_sdlt_body(
            utr="1234567890123",
            transaction_id="TX-001",
            effective_date="2024-06-15",
            line_map={
                "property_value": 400000,
                "is_additional_dwelling": True,
            },
        )
        assert "AdditionalDwelling" in xml
        assert "true" in xml

    def test_no_additional_dwelling_when_false(self):
        xml = build_sdlt_body(
            utr="1234567890123",
            transaction_id="TX-001",
            effective_date="2024-06-15",
            line_map={
                "property_value": 400000,
                "is_additional_dwelling": False,
            },
        )
        assert "AdditionalDwelling" not in xml

    def test_address_with_postcode(self):
        xml = build_sdlt_body(
            utr="1234567890123",
            transaction_id="TX-001",
            effective_date="2024-06-15",
            line_map={
                "property_value": 500000,
                "property_address_postcode": "SW1A 1AA",
            },
        )
        assert "Address" in xml
        assert "SW1A 1AA" in xml

    def test_no_address_without_postcode(self):
        xml = build_sdlt_body(
            utr="1234567890123",
            transaction_id="TX-001",
            effective_date="2024-06-15",
            line_map={
                "property_value": 500000,
            },
        )
        assert "Address" not in xml

    def test_calculation_section(self):
        xml = build_sdlt_body(
            utr="1234567890123",
            transaction_id="TX-001",
            effective_date="2024-06-15",
            line_map={
                "sdlt_payable": 15000,
                "effective_rate": 0.03,
            },
        )
        assert "Calculation" in xml
        assert "SDLTPayable" in xml
        assert "EffectiveRate" in xml

    def test_lease_fields(self):
        xml = build_sdlt_body(
            utr="1234567890123",
            transaction_id="TX-001",
            effective_date="2024-06-15",
            line_map={
                "property_value": 500000,
                "lease_premium": 100000,
                "lease_term_years": 10,
                "annual_rent": 24000,
                "npv_rent": 200000,
            },
        )
        assert "LeasePremium" in xml
        assert "LeaseTermYears" in xml
        assert "AnnualRent" in xml

    def test_purchaser_details(self):
        xml = build_sdlt_body(
            utr="1234567890123",
            transaction_id="TX-001",
            effective_date="2024-06-15",
            line_map={
                "property_value": 500000,
                "purchaser": {
                    "name": "Acme Properties Ltd",
                    "type": "company",
                },
            },
        )
        assert "Purchaser" in xml
        assert "Acme Properties Ltd" in xml
