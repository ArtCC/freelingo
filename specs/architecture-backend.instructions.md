---
description: "Backend architecture reference for FreeLingo: directory structure, database models, service layer, routers, schemas, core modules, code standards, environment variables, and test configuration."
applyTo: "backend/**"
---

# Architecture — Backend

> The general architecture overview (repository structure, data flows, auth design) lives in [architecture.instructions.md](architecture.instructions.md). Frontend-specific architecture lives in [architecture-frontend.instructions.md](architecture-frontend.instructions.md).
>
> API endpoints are documented separately in [api-endpoints.instructions.md](api-endpoints.instructions.md).
> Database model details are in [database-models.instructions.md](database-models.instructions.md).
> Service details are in [services.instructions.md](services.instructions.md).

## Directory structure

```
backend/
├── app/
│   ├── core/                    # Config, DB engine, security, deps, rate limiter
│   │   ├── __init__.py
│   │   ├── config.py            # Pydantic Settings — all env vars defined here
│   │   ├── database.py          # SQLAlchemy async engine + session factory
│   │   ├── deps.py              # FastAPI dependencies: get_redis, get_current_user, maintenance/subscription guards
│   │   ├── security.py          # JWT encode/decode, password hashing
│   │   ├── app_logger.py        # Structured logging (structlog)
│   │   └── limiter.py           # slowapi rate limiter setup
│   │
│   ├── models/                  # SQLAlchemy 2.0 ORM models (16 files, 22 model classes)
│   │   ├── __init__.py
│   │   ├── user.py              # User, UserPreferences, user quotas, avatar
│   │   ├── user_language.py     # UserLanguage (phase 10: multi-language learning)
│   │   ├── progress.py          # Progress (daily XP, streak, skills JSON)
│   │   ├── study_plan.py        # StudyPlan, DayPlan (week-by-week JSON)
│   │   ├── lesson.py            # Lesson + Exercise
│   │   ├── competency.py        # UserCompetency (curriculum tracking)
│   │   ├── flashcard.py         # Flashcard (SM-2 algorithm)
│   │   ├── conversation.py      # Conversation (voice sessions)
│   │   ├── chat_history.py      # ChatHistory (text chat messages)
│   │   ├── listening.py         # ListeningExercise, ListeningAttempt
│   │   ├── reading.py           # ReadingExercise, ReadingAttempt
│   │   ├── feedback.py          # FeedbackEntry, FeedbackVote, FeedbackComment, FeedbackReadState
│   │   ├── review.py            # Review (one moderated product review per user)
│   │   ├── resource_native_help.py # ResourceNativeHelp (global native-help cache for static resources)
│   │   ├── memory.py            # Memory (persistent LLM context)
│   │   └── llm_usage.py         # LLMUsage (token audit trail)
│   │
│   ├── schemas/                 # Pydantic v2 request/response schemas (15 modules)
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── admin.py
│   │   ├── assessment.py
│   │   ├── chat.py
│   │   ├── feedback.py
│   │   ├── flashcards.py
│   │   ├── language.py
│   │   ├── lessons.py
│   │   ├── listening.py
│   │   ├── progress.py
│   │   ├── reading.py
│   │   ├── review.py
│   │   ├── study_plan.py
│   │   └── tts_stt.py
│   │   ├── vocabulary.py
│   │   ├── curriculum.py
│   │   └── phrasebook.py
│   │
│   ├── routers/                 # FastAPI routers (23 REST + 1 WebSocket = 24 total)
│   │   ├── __init__.py
│   │   ├── admin.py             # Admin overview metrics, review signals, user management, filtered lists, maintenance toggle
│   │   ├── assessment.py        # Level assessment quiz + completion + static bank
│   │   ├── auth.py              # Register, login, refresh, logout, avatar upload/private retrieval/delete, verify-email, reset-password
│   │   ├── billing.py           # Stripe checkout, customer portal, webhook with current-subscription matching
│   │   ├── chat.py              # SSE chat streaming
│   │   ├── config.py            # Public config endpoint (maintenance mode, features)
│   │   ├── contact.py           # Contact form submission
│   │   ├── conversation.py      # WebSocket voice conversation
│   │   ├── curriculum.py        # Curriculum data (now auth-required)
│   │   ├── feedback.py          # Feedback CRUD, search, unread counters, author roles, admin status management
│   │   ├── flashcards.py        # Spaced-repetition flashcard CRUD + review
│   │   ├── freemium.py          # Freemium quota status and trial state
│   │   ├── grammar.py            # Grammar reference topics by language and CEFR level
│   │   ├── health.py            # Public minimal liveness check + private admin diagnostics
│   │   ├── languages.py         # Available target languages
│   │   ├── lessons.py           # Lesson content + exercise submission
│   │   ├── listening.py         # AI-generated listening exercises
│   │   ├── memories.py          # LLM memory management
│   │   ├── phrasebook.py        # Phrasebook categories and phrases
│   │   ├── progress.py          # User progress, XP, streak, skills, vocabulary summary
│   │   ├── reading.py           # AI-generated reading exercises
│   │   ├── reviews.py           # User reviews: create/state, public list, admin moderation
│   │   ├── stt.py               # Speech-to-text proxy
│   │   ├── study_plan.py        # Study plan generation + current/pending/generated lesson metadata
│   │   ├── tts.py               # Text-to-speech proxy
│   │   └── vocabulary.py        # Static vocabulary data (per language + per level)
│   │
│   ├── services/                # Business logic + external service clients (21 modules + prompts package)
│   │   ├── __init__.py
│   │   ├── assessment.py        # Adaptive quiz logic, CEFR level estimation
│   │   ├── assessment_voice_trial.py # One-time post-assessment voice demo token service
│   │   ├── conversation_pipeline.py  # WebSocket voice orchestrator: STT → LLM → TTS
│   │   ├── email_service.py     # SMTP email (verification, password reset, contact, admin notifications)
│   │   ├── flashcard_sm2.py     # SM-2 spaced repetition algorithm
│   │   ├── freemium_service.py  # Freemium quota checking, usage recording, trial state, status response builder
│   │   ├── language_helpers.py  # Language code parsing, script metadata, prompt length guidance, voice/engine selection
│   │   ├── lesson_generator.py  # LLM-powered lesson content generation
│   │   ├── listening_service.py # AI listening exercise generation + caching
│   │   ├── llm_adapter.py       # Multi-provider LLM interface (Ollama, OpenAI, Anthropic, DeepSeek)
│   │   ├── memory_service.py    # Autonomous LLM memory management
│   │   ├── progress_service.py  # XP calculation, streak logic, skill scoring
│   │   ├── prompts/             # Centralized LLM prompt templates and builders
│   │   ├── quota_service.py     # Token quota tracking and enforcement
│   │   ├── reading_service.py   # AI reading exercise generation + caching
│   │   ├── resource_native_help.py # Static-resource native-help cache helpers
│   │   ├── review_service.py    # User review creation, duplicate guard, approval, deletion
│   │   ├── stt_service.py       # Speech-to-text abstraction (local Whisper / OpenAI)
│   │   ├── study_plan_generator.py  # Deterministic unit distribution from curriculum
│   │   ├── subscription_service.py  # Stripe subscription management
│   │   ├── tts_service.py       # Text-to-speech abstraction (local Kokoro / OpenAI)
│   │   └── user_language_service.py # Multi-language study plan management (phase 10)
│   │
│   └── data/                    # Static curriculum, assessment, vocabulary, and phrasebook content (9 language modules)
│       ├── __init__.py
│       ├── _types.py             # Shared types (CEFRLevel, CurriculumUnit, AssessmentQuestion, VocabularyEntry, VocabularySet, PhrasebookEntry, PhrasebookCategory)
│       ├── curriculum.py         # Language-aware curriculum dispatcher
│       ├── assessment_bank.py    # Language-aware assessment bank dispatcher
│       ├── vocabulary.py         # Language-aware vocabulary dispatcher
│       ├── en_GB/                # British English — curriculum, assessment bank, vocabulary, phrasebook
│       ├── en_US/                # American English — curriculum, assessment bank, vocabulary, phrasebook
│       ├── de/                   # German — curriculum, assessment bank, vocabulary, phrasebook
│       ├── es/                   # Spanish — curriculum, assessment bank, vocabulary, phrasebook
│       ├── fr/                   # French — curriculum, assessment bank, vocabulary, phrasebook
│       ├── it/                   # Italian — curriculum, assessment bank, vocabulary, phrasebook
│       ├── ja/                   # Japanese — curriculum, assessment bank, vocabulary, phrasebook
│       ├── ko/                   # Korean — curriculum, assessment bank, vocabulary, phrasebook
│       ├── zh/                   # Mainland Chinese — curriculum, assessment bank, vocabulary, phrasebook
│       └── pt/                   # Portuguese — curriculum, assessment bank, vocabulary, phrasebook
│
├── alembic/
│   └── versions/                # DB migrations (49 migrations)
│
└── tests/                       # pytest suite (43 test files, 945 tests)
```

