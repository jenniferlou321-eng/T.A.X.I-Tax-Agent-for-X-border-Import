"""渠道管理路由 — OAuth、健康检查、HMRC 专用接口"""

from __future__ import annotations

from fastapi import APIRouter, Request, Query
from pydantic import BaseModel

router = APIRouter(prefix="/channel", tags=["channel"])


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str = ""


@router.get("/{country}/{tax_type}/health")
async def channel_health(country: str, tax_type: str, request: Request):
    """渠道健康检查"""
    registry = request.app.state.registry
    adapter = registry.get(country)
    from backend.models.tax_data import TaxType
    channel = adapter.get_channel(TaxType(tax_type))
    healthy = await channel.health_check()
    return {"country": country, "tax_type": tax_type, "healthy": healthy}


@router.get("/{country}/{tax_type}/auth-url")
async def channel_auth_url(
    country: str,
    tax_type: str,
    request: Request,
    redirect_uri: str = Query("", description="可选的覆盖 redirect_uri"),
):
    """获取 HMRC OAuth 授权 URL

    前端应引导用户打开此 URL，完成 Government Gateway 登录授权后，
    HMRC 将重定向到 redirect_uri 并附带 `code` 参数。
    """
    registry = request.app.state.registry
    adapter = registry.get(country)
    from backend.models.tax_data import TaxType
    channel = adapter.get_channel(TaxType(tax_type))

    # 获取 OAuth manager
    oauth = channel.oauth
    if redirect_uri:
        # 临时覆盖 redirect_uri
        original = oauth.config.redirect_uri
        oauth.config.redirect_uri = redirect_uri
        url = oauth.get_authorize_url()
        oauth.config.redirect_uri = original
    else:
        url = oauth.get_authorize_url()

    return {
        "auth_url": url,
        "country": country,
        "tax_type": tax_type,
    }


@router.post("/{country}/{tax_type}/callback")
async def channel_auth_callback(
    country: str,
    tax_type: str,
    req: OAuthCallbackRequest,
    request: Request,
):
    """处理 HMRC OAuth 回调 — 用 authorization code 换取 access token"""
    registry = request.app.state.registry
    adapter = registry.get(country)
    from backend.models.tax_data import TaxType
    channel = adapter.get_channel(TaxType(tax_type))

    oauth = channel.oauth
    result = await oauth.exchange_code(req.code)

    return {
        "success": result.success,
        "token": result.token if result.success else None,
        "expires_at": result.expires_at.isoformat() if result.expires_at else None,
        "error": result.error,
    }


@router.get("/{country}/{tax_type}/auth-status")
async def channel_auth_status(country: str, tax_type: str, request: Request):
    """检查当前渠道的认证状态"""
    registry = request.app.state.registry
    adapter = registry.get(country)
    from backend.models.tax_data import TaxType
    channel = adapter.get_channel(TaxType(tax_type))

    oauth = channel.oauth
    # 尝试 silent auth（不触发交互式授权）
    token_loaded = oauth._access_token is not None or oauth._load_token_silent()

    return {
        "authenticated": token_loaded and oauth._access_token is not None,
        "expires_at": oauth._expires_at if oauth._expires_at > 0 else None,
    }
