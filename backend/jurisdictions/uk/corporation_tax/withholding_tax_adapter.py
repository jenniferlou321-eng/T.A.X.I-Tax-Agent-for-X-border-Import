"""Withholding Tax 计算桥接器 — CT adapter 内部使用。

将 `uk/withholding_tax/calculator.py` 中的 DTA 税率表封装成 3 个简单函数,
供 `UKCTAdapter._build_wht_entries()` 调用,无需重复维护税率表。

返回 (rate, wht_amount, treaty_rate) 三元组:
- rate:        实际申报税率 (DTA 协定税率)
- wht_amount:  实际应扣税额 (gross × rate)
- treaty_rate: DTA 协定税率 (Decimal 字符串,如 "0.10")
"""

from __future__ import annotations

from decimal import Decimal

from backend.jurisdictions.uk.withholding_tax.calculator import get_treaty_rate


def compute_wht_interest(gross: float, recipient_country: str) -> tuple[float, float, str]:
    """计算利息 WHT。"""
    rate = get_treaty_rate(recipient_country, "interest")
    wht = float(Decimal(str(gross)) * rate)
    return float(rate), round(wht, 2), str(rate)


def compute_wht_royalty(gross: float, recipient_country: str) -> tuple[float, float, str]:
    """计算特许权使用费 WHT。"""
    rate = get_treaty_rate(recipient_country, "royalty")
    wht = float(Decimal(str(gross)) * rate)
    return float(rate), round(wht, 2), str(rate)


def compute_wht_dividend(
    gross: float,
    recipient_country: str,
    ownership_pct: float = 100.0,
) -> tuple[float, float, str]:
    """计算股息 WHT (UK 一般为 0%,除非非协定或小持股)。"""
    rate = get_treaty_rate(recipient_country, "dividend", Decimal(str(ownership_pct)))
    wht = float(Decimal(str(gross)) * rate)
    return float(rate), round(wht, 2), str(rate)