## Database models

The application uses 22 SQLAlchemy ORM model sections organized into 5 domains:

- **Core**: User (authentication, preferences, quotas, Stripe state, post-assessment voice demo state, freemium trial state), Progress (daily XP/streak/skills)
- **Study plan**: StudyPlan, Lesson, Exercise, UserCompetency (curriculum tracking)
- **Spaced repetition**: Flashcard (SM-2 algorithm)
- **Conversations**: Conversation, ChatHistory (text and voice transcripts)
- **AI-generated/static support content**: ListeningExercise, ListeningAttempt, ReadingExercise, ReadingAttempt (shared exercise pools), ResourceNativeHelp (global native-language cache for static resources)
- **Community**: FeedbackEntry, FeedbackVote, FeedbackComment (feature requests and bug reports), Review (moderated product reviews)
- **LLM**: Memory (global per-user persistent context with nullable study-plan provenance), LLMUsage (token audit trail)
- **Multi-language**: UserLanguage (phase 10 — enables learning multiple target languages per user)

All models use SQLAlchemy 2.0 declarative style with `Mapped[T]` type annotations. PostgreSQL JSON columns store structured content for lessons, plans, exercises, and skill scores.

Feedback entry and comment response schemas embed `FeedbackAuthor` with `id`, `username`, `display_name`, and `role`. The router resolves the current user role while building both individual and batched responses, allowing the frontend to distinguish administrator-authored community content without changing the feedback database models.

