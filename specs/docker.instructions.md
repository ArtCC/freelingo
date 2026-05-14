---
description: "Docker Compose specification for FreeLingo — all services (PostgreSQL, Redis, backend, frontend, Ollama, Kokoro TTS, Whisper STT), environment variables, operational notes, and deployment guidance."
applyTo: "docker-compose.yml, .env*, **/Dockerfile"
---

# Docker Compose — FreeLingo

## Service inventory

| Service | Image | Ports | Phase | Notes |
|---------|-------|-------|-------|-------|
| `postgres` | `postgres:16-alpine` | 5432 (internal) | 1 | Health check via `pg_isready` |
| `redis` | `redis:7-alpine` | 6379 (internal) | 1 | Password-protected, health check via `redis-cli ping` |
| `backend` | `ghcr.io/artcc/freelingo-backend:latest` | 8000 (internal) | 1 | Python 3.14, Uvicorn; runs migrations automatically on startup. Depends on postgres+redis. |
| `frontend` | `ghcr.io/artcc/freelingo-frontend:latest` | 3000 | 1 | Next.js 16; receives `BACKEND_URL` as runtime env var. Depends on backend. |
| `kokoro` | `ghcr.io/artcc/kokoro-fastapi-gpu:v0.2.4-master` | 8880 (internal) | 2 | TTS (custom fork with PyTorch 2.7+/cu128 for Blackwell GPU sm_120+). Only needed when `TTS_PROVIDER=local`. |
| `whisper` | `onerahmet/openai-whisper-asr-webservice:latest-gpu` | 9000 (internal) | 2 | STT, GPU via NVIDIA deploy block. Only needed when `STT_PROVIDER=local`. |

Ollama is assumed to run on the host machine for GPU access, accessed via `host.docker.internal:11434`. It can alternatively run as a Docker service with its own GPU deploy block.

---

## Docker Compose structure

The compose file defines 6 services (plus optional Ollama) and 2 named volumes (`postgres_data`, `redis_data`).

### PostgreSQL

- Alpine-based image for minimal footprint
- Database name, user, and password from environment variables
- Health check ensures backend waits for database readiness (`depends_on: condition: service_healthy`)
- Data persisted in named volume

### Redis

- Alpine-based image
- Password from `REDIS_PASSWORD` environment variable
- Health check via authenticated ping
- Data persisted in named volume

### Backend

- Pre-built image pulled from `ghcr.io/artcc/freelingo-backend:latest` (`pull_policy: always`)
- Startup command automatically runs `alembic upgrade head` before launching Uvicorn — no manual migration step needed
- Receives all configuration via environment variables (from `.env`)
- No bind mounts in production; CI/CD publishes the image
- Depends on healthy PostgreSQL and Redis

### Frontend

- Pre-built image pulled from `ghcr.io/artcc/freelingo-frontend:latest` (`pull_policy: always`)
- Receives `BACKEND_URL=http://backend:8000` at runtime (server-side Next.js Route Handlers proxy to the backend)
- Exposes port 3000 on the host
- Depends on backend

### Kokoro TTS

- Custom fork: `ghcr.io/artcc/kokoro-fastapi-gpu:v0.2.4-master` — PyTorch 2.7+ with cu128 for Blackwell GPU (sm_120+), backwards-compatible with sm_50+
- Only required when `TTS_PROVIDER=local`; can be removed from the compose stack when `TTS_PROVIDER=openai`
- NVIDIA GPU via `deploy.resources.reservations.devices` block
- No environment variables needed (uses defaults)

### Whisper STT

- GPU image by default (`latest-gpu`)
- Only required when `STT_PROVIDER=local`; can be removed when `STT_PROVIDER=openai`
- Environment: `ASR_MODEL` (from `${STT_MODEL:-large-v3-turbo}`), `ASR_ENGINE` (from `${STT_ENGINE:-faster_whisper}`)
- NVIDIA GPU via `deploy.resources.reservations.devices` block

---

## Environment variables (`.env`)

All required variables with their defaults (see `.env.example` at the repo root for the canonical reference):

```env
# ─── Database ────────────────────────────────────────────
POSTGRES_DB=freelingo
POSTGRES_USER=freelingo
POSTGRES_PASSWORD=CHANGE_ME_DB_PASSWORD

# ─── Data persistence (bind mounts for postgres and redis)
DATA_PATH=/opt/docker/freelingo

# ─── Redis ───────────────────────────────────────────────
REDIS_PASSWORD=CHANGE_ME_REDIS_PASSWORD

# ─── Auth ────────────────────────────────────────────────
# Generate with: openssl rand -hex 32
SECRET_KEY=CHANGE_ME_SECRET_KEY

# ─── CORS + Cookie ───────────────────────────────────────
CORS_ORIGINS=["http://localhost:3000"]
COOKIE_SECURE=false      # set true when serving over HTTPS

# ─── Registration ────────────────────────────────────────
ALLOW_REGISTRATION=true
FIRST_USER_IS_ADMIN=true

# ─── Email / SMTP ────────────────────────────────────────
# Works with any SMTP provider: Gmail (app password), Brevo, Resend, etc.
EMAIL_ENABLED=false
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@freelingo.app
SMTP_TLS=true
SMTP_SSL=false
# Destination address for contact-form submissions (requires EMAIL_ENABLED=true)
CONTACT_EMAIL=
# Public frontend URL used in email links (no trailing slash)
APP_BASE_URL=https://freelingo.app

# ─── LLM ─────────────────────────────────────────────────
# Options: ollama | openai | anthropic | deepseek
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma3:12b
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-3-5-haiku-latest
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-chat

# ─── TTS ─────────────────────────────────────────────────
# TTS_PROVIDER=local  → uses the kokoro Docker service
# TTS_PROVIDER=openai → uses OpenAI TTS (OPENAI_API_KEY required, no local service needed)
TTS_PROVIDER=local
TTS_BASE_URL=http://kokoro:8880
TTS_VOICE=af_heart
OPENAI_TTS_MODEL=tts-1
OPENAI_TTS_VOICE=nova
OPENAI_TTS_SPEED=1.0

# ─── STT ─────────────────────────────────────────────────
# STT_PROVIDER=local  → uses the whisper Docker service
# STT_PROVIDER=openai → uses OpenAI Whisper API (OPENAI_API_KEY required, no local service needed)
STT_PROVIDER=local
STT_BASE_URL=http://whisper:9000
STT_MODEL=large-v3-turbo
STT_ENGINE=faster_whisper
OPENAI_STT_MODEL=whisper-1

# ─── Logging ─────────────────────────────────────────────
LOG_LEVEL=INFO
```

