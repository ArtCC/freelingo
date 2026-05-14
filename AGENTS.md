# AGENTS.md — FreeLingo

## Project state

**v1.3.12 — All phases implemented.** Phase 1 (platform), Phase 1+ (resources hub), Phase 2 (TTS/STT), Phase 3 (voice conversation), and Phase 4 (multi-language support) are complete. Email verification and password reset are also included. The repo contains `backend/`, `frontend/`, `docker-compose.yml`, `.env.example`, and CI/CD via GitHub Actions. See [CHANGELOG.md](CHANGELOG.md) for the full version history.

## Architecture at a glance

Monorepo: `backend/` (Python 3.14 FastAPI) + `frontend/` (Next.js 16 App Router) deployed via Docker Compose with PostgreSQL 16 and Redis 7. The backend proxies all external services (Ollama, Kokoro, Whisper) — the frontend never calls them directly.

## Key constraints

- **Target language is always English.** User's native language (asked at registration) is used only for flashcard translations and tutor feedback.
- **First registered user becomes admin automatically** when `FIRST_USER_IS_ADMIN=true` (default).
- **Registration gating**: `ALLOW_REGISTRATION=false` blocks public signups; admin creates users or generates single-use invite links (48h expiry in Redis).
- **Ollama should run on the host for GPU access**, accessed via `host.docker.internal:11434`. On Linux, the backend service needs `extra_hosts: ["host.docker.internal:host-gateway"]`.

## Documentation maintenance (MANDATORY)

**Any code change that affects behaviour, models, endpoints, configuration, or dependencies MUST be followed by an update to all affected spec and MD files.**

Rules that apply without exception:

1. **Proactively identify affected docs.** After every implementation change, review which of the files below are impacted and list them explicitly before closing the task.
2. **Always inform and ask for confirmation.** Before updating any spec or MD file, state exactly what will change and wait for explicit user approval. Never silently update documentation.
3. **No task is complete without docs in sync.** A feature or fix is considered unfinished if the relevant spec files, `README.md`, `AGENTS.md`, or `CHANGELOG.md` have not been updated (or the user has explicitly opted out).
4. **Version and changelog.** Any user-visible change must be reflected in `CHANGELOG.md` and `specs/version.md` (with a version bump if warranted).

Files most commonly affected by code changes:

| Change type | Files to update |
|-------------|----------------|
| New/modified endpoint | `specs/api-endpoints.instructions.md`, `specs/rate-limiting.instructions.md` |
| New/modified model or migration | `specs/architecture.instructions.md` |
| New/modified service or env var | `specs/architecture.instructions.md`, `specs/docker.instructions.md`, `README.md` |
| New/modified auth flow | `specs/architecture.instructions.md`, `AGENTS.md` (Auth design section) |
| New phase or major feature | `specs/phase-*.instructions.md` (create if needed), `README.md`, `AGENTS.md`, `CHANGELOG.md`, `specs/version.md` |
| Docker/compose change | `specs/docker.instructions.md`, `README.md` |
| Rate limit change | `specs/rate-limiting.instructions.md`, `specs/api-endpoints.instructions.md` |
| Version bump | `specs/version.md`, `CHANGELOG.md`, `frontend/src/app/(app)/layout.tsx` (sidebar version string) |

---

## Spec files (authoritative)

These describe what was built — they are the reference documentation:

| File | Covers |
|------|--------|
| `specs/architecture.instructions.md` | DB models, service layer, LLM adapter, auth design, data flow, code standards, test config |
| `specs/api-endpoints.instructions.md` | All REST endpoints and WebSocket — paths, methods, rate limits, descriptions |
| `specs/docker.instructions.md` | docker-compose.yml (all phases), `.env.example`, DB migrations, operational notes |
| `specs/phase-1-platform.instructions.md` | Phase 1: scaffolding through frontend, prompts, SM-2, SSE chat, frontend components |
| `specs/phase-2-tts-stt.instructions.md` | Phase 2: Kokoro TTS, faster-whisper STT, pronunciation exercises |
| `specs/phase-1-plus.instructions.md` | Phase 1+: Learning Resources Hub — Grammar Reference, Vocabulary Hub, Phrasebook, Skills Tracker, Level Completion Test |
| `specs/phase-3-conversation.instructions.md` | Phase 3: WebSocket voice pipeline, VAD, barge-in, gapless audio |
| `specs/phase-4-target-language.instructions.md` | Phase 4: multi-language support, `target_language` (BCP-47), onboarding flow, auto-login on register |
| `specs/phase-5-stripe-subscriptions.instructions.md` | Phase 5: Stripe subscriptions & paywall, `STRIPE_ENABLED` toggle, Customer Portal, self-hosted safe |
| `specs/whats-new.instructions.md` | What's New modal: version-aware changelog overlay, localStorage trigger, priority with OnboardingTour |
| `specs/roadmap.instructions.md` | Development roadmap with milestones and completion criteria per phase |
| `specs/changelog.instructions.md` | Changelog format, entry style, and update rules |
| `specs/readme.instructions.md` | README structure, badges, and update guidelines |
| `specs/testing.instructions.md` | Testing strategy: pytest, Vitest, Playwright, fixtures, mocks, CI (pending) |
| `specs/llm-error-handling.instructions.md` | LLM failure modes: malformed JSON, timeouts, retries, context overflow |
| `specs/rate-limiting.instructions.md` | slowapi-based rate limits per-endpoint, self-hosted defaults |
| `specs/version.md` | Canonical project version — keep in sync with CHANGELOG and sidebar |

