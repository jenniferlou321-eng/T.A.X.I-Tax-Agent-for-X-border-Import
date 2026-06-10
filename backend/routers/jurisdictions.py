from fastapi import APIRouter, Request

router = APIRouter(tags=["jurisdictions"])


@router.get("/jurisdictions/")
async def list_jurisdictions(request: Request):
    """列出所有支持的管辖地和税种"""
    registry = request.app.state.registry
    return {"jurisdictions": registry.list_jurisdictions()}


@router.get("/jurisdictions/{country}/templates/{tax_type}")
async def get_template(country: str, tax_type: str, request: Request):
    """获取指定管辖地+税种的数据录入模板"""
    registry = request.app.state.registry
    return registry.get_template(country, tax_type)