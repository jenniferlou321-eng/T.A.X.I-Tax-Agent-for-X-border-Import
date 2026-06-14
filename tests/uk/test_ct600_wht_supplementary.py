"""Tests for CT600 WHT Supplementary embedding.

Verifies the end-to-end flow:
1. calculate_wht() in uk/withholding_tax/calculator.py computes correct DTA rate
2. UKCTAdapter.to_filing_format() auto-detects WHT line items and builds entries
3. build_ct600_body(wht_entries=...) embeds the entries as XML supplementary
4. metadata.wht_payments (structured list) also works
5. Jiahang case (UK→CN) interest £27,778 → WHT £2,778 (10% Art.11) and
   royalty £35,000 → WHT £3,500 (10% Art.12) appear in supplementary
"""

from datetime import date
from decimal import Decimal

from backend.jurisdictions.uk.corporation_tax.govtalk_body import build_ct600_body
from backend.jurisdictions.uk.corporation_tax.withholding_tax_adapter import (
    compute_wht_interest,
    compute_wht_royalty,
    compute_wht_dividend,
)
from backend.jurisdictions.uk.withholding_tax.calculator import (
    TREATY_RATES,
    get_treaty_rate,
    calculate_wht,
)
from backend.models.tax_data import (
    LineItem,
    TaxData,
    TaxType,
    TaxpayerInfo,
    FiscalPeriod,
    PeriodType,
)


# ── Test helpers ──

def _make_period() -> FiscalPeriod:
    return FiscalPeriod(
        year=2023,
        period_type=PeriodType.ANNUAL,
        period_key="2023-04-01_2024-03-31",
        start_date=date(2023, 4, 1),
        end_date=date(2024, 3, 31),
    )


def _make_taxpayer() -> TaxpayerInfo:
    return TaxpayerInfo(
        name="Jiahang UK Holdings Ltd",
        tax_id="1234567890",
        tax_id_type="utr",
    )


def _make_wht_data(line_items: list[LineItem], metadata: dict | None = None) -> TaxData:
    return TaxData(
        tax_type=TaxType.CORPORATION_TAX,
        period=_make_period(),
        taxpayer=_make_taxpayer(),
        line_items=line_items,
        metadata=metadata or {},
    )


# ── Direct WHT calculator tests ──

class TestComputeWHTInterest:
    def test_uk_to_cn_interest(self):
        """Jiahang case: £27,778 interest to CN parent, DTA Art.11 → 10%."""
        rate, wht, treaty = compute_wht_interest(27778, "CN")
        assert rate == 0.10
        assert wht == 2777.80
        assert treaty == "0.10"

    def test_uk_to_hk_interest_zero(self):
        """UK-HK DTA: interest generally 0%."""
        rate, wht, _ = compute_wht_interest(10000, "HK")
        assert rate == 0.0
        assert wht == 0.0

    def test_uk_to_us_interest_zero(self):
        """UK-US DTA: interest 0%."""
        rate, wht, _ = compute_wht_interest(50000, "US")
        assert rate == 0.0
        assert wht == 0.0


class TestComputeWHTRoyalty:
    def test_uk_to_cn_royalty(self):
        """Jiahang case: £35,000 royalty to CN, DTA Art.12 → 10%."""
        rate, wht, treaty = compute_wht_royalty(35000, "CN")
        assert rate == 0.10
        assert wht == 3500.00
        assert treaty == "0.10"

    def test_uk_to_hk_royalty_3pct(self):
        """UK-HK DTA: royalty 3%."""
        rate, wht, _ = compute_wht_royalty(10000, "HK")
        assert rate == 0.03
        assert wht == 300.0


class TestComputeWHTDividend:
    def test_uk_to_cn_25pct_holding_zero(self):
        """100% holding: dividend WHT 0% under UK-CN DTA Art.10(a)."""
        rate, wht, _ = compute_wht_dividend(100000, "CN", ownership_pct=100.0)
        assert rate == 0.0
        assert wht == 0.0

    def test_uk_to_cn_15pct_holding_5pct(self):
        """10-25% holding: dividend WHT 5% under UK-CN DTA Art.10(b)."""
        rate, wht, _ = compute_wht_dividend(100000, "CN", ownership_pct=15.0)
        assert rate == 0.05
        assert wht == 5000.0

    def test_uk_to_cn_5pct_holding_10pct(self):
        """<10% holding: dividend WHT 10% under UK-CN DTA Art.10(c)."""
        rate, wht, _ = compute_wht_dividend(100000, "CN", ownership_pct=5.0)
        assert rate == 0.10
        assert wht == 10000.0


# ── CT600 body builder with WHT supplementary ──

