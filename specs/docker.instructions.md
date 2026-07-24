---
description: "Docker Compose specification for FreeLingo: all services (PostgreSQL, Redis, backend, frontend, Ollama, Kokoro TTS, Whisper STT), environment variables, operational notes, and deployment guidance."
applyTo: "docker-compose.yml, .env*, **/Dockerfile"
---

# Docker Compose — FreeLingo

## Service inventory

- **`postgres`** — Image: `postgres:16-alpine`. Ports: 5432 (internal). Phase: 1. Notes: Health check via `pg_isready`
- **`redis`** — Image: `redis:7-alpine`. Ports: 6379 (internal). Phase: 1. Notes: Password-protected, health check via `redis-cli ping`
- **`backend`** — Image: `ghcr.io/artcc/freelingo-backend:latest`. Ports: 8000 (internal). Phase: 1. Notes: Runs Alembic migrations automatically before Uvicorn. Depends on healthy postgres + redis.
- **`frontend`** — Image: `ghcr.io/artcc/freelingo-frontend:latest`. Ports: 3000 (host). Phase: 1. Notes: Receives `BACKEND_URL` as runtime env var. Depends on backend.
- **`kokoro`** — Image: `ghcr.io/remsky/kokoro-fastapi-gpu:latest-cu128`. Ports: 8880 (internal). Phase: 2. Notes: TTS — upstream image (0.4.0+), cu128 variant for Blackwell/RTX 50-series. Only needed when `TTS_PROVIDER=local`.
- **`whisper`** — Image: `onerahmet/openai-whisper-asr-webservice:latest-gpu`. Ports: 9000 (internal). Phase: 2. Notes: STT — GPU via NVIDIA deploy block. Only needed when `STT_PROVIDER=local`.

Ollama is assumed to run on the host machine for GPU access, reached from containers via `host.docker.internal:11434`.

---

## Image channels

- Production — Branch: `main`; Backend image: `ghcr.io/artcc/freelingo-backend`; Frontend image: `ghcr.io/artcc/freelingo-frontend`
- Develop — Branch: `develop`; Backend image: `ghcr.io/artcc/freelingo-backend-develop`; Frontend image: `ghcr.io/artcc/freelingo-frontend-develop`

Both channels publish `:latest` and a short SHA tag on every push. The compose file uses production images by default.

---

## Docker Compose structure

### Named volumes

Two named volumes: `postgres_data` and `redis_data`. Both services also accept bind mounts via `DATA_PATH` for easier backup and access outside Docker.

### PostgreSQL

