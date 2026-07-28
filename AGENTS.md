# AGENTS.md — FreeLingo

## Project state

**v1.8.27 — Consistent pagination and complete histories.** Phase 1 (platform), Phase 1+ (resources hub), Phase 2 (TTS/STT), Phase 3 (voice conversation), Phase 4 (multi-language support), Phase 5 (Stripe subscriptions), Phase 6 (Listening exercises), Phase 7 (Reading exercises), Phase 8 (Feedback board), Phase 9 (LLM Memory), Phase 10 (Multi-Language), and Phase 11 (User Reviews) are complete. Paginated application lists show 10 results per page; Listening and Reading histories expose every attempt through the shared pagination controls, and Feedback uses deterministic tie-breaking between pages. The public landing review carousel requests up to 100 approved positive reviews and remains unpaginated. Public pages use the dot-grid background, while the authenticated application and its loading states use a solid background. The authenticated Feedback section shows per-user unread thread counters in the sidebar, red unread labels on specific feedback list items, and a gold `ADMIN` badge beside administrator-authored suggestions, bug reports, and replies without sending comment emails. Administration exposes maintenance mode in a dedicated System section rather than under Users, without changing the underlying runtime control. Japanese (`ja-JP`), Korean (`ko-KR`), and Mainland Chinese (`zh-CN`) have backend curriculum, grammar, vocabulary, phrasebook, and assessment data. Static grammar, phrasebook, vocabulary resources, lessons, newly generated lesson exercises, exercise hints, and newly generated lesson vocabulary include native-language learning support. Email verification and password reset are also included. Unsubscribed hosted users get one one-time post-assessment voice conversation demo, configurable via `ASSESSMENT_VOICE_TRIAL_DURATION_SECONDS` and defaulting to 5 minutes. Voice conversations are persisted as text transcripts alongside chat conversations. The AI tutor persona is named Lingu. The repo contains `backend/`, `frontend/`, `docker-compose.yml`, `.env.example`, and CI/CD via GitHub Actions. See [CHANGELOG.md](CHANGELOG.md) for the full version history.

## Architecture at a glance

Monorepo: `backend/` (Python 3.14 FastAPI) + `frontend/` (Next.js 16 App Router) deployed via Docker Compose with PostgreSQL 16 and Redis 7. The backend proxies all external services (Ollama, Kokoro, Whisper) — the frontend never calls them directly.

## Key constraints

- **Users can learn multiple languages simultaneously** — each language gets an isolated study plan, progress, flashcards, conversations, and competencies. Supported target languages: `en-US`, `en-GB`, `es-ES`, `it-IT`, `pt-PT`, `de-DE`, `fr-FR`, `ja-JP`, `ko-KR`, `zh-CN`. User's native language (asked at registration) is used for flashcard translations, tutor feedback, lesson and exercise `native_explanation` content, and cached native-language help in static grammar, phrasebook, and vocabulary resources.
- **User settings and memories are global (per user), not per language.** Profile (avatar, bio, display name, email, password, native language, UI locale), conversation limits (max duration, inactivity timeout, daily/weekly minutes, weekly sessions), token quota, subscription, and LLM memories are stored on the `users` table or keyed by `user_id` only — they do not change when switching the active study language. The `study_plan_id` column on `memories` tags each memory with the plan it was created in, but the settings page (`GET /api/memories`) lists all memories regardless of language. In chat/conversation context, memories are optionally filtered by `study_plan_id` to inject language-relevant context into the LLM prompt.
- **First registered user becomes admin automatically** when `FIRST_USER_IS_ADMIN=true` (default).
- **Registration gating**: `ALLOW_REGISTRATION=false` blocks public signups; admin creates users or generates single-use invite links (48h expiry in Redis).
- **Ollama should run on the host for GPU access**, accessed via `host.docker.internal:11434`. On Linux, the backend service needs `extra_hosts: ["host.docker.internal:host-gateway"]`.
- **Default target language is `en-GB`** — all fallback defaults across backend (service params, Query params, model column defaults, chat context, onboarding form) and frontend (`DEFAULT_TARGET_LANGUAGE` in `target-languages.ts`) use `en-GB`. `en-US` remains a supported language but is never used as a fallback default.

## Documentation maintenance (MANDATORY)

**Any code change that affects behaviour, models, endpoints, configuration, or dependencies MUST be followed by an update to all affected spec and MD files.**

Rules that apply without exception:

1. **Proactively identify affected docs.** After every implementation change, review which of the files below are impacted and list them explicitly before closing the task.
2. **Always inform and ask for confirmation.** Before updating any spec or MD file, state exactly what will change and wait for explicit user approval. Never silently update documentation.
3. **No task is complete without docs in sync.** A feature or fix is considered unfinished if the relevant spec files, `README.md`, `AGENTS.md`, or `CHANGELOG.md` have not been updated (or the user has explicitly opted out).
4. **Version and changelog.** Any user-visible change must be reflected in `CHANGELOG.md` and `specs/version.md` (with a version bump if warranted).

