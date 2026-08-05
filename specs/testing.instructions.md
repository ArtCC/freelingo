---
description: "Testing strategy for FreeLingo: backend pytest suite (43 test files, 945 tests, 84.42% last measured coverage, with SQLite in-memory DB and Redis mocking), frontend Vitest suite (38 test files, 436 tests, no configured coverage, covering stores, components, lib, hooks, app pages, i18n, billing paywall UI, billing success verification, feedback unread labels, SSE parsing, memory toasts, and middleware), E2E plan (Playwright, pending), CI integration, and coverage requirements."
applyTo: "**/*.test.*, **/*.spec.*, **/tests/**, **/__tests__/**"
---

# Testing — FreeLingo

## Overview

- Backend unit + integration — Framework: pytest + pytest-asyncio; Scope: API endpoints, services, SM-2 algorithm, data integrity; Coverage: 84.42% last measured (target: 70%); Status: Implemented
- Frontend unit — Framework: Vitest; Scope: Stores, components, hooks, lib, middleware; Coverage: Not configured; Status: Implemented
- E2E — Framework: Playwright; Scope: Critical user flows; Coverage: Smoke; Status: Pending

All tests pass on every push. Backend coverage threshold configured at 70%, last measured at 84.42%. Frontend tests cover stores, critical components (VoiceRecorder, AudioPlayer, ProfileSection, UnitCard/UnitDrawer, LanguageSwitcher, TargetLanguageSelector, review UI, LanguageBubbles, billing paywall UI, memory toast), billing success verification, app pages, hooks, lib modules, SSE framing, i18n, and middleware. Frontend coverage is not currently reported because Vitest coverage is not configured and `@vitest/coverage-v8` is not installed.

---

## Backend tests (pytest)

### Test infrastructure

- **Database**: SQLite in-memory (`sqlite+aiosqlite:///:memory:`) for fast, isolated tests — no PostgreSQL dependency. Tables are auto-created/dropped per test via `setup_db` fixture.
- **Redis**: mocked with an in-memory dict-based mock (implements `setex`, `get`, `delete`, `getex` with same interface as `redis.asyncio.Redis`). No Redis server needed.
- **LLM**: always mocked at the service layer. Tests never call real Ollama, OpenAI, Anthropic, or DeepSeek.
- **HTTP client**: `httpx.AsyncClient` with `ASGITransport` for FastAPI app testing, database and Redis dependencies overridden via `app.dependency_overrides`.
- **Async**: `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` decorators needed.
- **Warnings**: pytest filters known external `slowapi` deprecations (`python_multipart` pending deprecation and Python `cgi` deprecation) so the suite output stays focused on project warnings.

### Test file inventory

