# Python Chatbot API

A small, production-shaped chatbot backend built with FastAPI and Google's Gemini
Interactions API. It supports validated requests, multi-turn conversation chaining,
Google Search grounding, health checks, automatic OpenAPI docs, provider error
handling, tests, and Docker.

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
- Health check: <http://127.0.0.1:8000/health>

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
  "model": "gemini-3-flash-preview"
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
| `GEMINI_API_KEY` | required | Server-side Gemini credential |
| `GEMINI_MODEL` | `gemini-3-flash-preview` | Gemini model ID |
| `GEMINI_MAX_OUTPUT_TOKENS` | `65536` | Maximum tokens generated per response |
| `GEMINI_TIMEOUT_SECONDS` | `30` | Upstream request timeout |
| `GEMINI_TEMPERATURE` | `1` | Response randomness |
| `GEMINI_TOP_P` | `0.95` | Nucleus sampling threshold |
| `GEMINI_THINKING_LEVEL` | `high` | Model reasoning level |
| `GEMINI_ENABLE_GOOGLE_SEARCH` | `false` | Allow Gemini to use Google Search |
| `CHATBOT_SYSTEM_PROMPT` | helpful assistant prompt | System instruction sent on every turn |

Keep `.env` local. It is excluded by `.gitignore`; never place the API key in source
code or a frontend application.

The generation defaults match the Gemini example supplied for the project. Google
Search is disabled by default because its availability and quota depend on your
Gemini plan. Set `GEMINI_ENABLE_GOOGLE_SEARCH=true` when your plan supports it.

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
