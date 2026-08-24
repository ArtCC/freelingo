# Contributing to FreeLingo

Thank you for your interest in contributing. Bug reports, feature suggestions, documentation improvements, and pull requests are welcome. Please read these guidelines before contributing.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating you agree to abide by its terms. Report unacceptable behavior privately to the repository owner using one of the contact methods available on their [GitHub profile](https://github.com/artcc). Do not report Code of Conduct violations through public issues.

## Development setup

Follow [DEVELOPMENT.md](DEVELOPMENT.md) to prepare and run the local development environment before making code changes. Run the validation commands below from the repository root.

## How to contribute

### Reporting bugs

Open an issue with:
- A clear title describing the problem
- Steps to reproduce
- Expected vs actual behaviour
- FreeLingo version / commit hash

When permissions allow, apply the most appropriate label when opening or triaging an issue. If work on the issue has an associated branch, link that branch in the issue's GitHub Development section so the implementation can be tracked from the issue.

### Suggesting features

Open an issue describing the use case, not just the feature. The repository owner will review and label it. Check the [roadmap](specs/roadmap.instructions.md) first — the feature may already be planned.

### Branch workflow

FreeLingo follows the Git Flow branching model:

- **`develop`** — integration branch. All PRs target this branch. CI runs tests and lint on every PR.
- **`main`** — production branch. Merges from `develop` trigger Docker image publishing and releases.
- **`feature/<short-description>`** — feature, bug-fix, and documentation branches created from `develop` and merged back through a PR.
- **`release/<version>`** — maintainer-managed release preparation branches created from `develop` and merged into both `main` and `develop`.
- **`hotfix/<short-description>`** — maintainer-managed urgent production fixes created from `main` and merged into both `main` and `develop`.

Contributors must not open PRs directly against `main`; create branches from `develop` and target `develop` instead.

### Submitting a pull request

1. Fork the repository and create a branch from `develop`:
   ```bash
   git checkout -b feature/short-description
   ```
2. Follow the coding standards below.
3. Add or update tests. Coverage must remain ≥ 70 %.
4. Run validation before pushing:
   ```bash
   # Auto-format backend and frontend
   ./scripts/format.sh

   # Backend tests
   (source .venv/bin/activate && cd backend && pytest -v)

   # Frontend lint, typecheck, and tests
   (cd frontend && npm run lint && npx tsc --noEmit && npm run test:run)
   ```
5. Open a pull request against `develop`. CI will run backend tests and frontend lint/typecheck/tests automatically.

## Coding standards

| Layer | Standard |
|-------|----------|
| Python | ruff (`E, W, F, I, UP, B, S, ANN`, ANN101 ignored), Black (line-length 100) |
| TypeScript | No semicolons, single quotes, 2-space indent, trailing commas (es5), `prettier-plugin-tailwindcss` |

S and ANN rules are disabled in `tests/`.

The canonical formatter entry point is `./scripts/format.sh`. It uses `backend/pyproject.toml`, `frontend/.prettierrc`, and `frontend/eslint.config.mjs`; do not run equivalent long commands from arbitrary directories.

## Running tests locally

The backend test suite uses SQLite in-memory and mocked Redis — no Docker services required.

```bash
# Backend
(source .venv/bin/activate && cd backend && pytest -v)

# Run a single backend test file
(source .venv/bin/activate && cd backend && pytest tests/test_auth.py -v)
```

Frontend tests run locally and in CI:

```bash
(cd frontend && npm run lint && npx tsc --noEmit && npm run test:run)
```

> **Note:** `package-lock.json` must be generated with **npm 11**. If you update frontend dependencies, make sure you are using npm 11 locally before committing the lockfile.

## DB migrations

If you change a SQLAlchemy model, generate a migration. These commands must be run on the remote server where Docker is available:

```bash
docker compose exec backend alembic revision --autogenerate -m "short description"
docker compose exec backend alembic upgrade head
```

## Contributor License Agreement

By opening a pull request you accept the [Contributor License Agreement](CONTRIBUTOR_LICENSE_AGREEMENT.md). You retain any rights you hold in your contribution while granting the repository owner permission to use, modify, distribute, and relicense it. Contributing does not grant ownership, control, or decision-making rights over FreeLingo.
