"""OAuth2Manager — HMRC OAuth 2.0 认证管理"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import httpx

from backend.models.results import AuthResult

logger = logging.getLogger(__name__)


@dataclass
class OAuth2Config:
    """OAuth 2.0 配置"""
    authorize_url: str
    token_url: str
    client_id: str
    client_secret: str
    redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob"
    scopes: list[str] | None = None


class OAuth2Manager:
    """管理 OAuth 2.0 token 的获取、刷新和持久化"""

    def __init__(self, config: OAuth2Config, token_path: Path | None = None):
        self.config = config
        self.token_path = token_path or Path("data/oauth_token.json")
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._expires_at: float = 0.0

    # ── Public API ──

    # ── Web OAuth Flow (non-interactive) ──

    def get_authorize_url(self, state: str = "") -> str:
        """生成 HMRC OAuth 授权 URL（供前端跳转）"""
        scopes = " ".join(self.config.scopes or [])
        url = (
            f"{self.config.authorize_url}"
            f"?response_type=code"
            f"&client_id={self.config.client_id}"
            f"&redirect_uri={self.config.redirect_uri}"
            f"&scope={scopes}"
        )
        if state:
            url += f"&state={state}"
        return url

    async def exchange_code(self, code: str) -> AuthResult:
        """用 authorization code 换取 access_token（后端回调处理）"""
        return await self._exchange_code(code)

    # ── Internal auth flow ──

    async def authenticate(self) -> AuthResult:
        """获取有效的 access_token（Web/CLI 通用）"""
        return await self._do_authenticate(allow_interactive=True)

    async def authenticate_silent(self) -> AuthResult:
        """静默获取 token — Web 服务用，不会触发交互式输入"""
        return await self._do_authenticate(allow_interactive=False)

    async def _do_authenticate(self, allow_interactive: bool = True) -> AuthResult:
        """内部认证逻辑"""
        # 1. 尝试加载已有 token
        if not self._access_token:
            self._load_token()

        # 2. 如果 token 仍有效，直接返回
        if self._access_token and time.time() < self._expires_at - 300:
            return AuthResult(
                success=True,
                token=self._access_token,
                expires_at=datetime.fromtimestamp(self._expires_at, tz=timezone.utc),
            )

        # 3. 有 refresh_token 就刷新
        if self._refresh_token:
            result = await self._refresh()
            if result.success:
                return result

        # 4. 需要全新授权
        if allow_interactive:
            return await self._interactive_authorize()
        return AuthResult(
            success=False,
            error="HMRC OAuth required. Please connect via Settings first.",
        )

    async def _interactive_authorize(self) -> AuthResult:
        """交互式 Authorization Code Grant — CLI 用"""
        print("\n" + "=" * 60)
        print("🔐 HMRC OAuth 授权")
        print("=" * 60)
        print("\n1. 在浏览器中打开以下 URL:")
        print(f"   {self.get_authorize_url()}")
        print("\n2. 登录 Government Gateway 并授权")
        print("3. 复制浏览器重定向后 URL 中的 `code` 参数")
        print("\n" + "-" * 40)

        auth_code = input("请输入 authorization code: ").strip()
        return await self._exchange_code(auth_code)

    async def _exchange_code(self, code: str) -> AuthResult:
        """用 authorization code 换取 access_token"""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    self.config.token_url,
                    data={
                        "grant_type": "authorization_code",
                        "client_id": self.config.client_id,
                        "client_secret": self.config.client_secret,
                        "redirect_uri": self.config.redirect_uri,
                        "code": code,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                return AuthResult(success=False, error=f"Token exchange failed: {e}")

        self._access_token = data.get("access_token")
        self._refresh_token = data.get("refresh_token")
        expires_in = data.get("expires_in", 3600)
        self._expires_at = time.time() + expires_in
        self._save_token()

        return AuthResult(
            success=True,
            token=self._access_token,
            expires_at=datetime.fromtimestamp(self._expires_at, tz=timezone.utc),
        )

    async def _refresh(self) -> AuthResult:
        """用 refresh_token 刷新 access_token"""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    self.config.token_url,
                    data={
                        "grant_type": "refresh_token",
                        "client_id": self.config.client_id,
                        "client_secret": self.config.client_secret,
                        "refresh_token": self._refresh_token,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                return AuthResult(success=False, error=f"Token refresh failed: {e}")

        self._access_token = data.get("access_token")
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        expires_in = data.get("expires_in", 3600)
        self._expires_at = time.time() + expires_in
        self._save_token()

        return AuthResult(
            success=True,
            token=self._access_token,
            expires_at=datetime.fromtimestamp(self._expires_at, tz=timezone.utc),
        )

    # ── Persistence ──

    def _save_token(self) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_path, "w", encoding="utf-8") as f:
            json.dump({
                "access_token": self._access_token,
                "refresh_token": self._refresh_token,
                "expires_at": self._expires_at,
            }, f, ensure_ascii=False, indent=2)

    def _load_token(self) -> None:
        if not self.token_path.exists():
            return
        try:
            with open(self.token_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._access_token = data.get("access_token")
            self._refresh_token = data.get("refresh_token")
            self._expires_at = data.get("expires_at", 0.0)
        except Exception:
            pass

    def _load_token_silent(self) -> bool:
        """静默加载 token，不触发交互。返回是否成功加载。"""
        if self._access_token:
            return True
        self._load_token()
        return self._access_token is not None