- Alpine-based; credentials from env vars (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`)
- Health check ensures the backend waits for readiness before starting (`condition: service_healthy`)

### Redis

- Alpine-based; password-protected via `REDIS_PASSWORD`
- Health check via authenticated ping

### Backend

- Pulled with `pull_policy: always`; no bind mounts for source code
- Startup command: `alembic upgrade head` then `uvicorn` — no manual migration step ever needed
- Receives all configuration exclusively via environment variables
- Bind mounts only for user-generated content: `avatars/` and `audio/`. Avatar files are persisted in `avatars/` and served only through authenticated profile endpoints; `/api/avatars/{uuid}` is an internal stored reference, not a public static mount.
- Worker count controlled by `UVICORN_WORKERS` (default: 4)

### Frontend

- Pulled with `pull_policy: always`
- Single runtime env var: `BACKEND_URL=http://backend:8000` (used by Next.js Route Handlers; not exposed to the browser)
- Only service exposing a port to the host (3000)

### Kokoro TTS

- Upstream image (`0.4.0+`). Cu128 variant (`:latest-cu128`) for Blackwell/RTX 50-series (sm_120).
- For Maxwell/Pascal/Turing/Ampere/Hopper (sm_50–sm_90): use `:latest` (cu126, confirmed Pascal support in pyproject.toml).
- Remove from stack entirely when `TTS_PROVIDER=openai`
- GPU assigned via `deploy.resources.reservations.devices`; remove this block for CPU-only hosts

### Whisper STT

- GPU image by default; model and engine set via `ASR_MODEL` / `ASR_ENGINE` (forwarded from `STT_MODEL` and `STT_ENGINE`)
- Remove from stack entirely when `STT_PROVIDER=openai`
- GPU assigned via `deploy.resources.reservations.devices`; remove for CPU-only hosts

---

## Environment variables

The canonical reference is `.env.example` at the repo root. The categories operators must review before first deployment:

- Database — Key variables: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`; Notes: All three must be set
- Data path — Key variables: `DATA_PATH`; Notes: Host path for bind mounts (postgres, redis, avatars, audio)
- Cache — Key variables: `REDIS_PASSWORD`; Notes: Must match in Redis command and backend URL
- Auth — Key variables: `SECRET_KEY`; Notes: Generate with `openssl rand -hex 32`; never commit
- CORS / Cookie — Key variables: `CORS_ORIGINS`, `COOKIE_SECURE`; Notes: Set `COOKIE_SECURE=true` when serving over HTTPS
- Registration — Key variables: `ALLOW_REGISTRATION`, `FIRST_USER_IS_ADMIN`; Notes: Restrict signups and promote first user automatically
- Email / SMTP — Key variables: `EMAIL_ENABLED`, `SMTP_*`, `APP_BASE_URL`; Notes: Required for email verification and password reset
- Languages — Key variables: `AVAILABLE_TARGET_LANGUAGES`; Notes: Operator-configured target-language list; backend filters unsupported codes
- Usage quotas — Key variables: `DEFAULT_CONVERSATION_*`, `DEFAULT_MONTHLY_TOKENS_LIMIT`, `ASSESSMENT_VOICE_TRIAL_DURATION_SECONDS`; Notes: Defaults for new/subscribed users and the post-assessment voice demo; quota values of `0` mean unlimited
- LLM — Key variables: `LLM_PROVIDER`, `OLLAMA_*`, `OPENAI_*`, `ANTHROPIC_*`, `DEEPSEEK_*`; Notes: Provider selected via `LLM_PROVIDER`
- TTS — Key variables: `TTS_PROVIDER`, `TTS_BASE_URL`, `TTS_VOICE`, `OPENAI_TTS_*`; Notes: `local` or `openai`
- STT — Key variables: `STT_PROVIDER`, `STT_BASE_URL`, `STT_MODEL`, `STT_ENGINE`, `OPENAI_STT_MODEL`; Notes: `local` or `openai`
- Stripe — Key variables: `STRIPE_ENABLED`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_*`; Notes: Optional; disabled by default. Price IDs are configured manually from Stripe Dashboard when enabled
- Freemium — Key variables: `FREEMIUM_CHAT_DAILY_MESSAGES`, `FREEMIUM_LESSONS_DAILY`, `FREEMIUM_LISTENING_WEEKLY`, `FREEMIUM_READING_WEEKLY`, `FREEMIUM_VOICE_WEEKLY_MINUTES`, `FREEMIUM_TRIAL_ENABLED`, `FREEMIUM_TRIAL_DAYS`; Notes: Daily/weekly quota limits for free-tier users and 7-day no-card trial toggle. Self-hosted deployments (`STRIPE_ENABLED=false`) ignore freemium settings and grant full access
- Logging — Key variables: `LOG_LEVEL`; Notes: Default: `INFO`

---

## Operational notes

### First deployment

1. Copy `.env.example` → `.env` and fill in all `CHANGE_ME_*` values
2. `docker compose up -d` — the backend runs migrations automatically on first start

### Ollama on host (recommended)

Backend accesses Ollama via `host.docker.internal:11434`. On **Linux**, add `extra_hosts: ["host.docker.internal:host-gateway"]` to the backend service. On macOS and Windows, `host.docker.internal` resolves automatically.

Alternatively, Ollama can run as a Docker service with its own GPU deploy block; set `OLLAMA_BASE_URL=http://ollama:11434` accordingly.

### Database migrations

Run via the backend container after model changes. Migrations run automatically on every container startup (`alembic upgrade head`), so manual invocation is only needed when creating new revision files.

### GPU vs CPU

- Kokoro TTS — GPU image: `ghcr.io/remsky/kokoro-fastapi-gpu:latest-cu128`; CPU image: `ghcr.io/remsky/kokoro-fastapi-cpu:latest`; Change needed: Replace image; remove `deploy` block
- Whisper STT — GPU image: `*:latest-gpu`; CPU image: `*:latest`; Change needed: Replace tag; remove `deploy` block; use `STT_MODEL=small`

The `deploy.resources.reservations.devices` block requires the Docker NVIDIA runtime. Remove it entirely for CPU-only hosts.

---

## TTS/STT provider selection

- `TTS_PROVIDER` — Value: `local` (default); Behaviour: Routes TTS to the `kokoro` Docker service
- `TTS_PROVIDER` — Value: `openai`; Behaviour: Routes TTS to OpenAI TTS API — `kokoro` service not needed
- `STT_PROVIDER` — Value: `local` (default); Behaviour: Routes STT to the `whisper` Docker service
- `STT_PROVIDER` — Value: `openai`; Behaviour: Routes STT to OpenAI Whisper API — `whisper` service not needed

When using `openai` providers, the corresponding Docker service can be removed from the stack entirely.

---

## STT service API

The Whisper service (`onerahmet/openai-whisper-asr-webservice`) does **not** implement the OpenAI API format. The correct endpoint is:

```
POST /asr?output=json&language=en&task=transcribe
Content-Type: multipart/form-data
Field: audio_file
```

The backend's `STTService` calls this endpoint correctly. Do not confuse it with the OpenAI-compatible `/v1/audio/transcriptions` path, which does not exist in this service.
