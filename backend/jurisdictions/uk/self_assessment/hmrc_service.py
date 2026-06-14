"""HMRC Self Assessment Service — 封装 MTD for ITSA (Income Tax Self Assessment) API

Endpoints (HMRC Developer Hub 2026-06):
- GET  /self-assessment/accounts/{nino}              → 拿 accountId (sa-account-api/4.0)
- GET  /self-assessment/{nino}/tax-years            → 列出 tax years
- GET  /self-assessment/{nino}/{taxYear}/obligations → 申报义务
- GET  /individual-calculations/{nino}/{taxYear}     → HMRC 计算
- POST /individual-calculations/{nino}/{taxYear}     → 触发计算
- GET  /self-assessment/{nino}/{taxYear}/final-declaration → 拿最终申报数据
- POST /self-assessment/{nino}/{taxYear}/final-declaration → 申报 (此为不可逆操作)

各收入来源 (individuals-* family):
- /individuals/employments/{nino}/{taxYear}         (employment income)
- /individuals/self-employment/{nino}/{taxYear}      (self-employment)
- /individuals/uk-property/{nino}/{taxYear}          (property)
- /individuals/savings/{nino}/{taxYear}              (savings)
- /individuals/dividends/{nino}/{taxYear}            (dividends)
- /individuals/capital-gains-income/{nino}/{taxYear} (CGT)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import httpx

from backend.channels.oauth import OAuth2Manager
from backend.channels.fraud_headers import FraudPreventionHeaders
from backend.jurisdictions.uk._hmrc_base import HMRCService

logger = logging.getLogger(__name__)


@dataclass
class SAObligation:
    """Self Assessment tax year 申报义务"""
    tax_year: str            # e.g. "2023-24"
    start: date              # 2023-04-06
    end: date                # 2024-04-05
    due: date                # 2025-01-31
    status: str              # "O" (Open) | "F" (Fulfilled)


@dataclass
class SATaxYear:
    """SA tax year 元数据"""
    tax_year: str
    start: date
    end: date
    days_in_year: int
    filing_due: date


@dataclass
class SACalculation:
    """HMRC 端返回的 SA 计算结果"""
    tax_year: str
    total_income: Decimal
    total_allowances: Decimal
    total_taxable_income: Decimal
    income_tax_chargeable: Decimal
    nic_class_2: Decimal = Decimal("0")
    nic_class_4: Decimal = Decimal("0")
    total_nic: Decimal = Decimal("0")
    tax_due_total: Decimal = Decimal("0")
    pension_charges: Decimal = Decimal("0")
    savings_charges: Decimal = Decimal("0")
    total_tax_due: Decimal = Decimal("0")
    breakdown: list[dict] = field(default_factory=list)


class HMRCSAService(HMRCService):
    """HMRC Making Tax Digital for Income Tax (SA) API 客户端"""

    def __init__(
        self,
        base_url: str,
        oauth: OAuth2Manager,
        fraud_headers: FraudPreventionHeaders | None = None,
    ):
        super().__init__(
            base_url=base_url,
            oauth=oauth,
            fraud_headers=fraud_headers,
            accept_header="application/vnd.hmrc.8.0+json",  # individual-calculations-api 是 v8.0
        )

    # ── Accounts / Tax Years / Obligations ──

    async def get_account(self, nino: str) -> dict:
        """Get SA account information for a given NINO.

        Args:
            nino: National Insurance Number, e.g. "AB123456C"

        Returns:
            {"accountId": "...", "processingDate": "..."}  (sa-account-api v4.0)
        """
        token = await self._authenticate()
        client = await self._get_client()
        url = f"/self-assessment/accounts/{nino}"
        headers = self._build_headers(user_id=nino)
        headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "SA account")

        return resp.json()

    async def list_tax_years(self, nino: str) -> list[SATaxYear]:
        """List available tax years for a NINO."""
        token = await self._authenticate()
        client = await self._get_client()
        url = f"/self-assessment/{nino}/tax-years"
        headers = self._build_headers(user_id=nino)
        headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "tax years")

        data = resp.json()
        result = []
        for ty in data.get("taxYears", []):
            result.append(SATaxYear(
                tax_year=ty.get("taxYear", ""),
                start=date.fromisoformat(ty["startDate"]),
                end=date.fromisoformat(ty["endDate"]),
                days_in_year=int(ty.get("daysInYear", 365)),
                filing_due=date.fromisoformat(ty["filingDueDate"]) if "filingDueDate" in ty else None,
            ))
        return result

    async def get_obligations(self, nino: str) -> list[SAObligation]:
        """List all obligations (Open + Fulfilled) for a NINO across all tax years.

        Note: SA obligations are at NINO level, not per-tax-year (different from VAT).
        Returns:
            List of SAObligation for each (taxYear, obligationType) combination.
        """
        token = await self._authenticate()
        client = await self._get_client()
        url = f"/self-assessment/{nino}/obligations"
        headers = self._build_headers(user_id=nino)
        headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "SA obligations")

        data = resp.json()
        result = []
        for ob in data.get("obligations", []):
            try:
                result.append(SAObligation(
                    tax_year=ob.get("taxYear", ""),
                    start=date.fromisoformat(ob["startDate"]),
                    end=date.fromisoformat(ob["endDate"]),
                    due=date.fromisoformat(ob["dueDate"]),
                    status=ob.get("status", "O"),
                ))
            except (KeyError, ValueError) as e:
                logger.warning(f"Skipping malformed obligation: {ob} ({e})")
        return result

    # ── Calculations ──

    async def trigger_calculation(self, nino: str, tax_year: str, body: dict | None = None) -> str:
        """Trigger HMRC to compute tax. Returns calculationId.

        Args:
            nino: National Insurance Number
            tax_year: e.g. "2023-24"
            body: Optional final-declaration body (if filing in same call)
        """
        token = await self._authenticate()
        client = await self._get_client()
        url = f"/individual-calculations/{nino}/{tax_year}"
        headers = self._build_headers(user_id=nino)
        headers["Authorization"] = f"Bearer {token}"
        if body is None:
            body = {}  # Empty body — HMRC uses previously submitted income sources

        try:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "trigger calculation")

        data = resp.json()
        return data.get("id", data.get("calculationId", ""))

    async def get_calculation(self, nino: str, tax_year: str, calculation_id: str) -> SACalculation:
        """Retrieve a previously triggered calculation by its ID.

        Args:
            nino: NINO
            tax_year: e.g. "2023-24"
            calculation_id: UUID returned from trigger_calculation
        """
        token = await self._authenticate()
        client = await self._get_client()
        url = f"/individual-calculations/{nino}/{tax_year}/{calculation_id}"
        headers = self._build_headers(user_id=nino)
        headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "get calculation")

        data = resp.json()

        # Navigate HMRC's nested response structure
        calc = data.get("calculation", {})
        income = calc.get("incomeTax", calc)  # SA MTD returns incomeTax block
        allowances = calc.get("allowancesAndDeductions", {})

        # Extract income tax breakdown
        non_savings = income.get("nonSavingsIncome", {})
        savings = income.get("savingsIncome", {})
        dividend = income.get("dividendIncome", {})
        pension = income.get("pensionContributions", {})

        # Compute totals
        total_income = sum(_to_dec(
            block.get("incomeReceived", block.get("amount", 0))
        ) for block in [non_savings, savings, dividend] if block)

        total_allowances = _to_dec(allowances.get("totalAllowancesAndDeductions", 0))
        total_taxable_income = _to_dec(calc.get("totalTaxableIncome", 0))
        income_tax_chargeable = _to_dec(
            income.get("totalIncomeTax", income.get("incomeTaxChargeable", 0))
        )

        # NIC
        nic = calc.get("nic", {})
        nic_class_2 = _to_dec(nic.get("class2Amount", 0))
        nic_class_4 = _to_dec(nic.get("class4Amount", 0))
        total_nic = _to_dec(nic.get("totalNic", 0))

        return SACalculation(
            tax_year=tax_year,
            total_income=total_income,
            total_allowances=total_allowances,
            total_taxable_income=total_taxable_income,
            income_tax_chargeable=income_tax_chargeable,
            nic_class_2=nic_class_2,
            nic_class_4=nic_class_4,
            total_nic=total_nic,
            pension_charges=_to_dec(pension.get("pensionTaxDue", 0)),
            savings_charges=_to_dec(savings.get("savingsTaxDue", 0)),
            total_tax_due=_to_dec(calc.get("totalTaxDue", 0)),
            breakdown=calc.get("breakdown", []),
        )

    # ── Final Declaration (the IRREVERSIBLE filing step) ──

    async def get_final_declaration(self, nino: str, tax_year: str) -> dict:
        """Get the final declaration summary (what will be filed)."""
        token = await self._authenticate()
        client = await self._get_client()
        url = f"/self-assessment/{nino}/{tax_year}/final-declaration"
        headers = self._build_headers(user_id=nino)
        headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "get final declaration")

        return resp.json()

    async def submit_final_declaration(self, nino: str, tax_year: str, body: dict) -> dict:
        """Submit the final declaration to HMRC. **IRREVERSIBLE**.

        Args:
            nino: NINO
            tax_year: e.g. "2023-24"
            body: Declaration body (e.g. {"declaration": {"finalised": true, "signature": "..."}})

        Returns:
            HMRC response with transaction reference.
        """
        token = await self._authenticate()
        client = await self._get_client()
        url = f"/self-assessment/{nino}/{tax_year}/final-declaration"
        headers = self._build_headers(user_id=nino)
        headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "submit final declaration")

        return resp.json()

    # ── Income Sources (concrete sub-APIs) ──

    async def get_employments(self, nino: str, tax_year: str) -> list[dict]:
        """Get employment income sources for a tax year (SA102)."""
        token = await self._authenticate()
        client = await self._get_client()
        url = f"/individuals/employments/{nino}/{tax_year}"
        headers = self._build_headers(user_id=nino)
        headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "employments")

        data = resp.json()
        return data.get("employments", [])

    async def get_savings(self, nino: str, tax_year: str) -> list[dict]:
        """Get savings income for a tax year (SA106)."""
        token = await self._authenticate()
        client = await self._get_client()
        url = f"/individuals/savings/{nino}/{tax_year}"
        headers = self._build_headers(user_id=nino)
        headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "savings")

        data = resp.json()
        return data.get("savings", [])

    async def get_dividends(self, nino: str, tax_year: str) -> list[dict]:
        """Get dividend income for a tax year."""
        token = await self._authenticate()
        client = await self._get_client()
        url = f"/individuals/dividends/{nino}/{tax_year}"
        headers = self._build_headers(user_id=nino)
        headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "dividends")

        data = resp.json()
        return data.get("dividends", [])


def _to_dec(v) -> Decimal:
    """Convert a value to Decimal, defaulting to 0."""
    if v is None:
        return Decimal("0")
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")
