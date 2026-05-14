# FreeLingo

![License](https://img.shields.io/badge/license-AGPL%20v3-blue?style=flat-square)
![Next.js](https://img.shields.io/badge/next.js-16-black?style=flat-square)
![Python](https://img.shields.io/badge/python-3.14-blue?style=flat-square)
![Self-hosted](https://img.shields.io/badge/self--hosted-yes-orange?style=flat-square)
![Hosted](https://img.shields.io/badge/hosted%20service-available-green?style=flat-square)

<p align="left">
  <img src="assets/logo.png" alt="FreeLingo logo" width="200" />
</p>

Open source AI language learning platform available in two modes: self-hosted (free, run it on your own
infrastructure) and as a hosted service operated by the FreeLingo team (paid subscription).
A language model evaluates your CEFR level, generates a personalized study plan, and guides you through
grammar, vocabulary, reading comprehension, and writing lessons — with optional voice features.

The study plan follows a CEFR-aligned curriculum (A1-C2) organized into units with
clear competencies and prerequisites. After a deterministic placement assessment,
FreeLingo creates a weekly roadmap based on your selected intensity (4, 8, 12, or
16 weeks), then unlocks lessons in sequence: grammar, vocabulary, reading, writing,
and review.

The platform combines structure and adaptation: lessons are generated within
curriculum boundaries, flashcards use SM-2 spaced repetition, and the AI tutor
provides contextual streaming feedback in English (with optional brief support in
the learner's native language). Progress tracking includes XP, streaks, skill
scores, unit competencies, and an end-of-level completion test.

## Architecture

Monorepo: `backend/` (Python FastAPI) + `frontend/` (Next.js 16 App Router)
deployed via Docker Compose with PostgreSQL 16 and Redis 7.
The backend proxies all external services (Ollama, Kokoro, Whisper) —
the frontend never calls them directly.

## Repository

```
freelingo/
├── assets/             # Logos and static assets
├── backend/            # FastAPI (Python)
├── docs/               # GitHub Pages landing site
├── frontend/           # Next.js (React)
├── messages/           # i18n translation files (de, en, es, fr, it, nl, pl, pt, ro, ru)
├── specs/              # Specification files
├── AGENTS.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
└── docker-compose.yml
```

## Stack

| Layer      | Technology                                               |
|------------|----------------------------------------------------------|
| Frontend   | Next.js 16+, shadcn/ui, Tailwind CSS, Zustand, next-intl |
| Backend    | FastAPI, SQLAlchemy async, Alembic, Pydantic v2          |
| Database   | PostgreSQL 16                                            |
| Cache      | Redis 7                                                  |
| LLM        | Ollama (local) · OpenAI · Anthropic · DeepSeek           |
| TTS        | Kokoro-FastAPI (local) · OpenAI TTS API                  |
| STT        | faster-whisper (local) · OpenAI Whisper API              |
| Auth       | JWT (access + refresh), multi-user, roles (admin/user).  |
| Deploy     | Docker Compose                                           |

## Phases

| Phase | Name                   | Status              |
|-------|------------------------|---------------------|
| 1     | Learning platform      | ✅ Complete         |
| 1+    | Learning Resources Hub | ✅ Complete         |
| 2     | Local TTS + STT        | ✅ Complete         |
| 3     | Real-time conversation | ✅ Complete         |
| 4     | Multi-language support | ✅ Complete         |
| 5     | Stripe subscriptions   | ✅ Complete         |
| 6     | Listening              | 🔄 In progress      |

## Hosted service

> **Don't want to manage your own server?**  
> FreeLingo is available as a fully managed hosted service at **[freelingo.app](https://freelingo.app)**.

Sign up, choose a subscription plan, and start learning immediately — no Docker, no GPU, no maintenance required.
The hosted instance is operated by the FreeLingo team and always runs the latest stable version.

Self-hosting remains free and open source under the AGPL-3.0 licence. The hosted service exists for users who prefer a managed experience.

---

## Quick start

### Option A — Git clone + Docker Compose

**Requirements:** Docker, Docker Compose, Git, and [Ollama](https://ollama.com) running on the host.

```bash
# 1. Clone the repository
git clone https://github.com/artcc/freelingo.git
cd freelingo

# 2. Configure environment
cp .env.example .env
# Edit .env: set OLLAMA_BASE_URL, choose your model, and review other settings

# 3. Pull the recommended model (run on the host, not inside Docker)
ollama pull gemma3:12b

# 4. Start all services (migrations run automatically on first start)
docker compose up -d
```

Access at `http://localhost:3000` (or `http://<server-ip>:3000`).  
The first registered user becomes admin automatically.

---

### Option B — Portainer (Stack)

1. Open Portainer → **Stacks** → **Add stack**.
2. Choose **Repository** and enter the repo URL, or paste the contents of `docker-compose.yml` directly into the Web editor.
3. Scroll down to **Environment variables** and add the variables from `.env.example` (at minimum: `SECRET_KEY`, `OLLAMA_BASE_URL`, `POSTGRES_PASSWORD`).
4. Click **Deploy the stack**.
5. Access the app at `http://<server-ip>:3000`. Database migrations run automatically when the backend starts.

> **Tip:** If Ollama runs on the same host as Portainer, set `OLLAMA_BASE_URL=http://host.docker.internal:11434`. On Linux you may need to add the `extra_hosts` entry in the compose file (already included by default).

## Internal documentation

- [api-endpoints.instructions.md](specs/api-endpoints.instructions.md) — All REST endpoints and WebSocket — paths, methods, rate limits, descriptions
- [architecture.instructions.md](specs/architecture.instructions.md) — DB models, service layer, LLM adapter, auth design, data flow, code standards, test config
- [CHANGELOG.md](CHANGELOG.md) — Project changelog
- [changelog.instructions.md](specs/changelog.instructions.md) — Changelog format, entry style, and update rules
- [docker.instructions.md](specs/docker.instructions.md) — Docker Compose by phase, `.env.example`, DB migrations, operational notes
- [llm-error-handling.instructions.md](specs/llm-error-handling.instructions.md) — LLM failures: malformed JSON, timeouts, retries, context overflow
- [phase-1-platform.instructions.md](specs/phase-1-platform.instructions.md) — Phase 1: scaffolding through frontend, prompts, SM-2, SSE chat
- [phase-1-plus.instructions.md](specs/phase-1-plus.instructions.md) — Phase 1+: Learning Resources Hub — Grammar Reference, Vocabulary Hub, Phrasebook, Skills Tracker, Level Completion Test
- [phase-2-tts-stt.instructions.md](specs/phase-2-tts-stt.instructions.md) — Phase 2: Kokoro TTS, faster-whisper STT, pronunciation exercises
- [phase-3-conversation.instructions.md](specs/phase-3-conversation.instructions.md) — Phase 3: WebSocket voice pipeline, VAD, barge-in
- [phase-4-target-language.instructions.md](specs/phase-4-target-language.instructions.md) — Phase 4: target_language (BCP-47), onboarding flow, auto-login on register
- [phase-5-stripe-subscriptions.instructions.md](specs/phase-5-stripe-subscriptions.instructions.md) — Phase 5: Stripe subscriptions, paywall, Customer Portal, `STRIPE_ENABLED` toggle
- [phase-6-listening.instructions.md](specs/phase-6-listening.instructions.md) — Phase 6: Listening section
- [rate-limiting.instructions.md](specs/rate-limiting.instructions.md) — slowapi-based rate limits per-endpoint, self-hosted defaults
- [readme.instructions.md](specs/readme.instructions.md) — README structure, badges, and update guidelines
- [roadmap.instructions.md](specs/roadmap.instructions.md) — Development roadmap with milestones and completion criteria
- [testing.instructions.md](specs/testing.instructions.md) — Testing strategy: pytest, Vitest, Playwright, mocks, CI
- [version.md](specs/version.md) — Canonical project version and sync rules
- [whats-new.instructions.md](specs/whats-new.instructions.md) — What's New modal: version-aware changelog overlay, localStorage trigger, priority with OnboardingTour

## Operational notes

- The recommended model for Ollama is `gemma3:12b`. It can be changed in `.env`.
- The backend acts as a proxy for Ollama/TTS/STT calls so the frontend never talks directly to those services.
- The `LLM_PROVIDER` field controls the LLM provider: `ollama` (local, recommended), `openai`, `anthropic`, or `deepseek`.
- `TTS_PROVIDER` and `STT_PROVIDER` are independent: `local` (Kokoro / faster-whisper) or `openai` (OpenAI API).
- The target language is always **English** (`en-US` American English or `en-GB` British English). The variant is chosen on the `/onboarding` screen immediately after registration. The user's native language is asked during registration and is used only for flashcard translations and tutor feedback.

### CI/CD image channels

Docker images are published to two separate GHCR channels:

- Stable (production): pushes to `main`
  - `ghcr.io/artcc/freelingo-backend:latest`
  - `ghcr.io/artcc/freelingo-frontend:latest`
- Develop (pre-production tests): pushes to `develop`
  - `ghcr.io/artcc/freelingo-backend-develop:latest`
  - `ghcr.io/artcc/freelingo-frontend-develop:latest`

Use the `-develop` images for local or staging validation without touching production deployments.

## Reverse proxy requirement (real-time conversation)

The real-time voice conversation feature uses a WebSocket connection (`/ws/conversation`). Next.js does not proxy WebSocket upgrades natively, so **a reverse proxy is required in any production deployment** to route `/ws/*` traffic to the backend container.

This is also a hard browser requirement: `getUserMedia` (microphone access) only works in a [secure context](https://developer.mozilla.org/en-US/docs/Web/Security/Secure_Contexts) — HTTPS or localhost. A reverse proxy terminating TLS is therefore mandatory for the conversation feature to work at all in production.

The WebSocket URL is derived automatically from `window.location`, so no extra configuration is needed on the frontend side — just ensure your reverse proxy forwards `/ws/*` to `backend:8000`.

## Enabling TTS & STT

TTS and STT each support two providers, selected independently via `.env`.

### Provider options

| Variable | Values | Notes |
|----------|--------|-------|
| `TTS_PROVIDER` | `local` · `openai` | `local` uses Kokoro-FastAPI; `openai` uses OpenAI TTS API |
| `STT_PROVIDER` | `local` · `openai` | `local` uses faster-whisper; `openai` uses OpenAI Whisper API |
| `OPENAI_API_KEY` | string | Required for `openai` provider on either service |

When using `openai` providers, the `kokoro` and `whisper` Docker services can be removed from the stack — no local GPU required.

### Option A — Local providers (self-hosted, GPU recommended)

The `kokoro` and `whisper` services in `docker-compose.yml` are pre-configured for NVIDIA GPUs.

```env
TTS_PROVIDER=local
STT_PROVIDER=local
```

The Kokoro image (`ghcr.io/artcc/kokoro-fastapi-gpu`) ships with PyTorch 2.7+ (cu128), supporting all NVIDIA architectures including Blackwell (RTX 5000 series).

For CPU-only hosts, replace the image tags and remove the `deploy` block in `docker-compose.yml`:

```yaml
kokoro:
  image: ghcr.io/remsky/kokoro-fastapi-cpu:latest
  restart: unless-stopped

whisper:
  image: onerahmet/openai-whisper-asr-webservice:latest
  restart: unless-stopped
  environment:
    - ASR_MODEL=base
    - ASR_ENGINE=faster_whisper
```

> Use `ASR_MODEL=base` or `small` on CPU. Larger models are very slow without a GPU.

### Option B — OpenAI providers (no local GPU needed)

```env
TTS_PROVIDER=openai
STT_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

Uses the same `OPENAI_API_KEY` as the LLM if `LLM_PROVIDER=openai`. No extra services needed.

### TTS voice options (Kokoro-82M)

All voices are for English. Grades reflect training data quality and quantity.

| Voice | Gender | Accent | Grade |
|-------|--------|--------|-------|
| `af_heart` | F | American | A ⭐ |
| `af_bella` | F | American | A- |
| `af_nicole` | F | American | B- |
| `am_fenrir` | M | American | C+ |
| `am_michael` | M | American | C+ |
| `am_puck` | M | American | C+ |
| `bf_emma` | F | British | B- |
| `bm_george` | M | British | C |

Set with `TTS_VOICE=<voice>` in `.env`. Default: `af_heart`.

### STT model options (Whisper)

| Model | VRAM | Speed vs large | Notes |
|-------|------|----------------|-------|
| `tiny.en` | ~1 GB | ~10x | Very low accuracy |
| `small.en` | ~2 GB | ~4x | OK for CPU |
| `medium` | ~5 GB | ~2x | Good balance |
| `large-v3-turbo` | ~6 GB | ~8x | **Recommended** — best speed/accuracy ratio |
| `large-v3` | ~10 GB | 1x | Maximum accuracy |

Set with `STT_MODEL=<model>` in `.env`. Default: `large-v3-turbo`.

| Engine | Notes |
|--------|-------|
| `faster_whisper` | **Recommended** — 4× faster than openai_whisper, lower VRAM via CTranslate2 |
| `openai_whisper` | Original PyTorch implementation |
| `whisperx` | Adds speaker diarization; requires HuggingFace token |

Set with `STT_ENGINE=<engine>` in `.env`. Default: `faster_whisper`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on reporting bugs, suggesting features, and submitting pull requests.

## License

Distributed under the [GNU Affero General Public License v3](LICENSE).

## Author

**Arturo Carretero Calvo** — [@artcc](https://github.com/artcc)