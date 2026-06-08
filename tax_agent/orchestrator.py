"""Orchestrator — 6 阶段报税管线编排器"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from .config import FilingConfig
from .models.tax_data import TaxData, TaxType
from .models.template import DataTemplate, FieldType
from .models.results import (
    FilingStatus, FilingResult, FilingError, StageResult, FilingPayload,
    ValidationError, StatusResult,
)
from .services.state_machine import StateMachine
from .services.audit_log import AuditLog
from .jurisdictions import JurisdictionAdapter

logger = logging.getLogger(__name__)


class Orchestrator:
    """报税流程编排器 — 所有 Jurisdiction 共享同一管线"""

    def __init__(self, config: FilingConfig | None = None, audit_log: AuditLog | None = None):
        self.config = config or FilingConfig()
        self.audit = audit_log or AuditLog()

    async def run(
        self,
        adapter: JurisdictionAdapter,
        tax_type: TaxType,
        data: TaxData,
    ) -> FilingResult:
        """执行完整申报管线"""
        filing_id = self._generate_filing_id(
            adapter.country_code, tax_type, data.period.period_key
        )
        result = FilingResult(
            filing_id=filing_id,
            status=FilingStatus.PENDING,
        )

        self.audit.record(filing_id, "START", "pipeline_started", {
            "country": adapter.country_code,
            "tax_type": tax_type.value,
            "period": data.period.period_key,
        })
        result.audit_trail = self.audit.get_trail(filing_id)
        result.status = StateMachine.transition(FilingStatus.PENDING, FilingStatus.IN_PROGRESS)

        # ── [1] PRECHECK ──
        precheck_ok = await self._stage_precheck(result, filing_id, adapter, tax_type, data)
        if not precheck_ok:
            return result

        # ── [2] PREPARE ──
        payload = await self._stage_prepare(result, filing_id, adapter, tax_type, data)
        if payload is None:
            return result

        # ── [3] CALCULATE ──
        calc_ok = await self._stage_calculate(result, filing_id, adapter, tax_type, data)
        if not calc_ok:
            return result

        # ── [4] VALIDATE ──
        valid_ok = await self._stage_validate(result, filing_id, adapter, tax_type, data)
        if not valid_ok:
            return result

        # ── [5] SUBMIT ──
        submitted = await self._stage_submit(result, filing_id, adapter, tax_type, payload)
        if not submitted:
            return result

        # ── [6] TRACK ──
        await self._stage_track(result, filing_id, adapter, tax_type)

        self.audit.record(filing_id, "END", "pipeline_completed", {
            "final_status": result.status.value,
        })
        self.audit.persist(filing_id)
        result.audit_trail = self.audit.get_trail(filing_id)
        return result

    # ── Private stage methods ──

    async def _stage_precheck(
        self, result: FilingResult, filing_id: str,
        adapter: JurisdictionAdapter, tax_type: TaxType, data: TaxData,
    ) -> bool:
        """PRECHECK: 基于模板做字段级数据校验"""
        try:
            template = adapter.get_template(tax_type)
        except Exception as e:
            self._fail(result, filing_id, "PRECHECK", f"get_template_failed", str(e),
                       recoverable=False)
            return False

        check_errors: list[FilingError] = []
        for section in template.sections:
            for field in section.fields:
                if field.required:
                    found = any(
                        li.category == field.key for li in data.line_items
                    )
                    if not found and not field.auto_calculated:
                        check_errors.append(FilingError(
                            code="MISSING_REQUIRED_FIELD",
                            message=f"Required field missing: {field.label}",
                            stage="PRECHECK",
                            recoverable=False,
                        ))
                    elif found and field.field_type == FieldType.NUMBER:
                        for li in data.line_items:
                            if li.category == field.key:
                                v = field.validation
                                if v.min is not None and li.amount < v.min:
                                    check_errors.append(FilingError(
                                        code="VALUE_TOO_LOW",
                                        message=f"{field.label}: min {v.min}",
                                        stage="PRECHECK",
                                        recoverable=False,
                                    ))
                                if v.max is not None and li.amount > v.max:
                                    check_errors.append(FilingError(
                                        code="VALUE_TOO_HIGH",
                                        message=f"{field.label}: max {v.max}",
                                        stage="PRECHECK",
                                        recoverable=False,
                                    ))

        if check_errors:
            result.errors.extend(check_errors)
            result.stage_results["PRECHECK"] = StageResult(
                stage="PRECHECK", status="error",
                message=f"{len(check_errors)} field errors",
                detail={"error_count": len(check_errors), "errors": [
                    {"code": e.code, "message": e.message} for e in check_errors
                ]},
            )
            self.audit.record(filing_id, "PRECHECK", "failed", {
                "error_count": len(check_errors),
            })
            result.status = FilingStatus.ERROR
            return False

        result.stage_results["PRECHECK"] = StageResult(
            stage="PRECHECK", status="success",
            message=f"Template version {template.version}",
            detail={"template_version": template.version, "fields_checked": len([
                f for s in template.sections for f in s.fields
            ])},
        )
        self.audit.record(filing_id, "PRECHECK", "passed", {
            "template_version": template.version,
        })
        return True

    async def _stage_prepare(
        self, result: FilingResult, filing_id: str,
        adapter: JurisdictionAdapter, tax_type: TaxType, data: TaxData,
    ) -> FilingPayload | None:
        """PREPARE: 渠道认证 + 数据格式转换"""
        try:
            channel = adapter.get_channel(tax_type)
        except Exception as e:
            self._fail(result, filing_id, "PREPARE", "channel_error", str(e),
                       recoverable=False)
            return None

        # 认证
        auth_result = await channel.authenticate()
        if not auth_result.success:
            self._fail(result, filing_id, "PREPARE", "auth_failed",
                       auth_result.error or "Unknown auth error",
                       recoverable=True)
            return None

        # 格式转换
        try:
            payload = adapter.to_filing_format(tax_type, data)
            payload.idempotency_key = filing_id
        except Exception as e:
            self._fail(result, filing_id, "PREPARE", "format_error", str(e),
                       recoverable=False)
            return None

        result.stage_results["PREPARE"] = StageResult(
            stage="PREPARE", status="success",
            message=f"Auth OK, channel={channel.channel_type.value}",
            detail={"channel": channel.channel_type.value, "auth_success": True},
        )
        self.audit.record(filing_id, "PREPARE", "passed", {
            "channel": channel.channel_type.value,
        })
        return payload

    async def _stage_calculate(
        self, result: FilingResult, filing_id: str,
        adapter: JurisdictionAdapter, tax_type: TaxType, data: TaxData,
    ) -> bool:
        """CALCULATE: 税务计算"""
        try:
            calc = adapter.calculate(tax_type, data)
        except Exception as e:
            self._fail(result, filing_id, "CALCULATE", "calculation_error", str(e),
                       recoverable=False)
            return False

        result.stage_results["CALCULATE"] = StageResult(
            stage="CALCULATE", status="success",
            message=f"Tax due: {calc.total_tax_due}",
            detail={
                "total_tax_due": str(calc.total_tax_due),
                "breakdown": [{"category": b.category, "amount": str(b.amount)} for b in calc.breakdown],
                "warnings": calc.warnings,
            },
        )
        self.audit.record(filing_id, "CALCULATE", "passed", {
            "total_tax_due": str(calc.total_tax_due),
            "breakdown_count": len(calc.breakdown),
            "warnings": calc.warnings,
        })
        return True

    async def _stage_validate(
        self, result: FilingResult, filing_id: str,
        adapter: JurisdictionAdapter, tax_type: TaxType, data: TaxData,
    ) -> bool:
        """VALIDATE: 合规性校验"""
        try:
            report = adapter.validate(tax_type, data)
        except Exception as e:
            self._fail(result, filing_id, "VALIDATE", "validation_error", str(e),
                       recoverable=False)
            return False

        if not report.is_valid:
            for err in report.errors:
                result.errors.append(FilingError(
                    code="VALIDATION_ERROR",
                    message=f"{err.field}: {err.message}",
                    stage="VALIDATE",
                    recoverable=False,
                ))
            result.stage_results["VALIDATE"] = StageResult(
                stage="VALIDATE", status="error",
                message=f"{len(report.errors)} errors, {len(report.warnings)} warnings",
                detail={
                    "error_count": len(report.errors),
                    "warning_count": len(report.warnings),
                    "errors": [{"field": e.field, "message": e.message} for e in report.errors],
                },
            )
            result.status = FilingStatus.ERROR
            return False

        if report.warnings and self.config.warn_policy == "strict":
            for w in report.warnings:
                result.errors.append(FilingError(
                    code="VALIDATION_WARNING",
                    message=f"{w.field}: {w.message}",
                    stage="VALIDATE",
                    recoverable=False,
                ))
            result.stage_results["VALIDATE"] = StageResult(
                stage="VALIDATE", status="error",
                message=f"Strict mode: {len(report.warnings)} warnings treated as errors",
                detail={"warning_count": len(report.warnings), "strict_mode": True},
            )
            result.status = FilingStatus.ERROR
            return False

        result.stage_results["VALIDATE"] = StageResult(
            stage="VALIDATE", status="success",
            message="Valid" + (f" ({len(report.warnings)} warnings)" if report.warnings else ""),
            detail={
                "warning_count": len(report.warnings),
                "warnings": [{"field": w.field, "message": w.message} for w in report.warnings],
            },
        )
        self.audit.record(filing_id, "VALIDATE", "passed", {
            "warnings": [w.message for w in report.warnings],
        })
        return True

    async def _stage_submit(
        self, result: FilingResult, filing_id: str,
        adapter: JurisdictionAdapter, tax_type: TaxType, payload: FilingPayload,
    ) -> bool:
        """SUBMIT: 提交申报（含重试）"""
        channel = adapter.get_channel(tax_type)

        for attempt in range(1, self.config.max_retries + 1):
            try:
                submit_result = await channel.submit(payload)
            except Exception as e:
                self.audit.record(filing_id, "SUBMIT", f"attempt_{attempt}_error", {
                    "error": str(e),
                })
                if attempt < self.config.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                self._fail(result, filing_id, "SUBMIT", "submit_exception", str(e),
                           recoverable=True)
                return False

            if submit_result.success:
                result.receipt = submit_result.receipt
                result.status = StateMachine.transition(
                    FilingStatus.IN_PROGRESS, FilingStatus.SUBMITTED
                )
                raw = submit_result.raw_response or {}
                result.stage_results["SUBMIT"] = StageResult(
                    stage="SUBMIT", status="success",
                    message=f"Receipt: {submit_result.receipt.receipt_id if submit_result.receipt else 'N/A'}",
                    detail={
                        "receipt_id": submit_result.receipt.receipt_id if submit_result.receipt else None,
                        "processing_date": raw.get("processingDate"),
                        "form_bundle_number": raw.get("formBundleNumber"),
                        "payment_indicator": raw.get("paymentIndicator"),
                        "charge_ref_number": raw.get("chargeRefNumber"),
                    },
                )
                self.audit.record(filing_id, "SUBMIT", "submitted", {
                    "receipt_id": submit_result.receipt.receipt_id if submit_result.receipt else None,
                })
                return True

            # submit_result.success == False
            is_retryable = self._is_retryable(submit_result.error_code or "")
            if is_retryable and attempt < self.config.max_retries:
                self.audit.record(filing_id, "SUBMIT", f"retry_{attempt}", {
                    "error": submit_result.error_message,
                })
                await asyncio.sleep(2 ** attempt)
                continue

            self._fail(result, filing_id, "SUBMIT", submit_result.error_code or "unknown",
                       submit_result.error_message or "Submit failed",
                       recoverable=is_retryable)
            return False

        self._fail(result, filing_id, "SUBMIT", "max_retries_exceeded",
                   f"Failed after {self.config.max_retries} attempts",
                   recoverable=True)
        return False

    async def _stage_track(
        self, result: FilingResult, filing_id: str,
        adapter: JurisdictionAdapter, tax_type: TaxType,
    ) -> None:
        """TRACK: 轮询状态直到终态或超时"""
        if result.receipt is None:
            return

        channel = adapter.get_channel(tax_type)
        deadline = datetime.now(timezone.utc).timestamp() + self.config.track_timeout_hours * 3600

        while datetime.now(timezone.utc).timestamp() < deadline:
            try:
                status_result = await channel.get_status(result.receipt)
            except Exception:
                status_result = StatusResult(status=FilingStatus.SUBMITTED)

            if StateMachine.is_terminal(status_result.status):
                result.status = status_result.status
                result.stage_results["TRACK"] = StageResult(
                    stage="TRACK", status="success",
                    message=f"Final: {status_result.status.value} — {status_result.detail}",
                    detail={"final_status": status_result.status.value, "detail": status_result.detail},
                )
                self.audit.record(filing_id, "TRACK", "completed", {
                    "final_status": status_result.status.value,
                    "detail": status_result.detail,
                })
                return

            await asyncio.sleep(self.config.track_poll_interval_seconds)

        result.stage_results["TRACK"] = StageResult(
            stage="TRACK", status="warning",
            message="Tracking timeout reached, still SUBMITTED",
            detail={"timeout_hours": self.config.track_timeout_hours},
        )
        self.audit.record(filing_id, "TRACK", "timeout", {
            "timeout_hours": self.config.track_timeout_hours,
        })

    # ── Helpers ──

    def _fail(
        self, result: FilingResult, filing_id: str,
        stage: str, code: str, message: str, recoverable: bool,
    ) -> None:
        err = FilingError(
            code=code, message=message, stage=stage, recoverable=recoverable,
        )
        result.errors.append(err)
        result.stage_results[stage] = StageResult(
            stage=stage, status="error", message=message,
            detail={"code": code, "recoverable": recoverable},
        )
        result.status = FilingStatus.ERROR
        self.audit.record(filing_id, stage, "failed", {
            "code": code, "message": message,
        })

    @staticmethod
    def _generate_filing_id(country: str, tax_type: TaxType, period_key: str) -> str:
        short_uuid = uuid.uuid4().hex[:8]
        return f"{country}-{tax_type.value}-{period_key}-{short_uuid}"

    @staticmethod
    def _is_retryable(error_code: str) -> bool:
        retryable_codes = {"RATE_LIMITED", "SERVICE_UNAVAILABLE", "NETWORK_ERROR",
                          "GATEWAY_TIMEOUT", "submit_exception"}
        return error_code.upper() in retryable_codes