- **`conftest.py`** — Lines: 153. What it covers: Shared fixtures: in-memory SQLite engine, test DB session, mock Redis, HTTP client, test user and admin creation
- **`test_auth.py`** — Lines: 593. What it covers: Registration (success, duplicate, invite gating), login, refresh (rotation, replay detection), logout, me, update-profile
- **`test_auth_extra.py`** — Lines: 143. What it covers: Additional auth edge cases and error scenarios
- **`test_admin.py`** — Lines: 245. What it covers: CRUD users, role enforcement (403 for non-admin), invite creation with 48h expiry
- **`test_admin_extra.py`** — Lines: 149. What it covers: Additional admin operations and permission checks
- **`test_avatar.py`** — Lines: 366. What it covers: Avatar upload, content-type/signature validation, UUID reference storage, private retrieval, non-public reference guard, replacement, deletion, and legacy retrieval compatibility
- **`test_assessment.py`** — Lines: 165. What it covers: Quiz start (mocked LLM), submit and deterministic evaluation, legacy endpoints, LLM error handling
- **`test_assessment_router.py`** — Lines: —. What it covers: Full assessment router: start, submit, evaluate, free-write, complete, post-assessment voice trial grant/regeneration, level-test questions/submit/result (58 tests, 51%→98% coverage)
- **`test_study_plan.py`** — Lines: 500+. What it covers: Plan generation, today's lessons, auto-generation on access, generated lesson metadata, native-language lesson-generation context, unit progression
- **`test_lessons.py`** — Lines: 400+. What it covers: Lesson CRUD, exercise answering (multiple_choice, free_write, pronunciation), invalid exercise regeneration, completion flow, progress update on complete
- **`test_lessons_extra.py`** — Lines: 106. What it covers: Additional lesson scenarios and edge cases
- **`test_lessons_router.py`** — Lines: —. What it covers: Lesson router: get lesson with exercises, atomic/idempotent completion including rollback and quota-bypass retries, native-language explanation generation/caching, answer exercises (all 4 types), lifecycle, fill-blank sanitization (41 tests, 58%→99% coverage)
- **`test_flashcards.py`** — Lines: 136. What it covers: SM-2 algorithm (all quality levels 0–5, interval and ease_factor transitions, edge cases), card CRUD
- **`test_flashcards_extra.py`** — Lines: 201. What it covers: Additional flashcard scenarios and SM-2 edge cases
- **`test_chat.py`** — Lines: 54. What it covers: SSE streaming chunks, conversation creation and messaging
- **`test_chat_conversations.py`** — Lines: 254. What it covers: Persistent conversations, message history, conversation management
- **`test_contact.py`** — Lines: —. What it covers: Contact form forwarding, admin-locale selection, email disabled/missing-destination no-op behavior, and email failure mapping to HTTP 502 (4 tests)
- **`test_progress.py`** — Lines: 48. What it covers: Progress summary and history with empty and populated data
- **`test_progress_extra.py`** — Lines: 83. What it covers: Additional progress tracking scenarios
- **`test_conversation.py`** — Lines: 555+. What it covers: WebSocket authentication, TTS/STT disabled rejection, conversation warmup, post-assessment voice trial token acceptance/rejection, pipeline lifecycle, session management
- **`test_conversation_pipeline_service.py`** — Lines: —. What it covers: Conversation pipeline service: system prompt, native-language name injection, sentence cleaning, TTS queue, greet, audio processing, barge-in, usage tracking, inactivity watcher, max-duration watcher, full lifecycle
- **`test_email_service.py`** — Lines: —. What it covers: Email template rendering escapes user-controlled values by default while preserving explicitly trusted internal HTML, including contact/review templates (3 tests)
- **`test_frontend_data_integrity.py`** — Lines: 168+. What it covers: Cross-reference validation for grammar, vocabulary, related grammar slugs, and vocabulary IDs across backend language data, including Japanese, Korean, and Mainland Chinese.
- **`test_grammar.py`** — Lines: 290+. What it covers: Grammar API: list topics, topic detail, language switching, auth, error cases, Japanese/Korean/Mainland Chinese data resolution, and native-help generation/cache refresh.
- **`test_listening.py`** — Lines: 503. What it covers: Exercise pool (next / generate), generation lock, audio serving, answer evaluation (score + XP), attempt deduplication, history
- **`test_listening_extra.py`** — Lines: 208. What it covers: Additional listening exercise scenarios
- **`test_reading.py`** — Lines: 400+. What it covers: Reading exercise generation with `structured_output()`, language-aware CJK length guidance, comprehension questions, answer evaluation, XP calculation
- **`test_reading_extra.py`** — Lines: 255. What it covers: Additional reading exercise scenarios
- **`test_vocabulary.py`** — Lines: 175+. What it covers: Vocabulary API: list sets, by-level, set detail, language switching, auth, error cases, Japanese/Korean/Mainland Chinese data resolution, and native-help generation/cache refresh.
- **`test_feedback.py`** — Lines: 1500+. What it covers: Feedback board: feature requests, bug reports, default exclusion of done entries, voting, comments, admin moderation, unread thread counters, per-thread read markers, and per-entry `unread_by_me` response flags
- **`test_billing.py`** — Lines: 381+. What it covers: Stripe subscriptions, Checkout customer reuse, Customer Portal access including payment-recovery states, webhooks, payment status, real Stripe subscription statuses, unknown-status fallback, subscription lifecycle, webhook retry behavior on processing failure, current Stripe Invoice subscription shape, `stripe_subscription_id` persistence/backfill, and stale subscription-event ignoring
- **`test_maintenance.py`** — Lines: 153. What it covers: Maintenance mode toggle, API behavior during maintenance
- **`test_memories.py`** — What it covers: global LLM memory (Phase 9), strict native tool schema, escaped context, manual creation and duplicate validation, authenticated ungated management, ownership, exact deduplication, hard cap including eviction of existing FIFO entries, shared per-user locks for deletion/clear-all, and text chat tool-update events
- **`test_llm_adapter.py`** — Also covers progressive visible text before the tool path is known and during continuation, OpenAI GPT-5.6 tool rounds with `reasoning_effort="none"`, one-round native tool streaming for OpenAI-compatible and Anthropic providers, exact and generic pre-output fallback without tools, one-time positive capability logging, failed-continuation recovery with usage accumulation, and one-call execution limits
- **`test_multi_language.py`** — Also covers global cross-language memory retrieval and memory preservation through language deletion
- **`frontend/tests/lib/memories.test.ts` and `frontend/tests/app/settings-memories.test.tsx`** — Cover memory API helpers and add/list/delete/clear Settings states
- **`frontend/tests/lib/sse.test.ts`** — Covers SSE events fragmented across byte chunks, CRLF framing, malformed-event isolation, and truncated final-event rejection
- **`frontend/tests/components/MemorySavedToast.test.tsx`** — Covers live-region semantics, automatic dismissal, and timer restart
- **`test_multi_language.py`** — Lines: —. What it covers: Multi-language isolation, active language switching, language API, onboarding language creation, curriculum dispatch
- **`test_llm_adapter.py`** — Lines: —. What it covers: LLM adapter: JSON parsing, streaming, 5 exception classes, 4 provider init paths, chat (streaming + non-streaming), Anthropic error mapping, structured output with retry, DeepSeek provider, edge cases (63 tests, 38%→100% coverage)
- **`test_prompts.py`** — Lines: —. What it covers: Centralized prompt builders, regional/native language names, language capability metadata, memory instructions, JSON-only block reuse, language overlays including CJK readiness overlays and aliases
- **`test_reviews.py`** — Lines: —. What it covers: User reviews: creation, editing, rating validation, duplicate guard, public filtering, admin moderation, permissions, admin email notification on creation
- **`test_phrasebook.py`** — Lines: 330+. What it covers: Phrasebook API: list categories, by-level filtering, category detail, language switching, auth, error cases, Japanese/Korean/Mainland Chinese data resolution, and native-help generation/cache refresh.
- **`test_quota_service.py`** — Lines: —. What it covers: Quota service: key helpers, quota status, session tracking, daily/weekly minute checks, monthly token tracking, combined quota validation, full session lifecycle (71 tests, 37%→100% coverage)
- **`test_flashcard_sm2.py`** — Lines: —. What it covers: Flashcard service: `_clean_generated_word`, `_get_lang_hint` (10 languages + fallbacks), native-language name injection, `generate_flashcards`, `lookup_word`
- **`test_assessment_bank.py`** — Lines: —. What it covers: Assessment bank dispatcher: all 10 backend data languages including Japanese, Korean, and Mainland Chinese, unknown fallback to en-GB, ISO prefix fallback, cache reuse (14 tests, 0%→100% coverage)
- **`test_limiter.py`** — Lines: —. What it covers: Rate limiter: `_get_real_ip` (X-Real-IP, X-Forwarded-For single/multiple, client host fallback, unknown), limiter construction (9 tests, 42%→100% coverage)
- **`test_lesson_generator.py`** — Lines: —. What it covers: Lesson generator service: `get_valid_grammar_slugs`, `generate_lesson`, exercise schema validation, fill-blank sanitization, grammar refs filtering, `evaluate_free_write`, `evaluate_pronunciation`, `evaluate_fill_blank` (16 tests, 51%→100% coverage)
- **`test_listening_service.py`** — Lines: —. What it covers: Listening service DB layer and generation: `structured_output()` generation persistence, language-aware CJK length guidance, `get_available_exercise`, `submit_attempt` (correct/partial/duplicate/replay/not-found), `get_user_history` (empty/attempts/limit/language filter)

