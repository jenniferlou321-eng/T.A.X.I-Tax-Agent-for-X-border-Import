"""JurisdictionRegistry — 管辖地适配器注册与查找"""

from .models.tax_data import TaxType
from .jurisdictions import JurisdictionAdapter


class JurisdictionRegistry:
    """管理所有已注册的管辖地适配器"""

    def __init__(self):
        self._adapters: dict[str, JurisdictionAdapter] = {}

    def register(self, adapter: JurisdictionAdapter) -> None:
        """注册一个管辖地适配器"""
        self._adapters[adapter.country_code] = adapter

    def get(self, country_code: str) -> JurisdictionAdapter:
        """按国家代码获取适配器"""
        adapter = self._adapters.get(country_code)
        if adapter is None:
            raise ValueError(f"Jurisdiction '{country_code}' not registered")
        return adapter

    def list_jurisdictions(self) -> list[dict]:
        """列出所有支持的管辖地及其税种"""
        return [
            {
                "country_code": a.country_code,
                "country_name": a.country_name,
                "tax_types": [t.value for t in a.tax_types],
                "supported_channels": [c.value for c in a.supported_channels],
            }
            for a in self._adapters.values()
        ]

    def get_template(self, country_code: str, tax_type: str) -> dict:
        """获取指定管辖地+税种的数据模板"""
        adapter = self.get(country_code)
        tt = TaxType(tax_type)
        template = adapter.get_template(tt)
        return {
            "tax_type": template.tax_type.value,
            "jurisdiction": template.jurisdiction,
            "version": template.version,
            "valid_from": template.valid_from.isoformat(),
            "valid_until": template.valid_until.isoformat() if template.valid_until else None,
            "sections": [
                {
                    "title": s.title,
                    "description": s.description,
                    "is_optional": s.is_optional,
                    "fields": [
                        {
                            "key": f.key,
                            "label": f.label,
                            "field_type": f.field_type.value,
                            "required": f.required,
                            "hint": f.hint,
                            "example": f.example,
                            "auto_calculated": f.auto_calculated,
                            "allow_manual_override": f.allow_manual_override,
                            "validation": {
                                "min": float(f.validation.min) if f.validation.min is not None else None,
                                "max": float(f.validation.max) if f.validation.max is not None else None,
                                "decimal_places": f.validation.decimal_places,
                                "options": f.validation.options,
                            },
                        }
                        for f in s.fields
                    ],
                }
                for s in template.sections
            ],
        }