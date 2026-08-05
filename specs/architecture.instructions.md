---
description: "General architecture overview: repository structure, data flows, auth design, and test summary. Backend-specific detail lives in architecture-backend.instructions.md; frontend-specific detail in architecture-frontend.instructions.md."
applyTo: "backend/**, frontend/**"
---

# Architecture — FreeLingo

This is the general architecture reference — the project "organigram". For backend-specific architecture (models, services, routers, env vars, Python standards) see [architecture-backend.instructions.md](architecture-backend.instructions.md). For frontend-specific architecture (pages, components, stores, TypeScript standards) see [architecture-frontend.instructions.md](architecture-frontend.instructions.md).

> API endpoints are documented separately in [api-endpoints.instructions.md](api-endpoints.instructions.md).

## Repository structure

```
freelingo/
├── backend/                     # Python 3.14 FastAPI
│   ├── app/
│   │   ├── core/                # Config, DB engine, security, deps, rate limiter (7 modules)
│   │   ├── models/              # SQLAlchemy 2.0 ORM models (16 files, 22 model classes)
│   │   ├── schemas/             # Pydantic v2 request/response schemas (15 modules)
│   │   ├── routers/             # 24 routers (23 REST + 1 WebSocket)
│   │   ├── services/            # Business logic + external service clients (21 modules + prompts package)
│   │   └── data/                # Static curriculum and content data (9 language modules)
│   │       ├── en/              # English curriculum (A1–C2)
│   │       ├── es/              # Spanish curriculum (A1–C2)
│   │       ├── it/              # Italian curriculum (A1–C2)
│   │       └── pt/              # Portuguese curriculum (A1–C2)
│   ├── alembic/
│   │   └── versions/            # DB migrations (49)
│   └── tests/                   # pytest suite (43 test files, 966 tests)
│
├── frontend/                    # Next.js 16 App Router
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/          # Public routes: login, register, onboarding, verify-email, forgot-password, reset-password, billing (7 pages)
│   │   │   ├── (app)/           # Authenticated routes — sidebar layout
│   │   │   │   ├── admin/       # Admin overview (admin only)
│   │   │   │   ├── admin/users/ # User management (admin only)
│   │   │   │   ├── admin/feedback/ # Feedback board admin panel (admin only)
│   │   │   │   ├── admin/reviews/ # Review moderation (admin only)
│   │   │   │   ├── admin/system/ # Runtime system controls (admin only)
│   │   │   │   ├── assessment/  # Level test entry + adaptive quiz
│   │   │   │   ├── chat/        # AI tutor chat (SSE streaming, conversation history)
│   │   │   │   ├── conversation/ # Real-time voice conversation (WebSocket + VAD)
│   │   │   │   ├── dashboard/   # Home with XP, streak, plan summary
│   │   │   │   ├── faq/         # Frequently asked questions
│   │   │   │   ├── feedback/    # Feature requests & bug reports board
│   │   │   │   ├── flashcards/  # Spaced-repetition flashcard review
│   │   │   │   ├── grammar/     # Grammar reference (index + [slug] detail)
│   │   │   │   ├── lesson/[id]/ # Lesson player
│   │   │   │   ├── listening/   # AI-generated listening exercises
│   │   │   │   ├── phrasebook/  # Phrasebook
│   │   │   │   ├── plan/        # Study plan + unit drawer
│   │   │   │   ├── progress/    # Skills tracker
│   │   │   │   ├── reading/     # AI-generated reading exercises
│   │   │   │   ├── settings/    # Profile, avatar, conversation settings
│   │   │   │   └── vocabulary/  # Vocabulary hub (index + [setId] detail)
│   │   │   ├── (legal)/         # Terms and Privacy pages — minimal layout
│   │   │   └── api/             # Next.js Route Handlers: chat (SSE), tts, stt proxies
│   │   ├── components/          # 11 component directories + 4 standalone files
│   │   ├── data/                # Data access layer (API-backed for curriculum, vocab, phrasebook; static for grammar)
│   │   ├── store/               # Zustand stores: auth, config, language, loading, progress, theme (6)
│   │   ├── lib/                 # Utilities: api, audio, conversation-ws, locales, mappers, target-languages, utils (7)
│   │   ├── i18n/                # next-intl locale resolver
│   │   └── middleware.ts        # Auth guard + locale detection
│   ├── tests/                   # Vitest suite (39 test files, 440 tests)
│   ├── public/                  # Static assets (flags/, vad/ WASM models)
│   └── scripts/                 # Postinstall helpers (copy-vad-models.js)
│
├── messages/                    # i18n bundles (en, es, fr, pt, de, it, nl, pl, ro, ru)
├── specs/                       # Architecture and phase specification files
├── docs/                        # Documentation site
├── assets/                      # Logo and branding
├── .github/                     # CI/CD workflows (GitHub Actions)
├── docker-compose.yml
├── .env.example
├── AGENTS.md                    # Agent instructions for AI assistants
├── CHANGELOG.md
└── README.md
```

## Data flow — Complete assessment → study