## Run order (first deployment)

1. `docker compose up -d` — start all services (DB migrations run automatically on backend startup)

## Development environment constraints

- **No Docker locally.** The development machine does not have Docker installed. Never suggest `docker` or `docker compose` commands to run locally.
- **Not deployed locally.** The application runs in a remote server; the dev machine is used only for editing and pushing code. CI/CD (GitHub Actions) builds and publishes the Docker images.
- **Image channels are separated by branch.** `main` publishes stable images (`ghcr.io/artcc/freelingo-backend` and `ghcr.io/artcc/freelingo-frontend`), while `develop` publishes test images with `-develop` suffix (`ghcr.io/artcc/freelingo-backend-develop` and `ghcr.io/artcc/freelingo-frontend-develop`).
- **Cannot test the running app locally.** Validation is limited to static checks: `npx tsc --noEmit` (frontend) and `python3 -m compileall app/ alembic/ -q` (backend).
- **package-lock.json must be generated with npm 11** (the version installed locally). The Dockerfile upgrades npm to v11 before `npm ci` to stay in sync.

## Commands

```bash
# Lint & format backend
ruff check --fix backend/ && black backend/

# Lint & format frontend
npx eslint src/ --ext .ts,.tsx && npx prettier --write src/

# Run all backend tests (coverage must be ≥70%)
cd backend && pytest

# Run single test file
pytest tests/test_auth.py -v

# DB migrations (run on the remote server, not locally)
docker compose exec backend alembic revision --autogenerate -m "description"
docker compose exec backend alembic upgrade head
```

## Auth design (do not deviate)

| Token | Type | Duration | Storage |
|-------|------|----------|---------|
| `access_token` | JWT HS256 | 15 min | Zustand store (JS memory) |
| `refresh_token` | Opaque UUID4 | 30 days | httpOnly cookie + Redis (`refresh:{token}` → user_id) |

- Access token verified without DB hit (JWT decode only).
- Refresh tokens stored in Redis with native TTL for auto-expiry.
- **On refresh: old token deleted, new token created** (rotation + replay detection).
- Logout deletes the refresh token from Redis and clears the cookie.
- Frontend interceptor: on 401, silent refresh → retry. Redirect to `/login` if refresh fails.

## Code standards (non-default choices)

- **Python**: ruff with rules `E, W, F, I, UP, B, S, ANN` (ANN101 ignored). Black line-length 100. S and ANN rules disabled in `tests/`.
- **TypeScript**: no semicolons, single quotes, 2-space tabs, trailing commas es5. `prettier-plugin-tailwindcss` required.
- **shadcn/ui** components must be installed: `button card input progress badge separator sheet tabs`.

## TTS & STT services

Both TTS and STT are always active — the app has no meaning without voice. The provider is selected per-service:

- `TTS_PROVIDER=local` → Kokoro-FastAPI (`kokoro` Docker service, GPU recommended)
- `TTS_PROVIDER=openai` → OpenAI TTS API (`OPENAI_API_KEY` required, no local service needed)
- `STT_PROVIDER=local` → faster-whisper (`whisper` Docker service, GPU recommended)
- `STT_PROVIDER=openai` → OpenAI Whisper API (`OPENAI_API_KEY` required, no local service needed)

When using `openai` providers, the `kokoro` and `whisper` Docker services can be removed from the compose stack. The `OPENAI_API_KEY` used for LLM is reused for TTS/STT.

Default STT model (local): `large-v3-turbo` via `STT_MODEL` in `.env`. Engine via `STT_ENGINE`.
Default OpenAI TTS model: `tts-1` via `OPENAI_TTS_MODEL`. Voice via `OPENAI_TTS_VOICE` (default: `nova`).
Default OpenAI STT model: `whisper-1` via `OPENAI_STT_MODEL`.