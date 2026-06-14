"""CT600 GovTalk Body Builder — 构建 Corporation Tax Return 的 IRenvelope XML。

CT600 通过 GovTalk XML 提交到 HMRC Transaction Engine。
Class = "HMRC-CT-CT600"
Schema namespace = "http://www.govtalk.gov.uk/taxation/CT/5.0"

支持:
- 主表 CT600 全部 box (trading / non-trading / capital allowances / reliefs / computation)
- Supplementary — WHT Interest / WHT Royalty 申报(由 UK→境外付款代扣)
- Supplementary — 多笔付款 + 多收款国(每条 disclosure 一个 SupplementaryEntry)
"""

from __future__ import annotations

from typing import Iterable

from xml.etree import ElementTree as ET

NS_CT = "http://www.govtalk.gov.uk/taxation/CT/5.0"


def build_ct600_body(
    ctref: str,
    company_name: str,
    period_start: str,
    period_end: str,
    line_map: dict[str, float | int | str],
    wht_entries: Iterable[dict] | None = None,
) -> str:
    """构建 CT600 的 IRenvelope XML body。

    Args:
        ctref: Corporation Tax Reference (10 位数字)
        company_name: 公司名称
        period_start: 会计期间开始 (YYYY-MM-DD)
        period_end: 会计期间结束 (YYYY-MM-DD)
        line_map: CT600 各 box 值,来自 adapter 的 to_filing_format()
            常见 key: turnover, trading_income, trading_expenses,
            investment_income, property_income, chargeable_gains,
            capital_allowances_claimed, trading_losses_brought_forward,
            group_relief_claimed, rd_qualifying_expenditure,
            taxable_total_profits, ct_rate_applied,
            corporation_tax_chargeable, tax_already_paid,
            amount_payable, num_associated_companies, etc.
        wht_entries: WHT supplementary entries (由 calculate_wht() 输出)
            每条 dict 形如:
              {
                "income_type": "interest" | "royalty" | "dividend",
                "gross_amount": Decimal/str,
                "wht_amount": Decimal/str,
                "rate": Decimal/str (e.g. "0.10"),
                "treaty_rate": Decimal/str,
                "recipient_country": "CN" | "HK" | ...,
                "recipient_name": "江苏嘉汉国际贸易有限公司",
                "date_paid": "2023-12-15",
              }

    Returns:
        CT600 业务 XML 字符串 (不含 GovTalk envelope,直接喂给 GovTalkClient.submit)
    """
    ir = ET.Element(f"{{{NS_CT}}}IRenvelope")
    ct600 = ET.SubElement(ir, f"{{{NS_CT}}}CT600")

    # 固定标识字段
    _add_text(ct600, f"{{{NS_CT}}}CTREF", ctref)
    _add_text(ct600, f"{{{NS_CT}}}CompanyName", company_name)
    _add_text(ct600, f"{{{NS_CT}}}PeriodStart", period_start)
    _add_text(ct600, f"{{{NS_CT}}}PeriodEnd", period_end)

    # 会计期间日期 (IRmark 前必须有)
    _add_text(ct600, f"{{{NS_CT}}}AccountsRef", f"{period_start}_{period_end}")

    # 映射 line_map → CT600 box 元素
    # 使用 snake_case → PascalCase 的映射,覆盖常见字段
    key_map = {
        "turnover": "Turnover",
        "trading_income": "TradingIncome",
        "trading_expenses": "TradingExpenses",
        "investment_income": "InvestmentIncome",
        "property_income": "PropertyIncome",
        "chargeable_gains": "ChargeableGains",
        "capital_allowances_claimed": "CapitalAllowancesClaimed",
        "trading_losses_brought_forward": "TradingLossesBroughtForward",
        "group_relief_claimed": "GroupReliefClaimed",
        "rd_qualifying_expenditure": "RDQualifyingExpenditure",
        "taxable_total_profits": "TaxableTotalProfits",
        "ct_rate_applied": "CTRateApplied",
        "corporation_tax_chargeable": "CorporationTaxChargeable",
        "marginal_relief": "MarginalRelief",
        "tax_already_paid": "TaxAlreadyPaid",
        "amount_payable": "AmountPayable",
        "num_associated_companies": "NumberOfAssociatedCompanies",
        "aia_expenditure": "AIAExpenditure",
        "fya_expenditure": "FYAExpenditure",
        "main_pool_wda": "MainPoolWDA",
        "special_rate_pool_wda": "SpecialRatePoolWDA",
        "structures_buildings_allowance": "StructuresBuildingsAllowance",
        "balancing_charges": "BalancingCharges",
        "total_allowance": "TotalAllowance",
        "current_year_loss": "CurrentYearLoss",
        "loss_relief_used": "LossReliefUsed",
        "carry_back_loss": "CarryBackLoss",
        "carry_forward_loss": "CarryForwardLoss",
        "surrendering_company_relief": "SurrenderingCompanyRelief",
        "max_claimable": "MaxClaimable",
        "relief_claimed": "ReliefClaimed",
    }

    for snake_key, pascal_key in key_map.items():
        if snake_key in line_map and line_map[snake_key] is not None:
            _add_text(ct600, f"{{{NS_CT}}}{pascal_key}", str(line_map[snake_key]))

    # 未知 key 直接透传 (大写首字母)
    known_keys = set(key_map.keys())
    for key, value in line_map.items():
        if key not in known_keys and value is not None:
            parts = key.split("_")
            pascal = "".join(p[0].upper() + p[1:] for p in parts)
            _add_text(ct600, f"{{{NS_CT}}}{pascal}", str(value))

    # ── Supplementary: WHT disclosures ──
    if wht_entries:
        _append_wht_supplementary(ct600, wht_entries)

    return ET.tostring(ir, encoding="unicode", xml_declaration=False)