`UserUpdateRequest` validates `native_language` against the same supported code set as registration. The frontend exposes a selector, while the backend validation keeps direct or modified API requests from persisting unknown language codes that would later enter native-language prompts and memory-tool descriptions.

For complete schema details, relationships, constraints, and business rules, see [database-models.instructions.md](database-models.instructions.md).

---

## Service layer

All external dependencies are accessed through the service layer. The frontend never calls Ollama, Kokoro, or Whisper directly — the backend is the single gateway.

The application uses 18 services plus a centralized `services/prompts/` package organized into 5 domains:

- **LLM & AI**: LLM Adapter (multi-provider), Assessment, Study Plan Generator, Lesson Generator, Flashcard SM-2
- **Media**: TTS Service, STT Service, Conversation Pipeline (WebSocket voice orchestrator)
- **Content**: Listening Service, Reading Service (AI-generated exercises with caching; generation responses validated with Pydantic `structured_output()` schemas), Resource Native Help (global cache for static-resource native-language helpers)
- **User**: Progress Service, Memory Service, Quota Service, Subscription Service, Freemium Service, User Language Service
- **Community**: Review Service
- **Infrastructure**: Language Helpers, Email Service
- **Prompt architecture**: prompt templates, shared blocks, CJK-ready language overlays, and builders live in `services/prompts/`; see [prompts.instructions.md](prompts.instructions.md)

