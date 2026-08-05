---
name: run-tests
description: Use when the user asks to run tests, ejecutar tests, lanzar tests, pytest, vitest, check types, typecheck, lint, or verify the codebase. Runs backend pytest, frontend vitest, frontend tsc/eslint/prettier, and backend ruff/black.
---

# Run Tests — FreeLingo

## Backend tests (pytest)

The project does NOT use Docker for local tests. Tests are fully isolated:

- SQLite in-memory (no PostgreSQL needed)
- Redis mocked in-memory (no Redis server needed)
- LLM always mocked (no external API calls)

### Prerequisites

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt
```

`.venv/` is already in `.gitignore`. Create it once, activate before each session.

### Run

```bash
source .venv/bin/activate && cd backend && pytest -v
```

Use a command timeout of at least 600 seconds for the full backend suite; the current run takes about 4 minutes and can exceed shorter 120-second tool defaults.

Options:

- Single file: `source .venv/bin/activate && cd backend && pytest tests/test_auth.py -v`
- Single test: `source .venv/bin/activate && cd backend && pytest tests/test_flashcards.py::test_quality_3_basic_progression -v`
- Coverage HTML: `source .venv/bin/activate && cd backend && pytest --cov-report=html`

## Frontend tests (vitest)

```bash
cd frontend && npm run test:run
```

440 tests covering stores, components, hooks, app pages, lib, i18n, middleware, review UI, review prompt triggers, billing UI, freemium state, memory management, SSE parsing, chat stream resets, toasts, and API interceptor. Frontend coverage is not configured/reported:

- `lib/api.ts` — auth interceptor, 401 refresh, retry
- `store/auth.ts` — isSubscribed(), logout
- `lib/audio.ts` — float32ToWav WAV encoding
- `lib/conversation-ws.ts` — WebSocket URL builder
- `middleware.ts` — route protection, locale detection
- `store/config.ts` — config loading, idempotency
- `store/language.ts` — language CRUD, switching
- `store/progress.ts` — XP, streak, unit progress, level test
- `lib/mappers.ts` — mapUser transformation
- `lib/target-languages.ts` — language code resolution
- `data/curriculum.ts` — curriculum data integrity
- `components/LanguageSwitcher.tsx` — sidebar dropdown
- `components/TargetLanguageSelector.tsx` — language grid
- `components/VoiceRecorder.tsx` — STT recorder states
- `components/AudioPlayer.tsx` — TTS player states
- `components/ProfileSection.tsx` — profile CRUD, avatar
- `components/UnitCard.tsx` + `UnitDrawer.tsx` — plan units
- `components/reviews/*` — review prompt and landing carousel
- `app/(app)/admin/reviews/page.tsx` — review moderation UI
- `lib/reviews.ts` — review API client
- `lib/review-prompt-triggers.ts` — voice-session and unit-completion review prompt triggers

Options:

- Watch mode: `npm run test`
- Single file: `npx vitest run tests/lib/api.test.ts`

## Frontend checks

```bash
cd frontend && npx tsc --noEmit                 # TypeScript type checking
cd frontend && npm run lint                     # Lint
cd frontend && npx prettier --check src/        # Format check
```

## Backend lint

```bash
source .venv/bin/activate && cd backend && ruff check . && black --check .
```

## If a suite fails

- If any backend or frontend test fails after launching a suite, STOP immediately, report the failing test(s), and ask the user how to proceed.
- Do not modify production code or tests to make the suite pass without explicit user approval.
- If lint, typecheck, or format checks fail without test failures, report the error and ask before making non-formatting code changes.
- After the user approves a fix, re-run only the failing command unless they request the full suite.

## Canonical format script

```bash
./scripts/format.sh
```

Runs the same backend/frontend style tools from fixed project paths, so results do not depend on the current working directory.
