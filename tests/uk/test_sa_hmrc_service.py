"""Tests for HMRCSAService — Self Assessment REST API client."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.jurisdictions.uk.self_assessment.hmrc_service import (
    HMRCSAService,
    SAObligation,
    SACalculation,
)


@pytest.fixture
def mock_oauth():
    oauth = MagicMock()
    oauth.authenticate_silent = AsyncMock()
    oauth.authenticate_silent.return_value = MagicMock(success=True, token="sa_test_token")
    return oauth


@pytest.fixture
def sa_service(mock_oauth):
    return HMRCSAService(
        base_url="https://test-api.service.hmrc.gov.uk",
        oauth=mock_oauth,
    )


class TestHMRCSAServiceInit:
    def test_accept_header(self, sa_service):
        # SA individual-calculations-api is v8.0
        assert sa_service._accept_header == "application/vnd.hmrc.8.0+json"


class TestGetAccount:
    @pytest.mark.asyncio
    async def test_returns_account_data(self, sa_service):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "accountId": "ACC-001",
            "processingDate": "2025-01-15",
        }

        with patch.object(sa_service, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = mock_client

            result = await sa_service.get_account("AB123456C")

        assert result["accountId"] == "ACC-001"
        # Verify NINO in URL
        call_args = mock_client.get.call_args
        assert "AB123456C" in str(call_args)

    @pytest.mark.asyncio
    async def test_handles_auth_failure(self, sa_service):
        sa_service.oauth.authenticate_silent.return_value = MagicMock(
            success=False, error="Token expired"
        )
        with pytest.raises(PermissionError, match="HMRC auth failed"):
            await sa_service.get_account("AB123456C")


class TestListTaxYears:
    @pytest.mark.asyncio
    async def test_returns_tax_years(self, sa_service):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "taxYears": [
                {
                    "taxYear": "2023-24",
                    "startDate": "2023-04-06",
                    "endDate": "2024-04-05",
                    "daysInYear": 366,
                    "filingDueDate": "2025-01-31",
                },
                {
                    "taxYear": "2022-23",
                    "startDate": "2022-04-06",
                    "endDate": "2023-04-05",
                    "daysInYear": 365,
                },
            ]
        }

        with patch.object(sa_service, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = mock_client

            result = await sa_service.list_tax_years("AB123456C")

        assert len(result) == 2
        assert result[0].tax_year == "2023-24"
        assert result[0].start == date(2023, 4, 6)
        assert result[0].days_in_year == 366
        # Missing filing_due becomes None
        assert result[1].filing_due is None


class TestGetObligations:
    @pytest.mark.asyncio
    async def test_returns_obligations(self, sa_service):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "obligations": [
                {
                    "taxYear": "2023-24",
                    "startDate": "2023-04-06",
                    "endDate": "2024-04-05",
                    "dueDate": "2025-01-31",
                    "status": "O",
                },
            ]
        }

        with patch.object(sa_service, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = mock_client

            result = await sa_service.get_obligations("AB123456C")

        assert len(result) == 1
        assert result[0].tax_year == "2023-24"
        assert result[0].status == "O"

    @pytest.mark.asyncio
    async def test_skips_malformed_obligations(self, sa_service):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "obligations": [
                {"taxYear": "2023-24", "startDate": "bad-date", "endDate": "2024-04-05", "dueDate": "2025-01-31", "status": "O"},
                {"taxYear": "2022-23", "startDate": "2022-04-06", "endDate": "2023-04-05", "dueDate": "2024-01-31", "status": "F"},
            ]
        }

        with patch.object(sa_service, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = mock_client

            result = await sa_service.get_obligations("AB123456C")

        # Malformed first obligation is skipped
        assert len(result) == 1
        assert result[0].tax_year == "2022-23"


class TestTriggerCalculation:
    @pytest.mark.asyncio
    async def test_returns_calculation_id(self, sa_service):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "id": "calc-uuid-123",
            "calculationId": "calc-uuid-123",
        }

        with patch.object(sa_service, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = mock_client

            calc_id = await sa_service.trigger_calculation("AB123456C", "2023-24")

        assert calc_id == "calc-uuid-123"


class TestGetCalculation:
    @pytest.mark.asyncio
    async def test_parses_full_calculation(self, sa_service):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "calculation": {
                "totalTaxableIncome": 45000.00,
                "incomeTax": {
                    "nonSavingsIncome": {"incomeReceived": 50000, "totalIncomeTax": 7500},
                    "savingsIncome": {"amount": 1000, "savingsTaxDue": 200},
                    "dividendIncome": {"amount": 500, "totalTaxDue": 75},
                    "pensionContributions": {"pensionTaxDue": 0},
                    "totalIncomeTax": 7775,
                },
                "allowancesAndDeductions": {
                    "totalAllowancesAndDeductions": 5000,
                },
                "nic": {
                    "class2Amount": 3.45,
                    "class4Amount": 0,
                    "totalNic": 3.45,
                },
                "totalTaxDue": 7778.45,
                "breakdown": [{"key": "test", "value": 1}],
            }
        }

        with patch.object(sa_service, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = mock_client

            result = await sa_service.get_calculation("AB123456C", "2023-24", "calc-uuid-123")

        assert isinstance(result, SACalculation)
        assert result.tax_year == "2023-24"
        assert result.total_income == Decimal("51500")  # 50000+1000+500
        assert result.total_allowances == Decimal("5000")
        assert result.total_taxable_income == Decimal("45000")
        assert result.income_tax_chargeable == Decimal("7775")
        assert result.nic_class_2 == Decimal("3.45")
        assert result.total_nic == Decimal("3.45")
        assert result.savings_charges == Decimal("200")
        assert result.total_tax_due == Decimal("7778.45")


class TestFinalDeclaration:
    @pytest.mark.asyncio
    async def test_submit_final_declaration(self, sa_service):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "transactionReference": "TX-REF-001",
            "processingDate": "2025-01-15T10:00:00Z",
        }

        with patch.object(sa_service, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = mock_client

            result = await sa_service.submit_final_declaration(
                nino="AB123456C",
                tax_year="2023-24",
                body={"declaration": {"finalised": True}},
            )

        assert result["transactionReference"] == "TX-REF-001"

    @pytest.mark.asyncio
    async def test_get_final_declaration(self, sa_service):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "nino": "AB123456C",
            "taxYear": "2023-24",
            "declaration": {"finalised": False},
        }

        with patch.object(sa_service, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = mock_client

            result = await sa_service.get_final_declaration("AB123456C", "2023-24")

        assert result["nino"] == "AB123456C"


class TestIncomeSources:
    @pytest.mark.asyncio
    async def test_get_employments(self, sa_service):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "employments": [
                {"employmentId": "EMP-1", "employerName": "Acme Ltd", "payrollId": "P1", "employmentIncome": 50000},
            ]
        }

        with patch.object(sa_service, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = mock_client

            result = await sa_service.get_employments("AB123456C", "2023-24")

        assert len(result) == 1
        assert result[0]["employerName"] == "Acme Ltd"

    @pytest.mark.asyncio
    async def test_get_savings(self, sa_service):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"savings": [{"taxedUKInterest": 1000}]}

        with patch.object(sa_service, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = mock_client

            result = await sa_service.get_savings("AB123456C", "2023-24")

        assert len(result) == 1