class TestCT600BodyWithWHT:
    def test_no_wht_entries_no_supplementary(self):
        """Without wht_entries argument, no WHTSupplementary element."""
        xml = build_ct600_body(
            ctref="1234567890",
            company_name="Acme Ltd",
            period_start="2023-04-01",
            period_end="2024-03-31",
            line_map={"turnover": 1000000, "corporation_tax_chargeable": 250000},
        )
        assert "WHTSupplementary" not in xml
        assert "WHTEntry" not in xml

    def test_empty_wht_list_no_supplementary(self):
        """Empty wht_entries list should not produce supplementary."""
        xml = build_ct600_body(
            ctref="1234567890",
            company_name="Acme Ltd",
            period_start="2023-04-01",
            period_end="2024-03-31",
            line_map={"turnover": 1000000},
            wht_entries=[],
        )
        assert "WHTSupplementary" not in xml

    def test_interest_entry_embedded(self):
        """Interest WHT entry shows in supplementary with correct values."""
        xml = build_ct600_body(
            ctref="1234567890",
            company_name="Jiahang UK Holdings Ltd",
            period_start="2023-04-01",
            period_end="2024-03-31",
            line_map={"turnover": 5000000, "corporation_tax_chargeable": 43950},
            wht_entries=[{
                "income_type": "interest",
                "gross_amount": 27778,
                "wht_amount": 2777.80,
                "rate": "0.10",
                "treaty_rate": "0.10",
                "recipient_country": "CN",
                "recipient_name": "江苏嘉汉国际贸易有限公司",
                "date_paid": "2024-03-31",
            }],
        )
        assert "WHTSupplementary" in xml
        assert "WHTEntry" in xml
        assert "interest" in xml
        assert "27778" in xml
        assert "2777.80" in xml
        assert "CN" in xml
        assert "江苏嘉汉国际贸易有限公司" in xml

    def test_royalty_entry_embedded(self):
        """Royalty WHT entry shows in supplementary."""
        xml = build_ct600_body(
            ctref="1234567890",
            company_name="Jiahang UK Holdings Ltd",
            period_start="2023-04-01",
            period_end="2024-03-31",
            line_map={"turnover": 5000000},
            wht_entries=[{
                "income_type": "royalty",
                "gross_amount": 35000,
                "wht_amount": 3500.00,
                "rate": "0.10",
                "treaty_rate": "0.10",
                "recipient_country": "CN",
                "recipient_name": "江苏嘉汉国际贸易有限公司",
                "date_paid": "2024-03-31",
            }],
        )
        assert "royalty" in xml
        assert "35000" in xml
        assert "3500.00" in xml

    def test_dividend_zero_pct_not_embedded(self):
        """Dividend with 0% WHT should be filtered out by adapter,
        but if passed to body builder, no WHT is recorded (just zero entries)."""
        xml = build_ct600_body(
            ctref="1234567890",
            company_name="Jiahang UK Holdings Ltd",
            period_start="2023-04-01",
            period_end="2024-03-31",
            line_map={"turnover": 5000000},
            wht_entries=[],  # Adapter would filter out 0% dividend
        )
        assert "WHTDeductedTotal" not in xml or "0.00" in xml

    def test_multiple_recipients(self):
        """Multiple WHT entries (CN + HK) all appear with separate entries."""
        xml = build_ct600_body(
            ctref="1234567890",
            company_name="Multi-recipient Co",
            period_start="2023-04-01",
            period_end="2024-03-31",
            line_map={"turnover": 10000000},
            wht_entries=[
                {
                    "income_type": "interest",
                    "gross_amount": 27778,
                    "wht_amount": 2777.80,
                    "rate": "0.10",
                    "treaty_rate": "0.10",
                    "recipient_country": "CN",
                    "recipient_name": "CN parent",
                    "date_paid": "2023-12-15",
                },
                {
                    "income_type": "royalty",
                    "gross_amount": 10000,
                    "wht_amount": 300.0,
                    "rate": "0.03",
                    "treaty_rate": "0.03",
                    "recipient_country": "HK",
                    "recipient_name": "HK sister",
                    "date_paid": "2024-01-20",
                },
            ],
        )
        # 2 entries (count open tags — namespace prefix is ns0)
        assert xml.count("<ns0:WHTEntry>") == 2
        # Totals: interest 27778, royalty 10000, dividend 0
        assert "InterestPaidTotal" in xml
        assert "RoyaltiesPaidTotal" in xml
        # WHT total = 2777.80 + 300.00 = 3077.80
        assert "3077.80" in xml
        # Recipient countries both present
        assert ">CN<" in xml
        assert ">HK<" in xml

    def test_totals_correct(self):
        """Totals boxes reflect the entries correctly."""
        xml = build_ct600_body(
            ctref="1234567890",
            company_name="Test",
            period_start="2023-04-01",
            period_end="2024-03-31",
            line_map={"turnover": 1000000},
            wht_entries=[
                {
                    "income_type": "interest",
                    "gross_amount": 50000,
                    "wht_amount": 5000.0,
                    "rate": "0.10",
                    "treaty_rate": "0.10",
                    "recipient_country": "CN",
                    "recipient_name": "",
                    "date_paid": "",
                },
                {
                    "income_type": "interest",
                    "gross_amount": 30000,
                    "wht_amount": 3000.0,
                    "rate": "0.10",
                    "treaty_rate": "0.10",
                    "recipient_country": "CN",
                    "recipient_name": "",
                    "date_paid": "",
                },
            ],
        )
        # Total interest = 80000
        assert "80000.00" in xml
        # Total WHT = 8000
        assert "8000.00" in xml
        # EntryCount = 2
        assert "EntryCount" in xml
        assert ">2<" in xml

    def test_main_ct600_fields_still_present(self):
        """When adding WHT supplementary, main CT600 fields are preserved."""
        xml = build_ct600_body(
            ctref="1234567890",
            company_name="Jiahang UK Holdings Ltd",
            period_start="2023-04-01",
            period_end="2024-03-31",
            line_map={
                "turnover": 5000000,
                "trading_income": 4800000,
                "taxable_total_profits": 180000,
                "corporation_tax_chargeable": 43950,
            },
            wht_entries=[{
                "income_type": "interest",
                "gross_amount": 27778,
                "wht_amount": 2777.80,
                "rate": "0.10",
                "treaty_rate": "0.10",
                "recipient_country": "CN",
                "recipient_name": "江苏嘉汉国际贸易有限公司",
                "date_paid": "2024-03-31",
            }],
        )
        # Main fields
        assert "CTREF" in xml
        assert "1234567890" in xml
        assert "Jiahang UK Holdings Ltd" in xml
        assert "5000000" in xml
        assert "180000" in xml
        assert "43950" in xml
        # + supplementary
        assert "WHTSupplementary" in xml