---

## Operational notes

### Run order (first deployment)

1. Copy `.env.example` to `.env` and fill in `CHANGE_ME_*` values
2. `docker compose up -d` — start all services

The backend container automatically runs `alembic upgrade head` before starting Uvicorn, so there is no separate migration step.

### Ollama on host (recommended for GPU)

If Ollama runs directly on the host with GPU access, the backend accesses it via `host.docker.internal:11434`.

On **Linux**, `host.docker.internal` requires adding to the backend service:
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

On macOS and Windows, `host.docker.internal` resolves automatically.

### Ollama in Docker with GPU

Alternative: run Ollama as a Docker service with its own GPU deploy block. In that case, set `OLLAMA_BASE_URL=http://ollama:11434` in `.env`.

### Database migrations

```bash
# Run all pending migrations
docker compose exec backend alembic upgrade head

# Create a new migration after model changes
docker compose exec backend alembic revision --autogenerate -m "description"
docker compose exec backend alembic upgrade head
```

### Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend

# Check GPU utilization
docker compose exec whisper nvidia-smi
docker compose exec kokoro nvidia-smi
```

### Updating images

```bash
docker compose pull kokoro whisper
docker compose up -d kokoro whisper
```

### CI/CD image channels (main vs develop)

Backend and frontend images are published by GitHub Actions to two independent GHCR channels:

- Stable channel (production): push to `main` via `.github/workflows/docker-publish.yml`
  - `ghcr.io/artcc/freelingo-backend:latest`
  - `ghcr.io/artcc/freelingo-frontend:latest`
- Develop channel (pre-production): push to `develop` via `.github/workflows/docker-publish-develop.yml`
  - `ghcr.io/artcc/freelingo-backend-develop:latest`
  - `ghcr.io/artcc/freelingo-frontend-develop:latest`

This separation allows testing deploys from `develop` without affecting production images.

---

## GPU vs CPU

Both TTS and STT services default to GPU images with CUDA support (`*-gpu:latest`). For CPU-only hosts:

| Service | GPU image | CPU image | Additional changes |
|---------|-----------|-----------|-------------------|
| Kokoro TTS | `ghcr.io/artcc/kokoro-fastapi-gpu:v0.2.4-master` | `ghcr.io/remsky/kokoro-fastapi-cpu:latest` | Replace image, remove the entire `deploy` block |
| Whisper STT | `onerahmet/openai-whisper-asr-webservice:latest-gpu` | `onerahmet/openai-whisper-asr-webservice:latest` | Replace image tag, remove the `deploy` block; set `STT_MODEL=small` for acceptable performance |

The `deploy.resources.reservations.devices` block references NVIDIA GPUs via the Docker NVIDIA runtime. If this runtime is not installed on the host, Docker will error on startup. Remove these blocks entirely for CPU-only deployments.

---

## TTS/STT provider selection

The provider for each service is selected independently via env vars:

| Variable | Value | Behaviour |
|----------|-------|----------|
| `TTS_PROVIDER` | `local` (default) | Routes TTS requests to the `kokoro` Docker service |
| `TTS_PROVIDER` | `openai` | Routes TTS requests to OpenAI TTS API (`OPENAI_API_KEY` required) — `kokoro` service not needed |
| `STT_PROVIDER` | `local` (default) | Routes STT requests to the `whisper` Docker service |
| `STT_PROVIDER` | `openai` | Routes STT requests to OpenAI Whisper API (`OPENAI_API_KEY` required) — `whisper` service not needed |

When using `openai` providers, the `kokoro` and/or `whisper` services can be removed from the compose stack entirely.

---

## STT service API

**Important**: The Whisper service (`onerahmet/openai-whisper-asr-webservice`) does **not** implement the OpenAI API format. The actual endpoint is:

```
POST /asr?output=json&language=en&task=transcribe
Content-Type: multipart/form-data
Field: audio_file (the audio binary)
```

The backend's `STTService` correctly calls this endpoint. Earlier versions of this spec incorrectly documented the OpenAI-compatible `/v1/audio/transcriptions` endpoint, which does not exist in this service.