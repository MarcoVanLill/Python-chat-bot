# Python Chatbot API

A small, production-shaped chatbot backend built with FastAPI and the OpenAI
Responses API. It supports validated requests, multi-turn conversation chaining,
health checks, automatic OpenAPI docs, provider error handling, tests, and Docker.

## Requirements

- Python 3.11 or newer
- An OpenAI API key
- [`uv`](https://docs.astral.sh/uv/) (recommended), or `pip`

## Run locally

From PowerShell:

```powershell
Copy-Item .env.example .env
# Open .env and replace your_api_key_here with your real key.

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
  "response_id": "resp_...",
  "model": "gpt-6-luna"
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

The OpenAI Responses API stores response objects so `previous_response_id` can
continue a conversation. Do not expose response IDs across users in a real product.
Add your own authentication and associate conversation IDs with the authenticated user.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | required | Server-side OpenAI credential |
| `OPENAI_MODEL` | `gpt-6-luna` | Responses API model ID |
| `OPENAI_MAX_OUTPUT_TOKENS` | `1024` | Maximum tokens generated per response |
| `OPENAI_TIMEOUT_SECONDS` | `30` | Upstream request timeout |
| `CHATBOT_SYSTEM_PROMPT` | helpful assistant prompt | Instruction sent on every turn |

Keep `.env` local. It is excluded by `.gitignore`; never place the API key in source
code or a frontend application.

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
  service.py       OpenAI integration
tests/
  test_api.py
```
