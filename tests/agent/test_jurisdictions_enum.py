from backend.models.jurisdictions import JURISDICTIONS, TAX_TYPES, is_valid_jurisdiction


def test_jurisdictions_frozenset():
    assert isinstance(JURISDICTIONS, frozenset)
    assert JURISDICTIONS == frozenset({"uk", "de", "cn", "fr", "testland"})


def test_tax_types_frozenset():
    assert isinstance(TAX_TYPES, frozenset)
    assert TAX_TYPES == frozenset({
        "vat", "self_assessment", "corporation_tax", "paye", "stamp_duty",
        "cn_vat", "cn_cit",
    })


def test_is_valid_jurisdiction():
    assert is_valid_jurisdiction("uk", "vat") is True
    assert is_valid_jurisdiction("de", "vat") is True
    # 大写拒绝
    assert is_valid_jurisdiction("UK", "vat") is False
    # 空拒绝
    assert is_valid_jurisdiction("", "vat") is False
    # 未知 cc 拒绝
    assert is_valid_jurisdiction("xx", "vat") is False
    # 未知 tt 拒绝
    assert is_valid_jurisdiction("uk", "VT") is False
    # 未知 tt 拒绝(典型 typo)
    assert is_valid_jurisdiction("uk", "vat_return") is False