**Total: 43 test files, 945 tests.**

### Coverage

- **Current coverage**: 84.42% last measured (above 70% target)
- **Configured threshold**: 70% (enforced via `pytest --cov-fail-under=70`)

### Test patterns

**Mocking LLM**: Mock `llm_adapter.LLMAdapter` as a singleton. Three pattern variants:

- `chat()` → returns a deterministic string (used in assessment, flashcards, chat tests)
- `chat(stream=True)` → returns an async generator yielding token chunks (used in chat SSE tests)
- `structured_output()` → returns a pre-built Pydantic model (used in assessment, lesson, flashcard, reading, and listening tests)

**Mocking Redis**: Mock `get_redis` dependency. The in-memory mock stores `refresh:{token}` → user_id mappings and `invite:{token}` → "1" for invite tokens, matching the real Redis interface.

**Test user creation**: The `test_user` and `admin_user` fixtures create users directly in the test database and return them with pre-built JWT Authorization headers. Each test gets a fresh database via the `setup_db` fixture's autouse create/drop cycle.

### Key test cases

**Auth**:

- Register success, duplicate username rejection, ALLOW_REGISTRATION=false returns 403, first user becomes admin
- Login success sets httpOnly cookie, invalid credentials return 401, inactive user returns 401
- Refresh rotates token (deletes old, creates new), missing cookie returns 401, replayed token returns 401
- Logout deletes refresh token from Redis and clears cookie
- PATCH /me updates display_name, email, password, english_variant, conversation settings

