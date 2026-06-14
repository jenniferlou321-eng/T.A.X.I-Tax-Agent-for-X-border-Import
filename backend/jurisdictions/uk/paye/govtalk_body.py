"""PAYE RTI GovTalk Body Builder — 构建 FPS/EPS/EYU 的 IRenvelope XML。

PAYE/RTI 通过 GovTalk XML 提交到 HMRC Transaction Engine。
Class 标识:
- FPS: "HMRC-PAYE-RTI-FPS"
- EPS: "HMRC-PAYE-RTI-EPS"
- EYU: "HMRC-PAYE-RTI-EYU"
Schema namespace = "http://www.govtalk.gov.uk/taxation/PAYE/RTI/2.0"
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

NS_RTI = "http://www.govtalk.gov.uk/taxation/PAYE/RTI/2.0"


def build_fps_body(
    empref: str,
    tax_year: str,
    period_start: str,
    period_end: str,
    line_map: dict[str, float | int | str],
) -> str:
    """构建 FPS (Full Payment Submission) 的 IRenvelope XML body。

    Args:
        empref: Employer PAYE Reference (如 "123/AB45678")
        tax_year: 税年 (如 "2024-25")
        period_start: 期间开始 (YYYY-MM-DD)
        period_end: 期间结束 (YYYY-MM-DD)
        line_map: FPS 各字段值,来自 adapter 的 to_filing_format()

    Returns:
        FPS 业务 XML 字符串 (直接喂给 GovTalkClient.submit)
    """
    ir = ET.Element(f"{{{NS_RTI}}}IRenvelope")
    fps = ET.SubElement(ir, f"{{{NS_RTI}}}FPS")

    _add_text(fps, f"{{{NS_RTI}}}EmpRef", empref)
    _add_text(fps, f"{{{NS_RTI}}}TaxYear", tax_year)
    _add_text(fps, f"{{{NS_RTI}}}PeriodStart", period_start)
    _add_text(fps, f"{{{NS_RTI}}}PeriodEnd", period_end)

    # FPS 字段映射
    key_map = {
        "total_paye_income": "TotalPAYEIncome",
        "total_tax_deducted": "TotalTaxDeducted",
        "total_nic_employer": "TotalNICEmployer",
        "total_nic_employee": "TotalNICEmployee",
        "student_loan_deduction": "StudentLoanDeduction",
        "postgrad_loan_deduction": "PostgradLoanDeduction",
        "statutory_maternity_pay": "StatutoryMaternityPay",
        "statutory_paternity_pay": "StatutoryPaternityPay",
        "statutory_sick_pay": "StatutorySickPay",
        "employment_allowance_claimed": "EmploymentAllowanceClaimed",
        "number_of_employees": "NumberOfEmployees",
        "payment_date": "PaymentDate",
    }

    _populate_fields(fps, key_map, line_map)

    # Employee-level data (如果提供)
    employees_data = line_map.get("employees")
    if isinstance(employees_data, list):
        employees_el = ET.SubElement(fps, f"{{{NS_RTI}}}Employees")
        for emp in employees_data:
            emp_el = ET.SubElement(employees_el, f"{{{NS_RTI}}}Employee")
            if isinstance(emp, dict):
                for k, v in emp.items():
                    _add_text(emp_el, f"{{{NS_RTI}}}{k[0].upper() + k[1:]}", str(v))

    return ET.tostring(ir, encoding="unicode", xml_declaration=False)


def build_eps_body(
    empref: str,
    tax_year: str,
    period_start: str,
    period_end: str,
    line_map: dict[str, float | int | str],
) -> str:
    """构建 EPS (Employer Payment Summary) 的 IRenvelope XML body。

    EPS 用于报告: CIS 扣减、学徒税、雇佣津贴、法定支付等调整项。

    Args:
        empref: Employer PAYE Reference
        tax_year: 税年
        period_start: 期间开始
        period_end: 期间结束
        line_map: EPS 各字段值

    Returns:
        EPS 业务 XML 字符串
    """
    ir = ET.Element(f"{{{NS_RTI}}}IRenvelope")
    eps = ET.SubElement(ir, f"{{{NS_RTI}}}EPS")

    _add_text(eps, f"{{{NS_RTI}}}EmpRef", empref)
    _add_text(eps, f"{{{NS_RTI}}}TaxYear", tax_year)
    _add_text(eps, f"{{{NS_RTI}}}PeriodStart", period_start)
    _add_text(eps, f"{{{NS_RTI}}}PeriodEnd", period_end)

    # Apprenticeship Levy section
    levy_data = line_map.get("apprenticeshipLevy")
    if isinstance(levy_data, dict) or any(
        k in line_map for k in ("total_pay_bill", "apprenticeship_levy_payable")
    ):
        levy_el = ET.SubElement(eps, f"{{{NS_RTI}}}ApprenticeshipLevy")
        if isinstance(levy_data, dict):
            for k, v in levy_data.items():
                _add_text(levy_el, f"{{{NS_RTI}}}{k[0].upper() + k[1:]}", str(v))
        else:
            _add_text(levy_el, f"{{{NS_RTI}}}TotalPayBill",
                      str(line_map.get("total_pay_bill", 0)))
            _add_text(levy_el, f"{{{NS_RTI}}}LevyAllowance",
                      str(line_map.get("levy_allowance", 1250)))
            _add_text(levy_el, f"{{{NS_RTI}}}LevyDueYTD",
                      str(line_map.get("apprenticeship_levy_payable", 0)))

    # Employment Allowance section
    ea_data = line_map.get("employmentAllowance")
    if isinstance(ea_data, dict) or "employment_allowance_claimed" in line_map:
        ea_el = ET.SubElement(eps, f"{{{NS_RTI}}}EmploymentAllowance")
        if isinstance(ea_data, dict):
            for k, v in ea_data.items():
                _add_text(ea_el, f"{{{NS_RTI}}}{k[0].upper() + k[1:]}", str(v))
        else:
            _add_text(ea_el, f"{{{NS_RTI}}}AmountClaimed",
                      str(line_map.get("employment_allowance_claimed", 0)))

    # Statutory Payments section
    sp_keys = ("statutory_maternity_pay", "statutory_paternity_pay",
               "statutory_sick_pay", "statutory_adoption_pay")
    if any(k in line_map for k in sp_keys):
        sp_el = ET.SubElement(eps, f"{{{NS_RTI}}}StatutoryPayments")
        for k in sp_keys:
            if k in line_map and line_map[k]:
                pascal = k[0].upper() + k[1:].replace("_", "")
                _add_text(sp_el, f"{{{NS_RTI}}}{pascal}", str(line_map[k]))

    # CIS deductions
    cis_data = line_map.get("cisDeductions")
    if isinstance(cis_data, dict):
        cis_el = ET.SubElement(eps, f"{{{NS_RTI}}}CISDeductions")
        for k, v in cis_data.items():
            _add_text(cis_el, f"{{{NS_RTI}}}{k[0].upper() + k[1:]}", str(v))

    # Generic field pass-through
    key_map = {
        "no_payment_for_period": "NoPaymentForPeriod",
        "period_inactivity": "PeriodInactivity",
    }
    _populate_fields(eps, key_map, line_map)

    return ET.tostring(ir, encoding="unicode", xml_declaration=False)


def build_eyu_body(
    empref: str,
    tax_year: str,
    period_start: str,
    period_end: str,
    line_map: dict[str, float | int | str],
) -> str:
    """构建 EYU (Earlier Year Update) 的 IRenvelope XML body。

    EYU 用于更正上一税务年度的 FPS 数据。

    Args:
        empref: Employer PAYE Reference
        tax_year: 被更正的税年
        period_start: 期间开始
        period_end: 期间结束
        line_map: EYU 调整字段

    Returns:
        EYU 业务 XML 字符串
    """
    ir = ET.Element(f"{{{NS_RTI}}}IRenvelope")
    eyu = ET.SubElement(ir, f"{{{NS_RTI}}}EYU")

    _add_text(eyu, f"{{{NS_RTI}}}EmpRef", empref)
    _add_text(eyu, f"{{{NS_RTI}}}TaxYear", tax_year)
    _add_text(eyu, f"{{{NS_RTI}}}PeriodStart", period_start)
    _add_text(eyu, f"{{{NS_RTI}}}PeriodEnd", period_end)

    # EYU 字段 = FPS 字段 + 差值
    key_map = {
        "total_paye_income": "TotalPAYEIncome",
        "total_tax_deducted": "TotalTaxDeducted",
        "total_nic_employer": "TotalNICEmployer",
        "total_nic_employee": "TotalNICEmployee",
        "student_loan_deduction": "StudentLoanDeduction",
    }
    _populate_fields(eyu, key_map, line_map)

    return ET.tostring(ir, encoding="unicode", xml_declaration=False)


# ── Helpers ──

def _add_text(parent: ET.Element, tag: str, text: str) -> ET.Element:
    el = ET.SubElement(parent, tag)
    el.text = text
    return el


def _populate_fields(
    parent: ET.Element,
    key_map: dict[str, str],
    line_map: dict[str, float | int | str],
) -> None:
    """根据 key_map 映射,将 line_map 中的值写入 XML 元素。"""
    for snake_key, pascal_key in key_map.items():
        if snake_key in line_map and line_map[snake_key] is not None:
            _add_text(parent, f"{{{NS_RTI}}}{pascal_key}", str(line_map[snake_key]))