```
User visits /assessment
    ↓
Step 1: BeginnerGate ("Have you studied English before?")
    ↓ No → skip to A1, create plan directly
    ↓ Yes → continue
    ↓
Step 2: Adaptive quiz (15 questions, fetched from GET /api/assessment/bank)
    ↓
Step 3: Duration selector (4/8/12/16 weeks) + goals selection
    ↓
POST /api/assessment/complete → creates StudyPlan
    ↓
POST /api/study-plan/generate
    ↓
StudyPlanGenerator: distribute_units() from curriculum.py
    ↓ (deterministic — no LLM)
Persists StudyPlan with week-by-week DayPlan structure
    ↓
GET /api/study-plan/today → returns lessons for current day
    ↓ (auto-generates lesson content via LLM on first access)
LessonGenerator → LLM Adapter → structured lesson content
    ↓
Persists Lesson + Exercises in PostgreSQL; optional per-exercise native explanations remain in Lesson.content JSON
    ↓
Frontend ← Lesson content + exercises
```

## Data flow — Voice conversation

```
User opens /conversation
    ↓
Frontend: ConversationMode loads VAD (onnxruntime-web WASM)
    ↓
WebSocket connects to /ws/conversation
    ↓
Client sends first JSON auth frame with access token
    ↓
Backend validates auth, subscription, freemium trial/quota, maintenance mode, TTS service, STT service, quota, and selected target language plan
    ↓
User speaks → VAD detects speech → sends WAV chunks via WS
    ↓
ConversationPipeline:
  STT Service: WAV → text
  LLM Adapter: text → full response
  TTS Service: each sentence → MP3
    ↓
MP3 chunks sent back via WebSocket
  Frontend: AudioQueue schedules gapless playback
    ↓
Stable turn guard: frontend ignores user speech while the tutor turn is active
```

## Auth design

- access_token — Type: JWT; Algorithm: HS256; Duration: 15 min; Storage: Zustand store (JS memory)
- refresh_token — Type: Opaque UUID4; Algorithm: random; Duration: 30 days; Storage: httpOnly cookie + Redis: `refresh:{token}` → user_id
- email verification — Type: Opaque UUID4; Algorithm: random; Duration: 24 h; Storage: Redis: `verify_email:{token}` → user_id
- password reset — Type: Opaque UUID4; Algorithm: random; Duration: 1 h; Storage: Redis: `reset_password:{token}` → user_id
- maintenance mode — Type: bool flag; Algorithm: —; Duration: indefinite; Storage: Redis: `maintenance_mode` → `"1"` or `"0"`

**Design rationale:**

- **Access token**: verified without DB hit (JWT decode only). Short lifetime limits damage if leaked.
- **Refresh token**: stored in Redis with native TTL for auto-expiry. Opaque (not JWT) so no sensitive data in the cookie.
- **Token rotation**: on refresh, old token is deleted from Redis and a new one is created — prevents replay attacks.
- **Logout**: deletes the refresh token from Redis and clears the cookie.
- **Frontend interceptor** (`apiFetch`): on 401 response, silently refreshes the access token and retries the request. On refresh failure, redirects to `/login`.

### Maintenance mode

Stored as a simple Redis flag (`maintenance_mode` = `"1"` / `"0"`). Set explicitly by the admin at runtime via `PUT /api/admin/maintenance` — no restart required.

**Backend guard** (`app/core/deps.py`):

- `get_redis()` — centralized async Redis dependency.
- `check_maintenance_mode()` — raises HTTP 503 when `maintenance_mode == "1"`. Swallows Redis errors to fail open.
- `require_subscription` — checks only subscription status. It does not consult maintenance mode.
- `require_subscription_or_freemium(feature: str)` — factory dependency that checks: 1) `STRIPE_ENABLED=false` → pass, 2) subscribed → pass, 3) freemium trial active → pass, 4) freemium quota available for the feature → pass, 5) else → HTTP 402 with `{reason: "freemium_exhausted"}`. Used on chat, listening, reading, conversation warmup, and lesson completion endpoints. Memory management requires authentication only.
- `require_not_maintenance` — checks only the `maintenance_mode` flag for operational feature availability. Non-admin users receive HTTP 503 when maintenance is active; admins bypass the guard so they can verify gated features during maintenance. Applied explicitly alongside subscription/freemium checks on chat, listening, reading, and conversation warmup endpoints. The WebSocket (`/ws/conversation`) performs the same maintenance check manually. Memory-management endpoints intentionally remain available.

Memories are global per user. Text chat and voice load the same collection, use a normalized native `save_user_memory` tool with one continuation round, and retain `study_plan_id` only as nullable provenance. Deleting a language sets that provenance to `NULL` rather than deleting memory.

**Frontend**: `MaintenanceGate` component renders a static banner when `maintenance_mode` is true for non-admin users. Applied on top of `PaywallGate` in the four subscription-gated pages: `/chat`, `/conversation`, `/listening`, `/reading`. Administrators manage the flag from the dedicated `/admin/system` section; the admin overview keeps a read-only status summary linking to that page.

**Public exposure**: `GET /api/config` returns `maintenance_mode: bool` so the frontend can read the state without an authenticated request.

---

## Tests

Testing infrastructure and strategy are documented in [testing.instructions.md](testing.instructions.md).

**Summary:**

- **Backend**: pytest + pytest-asyncio, 43 test files, 966 tests, 84.79% last measured coverage (target: 70%)
- **Frontend**: Vitest, 39 test files, 440 tests covering stores, components, hooks, lib, i18n, app pages, billing paywall UI, billing success verification, feedback unread labels, SSE parsing, memory toasts, chat stream resets, and middleware; coverage is not configured/reported
- **E2E**: Playwright (planned, not yet implemented)