**Flashcards (SM-2)**:

- New card has default values: ease_factor=2.5, interval=0, repetitions=0, next_review=today
- Quality 0 resets repetitions to 0, sets interval to 1
- Quality 3: first review interval=1, second=6, subsequent=interval × ease_factor
- Ease factor increases with quality 5, decreases with quality < 3, floor at 1.3
- Next review date calculated correctly as today + interval days

**Admin**:

- List/create/get/update/delete users requires admin role; non-admin returns 403
- Invite token created with 48-hour TTL, returned as URL `/register?invite=<token>`

**Assessment**:

- Deterministic evaluation finds highest level with >= 2 questions and >= 60% correct
- Free-write evaluation (mocked LLM) returns adjusted_level, score, analysis
- Level test generation (mocked LLM) constrained to grammar/vocabulary from curriculum

**WebSocket conversation**:

- Connection with valid JWT succeeds
- Connection rejected with 4001 close code when TTS_ENABLED=false or STT_ENABLED=false
- Pipeline lifecycle: connect → auth → audio receive → STT → LLM → TTS → send → disconnect

**Data integrity**:

- Every grammar_slug in curriculum.ts referenced by curriculum units exists in grammar.ts
- Every vocabulary_set_id referenced by each language's curriculum exists in that language's backend vocabulary data, including Japanese, Korean, and Mainland Chinese.
- Every related grammar slug in grammar topics points to an existing topic

### Running tests

```bash
cd backend

# All tests with coverage
pytest

# Single test file
pytest tests/test_auth.py -v

# Single test function
pytest tests/test_flashcards.py::test_quality_3_basic_progression -v

# With HTML coverage report
pytest --cov-report=html
```

---

## Frontend tests (Vitest)

### Test infrastructure

