"""UK 全部 tax_type 的 prompt 注册。"""
from __future__ import annotations

from . import vat
from . import self_assessment
from . import corporation_tax
from . import paye
from . import stamp_duty

__all__ = ["vat", "self_assessment", "corporation_tax", "paye", "stamp_duty"]
