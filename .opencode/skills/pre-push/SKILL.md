---
name: pre-push
description: Use when the user asks to check before pushing, pre-push, verificar antes de pushear, run all checks, or quiere validar que todo pasa antes de hacer push. Auto-formats code then runs the same checks as CI (pytest, eslint, tsc).
---

# Pre-Push Checks — FreeLingo

Auto-formats code, then validates everything CI enforces on `develop`. Mirrors `.github/workflows/pr-develop-checks.yml`.

## Order

Run in this sequence, stopping on first failure:

### 0. Auto-format (always run first)

```bash
./scripts/format.sh
```

Fixes what can be fixed automatically: Python lint + format, JS/TS lint + format.

### 1. Backend tests

```bash
source .venv/bin/activate && cd backend && pytest -v
```

945 backend tests, >= 70% backend coverage required. Current backend coverage is 84.42% last measured. SQLite in-memory, no Docker needed.

Use a command timeout of at least 600 seconds for the full backend suite; the current run takes about 4 minutes and can exceed shorter 120-second tool defaults.

### 2. Frontend lint + typecheck + tests

```bash
cd frontend && npm run lint && npx tsc --noEmit && npm run test:run
```

## What each step does

- Step 0: `./scripts/format.sh` runs the canonical formatter from the repository root.
- Step 0: backend formatting uses `ruff --fix` and `black` from `backend/pyproject.toml`.
- Step 0: frontend formatting uses `eslint --fix` plus `prettier --write` from `frontend/.prettierrc` and `frontend/eslint.config.mjs`.
- Step 1: `pytest` runs 945 backend tests with SQLite in-memory.
- Step 2: `eslint` verifies no remaining JS/TS lint errors.
- Step 2: `tsc --noEmit` runs TypeScript type checking.
- Step 2: `vitest` runs 436 frontend tests; frontend coverage is not configured.

**Note:** CI does not run ruff/black checks — only pytest, eslint, tsc, and vitest. Backend lint (ruff/black) is kept in step 0 as auto-format only.

The canonical one-command local validation is `./scripts/pre-push.sh`. The steps above are kept expanded so failures can be rerun independently.

## Requirements

- `.venv/` at project root (create once: `python3 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt`)
- `frontend/node_modules` exists (install once: `cd frontend && npm install`)

## If something fails

1. If step 0 fails, report the formatter/lint error and ask the user how to proceed before changing code manually.
2. If any backend or frontend test fails after launching a suite, STOP immediately, report the failing test(s), and ask the user how to proceed. Do not modify production code or tests to make the suite pass without explicit approval.
3. If lint or typecheck fails without test failures, report the error and ask before making non-formatting code changes.
4. After the user approves a fix, re-run **only the failing step** unless they ask for the full suite again.
5. Once all pass, the branch is safe to push.