Key architectural decisions:

- **LLM Adapter** is a singleton with provider-agnostic interface (Ollama, OpenAI, Anthropic, DeepSeek). Streaming native tools normalize OpenAI-compatible and Anthropic events, forward visible text progressively while filtering tool metadata, execute at most one call, and continue once with provider-native tool-result messages. OpenAI GPT-5.6 Chat Completions set `reasoning_effort="none"` only for tool rounds. Across every provider, a tool-enabled failure before visible output falls back to the original turn without tools and becomes session-local unavailable capability for voice; continuation failures after visible output keep the partial response instead of duplicating it or failing the turn. Memory executor failures are logged and returned only as failed tool results.
- **Memory Service** owns strict native `save_user_memory` execution, escaped global context, exact per-user deduplication, a 150-item cap, manual creation, and owner-scoped management. Saves, individual deletion, and clear-all serialize on the same user-row lock. `study_plan_id` records nullable provenance only.
- **Voice memory capability** is session-local state on `ConversationPipeline`. Once a model explicitly rejects tools, later turns in the same WebSocket session omit them; a new voice session probes capability again.
- **Study Plan Generator** and **Lesson Generator** are deterministic within curriculum constraints; lesson generation can include native-language support at lesson level, per-exercise explanation level, and per-exercise pre-answer hint level without adding separate exercise-table columns, enriched lesson vocabulary with native-language translation/example notes inside lesson JSON, and missing exercise native explanations or hints can be generated on demand and cached in lesson JSON
- **TTS/STT services** abstract local (Kokoro/Whisper) and cloud (OpenAI) providers behind common interfaces
- **Conversation Pipeline** orchestrates real-time voice: cancellable greeting, STT → full LLM response → sentence-level TTS chunks, serialized WebSocket sends, empty-STT guard, and backend barge-in support with frontend automatic interruption disabled
- **Language Helpers** centralize target-language display names, ISO codes, script metadata, romanization metadata, word-spacing metadata, and reading/listening length guidance. Japanese (`ja-JP`), Korean (`ko-KR`), and Mainland Chinese (`zh-CN`) are enabled in backend language allow-lists and static content dispatchers.

For complete service details, APIs, and implementation notes, see [services.instructions.md](services.instructions.md).

---

## Code standards (Python 3.14)

- ruff — Linting + isort + pyupgrade (rules: E, W, F, I, UP, B, S, ANN)
- black — Code formatting (line-length 100)

- ANN101 (missing self type annotation) ignored globally.
- S and ANN rules disabled in `tests/` directory.

---

## Tests

Testing infrastructure and strategy are documented in [testing.instructions.md](testing.instructions.md).

**Summary:**

- **Framework**: pytest + pytest-asyncio + httpx AsyncClient
- **Test files**: 43 (plus conftest.py for shared fixtures)
- **Tests**: 945
- **Coverage**: 84.42% last measured (target: ≥70%)
- **Key fixtures**: async database session, test client with auth headers, Redis mock, user_language fixture

---

## Environment variables

All configuration is environment-driven. Variables are defined in `app/core/config.py` (Pydantic Settings). 63 variables total — the complete list below.

### Core

- DATABASE_URL — Default: —; Purpose: asyncpg connection string
- REDIS_URL — Default: redis://localhost:6379/0; Purpose: Redis connection string
- SECRET_KEY — Default: —; Purpose: JWT signing key (HS256)
- ACCESS_TOKEN_EXPIRE_MINUTES — Default: 15; Purpose: JWT lifetime
- REFRESH_TOKEN_EXPIRE_DAYS — Default: 30; Purpose: Refresh token TTL
- CORS_ORIGINS — Default: ["http://localhost:3000"]; Purpose: Allowed CORS origins (JSON array)
- COOKIE_SECURE — Default: false; Purpose: Set `Secure` flag on cookies
- LOG_LEVEL — Default: INFO; Purpose: Application log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)

### Default usage quotas

