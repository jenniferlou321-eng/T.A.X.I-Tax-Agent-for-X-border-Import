"""UK HMRC 配置 — API 端点、OAuth scope、环境切换

支持从 .env 文件读取凭据：
    HMRC_CLIENT_ID=your_client_id
    HMRC_CLIENT_SECRET=your_client_secret
    HMRC_SANDBOX=true
    HMRC_REDIRECT_URI=urn:ietf:wg:oauth:2.0:oob
"""

import os
from dataclasses import dataclass
from pathlib import Path

from backend.channels.oauth import OAuth2Config


def _load_dotenv() -> None:
    """轻量级 .env 文件加载器（不依赖 python-dotenv）"""
    # repo-root .env (this file lives at backend/jurisdictions/uk/, root is parents[3])
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
    except Exception:
        pass


# 启动时自动加载 .env
_load_dotenv()


# ── OAuth 范围定义 ──

VAT_SCOPES = ["read:vat", "write:vat"]
SA_SCOPES = ["read:self-assessment", "write:self-assessment"]
CT_SCOPES = ["read:corporation-tax", "write:corporation-tax"]
PAYE_SCOPES = ["read:paye", "write:paye"]
SDLT_SCOPES = ["read:stamp-duty", "write:stamp-duty"]
NI_SCOPES = ["read:national-insurance", "write:national-insurance"]
CGT_SCOPES = ["read:capital-gains", "write:capital-gains"]


@dataclass
class HMRCConfig:
    """HMRC API 配置 — 支持沙盒/生产环境切换"""

    sandbox: bool = os.environ.get("HMRC_SANDBOX", "true").lower() == "true"

    @property
    def base_url(self) -> str:
        return (
            "https://test-api.service.hmrc.gov.uk"
            if self.sandbox
            else "https://api.service.hmrc.gov.uk"
        )

    def _oauth_config(self, scopes: list[str]) -> OAuth2Config:
        return OAuth2Config(
            authorize_url=f"{self.base_url}/oauth/authorize",
            token_url=f"{self.base_url}/oauth/token",
            client_id=os.environ.get("HMRC_CLIENT_ID", ""),
            client_secret=os.environ.get("HMRC_CLIENT_SECRET", ""),
            redirect_uri=os.environ.get("HMRC_REDIRECT_URI", "urn:ietf:wg:oauth:2.0:oob"),
            scopes=scopes,
        )

    @property
    def vat_oauth(self) -> OAuth2Config:
        return self._oauth_config(VAT_SCOPES)

    @property
    def sa_oauth(self) -> OAuth2Config:
        return self._oauth_config(SA_SCOPES)

    @property
    def ct_oauth(self) -> OAuth2Config:
        return self._oauth_config(CT_SCOPES)

    @property
    def paye_oauth(self) -> OAuth2Config:
        return self._oauth_config(PAYE_SCOPES)

    @property
    def sdlt_oauth(self) -> OAuth2Config:
        return self._oauth_config(SDLT_SCOPES)

    @property
    def ni_oauth(self) -> OAuth2Config:
        return self._oauth_config(NI_SCOPES)

    @property
    def cgt_oauth(self) -> OAuth2Config:
        return self._oauth_config(CGT_SCOPES)

    # ── API 端点 ──

    # VAT
    VAT_SUBMIT_ENDPOINT = "/organisations/vat/{vrn}/returns"
    VAT_STATUS_ENDPOINT = "/organisations/vat/{vrn}/returns/{period_key}"
    VAT_OBLIGATIONS_ENDPOINT = "/organisations/vat/{vrn}/obligations"

    # Self Assessment
    SA_SUBMIT_ENDPOINT = "/individuals/self-assessment/returns"
    SA_DISCOVERY_ENDPOINT = "/individuals/self-assessment/uk-properties"
    SA_CALCULATE_ENDPOINT = "/individuals/self-assessment/calculations"
    SA_OBLIGATIONS_ENDPOINT = "/individuals/self-assessment/obligations/{nino}/{taxYear}"

    # Corporation Tax
    CT_SUBMIT_ENDPOINT = "/company/corporation-tax/returns"
    CT_CALCULATE_ENDPOINT = "/company/corporation-tax/calculations"
    CT_OBLIGATIONS_ENDPOINT = "/company/corporation-tax/obligations/{ctref}"

    # PAYE (RTI)
    PAYE_FPS_ENDPOINT = "/employers/paye/employer/{empref}/fps"
    PAYE_EPS_ENDPOINT = "/employers/paye/employer/{empref}/eps"
    PAYE_EYU_ENDPOINT = "/employers/paye/employer/{empref}/eyu"

    # Stamp Duty Land Tax
    SDLT_SUBMIT_ENDPOINT = "/stamp-duty-land-tx/returns"
    SDLT_CALCULATE_ENDPOINT = "/stamp-duty-land-tx/calculations"

    # National Insurance
    NI_CONTRIBUTIONS_ENDPOINT = "/individuals/national-insurance/contributions"

    # Capital Gains
    CGT_PROPERTIES_ENDPOINT = "/individuals/capital-gains/properties"
    CGT_DISPOSALS_ENDPOINT = "/individuals/capital-gains/disposals"


# 全局单例（从环境变量自动配置）
hmrc_config = HMRCConfig()