Spec formatting rule:

- Do not use Markdown tables in `specs/` or other long-form project docs. They render poorly and become visually misaligned with long endpoint, model, or configuration descriptions. Use concise bullet lists instead, preserving the same fields and details.

Files most commonly affected by code changes:

- **New/modified endpoint** — `specs/api-endpoints.instructions.md`, `specs/rate-limiting.instructions.md`
- **New/modified model or migration** — `specs/database-models.instructions.md`, `specs/architecture-backend.instructions.md`
- **New/modified service or env var** — `specs/services.instructions.md`, `specs/architecture-backend.instructions.md`, `specs/docker.instructions.md`, `README.md`
- **New/modified auth flow** — `specs/architecture.instructions.md`, `AGENTS.md` (Auth design section)
- **Study plan / lesson / progress change** — `specs/study-plan.instructions.md`, `specs/api-endpoints.instructions.md`, `specs/architecture.instructions.md`
- **Frontend component/page change** — `specs/architecture-frontend.instructions.md`
- **New phase or major feature** — `specs/phase-*.instructions.md` (create if needed), `README.md`, `AGENTS.md`, `CHANGELOG.md`, `specs/version.md`
- **Docker/compose change** — `specs/docker.instructions.md`, `README.md`
- **Rate limit change** — `specs/rate-limiting.instructions.md`, `specs/api-endpoints.instructions.md`
- **Version bump** — `specs/version.md`, `CHANGELOG.md`, `frontend/src/app/(app)/layout.tsx` (sidebar version string)

---

## Spec files (authoritative)

These describe what was built — they are the reference documentation:

- `specs/architecture.instructions.md` — Repository structure, data flows, auth design, test summary
- `specs/architecture-backend.instructions.md` — Backend architecture: models (21), services (20), routers (23), schemas (15), env vars (56), Python code standards
- `specs/architecture-frontend.instructions.md` — Frontend architecture: pages, components, stores (6), lib modules (9), TypeScript code standards
- `specs/add-target-language.instructions.md` — Canonical checklist for adding new target languages, based on the British English (`en-GB`) data package structure and current dispatchers
- `specs/database-models.instructions.md` — **21 SQLAlchemy ORM models**: full schema details, relationships, constraints, business rules
- `specs/services.instructions.md` — **20 backend services**: LLM, TTS/STT, study plan, lessons, static-resource native help, flashcards, listening, reading, reviews, memory, progress, quotas, subscriptions, post-assessment voice trial, voice conversation pipeline
- `specs/prompts.instructions.md` — LLM prompt architecture: centralized builders, shared prompt blocks, active prompt inventory, dynamic variables, and maintenance rules
- `specs/api-endpoints.instructions.md` — All REST endpoints and WebSocket — paths, methods, rate limits, descriptions
- `specs/study-plan.instructions.md` — **Current-state reference** for the study plan & lesson system: data model, `progress_day` semantics, auto-advance, skip day, pending lessons, lesson lifecycle, frontend integration
- `specs/docker.instructions.md` — docker-compose.yml (all phases), `.env.example`, DB migrations, operational notes
- `specs/phase-1-platform.instructions.md` — Phase 1: scaffolding through frontend, prompts, SM-2, SSE chat, frontend components
- `specs/phase-2-tts-stt.instructions.md` — Phase 2: Kokoro TTS, faster-whisper STT, pronunciation exercises
- `specs/phase-1-plus.instructions.md` — Phase 1+: Learning Resources Hub — Grammar Reference, Vocabulary Hub, Phrasebook, Skills Tracker, Level Completion Test
- `specs/phase-3-conversation.instructions.md` — Phase 3: WebSocket voice pipeline, VAD, barge-in, gapless audio
- `specs/phase-4-target-language.instructions.md` — Phase 4: multi-language support, `target_language` (BCP-47), onboarding flow, auto-login on register
- `specs/phase-5-stripe-subscriptions.instructions.md` — Phase 5: Stripe subscriptions & paywall, `STRIPE_ENABLED` toggle, Customer Portal, self-hosted safe
- `specs/phase-6-listening.instructions.md` — Phase 6: AI-generated listening exercises, LLM+TTS generation pipeline, Redis lock, audio storage, 5 endpoints, frontend 6-state UI
- `specs/phase-7-reading.instructions.md` — Phase 7: AI-generated reading comprehension exercises, LLM generation pipeline, Redis lock, 4 endpoints, frontend 2-column layout
- `specs/phase-8-feedback.instructions.md` — Phase 8: Feedback board — feature requests & bug reports, voting, comments, admin panel, 9 endpoints
- `specs/phase-9-memories.instructions.md` — Phase 9: LLM Memory — AI tutor autonomously remembers details about the student, injects into future conversations
- `specs/phase-10-multi-language.instructions.md` — Phase 10: Multi-Language — users can learn multiple languages simultaneously, each with independent study plans and progress
- `specs/phase-11-reviews.instructions.md` — Phase 11: User Reviews — one verified review per user, admin approval, and approved positive reviews displayed on the landing page
- `specs/whats-new.instructions.md` — What's New modal: version-aware changelog overlay, localStorage trigger, priority with OnboardingTour
- `specs/roadmap.instructions.md` — Development roadmap with milestones and completion criteria per phase
- `specs/changelog.instructions.md` — Changelog format, entry style, and update rules
- `specs/readme.instructions.md` — README structure, badges, and update guidelines
- `specs/testing.instructions.md` — Testing strategy: pytest, Vitest, Playwright, fixtures, mocks, CI (pending)
- `specs/llm-error-handling.instructions.md` — LLM failure modes: malformed JSON, timeouts, retries, context overflow
- `specs/rate-limiting.instructions.md` — slowapi-based rate limits per-endpoint, self-hosted defaults
- `specs/version.md` — Canonical project version — keep in sync with CHANGELOG and sidebar