- **Framework**: Vitest with jsdom environment
- **Setup file**: `tests/setup.ts` — provides `localStorage` mock and `next/navigation` mock
- **Config**: `vitest.config.ts` with `@/` path alias
- **Location**: `frontend/tests/` (separate from source, mirroring backend structure)
- **Run**: `npm run test:run` (CI/single run) or `npm run test` (watch mode)

### Test file inventory

- **`tests/setup.ts`** — Tests: —. What it covers: Global mocks: `localStorage` (full Storage interface), `next/navigation` (`useRouter`, `usePathname`, `useSearchParams`)
- **`tests/lib/api.test.ts`** — Tests: 8. What it covers: `apiFetch`: Bearer token attachment, 401 refresh + retry, logout on refresh failure, concurrent refresh deduplication, loading counter inc/dec, custom header preservation
- **`tests/store/auth.test.ts`** — Tests: 11. What it covers: `isSubscribed()`: Stripe on/off × subscription states (active, trialing, past_due, canceled, none, null user). Store: `setTokens`, `setUser`, `logout` (clears `fl_tour_done` from localStorage)
- **`tests/lib/audio.test.ts`** — Tests: 8. What it covers: `float32ToWav`: WAV header (RIFF/WAVE/fmt/data), PCM format chunk, buffer size, RIFF chunk size, sample clamping [-1,1], silence encoding, empty arrays, different sample rates
- **`tests/lib/conversation-ws.test.ts`** — Tests: 6. What it covers: `buildConversationWsUrl`: https→wss, http→ws, same-origin fallback from `window.location`, whitespace trimming, trailing slash handling
- **`tests/middleware.test.ts`** — Tests: 12. What it covers: Route protection: redirect to `/login` without `refresh_token`, allow with token, public routes pass through. Locale detection: cookie > Accept-Language > default `en`, cookie persistence, header injection
- **`tests/store/config.test.ts`** — Tests: 5. What it covers: `load()`: fetches `/api/config`, idempotency (no double-fetch), keeps defaults on network error, keeps defaults on non-ok response, uses defaults for missing fields
- **`tests/lib/mappers.test.ts`** — Tests: 10. What it covers: `mapUser`: snake_case→camelCase mapping, fallback to `current` user for PATCH responses, explicit null avatar clearing, safe defaults when no current user, API data preferred over current
- **`tests/lib/target-languages.test.ts`** — Tests: 29. What it covers: target-language metadata, supported language invariants, `TARGET_LANGUAGE_CATALOG`, `getLanguageByCode` lookup, default target language, and CJK readiness capabilities/text classes
- **`tests/store/language.test.ts`** — Tests: 29. What it covers: Language store: fetchLanguages, switchLanguage, addLanguage, removeLanguage, active language tracking
- **`tests/lib/utils.test.ts`** — Tests: 10. What it covers: `cn()`: single/multiple/conditional classes, Tailwind conflict resolution (twMerge), array/object inputs, falsy values, empty/null handling
- **`tests/lib/logger.test.ts`** — Tests: 10. What it covers: `getLogger()`: debug/info/warn/error console calls with namespace, string/object/Error payload serialization, undefined/unserializable payload, `silentLogger` no-ops
- **`tests/hooks/useLogout.test.tsx`** — Tests: 1. What it covers: `useLogout()`: calls API logout endpoint, redirects to /login
- **`tests/store/theme.test.ts`** — Tests: 5. What it covers: Theme store: default `system`, `setTheme` transitions (light/dark/system), localStorage persistence (`fl-theme` key)
- **`tests/store/loading.test.ts`** — Tests: 9. What it covers: Loading store: `inc`/`dec`/`finishComplete` state machine, count never below 0, auto `complete` flag when count reaches 0, reset on next `inc`
- **`tests/store/freemium.test.ts`** — Tests: 2. What it covers: Freemium status cache reuse and forced refresh after lesson completion
- **`tests/components/LanguageSwitcher.test.tsx`** — Tests: 10. What it covers: LanguageSwitcher: rendering, dropdown open/close, CEFR badges, active checkmark, language switch, toast, router refresh
- **`tests/components/LanguageBubbles.test.tsx`** — Tests: 2. What it covers: LanguageBubbles renders one bubble per supported target language and positions bubbles from the supported-language count
- **`tests/components/TargetLanguageSelector.test.tsx`** — Tests: 10. What it covers: TargetLanguageSelector: grid rendering, catalog filtering by `availableCodes`, active/inactive states, onChange callback, flag images
- **`tests/components/VoiceRecorder.test.tsx`** — Tests: 24. What it covers: VoiceRecorder: idle/recording/transcribing/error states, getUserMedia mock, AudioContext lifecycle, STT API call, auto-stop, mic denied error, resampling
- **`tests/components/AudioPlayer.test.tsx`** — Tests: 36. What it covers: AudioPlayer: idle/loading/playing/error states, TTS API call, play/pause/stop, voice resolution (prop > localStorage > default), audio queue, unmount safety
- **`tests/components/ProfileSection.test.tsx`** — Tests: 48. What it covers: ProfileSection: form fields, save flow, avatar upload/remove (File/FileReader mock), password change (validation, mismatch), locale change with reload, API error states
- **`tests/components/BillingPaywall.test.tsx`** — Tests: 11. What it covers: Billing UI: Settings payment-recovery states via Customer Portal, canceled/incomplete/unsubscribed plan buttons, dashboard recovery banner, gated-page paywall recovery copy, and logged-in landing pricing direct Checkout
- **`tests/components/UnitCard.test.tsx`** — Tests: 41. What it covers: UnitCard: all 5 status states (completed/active/locked/level-test/default), progress bar, click interactions. UnitDrawer: grammar points, lesson list, Start/Continue/Review actions, completion states, escape/outside-click dismiss
- **`tests/store/progress.test.ts`** — Tests: 48. What it covers: Progress store: 10 initial state fields, setProgress/setTodayLessons/completeLesson/setCurrentUnit/setPlanDuration/updateUnitProgress/unlockLevelTest/setLevelTestResult, state transition isolation
- **`tests/lib/reviews.test.ts`** — Tests: 6. What it covers: Review API client helpers for my-review, create/update/delete, public, admin update, and delete calls
- **`tests/lib/review-prompt-triggers.test.ts`** — Tests: 7. What it covers: Review prompt trigger helpers for voice sessions and unit completion: 5-minute voice threshold, unit-completed gate, dismissal cooldown expiry, and maximum dismissal count
- **`tests/components/ReviewPrompt.test.tsx`** — Tests: 6. What it covers: Review prompt status check, rating validation, rating-only and commented submission, dismissal, duplicate-review suppression, status-check failure guard
- **`tests/components/LandingReviewsCarousel.test.tsx`** — Tests: 3. What it covers: Landing reviews carousel rendering with comments, rating-only fallback text, empty list behavior
- **`tests/app/billing-success.test.tsx`** — Tests: 3. What it covers: Billing success page: shows Premium-active copy only after `/me` confirms `active`/`trialing`, refreshes the session when no access token is in memory, and keeps pending-confirmation copy when the subscription is not yet synced.
- **`tests/app/admin-overview.test.tsx`** — Tests: 2. What it covers: Admin overview rendering and metrics
- **`tests/app/admin-query-params.test.tsx`** — Tests: 2. What it covers: Admin query param parsing and state handling
- **`tests/app/admin-reviews.test.tsx`** — Tests: 3. What it covers: Admin review moderation list, approval action, delete confirmation
- **`tests/i18n/admin-messages.test.ts`** — Tests: 1. What it covers: Admin message bundle integrity

