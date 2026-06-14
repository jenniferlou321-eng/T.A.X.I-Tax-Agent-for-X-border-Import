"""SDLT GovTalk Body Builder — 构建 Stamp Duty Land Tax Return 的 IRenvelope XML。

SDLT 通过 GovTalk XML 提交到 HMRC Transaction Engine。
Class = "HMRC-SDLT-RETURN"
Schema namespace = "http://www.govtalk.gov.uk/taxation/SDLT/2.0"
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

NS_SDLT = "http://www.govtalk.gov.uk/taxation/SDLT/2.0"


def build_sdlt_body(
    utr: str,
    transaction_id: str,
    effective_date: str,
    line_map: dict[str, float | int | str],
) -> str:
    """构建 SDLT Return 的 IRenvelope XML body。

    Args:
        utr: Unique Transaction Reference (SDLT UTR, 13-17 位)
        transaction_id: 交易 ID (提交方生成)
        effective_date: 交易生效日期 (YYYY-MM-DD)
        line_map: SDLT 各字段值,来自 adapter 的 to_filing_format()
            常见 key: property_value, property_type, buyer_type,
            sdlt_payable, effective_rate, is_additional_dwelling,
            property_address_postcode, etc.

    Returns:
        SDLT 业务 XML 字符串 (不含 GovTalk envelope,直接喂给 GovTalkClient.submit)
    """
    ir = ET.Element(f"{{{NS_SDLT}}}IRenvelope")
    sdlt = ET.SubElement(ir, f"{{{NS_SDLT}}}SDLTReturn")

    # 固定标识字段
    _add_text(sdlt, f"{{{NS_SDLT}}}UTR", utr)
    _add_text(sdlt, f"{{{NS_SDLT}}}TransactionID", transaction_id)
    _add_text(sdlt, f"{{{NS_SDLT}}}EffectiveDate", effective_date)

    # Property details
    property_el = ET.SubElement(sdlt, f"{{{NS_SDLT}}}Property")
    _add_text(property_el, f"{{{NS_SDLT}}}PropertyValue",
              str(line_map.get("property_value", 0)))
    _add_text(property_el, f"{{{NS_SDLT}}}PropertyType",
              str(line_map.get("property_type", "residential")))
    _add_text(property_el, f"{{{NS_SDLT}}}BuyerType",
              str(line_map.get("buyer_type", "individual")))

    # Additional dwelling surcharge
    if line_map.get("is_additional_dwelling"):
        _add_text(property_el, f"{{{NS_SDLT}}}AdditionalDwelling", "true")

    # Address (if provided)
    postcode = line_map.get("property_address_postcode", "")
    if postcode:
        address_el = ET.SubElement(property_el, f"{{{NS_SDLT}}}Address")
        _add_text(address_el, f"{{{NS_SDLT}}}Postcode", postcode)

    # Calculation result
    calc_el = ET.SubElement(sdlt, f"{{{NS_SDLT}}}Calculation")
    _add_text(calc_el, f"{{{NS_SDLT}}}SDLTPayable",
              str(line_map.get("sdlt_payable", 0)))
    _add_text(calc_el, f"{{{NS_SDLT}}}EffectiveRate",
              str(line_map.get("effective_rate", 0)))

    # Key map for remaining SDLT fields
    key_map = {
        "consideration_money": "ConsiderationMoney",
        "consideration_stock": "ConsiderationStock",
        "consideration_debt": "ConsiderationDebt",
        "vat_on_consideration": "VATOnConsideration",
        "relief_claimed": "ReliefClaimed",
        "relief_type": "ReliefType",
        "exemption_claimed": "ExemptionClaimed",
        "lease_premium": "LeasePremium",
        "lease_term_years": "LeaseTermYears",
        "annual_rent": "AnnualRent",
        "npv_rent": "NPVRent",
        "npv_rent_sdlt": "NPVRentSDLT",
        "number_of_purchasers": "NumberOfPurchasers",
        "is_linked": "IsLinkedTransaction",
    }

    for snake_key, pascal_key in key_map.items():
        if snake_key in line_map and line_map[snake_key] is not None:
            _add_text(sdlt, f"{{{NS_SDLT}}}{pascal_key}", str(line_map[snake_key]))

    # Purchaser details (if provided)
    purchaser_data = line_map.get("purchaser")
    if isinstance(purchaser_data, dict):
        purchaser_el = ET.SubElement(sdlt, f"{{{NS_SDLT}}}Purchaser")
        for k, v in purchaser_data.items():
            pascal = k[0].upper() + k[1:].replace("_", "")
            _add_text(purchaser_el, f"{{{NS_SDLT}}}{pascal}", str(v))

    return ET.tostring(ir, encoding="unicode", xml_declaration=False)


def _add_text(parent: ET.Element, tag: str, text: str) -> ET.Element:
    el = ET.SubElement(parent, tag)
    el.text = text
    return el
