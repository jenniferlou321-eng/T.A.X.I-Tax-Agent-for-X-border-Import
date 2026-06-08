# 🔐 HMRC OAuth 2.0 授权流程

> 基于 OAuth 2.0 Authorization Code Grant，是 HMRC MTD for VAT API 唯一支持的认证方式

## 📊 流程总览

```
┌──────────┐                  ┌──────────┐                ┌──────────┐
│  TaxAgent│                  │  HMRC    │                │  用户    │
│  后端    │                  │  OAuth   │                │  浏览器  │
└────┬─────┘                  └────┬─────┘                └────┬─────┘
     │                              │                           │
     │  1. 生成 auth URL            │                           │
     │  ─────────────────────────▶  │                           │
     │                              │                           │
     │  2. 返回 auth URL            │                           │
     │  ◀─────────────────────────  │                           │
     │                              │                           │
     │  3. 重定向用户到 auth URL ──────────────────────────────▶ │
     │                              │                           │
     │                              │  4. 用户在 GG 登录        │
     │                              │  ◀─────────────────────── │
     │                              │                           │
     │                              │  5. 用户授权应用          │
     │                              │  ◀─────────────────────── │
     │                              │                           │
     │                              │  6. 重定向到 redirect_uri │
     │                              │     带上 authorization    │
     │                              │     code                  │
     │  7. 用户把 code 发给后端 ◀─────────────────────────────── │
     │                              │                           │
     │  8. 用 code 交换 access_token│                           │
     │  ─────────────────────────▶  │                           │
     │                              │                           │
     │  9. 返回 token (4h 有效)     │                           │
     │  ◀─────────────────────────  │                           │
     │                              │                           │
     │  10. 用 token 调 API         │                           │
     │  ─────────────────────────▶  │                           │
     │                              │                           │
     │  11. 4h 后用 refresh_token   │                           │
     │  ─────────────────────────▶  │                           │
     │  12. 新 access_token         │                           │
     │  ◀─────────────────────────  │                           │
```

---

## 🔑 关键术语

| 术语 | 含义 |
|------|------|
| **Client ID** | 应用的公开标识（HMRC Developer Hub 获取）|
| **Client Secret** | 应用的私钥，**绝不**出现在前端代码 |
| **Redirect URI** | 授权完成后重定向地址，**必须**在 Developer Hub 预先注册 |
| **Scope** | 权限范围：`read:vat`, `write:vat` |
| **Authorization Code** | 短期凭证（5 分钟内有效），用于交换 token |
| **Access Token** | API 调用凭证，**4 小时**有效 |
| **Refresh Token** | 长期凭证，**18 个月**内可用 |

---

## 📂 项目中的 OAuth 实现

```
tax_agent/channels/oauth.py    # OAuth2Manager
  ├── get_authorize_url()       # 生成授权 URL（前端跳转用）
  ├── exchange_code(code)       # 后端用 code 换 token
  ├── authenticate_silent()     # Web 服务用，永不阻塞
  ├── _refresh()                # 用 refresh_token 换新 access_token
  └── _load_token_silent()      # 静默加载持久化的 token
```

---

## 🛠️ 实施步骤

### Step 1: 在 HMRC Developer Hub 创建应用

1. 访问 https://developer.service.hmrc.gov.uk/developer/login
2. 登录后点击 **Add an application**
3. 填写：
   - **Application name**: 你的应用名
   - **Environment**: Sandbox（开发）/ Production（生产）
4. 保存获取 **Client ID** 和 **Client Secret**
5. 在 **APIs** 标签添加 `VAT (MTD) - v1.0`
6. 在 **Redirect URIs** 添加 `http://localhost:8080`（开发）或 `https://yourapp.com/callback`（生产）

### Step 2: 在 TaxAgent 中配置

`tax_agent/.env`：
```bash
HMRC_CLIENT_ID=2U9ktG6rDRDpxUG1kNJ4Mld8y6Fl
HMRC_CLIENT_SECRET=ef505ced-ee2c-4797-85b6-c673de1e9121
HMRC_SANDBOX=true
HMRC_REDIRECT_URI=http://localhost:8080
```

### Step 3: 通过 API 获取授权 URL

```bash
curl "http://localhost:8765/api/channel/uk/vat/auth-url"
```

返回：
```json
{
  "auth_url": "https://test-api.service.hmrc.gov.uk/oauth/authorize?response_type=code&client_id=...&redirect_uri=http://localhost:8080&scope=read:vat+write:vat"
}
```

### Step 4: 用户在浏览器完成授权

引导用户打开 auth_url，流程：
1. **Accept additional cookies**（如果显示）
2. **Sign in to the HMRC online service**
3. **Continue**（显示应用请求的权限）
4. **What you will need** 页面再次点击 **Sign in**
5. **Test login 页面**：填入 Government Gateway 凭据（沙盒用 Test User）
6. **Grant scope 页面**：点击 **Give permission**
7. 浏览器重定向到 `http://localhost:8080?code=AUTHORIZATION_CODE&state=...`

