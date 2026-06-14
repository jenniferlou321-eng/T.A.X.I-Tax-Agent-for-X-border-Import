"""Tests for PAYE RTI GovTalk body builders (FPS, EPS, EYU)."""

from backend.jurisdictions.uk.paye.govtalk_body import (
    build_fps_body,
    build_eps_body,
    build_eyu_body,
    NS_RTI,
)


class TestBuildFPSBody:
    def test_basic_fields(self):
        xml = build_fps_body(
            empref="123/AB45678",
            tax_year="2024-25",
            period_start="2024-04-06",
            period_end="2024-05-05",
            line_map={
                "total_paye_income": 50000,
                "total_tax_deducted": 8000,
            },
        )
        assert "123/AB45678" in xml
        assert "2024-25" in xml
        assert "50000" in xml
        assert "8000" in xml

    def test_contains_irenvelope_root(self):
        xml = build_fps_body(
            empref="123/AB45678",
            tax_year="2024-25",
            period_start="2024-04-06",
            period_end="2024-05-05",
            line_map={},
        )
        assert "IRenvelope" in xml
        assert "FPS" in xml

    def test_employee_data(self):
        xml = build_fps_body(
            empref="123/AB45678",
            tax_year="2024-25",
            period_start="2024-04-06",
            period_end="2024-05-05",
            line_map={
                "employees": [
                    {"name": "John Smith", "pay": 3000},
                ],
            },
        )
        assert "John Smith" in xml
        assert "3000" in xml


class TestBuildEPSBody:
    def test_basic_fields(self):
        xml = build_eps_body(
            empref="123/AB45678",
            tax_year="2024-25",
            period_start="2024-04-06",
            period_end="2024-05-05",
            line_map={
                "total_pay_bill": 500000,
                "apprenticeship_levy_payable": 1250,
                "employment_allowance_claimed": 5000,
            },
        )
        assert "123/AB45678" in xml
        assert "500000" in xml
        assert "1250" in xml

    def test_apprenticeship_levy_section(self):
        xml = build_eps_body(
            empref="123/AB45678",
            tax_year="2024-25",
            period_start="2024-04-06",
            period_end="2024-05-05",
            line_map={
                "total_pay_bill": 1000000,
                "apprenticeship_levy_payable": 3750,
            },
        )
        assert "ApprenticeshipLevy" in xml
        assert "TotalPayBill" in xml
        assert "LevyDueYTD" in xml

    def test_employment_allowance_section(self):
        xml = build_eps_body(
            empref="123/AB45678",
            tax_year="2024-25",
            period_start="2024-04-06",
            period_end="2024-05-05",
            line_map={
                "employment_allowance_claimed": 5000,
            },
        )
        assert "EmploymentAllowance" in xml

    def test_statutory_payments(self):
        xml = build_eps_body(
            empref="123/AB45678",
            tax_year="2024-25",
            period_start="2024-04-06",
            period_end="2024-05-05",
            line_map={
                "statutory_maternity_pay": 1000,
                "statutory_sick_pay": 500,
            },
        )
        assert "StatutoryPayments" in xml

    def test_no_levy_no_levy_section(self):
        xml = build_eps_body(
            empref="123/AB45678",
            tax_year="2024-25",
            period_start="2024-04-06",
            period_end="2024-05-05",
            line_map={},
        )
        # No levy data → no ApprenticeshipLevy element
        assert "ApprenticeshipLevy" not in xml

    def test_nested_apprenticeshipLevy_dict(self):
        """When line_map has apprenticeshipLevy as a dict, use it directly."""
        xml = build_eps_body(
            empref="123/AB45678",
            tax_year="2024-25",
            period_start="2024-04-06",
            period_end="2024-05-05",
            line_map={
                "apprenticeshipLevy": {
                    "totalPayBill": 2000000,
                    "levyDueYTD": 7500,
                },
            },
        )
        assert "ApprenticeshipLevy" in xml
        assert "2000000" in xml
        assert "7500" in xml


class TestBuildEYUBody:
    def test_basic_fields(self):
        xml = build_eyu_body(
            empref="123/AB45678",
            tax_year="2023-24",
            period_start="2023-04-06",
            period_end="2024-04-05",
            line_map={
                "total_paye_income": 45000,
                "total_tax_deducted": 7000,
            },
        )
        assert "123/AB45678" in xml
        assert "2023-24" in xml
        assert "EYU" in xml
        assert "45000" in xml

    def test_contains_irenvelope(self):
        xml = build_eyu_body(
            empref="123/AB45678",
            tax_year="2023-24",
            period_start="2023-04-06",
            period_end="2024-04-05",
            line_map={},
        )
        assert "IRenvelope" in xml
