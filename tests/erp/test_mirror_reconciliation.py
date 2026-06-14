"""关联交易镜像对账 — 单元测试"""

from datetime import date
from decimal import Decimal

import pytest

from backend.erp.reconciliation import (
    MirrorTxn,
    MirrorPair,
    MirrorReconciliationReport,
    reconcile_mirror,
    txn_from_dict,
    DEFAULT_TOLERANCE,
)


# ── Fixtures ──


def make_uk(id_="C1-109", related="C1-011", amount=12500, fx=8.6, tax=1250,
            txn_type="interest_payment", txn_date=None, currency="GBP"):
    return MirrorTxn(
        id=id_,
        date=txn_date or date(2023, 4, 10),
        amount=Decimal(str(amount)),
        currency=currency,
        fx_rate=Decimal(str(fx)),
        tax_amount=Decimal(str(tax)),
        counterparty="Jiangsu Jiahang (CN parent)",
        related_party_id=related,
        side="uk",
        txn_type=txn_type,
    )


def make_cn(id_="C1-011", related="C1-109", amount=107500, fx=None, tax=10750,
            txn_type="interest_received", txn_date=None, currency="CNY"):
    """CN side: amount already in CNY; fx_rate not needed when currency is base."""
    return MirrorTxn(
        id=id_,
        date=txn_date or date(2023, 4, 10),
        amount=Decimal(str(amount)),
        currency=currency,
        fx_rate=Decimal(str(fx)) if fx is not None else None,
        tax_amount=Decimal(str(tax)),
        counterparty="Jiahang UK Holdings (UK sub)",
        related_party_id=related,
        side="cn",
        txn_type=txn_type,
    )


# ── Basic pairing ──


class TestBasicPairing:

    def test_simple_pair(self):
        """UK 利息 + CN 利息收入匹配"""
        uk = make_uk(amount=12500, fx=8.6, tax=1250)  # base = 107500
        cn = make_cn(amount=107500, tax=10750)
        report = reconcile_mirror([uk], [cn], base_currency="CNY")
        assert report.total_pairs == 1
        assert report.balanced_pairs == 1
        assert report.unmatched_uk == []
        assert report.unmatched_cn == []

    def test_pair_uk_rp_points_to_cn_id(self):
        """UK.related_party_id 指向 CN.id"""
        uk = make_uk(id_="UK-001", related="CN-001")
        cn = make_cn(id_="CN-001", related="UK-001")
        report = reconcile_mirror([uk], [cn])
        assert report.total_pairs == 1

    def test_pair_cn_rp_points_to_uk_id(self):
        """CN.related_party_id 指向 UK.id"""
        uk = make_uk(id_="UK-002")
        cn = make_cn(id_="CN-002", related="UK-002")
        report = reconcile_mirror([uk], [cn])
        assert report.total_pairs == 1


# ── Unmatched ──


class TestUnmatched:

    def test_uk_only_no_cn_counterpart(self):
        uk = make_uk(id_="UK-orphan")
        report = reconcile_mirror([uk], [])
        assert report.total_pairs == 0
        assert report.unmatched_uk == [uk]

    def test_cn_only_no_uk_counterpart(self):
        cn = make_cn(id_="CN-orphan")
        report = reconcile_mirror([], [cn])
        assert report.total_pairs == 0
        assert report.unmatched_cn == [cn]

    def test_skip_txns_without_related_party_id(self):
        uk = MirrorTxn(id="UK-norp", date=date(2023, 1, 1), amount=Decimal("100"),
                       currency="GBP", side="uk")
        cn = MirrorTxn(id="CN-norp", date=date(2023, 1, 1), amount=Decimal("860"),
                       currency="CNY", side="cn")
        report = reconcile_mirror([uk], [cn])
        assert report.total_pairs == 0
        assert report.unmatched_uk == [uk]
        assert report.unmatched_cn == [cn]


# ── Amount discrepancies ──


class TestAmountChecks:

    def test_amount_within_tolerance(self):
        """rounding 差异(£0.5 内)→ info level,不阻挡 balanced"""
        uk = make_uk(amount=12500, fx=8.6)  # base = 107500.00
        cn = make_cn(amount=107500.50, tax=0)  # +0.5 rounding
        report = reconcile_mirror([uk], [cn])
        assert report.balanced_pairs == 1
        info = [d for d in report.pairs[0].discrepancies if d.severity == "info"]
        assert any("rounding" in d.message for d in info)

    def test_amount_exceeds_tolerance_error(self):
        """大差异 → error"""
        uk = make_uk(amount=12500, fx=8.6)  # base = 107500
        cn = make_cn(amount=110000)         # +2500 diff
        report = reconcile_mirror([uk], [cn])
        assert report.error_pairs == 1
        amount_err = [d for d in report.pairs[0].discrepancies if d.field == "amount"]
        assert amount_err[0].severity == "error"

    def test_fx_must_be_consistent(self):
        """UK/CN 双方对同一基准的 FX 应当接近"""
        uk = make_uk(amount=1000, fx=8.6)   # base 8600
        cn = make_cn(amount=8600, fx=8.6)   # mismatched currency use case
        # 这里两边都给了 fx,因为 currency 不同(GBP vs CNY),会触发 FX check
        report = reconcile_mirror([uk], [cn])
        # 双方都是 8.6 → 0 差异,no warning
        fx_warnings = [d for d in report.pairs[0].discrepancies if d.field == "fx_rate"]
        assert fx_warnings == []

    def test_fx_diverges_warning(self):
        uk = make_uk(amount=1000, fx=8.6)
        cn = make_cn(amount=8600, fx=9.0)  # +4.6% FX 差
        report = reconcile_mirror([uk], [cn])
        fx_warnings = [d for d in report.pairs[0].discrepancies
                       if d.field == "fx_rate" and d.severity == "warning"]
        assert len(fx_warnings) == 1