**Total: 436 tests across 38 files. Frontend coverage is not configured/reported.**

### Running tests

```bash
cd frontend

# All tests (single run, for CI)
npm run test:run

# Watch mode (development)
npm run test

# Single test file
npx vitest run tests/lib/api.test.ts

# Single test by name
npx vitest run -t "attaches Bearer token"
```

---

## E2E tests (Playwright — pending)

### Planned critical flows

```
frontend/e2e/
├── auth.spec.ts            # Register → login → logout, protected routes
├── assessment.spec.ts      # Complete placement test, view results
├── study-plan.spec.ts      # Generate plan, view today's lessons
├── lesson.spec.ts          # Complete a full lesson with exercises
├── flashcards.spec.ts      # Review session, SM-2 progression
├── chat.spec.ts            # Send message, receive streaming response
└── admin.spec.ts           # Create user, generate invite, edit roles
```

### Design notes

- E2E tests run against a deployed instance (remote server), not a local Docker Compose stack
- The web server is started separately — Playwright config uses `reuseExistingServer: true` with a target URL
- Tests use `data-testid` attributes on key interactive elements (buttons, inputs, status indicators)
- Each spec is independent — tests within a spec are isolated by fresh browser contexts

---

## CI integration

CI runs on GitHub Actions, triggered on pushes and pull requests. The project is self-hosted; CI is for quality gates before Docker packaging.