# ── End-to-end: calculate_wht → adapter → body builder ──

class TestEndToEndJiahangCase:
    """Full pipeline: line_items → calculate_wht() result → to_filing_format → CT600 XML."""

    def test_jiahang_interest_and_royalty_appear(self):
        """Jiahang case: interest £27,778 + royalty £35,000 to CN parent.
        Both should be in CT600 supplementary with correct WHT amounts."""
        data = _make_wht_data(
            line_items=[
                LineItem(category="trading_income", amount=Decimal("4800000")),
                LineItem(category="trading_expenses", amount=Decimal("4000000")),
                LineItem(category="interest_amount", amount=Decimal("27778")),
                LineItem(category="royalty_amount", amount=Decimal("35000")),
            ],
            metadata={"recipient_country": "CN", "recipient_name": "江苏嘉汉国际贸易有限公司"},
        )

        # Step 1: calculate WHT standalone
        wht_result = calculate_wht(data)
        assert wht_result.total_tax_due == Decimal("6277.80")  # 2777.80 + 3500.00

        # Step 2: adapter builds WHT entries
        from backend.jurisdictions.uk.corporation_tax import UKCTAdapter
        adapter = UKCTAdapter()
        entries = adapter._build_wht_entries(data, {li.category: float(li.amount) for li in data.line_items})
        assert len(entries) == 2

        interest_entry = next(e for e in entries if e["income_type"] == "interest")
        royalty_entry = next(e for e in entries if e["income_type"] == "royalty")
        assert interest_entry["gross_amount"] == 27778
        assert interest_entry["wht_amount"] == 2777.80
        assert interest_entry["recipient_country"] == "CN"
        assert royalty_entry["gross_amount"] == 35000
        assert royalty_entry["wht_amount"] == 3500.00

        # Step 3: build CT600 XML
        line_map = {li.category: float(li.amount) for li in data.line_items}
        xml = build_ct600_body(
            ctref="1234567890",
            company_name="Jiahang UK Holdings Ltd",
            period_start="2023-04-01",
            period_end="2024-03-31",
            line_map=line_map,
            wht_entries=entries,
        )
        # Both entries in XML (open tag only)
        assert xml.count("<ns0:WHTEntry>") == 2
        assert "27778" in xml
        assert "35000" in xml
        assert "2777.80" in xml
        assert "3500.00" in xml
        # Total WHT 6277.80
        assert "6277.80" in xml
        # Recipient
        assert "江苏嘉汉国际贸易有限公司" in xml

    def test_jiahang_dividend_0pct_excluded(self):
        """100% holding: dividend 0% — should NOT appear in supplementary."""
        data = _make_wht_data(
            line_items=[
                LineItem(category="dividend_amount", amount=Decimal("130000")),
            ],
            metadata={"recipient_country": "CN", "ownership_pct": 100},
        )

        from backend.jurisdictions.uk.corporation_tax import UKCTAdapter
        adapter = UKCTAdapter()
        entries = adapter._build_wht_entries(
            data, {li.category: float(li.amount) for li in data.line_items}
        )
        # 0% dividend → filtered out by adapter
        assert entries == []

        wht_result = calculate_wht(data)
        assert wht_result.total_tax_due == Decimal("0")

    def test_to_filing_format_includes_wht_supplementary(self):
        """to_filing_format() should set body['wht_supplementary'] when WHT present."""
        data = _make_wht_data(
            line_items=[
                LineItem(category="trading_income", amount=Decimal("1000000")),
                LineItem(category="interest_amount", amount=Decimal("50000")),
            ],
            metadata={"recipient_country": "CN"},
        )

        from backend.jurisdictions.uk.corporation_tax import UKCTAdapter
        adapter = UKCTAdapter()
        payload = adapter.to_filing_format(TaxType.CORPORATION_TAX, data)
        body = payload.body

        assert "wht_supplementary" in body
        assert len(body["wht_supplementary"]) == 1
        entry = body["wht_supplementary"][0]
        assert entry["income_type"] == "interest"
        assert entry["gross_amount"] == 50000
        assert entry["wht_amount"] == 5000.0
        assert entry["recipient_country"] == "CN"

    def test_to_filing_format_no_wht_omits_key(self):
        """No cross-border WHT → no wht_supplementary key."""
        data = _make_wht_data(
            line_items=[
                LineItem(category="trading_income", amount=Decimal("1000000")),
            ],
        )

        from backend.jurisdictions.uk.corporation_tax import UKCTAdapter
        adapter = UKCTAdapter()
        payload = adapter.to_filing_format(TaxType.CORPORATION_TAX, data)
        assert "wht_supplementary" not in payload.body