# ── Date checks ──


class TestDateChecks:

    def test_dates_within_tolerance(self):
        uk = make_uk(txn_date=date(2023, 4, 10))
        cn = make_cn(txn_date=date(2023, 4, 12))  # +2 days
        report = reconcile_mirror([uk], [cn])
        assert report.balanced_pairs == 1
        date_warnings = [d for d in report.pairs[0].discrepancies
                         if d.field == "date"]
        assert date_warnings == []

    def test_dates_exceed_tolerance_warning(self):
        uk = make_uk(txn_date=date(2023, 4, 10))
        cn = make_cn(txn_date=date(2023, 5, 1))  # +21 days
        report = reconcile_mirror([uk], [cn])
        date_warnings = [d for d in report.pairs[0].discrepancies
                        if d.field == "date"]
        assert date_warnings[0].severity == "warning"


# ── Tax / WHT checks ──


class TestTaxChecks:

    def test_wht_consistent(self):
        """UK WHT £1,250 ↔ CN 计提 ¥10,750(8.6×1,250)"""
        uk = make_uk(tax=1250)
        cn = make_cn(tax=10750)
        report = reconcile_mirror([uk], [cn])
        tax_warnings = [d for d in report.pairs[0].discrepancies if d.field == "tax"]
        assert tax_warnings == []

    def test_wht_mismatch_warning(self):
        uk = make_uk(tax=1250)
        cn = make_cn(tax=12500)  # 数量级差 → 警告
        report = reconcile_mirror([uk], [cn])
        tax_warnings = [d for d in report.pairs[0].discrepancies if d.field == "tax"]
        assert tax_warnings[0].severity == "warning"


# ── Direction checks ──


class TestDirectionChecks:

    def test_directions_match(self):
        uk = make_uk(txn_type="interest_payment")
        cn = make_cn(txn_type="interest_received")
        report = reconcile_mirror([uk], [cn])
        dir_err = [d for d in report.pairs[0].discrepancies if d.field == "direction"]
        assert dir_err == []

    def test_directions_mismatch_error(self):
        uk = make_uk(txn_type="interest_payment")
        cn = make_cn(txn_type="dividend_received")
        report = reconcile_mirror([uk], [cn])
        dir_err = [d for d in report.pairs[0].discrepancies if d.field == "direction"]
        assert dir_err[0].severity == "error"

    def test_directions_symmetric(self):
        """对称匹配:方向 pair 反过来也算"""
        uk = make_uk(txn_type="loan_disbursement")
        cn = make_cn(txn_type="capital_injection")
        report = reconcile_mirror([uk], [cn])
        dir_err = [d for d in report.pairs[0].discrepancies if d.field == "direction"]
        assert dir_err == []


# ── Summary ──


class TestSummary:

    def test_summary_coverage(self):
        uk = make_uk()
        cn = make_cn()
        uk2 = make_uk(id_="UK-orphan")
        report = reconcile_mirror([uk, uk2], [cn])
        s = report.summary()
        assert s["uk_transactions"] == 2
        assert s["cn_transactions"] == 1
        assert s["pairs"] == 1
        assert s["unmatched_uk"] == 1
        assert s["unmatched_cn"] == 0
        assert s["coverage_uk_pct"] == "50.0%"
        assert s["coverage_cn_pct"] == "100.0%"

    def test_balanced_count(self):
        uks = [make_uk(id_=f"UK-{i}", related=f"CN-{i}") for i in range(3)]
        cns = [make_cn(id_=f"CN-{i}", related=f"UK-{i}") for i in range(3)]
        # 故意让一对金额不对
        cns[0] = make_cn(id_="CN-0", related="UK-0", amount=999999)
        report = reconcile_mirror(uks, cns)
        assert report.total_pairs == 3
        assert report.balanced_pairs == 2
        assert report.error_pairs == 1


# ── Dictionary conversion ──


class TestDictConversion:

    def test_txn_from_dict_jiahang_format(self):
        d = {
            "id": "C1-109",
            "txn_date": "2023-04-10",
            "net_amount": 12500,
            "vat_amount": 1250,
            "currency": "GBP",
            "fx_rate": 8.6,
            "related_party_id": "C1-011",
            "txn_type": "interest_payment",
            "counterparty": "Jiangsu Jiahang (CN parent)",
            "notes": "贷款利息第一期",
        }
        t = txn_from_dict(d, side="uk")
        assert t.id == "C1-109"
        assert t.amount == Decimal("12500")
        assert t.fx_rate == Decimal("8.6")
        assert t.related_party_id == "C1-011"
        assert t.side == "uk"
        assert t.base_amount == Decimal("107500.00")

    def test_txn_from_dict_missing_net_falls_back_gross(self):
        d = {
            "id": "T1",
            "txn_date": "2023-01-01",
            "gross_amount": 1000,
            "currency": "GBP",
        }
        t = txn_from_dict(d, side="uk")
        assert t.amount == Decimal("1000")

    def test_txn_from_dict_no_fx_returns_amount(self):
        d = {
            "id": "T1",
            "txn_date": "2023-01-01",
            "net_amount": 5000,
            "currency": "CNY",
        }
        t = txn_from_dict(d, side="cn")
        assert t.base_amount == Decimal("5000")  # no fx, returns amount