- DEFAULT_CONVERSATION_MAX_DURATION — Default: 1800; Purpose: default max voice session duration in seconds for new users; supported values: `900`, `1800`
- DEFAULT_CONVERSATION_INACTIVITY_TIMEOUT — Default: 180; Purpose: default inactivity disconnect timeout in seconds for new users; supported values: `60`, `180`, `300`
- DEFAULT_CONVERSATION_WEEKLY_SESSIONS — Default: 0; Purpose: default weekly voice session quota; `0` means unlimited
- DEFAULT_CONVERSATION_DAILY_MINUTES — Default: 30; Purpose: default daily voice conversation minutes
- DEFAULT_CONVERSATION_WEEKLY_MINUTES — Default: 90; Purpose: default weekly voice conversation minutes
- DEFAULT_MONTHLY_TOKENS_LIMIT — Default: 1000000; Purpose: default monthly LLM token quota; `0` means unlimited
- ASSESSMENT_VOICE_TRIAL_DURATION_SECONDS — Default: 300; Purpose: post-assessment voice demo duration in seconds

### Auth & registration

- ALLOW_REGISTRATION — Default: true; Purpose: Enables/disables public signups
- FIRST_USER_IS_ADMIN — Default: true; Purpose: Auto-admin for first user
- BLOCKED_EMAIL_DOMAINS — Default: []; Purpose: JSON array of blocked email domains (disposable/temporary providers)

### LLM

- LLM_PROVIDER — Default: ollama; Purpose: `ollama` / `openai` / `anthropic` / `deepseek`
- OLLAMA_BASE_URL — Default: http://host.docker.internal:11434; Purpose: Ollama API endpoint
- OLLAMA_MODEL — Default: gemma4:e4b; Purpose: Model tag to use with Ollama
- OPENAI_API_KEY — Default: ``; Purpose: OpenAI API key (also reused for TTS/STT when provider is `openai`)
- OPENAI_MODEL — Default: gpt-4o-mini; Purpose: OpenAI chat model
- ANTHROPIC_API_KEY — Default: ``; Purpose: Anthropic API key
- ANTHROPIC_MODEL — Default: claude-3-5-haiku-latest; Purpose: Anthropic chat model
- DEEPSEEK_API_KEY — Default: ``; Purpose: DeepSeek API key
- DEEPSEEK_MODEL — Default: deepseek-chat; Purpose: DeepSeek chat model

### TTS

- TTS_PROVIDER — Default: local; Purpose: `local` (Kokoro) or `openai`
- TTS_BASE_URL — Default: http://kokoro:8880; Purpose: Kokoro-FastAPI endpoint (local provider)
- TTS_VOICE — Default: af_heart; Purpose: Kokoro voice ID (local provider)
- OPENAI_TTS_MODEL — Default: tts-1; Purpose: OpenAI TTS model (openai provider)
- OPENAI_TTS_VOICE — Default: nova; Purpose: OpenAI TTS voice (openai provider)
- OPENAI_TTS_SPEED — Default: 1.0; Purpose: OpenAI TTS playback speed (openai provider)

### STT

- STT_PROVIDER — Default: local; Purpose: `local` (faster-whisper) or `openai`
- STT_BASE_URL — Default: http://whisper:9000; Purpose: Whisper ASR endpoint (local provider)
- OPENAI_STT_MODEL — Default: whisper-1; Purpose: OpenAI STT model (openai provider)

> `STT_MODEL` and `STT_ENGINE` are Docker-level variables passed to the Whisper container — they are **not** consumed by the Python backend.

### Stripe

- STRIPE_ENABLED — Default: false; Purpose: Enable Stripe paywall; `false` = all active users have full access
- STRIPE_SECRET_KEY — Default: ``; Purpose: Stripe secret key
- STRIPE_WEBHOOK_SECRET — Default: ``; Purpose: Stripe webhook signing secret
- STRIPE_PRICE_MONTHLY — Default: ``; Purpose: Stripe Price ID for monthly plan; required when `STRIPE_ENABLED=true`
- STRIPE_PRICE_YEARLY — Default: ``; Purpose: Stripe Price ID for yearly plan; required when `STRIPE_ENABLED=true`
- STRIPE_TRIAL_DAYS — Default: 7; Purpose: Free trial duration in days
- STRIPE_BASE_URL — Default: http://localhost:3000; Purpose: Frontend base URL used in Stripe redirect URLs