## Run order (first deployment)

1. `docker compose up -d` — start all services (DB migrations run automatically on backend startup)

## Development environment constraints

- **No Docker locally.** The development machine does not have Docker installed. Never suggest `docker` or `docker compose` commands to run locally.
- **Not deployed locally.** The application runs in a remote server; the dev machine is used only for editing and pushing code. CI/CD (GitHub Actions) builds and publishes the Docker images.
- **Cannot test the running app locally.** The running app is on a remote server. Local validation is limited to backend unit tests/static checks and frontend lint/typecheck/unit tests. Use the `run-tests` skill for requested test/lint/typecheck runs and the `pre-push` skill for final full validation before pushing.
- **package-lock.json must be generated with npm 11** (the version installed locally). The Dockerfile upgrades npm to v11 before `npm ci` to stay in sync.

## Commands

```bash
# Lint & format backend
source .venv/bin/activate && cd backend && ruff check --fix . && black .

# Lint & format frontend
cd frontend && npx eslint src/ --ext .ts,.tsx --fix && npx prettier --write src/

# Canonical formatter from repo root (preferred)
./scripts/format.sh

# Run all backend tests (coverage must be ≥70%)
source .venv/bin/activate && cd backend && pytest -v

# Run single test file
source .venv/bin/activate && cd backend && pytest tests/test_auth.py -v

# Run frontend lint, typecheck, and tests
cd frontend && npm run lint && npx tsc --noEmit && npm run test:run

# DB migrations (run on the remote server, not locally)
docker compose exec backend alembic revision --autogenerate -m "description"
docker compose exec backend alembic upgrade head
```

## Validation and test accounting

- When finishing a feature or task that requires test validation, use only the `pre-push` skill for the final test run.
- If new backend tests are added, update the documented backend test count and backend coverage percentage wherever those metrics are recorded.
- If new frontend tests are added, update the documented frontend test count wherever it is recorded. Frontend coverage percentage is not tracked.
- **If any test fails after launching a suite, STOP and ask the user what to do.** Never modify production code or tests to make tests pass without explicit user approval. Report the failing test(s), include the relevant error summary, and wait for instructions before changing code or tests.

## Auth design (do not deviate)

- `access_token` — Type: JWT HS256. Duration: 15 min. Storage: Zustand store (JS memory).
- `refresh_token` — Type: Opaque UUID4. Duration: 30 days. Storage: httpOnly cookie + Redis (`refresh:{token}` → user_id).

- Access token verified without DB hit (JWT decode only).
- Refresh tokens stored in Redis with native TTL for auto-expiry.
- **On refresh: old token deleted, new token created** (rotation + replay detection).
- Logout deletes the refresh token from Redis and clears the cookie.
- Frontend interceptor: on 401, silent refresh → retry. Redirect to `/login` if refresh fails.

## Code standards (non-default choices)

- **Python**: ruff with rules `E, W, F, I, UP, B, S, ANN` (ANN101 ignored). Black line-length 100. S and ANN rules disabled in `tests/`.
- **TypeScript**: no semicolons, single quotes, 2-space tabs, trailing commas es5. `prettier-plugin-tailwindcss` required.
- **Formatting entrypoint**: use `./scripts/format.sh` from the repository root. It runs the same ruff/black/eslint/prettier commands from fixed backend/frontend directories so formatter results do not depend on the current working directory.
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