def _append_wht_supplementary(ct600: ET.Element, entries: Iterable[dict]) -> None:
    """附加 WHT supplementary entries 到 CT600。

    模拟 CT600 supplementary pages (i.e. Form CT600A pages),包含:
    - InterestPaid (Box 270) — 利息总额
    - RoyaltiesPaid (Box 275) — 特许权使用费总额
    - WHTDeducted (Box 280) — 已扣 WHT 总额
    - Per-recipient disclosure — 每笔付款的详情
    """
    supp = ET.SubElement(ct600, f"{{{NS_CT}}}WHTSupplementary")

    total_interest = 0.0
    total_royalty = 0.0
    total_dividend = 0.0
    total_wht = 0.0

    entries_list = list(entries)

    for entry in entries_list:
        gross = float(entry.get("gross_amount", 0) or 0)
        wht = float(entry.get("wht_amount", 0) or 0)
        income_type = entry.get("income_type", "")

        if income_type == "interest":
            total_interest += gross
        elif income_type == "royalty":
            total_royalty += gross
        elif income_type == "dividend":
            total_dividend += gross

        total_wht += wht

        # 单笔披露
        item = ET.SubElement(supp, f"{{{NS_CT}}}WHTEntry")
        _add_text(item, f"{{{NS_CT}}}IncomeType", income_type)
        _add_text(item, f"{{{NS_CT}}}GrossAmount", f"{gross:.2f}")
        _add_text(item, f"{{{NS_CT}}}WHTAmount", f"{wht:.2f}")
        _add_text(item, f"{{{NS_CT}}}Rate", str(entry.get("rate", "0")))
        _add_text(item, f"{{{NS_CT}}}TreatyRate", str(entry.get("treaty_rate", "")))
        _add_text(item, f"{{{NS_CT}}}RecipientCountry", entry.get("recipient_country", ""))
        _add_text(item, f"{{{NS_CT}}}RecipientName", entry.get("recipient_name", ""))
        if entry.get("date_paid"):
            _add_text(item, f"{{{NS_CT}}}DatePaid", entry["date_paid"])

    # 汇总 box
    _add_text(supp, f"{{{NS_CT}}}InterestPaidTotal", f"{total_interest:.2f}")
    _add_text(supp, f"{{{NS_CT}}}RoyaltiesPaidTotal", f"{total_royalty:.2f}")
    _add_text(supp, f"{{{NS_CT}}}DividendsPaidTotal", f"{total_dividend:.2f}")
    _add_text(supp, f"{{{NS_CT}}}WHTDeductedTotal", f"{total_wht:.2f}")
    _add_text(supp, f"{{{NS_CT}}}EntryCount", str(len(entries_list)))


def _add_text(parent: ET.Element, tag: str, text: str) -> ET.Element:
    """添加一个文本子元素。"""
    el = ET.SubElement(parent, tag)
    el.text = text
    return el


def _add_text(parent: ET.Element, tag: str, text: str) -> ET.Element:
    """添加一个文本子元素。"""
    el = ET.SubElement(parent, tag)
    el.text = text
    return el
