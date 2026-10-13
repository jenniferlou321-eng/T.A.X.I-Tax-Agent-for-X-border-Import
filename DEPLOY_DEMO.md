# T.A.X.I Recruiter Demo Deployment

This deployment recipe serves the existing Vite/React frontend and FastAPI backend from one Docker Web Service. It keeps the existing routes and SSE chat on the same origin and defaults to demo mode (no LLM key required, and HMRC mode is `mock`).

## Deploy to Render

1. Push this repository to a GitHub repository you control.
2. In Render, choose **New → Blueprint** and select the repository containing `render.yaml`, or create a Docker Web Service using the repository's `Dockerfile`.
3. Keep `TAXI_DEMO_MODE=1`, `HMRC_MODE=mock`, and `HMRC_SANDBOX=true` for a recruiter demo. Do not add HMRC production credentials.
4. Deploy and wait for `/health` to return HTTP 200.
5. Open the generated `https://…onrender.com` URL. The dashboard should load directly; no visitor login credentials or local setup are required.

## Optional real LLM (cost-bearing)

The default deployment has no LLM API key and uses the project's scripted/mock Agent responses. The current mock chat is most complete for the UK VAT journey; other implemented filing pages still use their existing local calculation and mock submission flows. To enable a real Anthropic-compatible model, add all three environment variables in the host dashboard:

- `TAXI_ANTHROPIC_API_KEY`
- `TAXI_ANTHROPIC_BASE_URL`
- `TAXI_ANTHROPIC_MODEL`

Do not commit these values to GitHub. Enabling a paid provider creates cost and abuse risk on a public site; do not enable it until request limits and abuse controls are in place. The HMRC integration should remain in mock/sandbox mode for a public portfolio demo.

## What is and is not represented

- Existing frontend pages and implemented API flows remain in the repository.
- `HMRC_MODE=mock` means a displayed receipt is a simulated demo result, not a legal/tax submission.
- Supported production tax coverage is narrower than all the examples and roadmap entries. Do not present unfinished tax types as production-ready.
- The app's in-memory filing records and local workspace are demo storage, not multi-user durable SaaS storage.

## Local smoke test

```bash
docker build -t taxi-demo .
docker run --rm -p 8000:8000 taxi-demo
```

Then open `http://localhost:8000`, and check `http://localhost:8000/health`. The container build needs network access to install npm and Python dependencies.
