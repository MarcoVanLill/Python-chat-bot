# Python Chatbot API

A production-oriented chatbot backend built with FastAPI and Google's Gemini
Interactions API. It supports validated requests, multi-turn conversation chaining,
bounded concurrency, hard request deadlines, optional Google Search grounding,
health checks, request IDs, provider error handling, tests, and a hardened container.

## Requirements

- Python 3.11 or newer
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
- [`uv`](https://docs.astral.sh/uv/) (recommended), or `pip`

## Run locally

From PowerShell:

```powershell
Copy-Item .env.example .env
# Open .env and set GEMINI_API_KEY to your real key.

uv sync --extra dev
uv run uvicorn chatbot_api.main:app --reload
```

The service is then available at:

- API: <http://127.0.0.1:8000>
- Interactive Swagger docs: <http://127.0.0.1:8000/docs>
- Liveness: <http://127.0.0.1:8000/health/live>
- Readiness: <http://127.0.0.1:8000/health/ready>

You can also install with pip:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn chatbot_api.main:app --reload
```

## Send a message

```powershell
$body = @{ message = "What is FastAPI?" } | ConvertTo-Json
$reply = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/chat `
  -ContentType "application/json" `
  -Body $body

$reply
```

The response contains a `response_id`:

```json
{
  "message": "FastAPI is ...",
  "response_id": "interaction_...",
  "model": "gemini-3.8-flash"
}
```

To continue the same conversation, send that ID with the next message:

```powershell
$body = @{
  message = "Show me a tiny example."
  previous_response_id = $reply.response_id
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/chat `
  -ContentType "application/json" `
  -Body $body
```

The API maps `previous_response_id` to Gemini's `previous_interaction_id` so the
conversation can continue without your client resending the full transcript. Gemini
retains stored interactions according to your account tier, so persist the transcript
yourself if you need durable conversation history. Do not expose response IDs across
users in a real product; associate them with the authenticated user.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENVIRONMENT` | `development` | Use `production` to require production startup checks |
| `APP_DOCS_ENABLED` | `true` | Enable Swagger, ReDoc, and the OpenAPI document |
| `CORS_ALLOWED_ORIGINS` | `[]` | JSON array of browser origins allowed to call the API |
| `TRUSTED_HOSTS` | `[]` | JSON array of accepted HTTP host names |
| `CHATBOT_REQUEST_TIMEOUT_SECONDS` | `45` | Hard deadline including queue and provider retry time |
| `CHATBOT_MAX_CONCURRENT_REQUESTS` | `20` | Maximum concurrent Gemini calls per process |
| `CHATBOT_RETRY_AFTER_SECONDS` | `30` | Value returned in `Retry-After` for transient failures |
| `GEMINI_API_KEY` | required | Server-side Gemini credential |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Stable Gemini model ID |
| `GEMINI_MAX_OUTPUT_TOKENS` | `4096` | Maximum tokens generated per response |
| `GEMINI_TIMEOUT_SECONDS` | `20` | Timeout for each upstream SDK attempt |
| `GEMINI_RETRY_ATTEMPTS` | `2` | Total SDK attempts, including the first request |
| `GEMINI_THINKING_LEVEL` | `low` | Model reasoning level (`low`, `medium`, or `high`) |
| `GEMINI_ENABLE_GOOGLE_SEARCH` | `false` | Allow Gemini to use Google Search |
| `CHATBOT_SYSTEM_PROMPT` | helpful assistant prompt | System instruction sent on every turn |

Keep `.env` local. It is excluded by `.gitignore`; never place the API key in source
code or a frontend application.

The defaults target interactive chat latency. Google Search is disabled because its
availability and quota depend on your Gemini plan. Set
`GEMINI_ENABLE_GOOGLE_SEARCH=true` only when your plan supports it. The API returns
`Retry-After` for upstream rate limits and availability failures, and every response
contains an `X-Request-ID` header for correlation.

Stable-model access depends on the Gemini project and billing tier. If your local
free-tier key cannot access `gemini-3.8-flash`, you can use
`GEMINI_MODEL=gemini-3-flash-preview` for development. Keep the stable model for a
paid production deployment.

Gemini interaction history is provider-managed and is not durable application
storage. For a multi-user product, persist your own conversation ID and associate the
provider interaction ID with the authenticated user.

## Test and lint

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Tests replace the real model service, so they do not spend API credits or require a key.

## Docker

```powershell
docker build -t python-chat-bot .
docker run --rm -p 8000:8000 --env-file .env python-chat-bot
```

The image installs the exact `uv.lock` dependency set, runs as UID/GID `10001`,
disables interactive API docs, checks `/health/live`, and refuses to start without
`GEMINI_API_KEY`. Inject the key from your hosting platform's secret manager rather
than copying `.env` into the image. Terminate HTTPS at a trusted reverse proxy or the
hosting platform.

When configuring `TRUSTED_HOSTS`, include your public API host and `127.0.0.1` so the
container health check remains valid. If a browser frontend calls this API, configure
`CORS_ALLOWED_ORIGINS` explicitly, for example:

```env
CORS_ALLOWED_ORIGINS=["https://app.example.com"]
TRUSTED_HOSTS=["api.example.com","127.0.0.1"]
```

Run one Uvicorn process per container and scale containers through your deployment
platform. The concurrency limit is per process.

## Remaining public-API security layer

This hardening pass does not create user accounts or issue JWTs. Before exposing the
chat route to untrusted users, add OIDC/JWT validation from your chosen identity
provider, per-user rate limiting, and server-owned conversation records. Distributed
idempotency and rate limiting should use shared storage such as Redis when the service
runs on more than one container.

## Project layout

```text
src/chatbot_api/
  api.py           HTTP route
  config.py        environment configuration
  dependencies.py  dependency wiring
  main.py          FastAPI application
  schemas.py       request and response models
  service.py       Gemini integration
tests/
  test_api.py
  test_service.py
```

See Google's [Interactions API documentation](https://ai.google.dev/gemini-api/docs/interactions-overview)
and the [`google-genai` Python SDK](https://googleapis.github.io/python-genai/) for
provider-specific details.