The app does not create Stripe products or prices automatically; operators configure the Stripe Price IDs from the Stripe Dashboard.

### Freemium

- FREEMIUM_CHAT_DAILY_MESSAGES — Default: 5; Purpose: daily AI chat messages for free-tier users. `0` = blocked.
- FREEMIUM_LESSONS_DAILY — Default: 3; Purpose: daily lesson completions for free-tier users. `0` = blocked.
- FREEMIUM_LISTENING_WEEKLY — Default: 3; Purpose: weekly listening exercises for free-tier users. `0` = blocked.
- FREEMIUM_READING_WEEKLY — Default: 3; Purpose: weekly reading exercises for free-tier users. `0` = blocked.
- FREEMIUM_VOICE_WEEKLY_MINUTES — Default: 5; Purpose: weekly voice conversation minutes for free-tier users. `0` = blocked.
- FREEMIUM_TRIAL_ENABLED — Default: true; Purpose: enable 7-day no-card trial for new users
- FREEMIUM_TRIAL_DAYS — Default: 7; Purpose: duration of freemium trial in days

### Email

- EMAIL_ENABLED — Default: false; Purpose: Enable SMTP email (verification, password reset, contact form, admin notifications)
- CONTACT_EMAIL — Default: ``; Purpose: Destination address for contact form submissions and admin notifications
- SMTP_HOST — Default: localhost; Purpose: SMTP server hostname
- SMTP_PORT — Default: 587; Purpose: SMTP server port
- SMTP_USER — Default: ``; Purpose: SMTP username
- SMTP_PASSWORD — Default: ``; Purpose: SMTP password
- SMTP_FROM — Default: noreply@freelingo.app; Purpose: From address for outgoing emails
- SMTP_TLS — Default: true; Purpose: Use STARTTLS
- SMTP_SSL — Default: false; Purpose: Use implicit SSL (port 465)
- APP_BASE_URL — Default: http://localhost:3000; Purpose: Public frontend URL (used in email links)

### Other

- RATE_LIMIT_ENABLED — Default: true; Purpose: Enable slowapi rate limiting
- AUDIO_STORAGE_PATH — Default: /data/audio; Purpose: Docker volume path for generated listening MP3 files
- AVAILABLE_TARGET_LANGUAGES — Default: ["de-DE","en-GB","en-US","es-ES","fr-FR","it-IT","ja-JP","ko-KR","pt-PT","zh-CN"]; Purpose: Operator-configured BCP-47 target-language list; entries not present in backend `SUPPORTED_TARGET_LANGUAGES` are filtered out

### Docker-level variables (not consumed by Python backend)

- POSTGRES_DB — Default: freelingo; Consumed by: PostgreSQL container + DATABASE_URL composition
- POSTGRES_USER — Default: freelingo; Consumed by: PostgreSQL container + DATABASE_URL composition
- POSTGRES_PASSWORD — Default: —; Consumed by: PostgreSQL container + DATABASE_URL composition
- DATA_PATH — Default: /opt/docker/freelingo; Consumed by: Docker bind mounts for persistent data
- REDIS_PASSWORD — Default: —; Consumed by: Redis container + REDIS_URL composition
- STT_MODEL — Default: large-v3-turbo; Consumed by: Whisper Docker container (ASR_MODEL)
- STT_ENGINE — Default: faster_whisper; Consumed by: Whisper Docker container (ASR_ENGINE)
- UVICORN_WORKERS — Default: 4; Consumed by: Docker entrypoint command

For Docker configuration details, see [docker.instructions.md](docker.instructions.md).
