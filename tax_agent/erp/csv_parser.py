"""CSV 解析器入口 — bytes → ImportResult"""
from __future__ import annotations

import csv
import hashlib
import io
from decimal import Decimal
from typing import List, Tuple

from ..models.erp_models import (
    ERPNineBox, ImportResult, SalesTransaction, PurchaseTransaction,
)
from .profiles import GenericProfile, REQUIRED_COLUMNS


class CsvParseError(ValueError):
    """Header-level CSV 错误（不是单行错误）"""


_PROFILES = {"generic": GenericProfile()}


def detect_profile(headers: List[str]) -> Tuple[str, float]:
    """根据 header 行检测最匹配的 profile。返回 (profile_name, confidence)。
    v0 只有一个 profile，固定返 generic。"""
    best_name, best_score = "generic", 0.0
    for name, p in _PROFILES.items():
        score = p.detect(headers)
        if score > best_score:
            best_name, best_score = name, score
    return best_name, best_score


def parse_csv(file_bytes: bytes, profile: str | None = None) -> ImportResult:
    """解析 CSV bytes → ImportResult。

    - profile=None: auto-detect
    - profile='generic': 强制走 GenericProfile
    - 行级错误写入 rejected_rows，不抛异常
    - header 缺失/污染 → 抛 CsvParseError
    """
    # 1. 解码 + 去 BOM
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise CsvParseError(f"file not utf-8: {e}") from e

    # 2. 读 header
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    if not headers:
        raise CsvParseError("file has no header row")

    # 3. 选 profile
    if profile is None:
        profile, _ = detect_profile(headers)
    if profile not in _PROFILES:
        raise CsvParseError(f"unknown profile: {profile!r}")
    profile_obj = _PROFILES[profile]

    # 4. 检查必填列
    headers_lower = [h.strip().lower() for h in headers]
    missing = [c for c in REQUIRED_COLUMNS if c not in headers_lower]
    if missing:
        raise CsvParseError(f"header missing required column(s): {missing}")

    # 5. 逐行解析
    sales: List[SalesTransaction] = []
    purchases: List[PurchaseTransaction] = []
    rejected: List[dict] = []
    warnings: List[str] = []

    for row_index, row in enumerate(reader, start=1):  # 1=first data row
        if not any(row.values()):  # 空行
            continue
        txn, err = profile_obj.transform_row(row, row_index)
        if err:
            rejected.append({"row_index": row_index, "reason": err, "raw": dict(row)})
            continue
        if isinstance(txn, SalesTransaction):
            sales.append(txn)
        elif isinstance(txn, PurchaseTransaction):
            purchases.append(txn)

    # 6. 算 9-Box（v0 简化：从交易数据汇总，不调 reconcile.py）
    nine_box = _compute_9box_from_transactions(sales, purchases)

    # 7. source hash
    source_hash = hashlib.sha256(file_bytes).hexdigest()[:16]

    return ImportResult(
        sales=sales,
        purchases=purchases,
        erp_provided_boxes=nine_box,
        source_profile=profile,
        source_filename="<from-bytes>",
        source_hash=source_hash,
        warnings=warnings,
        rejected_rows=rejected,
    )


def _compute_9box_from_transactions(
    sales: List[SalesTransaction], purchases: List[PurchaseTransaction],
) -> ERPNineBox:
    """v0 简化版 9-Box 计算（不调 reconcile.py，避免循环 import）。"""
    box1 = sum((t.vat_amount for t in sales if t.vat_rate > 0), Decimal("0"))
    box2 = sum((t.vat_amount for t in purchases if t.is_eu_acquisition), Decimal("0"))
    box3 = box1 + box2
    box4 = sum((t.vat_amount for t in purchases if t.is_recoverable), Decimal("0"))
    box5 = abs(box3 - box4)
    box6 = int(sum((t.net_amount for t in sales), Decimal("0")))
    box7 = int(sum((t.net_amount for t in purchases), Decimal("0")))
    box8 = int(sum((t.net_amount for t in sales if t.is_eu), Decimal("0")))
    box9 = int(sum((t.net_amount for t in purchases if t.is_eu_acquisition), Decimal("0")))
    return ERPNineBox(
        box1_vat_due_sales=box1,
        box2_vat_due_acquisitions=box2,
        box3_total_vat_due=box3,
        box4_vat_reclaimed=box4,
        box5_net_vat_due=box5,
        box6_total_sales_ex_vat=box6,
        box7_total_purchases_ex_vat=box7,
        box8_total_goods_supplied_eu=box8,
        box9_total_goods_acquired_eu=box9,
    )
