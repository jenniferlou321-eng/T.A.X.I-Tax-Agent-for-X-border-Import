# T.A.X.I Live DeepSeek deployment (recruiter demo)

This is the original product with minimal deployment/runtime changes, NOT a mock chat replacement. HMRC_MODE=mock only simulates the final tax authority submission. The LLM itself uses a live API and Skills/MCP/Tools are expected to work.

## Setup

1. Create a repository under your own GitHub account from this project. Keep the MIT LICENSE and team credits.
2. Upload these updated files (do not commit secrets). Use Render **New > Blueprint** to import `render.yaml`, or **New > Web Service > Docker** (select Starter plan for reliable memory and uptime).
3. In Render Environment enter `TAXI_ANTHROPIC_API_KEY` (your DeepSeek key). Do not put key in the repo. Also set `TAXI_REQUIRE_LIVE_AGENT=1`, `TAXI_ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`, and `TAXI_ANTHROPIC_MODEL=deepseek-flash` (confirm the model name from DeepSeek console).
4. Deploy; check the Build and Runtime logs, then `/health` and the browser homepage.
5. Test live text generation AND verify at least one real Knowledge Search / VAT Calculate MCP tool call. Plain text reply alone does not verify Agent functionality. Test the ERP upload and refresh behavior. Keep HMRC submissions in sandbox/mock mode.

## Strict live mode

With `TAXI_REQUIRE_LIVE_AGENT=1`, startup fails on missing key/SDK, and SDK timeouts or errors never silently produce scripted mock chat or a reduced-tools HTTP chat response. Actual compatibility of current DeepSeek API with Claude Agent SDK must be tested on the running Render instance.

## Security before sharing publicly

Restrict access (password/auth proxy) or enable request rate limits, per-user limits and budget alerts. Review SDK filesystem permissions and session/workspace isolation; never upload real enterprise data. A public anonymous endpoint with your personal paid key can be abused. Free/ephemeral disk plans may lose workspace/audit/session changes after restart. Use a persistent disk if needed.

## Limitations

No API secret supplied and no access to Render account from this build environment. Full SDK+MCP, Docker and npm integration tests were not executed here. Passing syntax/static checks does not guarantee production works. Inspect Render logs; a successful `/health` alone does not prove AI tools work.
