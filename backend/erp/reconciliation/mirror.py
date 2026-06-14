"""关联交易镜像对账 — UK ↔ CN 双方同一笔关联交易的一致性核对

场景:
嘉汉案例中,UK 子公司与 CN 母公司之间存在多笔关联交易(母公司追加资本、
进口机械、贷款利息、特许权、股息等)。两边 ERP 系统独立记账,需要自动
对账确保:
- 同一笔交易在双方账套中存在
- 金额、汇率一致(折算到同一基准货币)
- 交易日期接近
- WHT 扣缴与境外税收抵免互相呼应
- 方向一致(UK 支出 ↔ CN 收入)

输入:
- `uk_transactions`: UK 侧 transaction 列表(每条带 related_party_id)
- `cn_transactions`: CN 侧 transaction 列表(每条带 related_party_id)
- `base_currency`: 折算基准货币(默认 "CNY")

输出:
- `MirrorReconciliationReport`: 含成对/未成对/差异,每对差异列出原因
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


# ── Constants ──

DEFAULT_TOLERANCE = Decimal("1.00")          # 金额容差(基准货币)
DEFAULT_DATE_TOLERANCE_DAYS = 7              # 日期容差
DEFAULT_FX_TOLERANCE = Decimal("0.02")       # 汇率容差(±2%)


# ── Data classes ──


@dataclass
class MirrorTxn:
    """对账用交易记录(归一化自两边 ERP 格式)"""
    id: str
    date: date
    amount: Decimal                      # net amount(原币)
    currency: str                        # 原币(GBP/CNY/EUR ...)
    fx_rate: Optional[Decimal] = None    # 折算到基准货币的汇率
    tax_amount: Decimal = Decimal("0")
    counterparty: str = ""
    description: str = ""
    related_party_id: Optional[str] = None   # 指向对方账套的 id
    side: str = ""                       # "uk" | "cn" — 标识原始来源
    txn_type: str = ""                   # loan_disbursement, interest_payment ...

    @property
    def base_amount(self) -> Decimal:
        """折算到基准货币的金额(fx_rate 缺失返回原值)。"""
        if self.fx_rate is None or self.fx_rate == 0:
            return self.amount
        return (self.amount * self.fx_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class MirrorDiscrepancy:
    """单对镜像的一处差异"""
    field: str                            # "amount" | "date" | "fx_rate" | "tax" | "direction"
    severity: str                         # "error" | "warning"
    message: str
    uk_value: Optional[str] = None
    cn_value: Optional[str] = None
    delta: Optional[Decimal] = None


@dataclass
class MirrorPair:
    """配对的关联交易"""
    uk_txn: MirrorTxn
    cn_txn: MirrorTxn
    discrepancies: list[MirrorDiscrepancy] = field(default_factory=list)

    @property
    def is_balanced(self) -> bool:
        return len([d for d in self.discrepancies if d.severity == "error"]) == 0

    @property
    def has_warnings(self) -> bool:
        return any(d.severity == "warning" for d in self.discrepancies)

    @property
    def pair_id(self) -> str:
        return f"{self.uk_txn.id}↔{self.cn_txn.id}"


@dataclass
class MirrorReconciliationReport:
    """完整对账报告"""
    base_currency: str
    pairs: list[MirrorPair] = field(default_factory=list)
    unmatched_uk: list[MirrorTxn] = field(default_factory=list)
    unmatched_cn: list[MirrorTxn] = field(default_factory=list)
    tolerance_amount: Decimal = DEFAULT_TOLERANCE
    tolerance_days: int = DEFAULT_DATE_TOLERANCE_DAYS

    @property
    def total_pairs(self) -> int:
        return len(self.pairs)

    @property
    def balanced_pairs(self) -> int:
        return sum(1 for p in self.pairs if p.is_balanced)

    @property
    def pair_with_warnings(self) -> int:
        return sum(1 for p in self.pairs if p.has_warnings and p.is_balanced)

    @property
    def error_pairs(self) -> int:
        return sum(1 for p in self.pairs if not p.is_balanced)

    @property
    def total_uk_txns(self) -> int:
        return len(self.pairs) + len(self.unmatched_uk)

    @property
    def total_cn_txns(self) -> int:
        return len(self.pairs) + len(self.unmatched_cn)

    def summary(self) -> dict:
        return {
            "base_currency": self.base_currency,
            "uk_transactions": self.total_uk_txns,
            "cn_transactions": self.total_cn_txns,
            "pairs": self.total_pairs,
            "balanced": self.balanced_pairs,
            "with_warnings": self.pair_with_warnings,
            "errors": self.error_pairs,
            "unmatched_uk": len(self.unmatched_uk),
            "unmatched_cn": len(self.unmatched_cn),
            "coverage_uk_pct": (
                f"{self.total_pairs / self.total_uk_txns * 100:.1f}%"
                if self.total_uk_txns else "n/a"
            ),
            "coverage_cn_pct": (
                f"{self.total_pairs / self.total_cn_txns * 100:.1f}%"
                if self.total_cn_txns else "n/a"
            ),
        }


# ── Pairing logic ──


def _pair_key(t: MirrorTxn) -> Optional[str]:
    """返回用于配对的 key(related_party_id)。None 表示不参与对账。"""
    if not t.related_party_id:
        return None
    return t.related_party_id.strip()


def reconcile_mirror(
    uk_transactions: list[MirrorTxn],
    cn_transactions: list[MirrorTxn],
    base_currency: str = "CNY",
    tolerance_amount: Decimal = DEFAULT_TOLERANCE,
    tolerance_days: int = DEFAULT_DATE_TOLERANCE_DAYS,
    tolerance_fx: Decimal = DEFAULT_FX_TOLERANCE,
) -> MirrorReconciliationReport:
    """对账 UK ↔ CN 关联交易。

    配对规则:
    - UK 的 `related_party_id` = CN 的 `id`,或反之
    - 双向映射都尝试:任一边的 related_party_id 指向另一边
    """
    # 索引:CN 端按 id 查,UK 端按 related_party_id 查
    cn_by_id: dict[str, MirrorTxn] = {t.id: t for t in cn_transactions}
    uk_by_rp: dict[str, MirrorTxn] = {
        rp: t for t in uk_transactions if (rp := _pair_key(t))
    }

    pairs: list[MirrorPair] = []
    matched_uk_ids: set[str] = set()
    matched_cn_ids: set[str] = set()

    # Pass 1: UK → CN 配对(用 UK 的 related_party_id 查 CN)
    for uk in uk_transactions:
        rp = _pair_key(uk)
        if not rp or rp not in cn_by_id:
            continue
        cn = cn_by_id[rp]
        # 一个 UK id 只能配一次
        if uk.id in matched_uk_ids or cn.id in matched_cn_ids:
            continue
        pair = MirrorPair(uk_txn=uk, cn_txn=cn)
        _check_pair(pair, base_currency, tolerance_amount, tolerance_days, tolerance_fx)
        pairs.append(pair)
        matched_uk_ids.add(uk.id)
        matched_cn_ids.add(cn.id)

    # Pass 2: CN → UK 配对(用 CN 的 related_party_id 查 UK,覆盖上面没配上的)
    uk_by_id: dict[str, MirrorTxn] = {t.id: t for t in uk_transactions}
    for cn in cn_transactions:
        if cn.id in matched_cn_ids:
            continue
        rp = _pair_key(cn)
        if not rp or rp not in uk_by_id:
            continue
        uk = uk_by_id[rp]
        if uk.id in matched_uk_ids:
            continue
        pair = MirrorPair(uk_txn=uk, cn_txn=cn)
        _check_pair(pair, base_currency, tolerance_amount, tolerance_days, tolerance_fx)
        pairs.append(pair)
        matched_uk_ids.add(uk.id)
        matched_cn_ids.add(cn.id)

    # 未成对
    unmatched_uk = [t for t in uk_transactions if t.id not in matched_uk_ids]
    unmatched_cn = [t for t in cn_transactions if t.id not in matched_cn_ids]

    return MirrorReconciliationReport(
        base_currency=base_currency,
        pairs=pairs,
        unmatched_uk=unmatched_uk,
        unmatched_cn=unmatched_cn,
        tolerance_amount=tolerance_amount,
        tolerance_days=tolerance_days,
    )


# ── Per-pair checks ──


def _check_pair(
    pair: MirrorPair,
    base_currency: str,
    tol_amount: Decimal,
    tol_days: int,
    tol_fx: Decimal,
) -> None:
    uk, cn = pair.uk_txn, pair.cn_txn

    # 1) 日期接近(±tol_days)
    if uk.date and cn.date:
        delta_days = abs((uk.date - cn.date).days)
        if delta_days > tol_days:
            pair.discrepancies.append(MirrorDiscrepancy(
                field="date",
                severity="warning",
                message=(
                    f"交易日期相差 {delta_days} 天(超过容差 {tol_days} 天): "
                    f"UK {uk.date.isoformat()} vs CN {cn.date.isoformat()}"
                ),
                uk_value=uk.date.isoformat(),
                cn_value=cn.date.isoformat(),
                delta=Decimal(delta_days),
            ))

    # 2) 折算后金额一致(基准货币)
    uk_base = uk.base_amount
    cn_base = cn.base_amount
    amt_delta = abs(uk_base - cn_base)
    if amt_delta > tol_amount:
        pair.discrepancies.append(MirrorDiscrepancy(
            field="amount",
            severity="error",
            message=(
                f"折算 {base_currency} 后金额差异 {amt_delta}: "
                f"UK {uk_base} vs CN {cn_base}"
            ),
            uk_value=str(uk_base),
            cn_value=str(cn_base),
            delta=amt_delta,
        ))
    elif amt_delta > 0:
        # 差异 ≤ tolerance 算作正常(rounding)
        pair.discrepancies.append(MirrorDiscrepancy(
            field="amount",
            severity="info",
            message=(
                f"折算后差异 {amt_delta} ≤ tolerance {tol_amount}(rounding 容差)"
            ),
            uk_value=str(uk_base),
            cn_value=str(cn_base),
            delta=amt_delta,
        ))

    # 3) 汇率一致性(同币种对同一基准,FX 应当匹配)
    if uk.fx_rate is not None and cn.fx_rate is not None and uk.currency != cn.currency:
        fx_diff = abs(uk.fx_rate - cn.fx_rate)
        fx_avg = (uk.fx_rate + cn.fx_rate) / 2
        if fx_avg > 0 and fx_diff / fx_avg > tol_fx:
            pair.discrepancies.append(MirrorDiscrepancy(
                field="fx_rate",
                severity="warning",
                message=(
                    f"汇率差异 {fx_diff} (UK {uk.fx_rate} vs CN {cn.fx_rate})"
                    f"超过 ±{tol_fx * 100}% 容差"
                ),
                uk_value=str(uk.fx_rate),
                cn_value=str(cn.fx_rate),
                delta=fx_diff,
            ))

    # 4) 税额 / WHT 一致性(对 WHT 类交易,UK 扣缴应当 ≈ CN 计提)
    # 折算到基准货币后比较
    if uk.tax_amount > 0 or cn.tax_amount > 0:
        if uk.tax_amount > 0 and cn.tax_amount > 0:
            # 折算 UK 税到基准货币
            uk_tax_base = (
                (uk.tax_amount * uk.fx_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if uk.fx_rate and uk.currency != base_currency else uk.tax_amount
            )
            cn_tax_base = (
                (cn.tax_amount * cn.fx_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if cn.fx_rate and cn.currency != base_currency else cn.tax_amount
            )
            tax_delta = abs(uk_tax_base - cn_tax_base)
            if tax_delta > tol_amount:
                pair.discrepancies.append(MirrorDiscrepancy(
                    field="tax",
                    severity="warning",
                    message=(
                        f"税额差异 {tax_delta} (基准 {base_currency}): "
                        f"UK WHT {uk_tax_base} vs CN 计提 {cn_tax_base}"
                    ),
                    uk_value=str(uk_tax_base),
                    cn_value=str(cn_tax_base),
                    delta=tax_delta,
                ))

    # 5) 方向(UK 支出 vs CN 收入 / UK 收入 vs CN 支出)
    if uk.txn_type and cn.txn_type:
        # 反向类型应匹配(loan_disbursement on UK side ↔ capital_injection on CN side)
        if not _directions_match(uk.txn_type, cn.txn_type):
            pair.discrepancies.append(MirrorDiscrepancy(
                field="direction",
                severity="error",
                message=(
                    f"交易方向不匹配: UK {uk.txn_type} vs CN {cn.txn_type}"
                ),
                uk_value=uk.txn_type,
                cn_value=cn.txn_type,
            ))


# 反向方向对(UK → CN 资金方向)
_DIRECTION_PAIRS = {
    ("loan_disbursement", "capital_injection"),       # 母公司追加资本
    ("loan_repayment", "loan_collection"),            # 还款
    ("interest_payment", "interest_received"),        # 利息(WHT 类)
    ("royalty_payment", "royalty_received"),          # 特许权(WHT 类)
    ("dividend_paid", "dividend_received"),           # 股息
    ("import_goods", "export_goods"),                 # 进出口
    ("service_received", "service_provided"),         # 服务
    ("management_fee_paid", "management_fee_received"),  # 管理费
}


def _directions_match(uk_type: str, cn_type: str) -> bool:
    pair = (uk_type, cn_type)
    if pair in _DIRECTION_PAIRS:
        return True
    # 允许对称匹配
    return (cn_type, uk_type) in _DIRECTION_PAIRS


# ── Convenience: 字典 → MirrorTxn ──


def txn_from_dict(d: dict, side: str) -> MirrorTxn:
    """从 ERP 字典格式构造 MirrorTxn。

    支持 jiahang erp_import.json 的字段名:
    - id, txn_date, net_amount/gross_amount, currency, fx_rate,
      vat_amount, counterparty, related_party_id, txn_type, notes
    """
    txn_date = d.get("txn_date")
    if isinstance(txn_date, str):
        parsed_date = date.fromisoformat(txn_date)
    elif isinstance(txn_date, date):
        parsed_date = txn_date
    else:
        parsed_date = date.today()

    # net_amount 优先,缺失回退 gross_amount
    amt = d.get("net_amount")
    if amt is None:
        amt = d.get("gross_amount", 0)
    return MirrorTxn(
        id=d["id"],
        date=parsed_date,
        amount=Decimal(str(amt)),
        currency=d.get("currency", "GBP" if side == "uk" else "CNY"),
        fx_rate=(
            Decimal(str(d["fx_rate"])) if d.get("fx_rate") is not None else None
        ),
        tax_amount=Decimal(str(d.get("vat_amount", 0) or 0)),
        counterparty=d.get("counterparty", ""),
        description=d.get("notes", ""),
        related_party_id=d.get("related_party_id"),
        side=side,
        txn_type=d.get("txn_type", ""),
    )