### Step 5: 交换 Code 换取 Token

后端需要本地 HTTP 服务器监听 8080 接收 code，或前端从 URL 中提取。

```bash
curl -X POST "http://localhost:8765/api/channel/uk/vat/callback" \
  -H "Content-Type: application/json" \
  -d '{"code": "AUTHORIZATION_CODE", "state": ""}'
```

返回：
```json
{
  "success": true,
  "token": "QGbWG8KckncuwwD4uYXgWxF4HQvuPmrmUqKgkpQP",
  "expires_at": "2026-06-01T15:34:39.624243+00:00"
}
```

### Step 6: Token 持久化

Token 自动保存到 `data/oauth_token.json`：
```json
{
  "access_token": "QGbWG8KckncuwwD4uYXgWxF4HQvuPmrmUqKgkpQP",
  "refresh_token": "a7r9Xb...",
  "expires_at": 1748796879.624
}
```

### Step 7: 自动刷新

后续 API 调用：
- 如果 token 即将过期（< 5 分钟），自动用 refresh_token 刷新
- 刷新失败 → 触发新的授权流程
- refresh_token 18 个月内有效

---

## 🤖 自动化授权（沙盒测试用）

为了沙盒测试，可以用 Playwright 自动化完整流程：

```python
from playwright.sync_api import sync_playwright
import requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# 1. 启动本地 HTTP server 接收 code
captured_code = None
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global captured_code
        code = parse_qs(urlparse(self.path).query).get("code", [None])[0]
        if code:
            captured_code = code
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h1>OK</h1>")
    def log_message(self, *a): pass

server = HTTPServer(("127.0.0.1", 8080), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

# 2. Playwright 自动化
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page()
    
    auth_url = "https://test-api.service.hmrc.gov.uk/oauth/authorize?..."
    page.goto(auth_url)
    
    # 接受 cookies
    page.click('button:has-text("Accept additional cookies")')
    # Sign in
    page.click('#signIn')
    # Continue
    page.click('a:has-text("Continue")')
    # 再次 sign in
    if "whatYouWillNeed" in page.url:
        page.click('#signIn')
    # Test login
    page.fill('input#userId', "TEST_USER_ID")
    page.fill('input#password', "TEST_PASSWORD")
    page.click('button:has-text("Sign in")')
    # Give permission
    page.click('button:has-text("Give permission")')
    
    browser.close()

server.shutdown()

# 3. 用 code 换 token
requests.post("http://localhost:8765/api/channel/uk/vat/callback",
    json={"code": captured_code, "state": ""})
```

---

## 🚨 错误处理

| 错误 | 原因 | 解决 |
|------|------|------|
| `redirect_uri is invalid` | redirect_uri 未在 Developer Hub 注册 | 添加到 Application 设置 |
| `client_id is invalid` | Client ID 错误或环境不匹配 | 检查 sandbox vs production |
| `client_secret is invalid` | Client Secret 错误 | 重新创建 |
| `redirect_uri_mismatch` | OAuth 时使用的 redirect_uri 与注册的不完全一致 | 必须 byte-for-byte 一致（包括端口、路径、query）|
| `unauthorized_client` | Application 未启用该 grant type | HMRC sandbox 总会支持 authorization_code |
| `access_denied` | 用户在授权页点了"拒绝" | 重新发起授权 |
| `invalid_grant` | code 已过期（5 分钟）或被用过 | 重新获取 code |
| `invalid_token` | access_token 过期 | 用 refresh_token 刷新 |

---

## 🔒 安全最佳实践

1. **Client Secret 绝不**暴露在前端代码或浏览器
2. 使用 **state 参数**防止 CSRF
3. 验证 **redirect_uri** 与注册值完全一致
4. Token 存储在**服务端**文件系统，**不**存 cookie
5. 使用 HTTPS 在生产环境
6. 定期 **轮换 Client Secret**（HMRC 支持最多 5 个）
7. 监控异常 OAuth 行为（多次失败的 code 尝试）

---

## 📐 与传统 API Key 的区别

| 维度 | OAuth 2.0 (HMRC MTD) | API Key |
|------|----------------------|---------|
| 身份绑定 | 绑定到具体纳税人 (VRN) | 仅绑定到应用 |
| 用户体验 | 需要浏览器交互 | 无感 |
| 权限粒度 | 按 scope 精细控制 | 全部或无 |
| 撤销机制 | 单 token 可撤销 | 需重置 key |
| HMRC 要求 | 强制（user-restricted API）| 不接受 |

HMRC MTD for VAT 是 **user-restricted endpoint**，必须用 OAuth 2.0。