### Workflow

- Backend tests — Steps: `pytest -v`; Threshold: >= 70% coverage
- Frontend lint — Steps: `npm run lint`; Threshold: Zero errors
- Frontend typecheck — Steps: `npx tsc --noEmit`; Threshold: Clean output
- Frontend tests — Steps: `npm run test:run`; Threshold: All 436 tests pass

**Note**: The backend test job uses SQLite (same as local tests), not PostgreSQL. No Docker services are required for the backend test job.

### Pre-push skill

The `run-tests` opencode skill is available for requested test, lint, typecheck, or targeted verification runs.

The `pre-push` opencode skill mirrors CI locally and also auto-formats before running checks. The canonical all-in-one command is `./scripts/pre-push.sh`; the canonical formatter-only command is `./scripts/format.sh`. Run order:

1. Auto-format (`./scripts/format.sh`: ruff --fix, black, eslint --fix, prettier --write from fixed backend/frontend directories)
2. Backend tests (pytest)
3. Frontend lint (npm run lint)
4. Frontend typecheck (tsc --noEmit)
5. Frontend tests (vitest)

---

## Testing rules

- **Mock LLM always** — never call Ollama, OpenAI, Anthropic, or DeepSeek in tests
- **Mock Redis always** — use in-memory dict mock, no Redis server needed
- **In-memory SQLite for backend tests** — fast, isolated, no Docker dependency
- **Test SM-2 algorithm in isolation** — pure function, no DB needed for the algorithm itself
- **Test streaming endpoints with chunk assertions** — verify SSE format and token ordering
- **Test error states explicitly** — 401, 403, 409, 422, 500 for every major endpoint
- **Each test file runs independently** — no shared state between files, fresh DB per test
- **Coverage thresholds enforced** — backend >= 70% (enforced); frontend coverage is not configured
- **No `docker compose` in test configs** — the development environment does not have Docker locally; E2E tests target a remote deployment
- **Data integrity tests validate cross-file references** — ensures curriculum, grammar, and backend vocabulary data files stay consistent across backend language packages, including Japanese, Korean, and Mainland Chinese.
- **Frontend: test critical logic + components** — test stores, utils, API client, middleware, and key components (VoiceRecorder, AudioPlayer, ProfileSection, UnitCard/UnitDrawer, LanguageSwitcher)
- **Frontend: mock `localStorage` and `next/navigation` globally** in `tests/setup.ts` — individual test files should not re-mock these
- **Frontend: tests live in `frontend/tests/`** — not co-located with source files, mirroring the backend `tests/` convention
- **Frontend: Component tests use vitest + @testing-library/react** — mock browser APIs (AudioContext, getUserMedia, FileReader) and external dependencies (next-intl, next/image, next/navigation)
- **Failure handling** — if any backend or frontend test fails after launching a suite, stop, report the failing test(s), and ask the user how to proceed before modifying production code or tests. After approval, re-run only the failing command unless the user requests the full suite.
