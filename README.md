# FreeLingo

![License](https://img.shields.io/badge/license-AGPL%20v3-blue?style=flat-square)
![Next.js](https://img.shields.io/badge/next.js-16-black?style=flat-square)
![Python](https://img.shields.io/badge/python-3.14-blue?style=flat-square)
![Self-hosted](https://img.shields.io/badge/self--hosted-yes-orange?style=flat-square)
![Hosted](https://img.shields.io/badge/hosted%20service-available-green?style=flat-square)

<p align="left">
  <img src="assets/logo.png" alt="FreeLingo logo" width="225" />
</p>

Open source AI language learning platform available in two modes: self-hosted (free, run it on your own
infrastructure) and as a hosted service operated by the FreeLingo team (paid subscription).
A language model evaluates your CEFR level, generates a personalized study plan, and guides you through
grammar, vocabulary, reading comprehension, writing lessons, AI-generated listening exercises, and AI-generated reading exercises — with optional voice features.

The study plan follows a CEFR-aligned curriculum (A1-C2) organized into units with
clear competencies and prerequisites. After a deterministic placement assessment,
FreeLingo creates a weekly roadmap based on your selected intensity (4, 8, 12, or
16 weeks), then unlocks lessons in sequence: grammar, vocabulary, reading, writing,
and review.

The platform combines structure and adaptation: lessons are generated within
curriculum boundaries, flashcards use SM-2 spaced repetition, and the AI tutor
provides contextual streaming feedback in English (with optional brief support in
the learner's native language). Listening exercises are generated on demand by the
LLM, synthesised to MP3 via TTS, and cached per CEFR level — the user listens,
answers 5 comprehension questions, and earns XP before the transcript is revealed.
Reading exercises follow the same caching model but without audio — the AI generates
a passage and 5 comprehension questions displayed side by side; the user reads and
answers immediately, earning XP per correct answer.
Progress tracking includes XP, streaks, skill scores, unit competencies, and an
end-of-level completion test.

## Hosted service

> **Don't want to manage your own server?**  
> FreeLingo is available as a fully managed hosted service at **[freelingo.app](https://freelingo.app)**.

Sign up, choose a subscription plan, and start learning immediately — no Docker, no GPU, no maintenance required.
The hosted instance is operated by the FreeLingo team and always runs the latest stable version.

Self-hosting remains free and open source under the AGPL-3.0 licence. The hosted service exists for users who prefer a managed experience.

## For businesses

Need FreeLingo for your team or organisation?

- **Private / on-premise deployment** — Deploy FreeLingo on your own infrastructure with full control over data and configuration. Ideal for schools, language academies, and companies with data-sovereignty requirements.
- **Dedicated managed instance** — Request a hosted instance operated exclusively for your organisation, without sharing resources with the public service.

[Get in touch](https://arturocarreterocalvo.com) to discuss your requirements.

If FreeLingo is useful to you or your organisation, consider [**sponsoring the project on GitHub**](https://github.com/sponsors/artcc) to support continued development and keep the self-hosted version free for everyone.

---

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
| 6     | Listening              | ✅ Complete         |
| 7     | Reading                | ✅ Complete         |

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
ollama pull gemma4:e4b

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

## Operational notes

- The recommended model for Ollama is `gemma4:e4b`. It can be changed in `.env`.
- The backend acts as a proxy for Ollama/TTS/STT calls so the frontend never talks directly to those services.
- The `LLM_PROVIDER` field controls the LLM provider: `ollama` (local, recommended), `openai`, `anthropic`, or `deepseek`.
- `TTS_PROVIDER` and `STT_PROVIDER` are independent: `local` (Kokoro / faster-whisper) or `openai` (OpenAI API).
- The target language is always **English** (`en-US` American English or `en-GB` British English). The variant is chosen on the `/onboarding` screen immediately after registration. The user's native language is asked during registration and is used only for flashcard translations and tutor feedback.

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

#### TTS voice options (Kokoro-82M)

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

#### STT model options (Whisper)

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

### Option B — OpenAI providers (no local GPU needed)

```env
TTS_PROVIDER=openai
STT_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

Uses the same `OPENAI_API_KEY` as the LLM if `LLM_PROVIDER=openai`. No extra services needed.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on reporting bugs, suggesting features, and submitting pull requests.

## License

Distributed under the [GNU Affero General Public License v3](LICENSE).

## Author

**Arturo Carretero Calvo** — [@artcc](https://github.com/artcc)