# ── metadata.wht_payments structured list ──

class TestWHTFromMetadata:
    def test_structured_wht_payments(self):
        """metadata.wht_payments list of dicts produces entries."""
        data = _make_wht_data(
            line_items=[LineItem(category="trading_income", amount=Decimal("1000000"))],
            metadata={
                "wht_payments": [
                    {
                        "income_type": "interest",
                        "gross_amount": 20000,
                        "recipient_country": "CN",
                        "recipient_name": "CN parent",
                        "date_paid": "2023-09-30",
                    },
                    {
                        "income_type": "royalty",
                        "gross_amount": 15000,
                        "recipient_country": "CN",
                        "recipient_name": "CN parent",
                        "date_paid": "2023-12-31",
                    },
                ]
            },
        )

        from backend.jurisdictions.uk.corporation_tax import UKCTAdapter
        adapter = UKCTAdapter()
        entries = adapter._build_wht_entries(
            data, {li.category: float(li.amount) for li in data.line_items}
        )
        assert len(entries) == 2
        assert entries[0]["wht_amount"] == 2000.0  # 20000 × 10%
        assert entries[1]["wht_amount"] == 1500.0  # 15000 × 10%

    def test_structured_wht_payments_takes_precedence(self):
        """If both metadata.wht_payments and line_items WHT present, structured wins."""
        data = _make_wht_data(
            line_items=[
                LineItem(category="interest_amount", amount=Decimal("10000")),
            ],
            metadata={
                "wht_payments": [
                    {
                        "income_type": "interest",
                        "gross_amount": 99999,  # Different from line_items
                        "recipient_country": "CN",
                    }
                ]
            },
        )

        from backend.jurisdictions.uk.corporation_tax import UKCTAdapter
        adapter = UKCTAdapter()
        entries = adapter._build_wht_entries(
            data, {li.category: float(li.amount) for li in data.line_items}
        )
        assert len(entries) == 1
        assert entries[0]["gross_amount"] == 99999  # From metadata, not 10000


# ── DTA coverage sanity ──

class TestTreatyRateCoverage:
    """Verify treaty rate table covers all expected jurisdictions."""

    def test_cn_interest_10pct(self):
        assert TREATY_RATES["CN"]["interest"] == Decimal("0.10")

    def test_cn_royalty_10pct(self):
        assert TREATY_RATES["CN"]["royalty"] == Decimal("0.10")

    def test_cn_dividend_25pct_0pct(self):
        assert TREATY_RATES["CN"]["dividend_25pct"] == Decimal("0.00")

    def test_hk_interest_0pct(self):
        assert TREATY_RATES["HK"]["interest"] == Decimal("0.00")

    def test_us_interest_0pct(self):
        assert TREATY_RATES["US"]["interest"] == Decimal("0.00")

    def test_unknown_country_falls_back_to_20pct(self):
        """Country with no DTA → UK statutory 20%."""
        rate = get_treaty_rate("ZZ", "interest")
        assert rate == Decimal("0.20")
