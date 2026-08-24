---
description: Development roadmap and completion status for FreeLingo.
applyTo: "backend/**, frontend/**, docker-compose.yml"
---

# Roadmap — FreeLingo

This document records what was built and the completion criteria met.

**Legend**: ⬜ Pending · 🔄 In progress · ✅ Done

---

## Phase 1 — Learning Platform

✅ Status: Complete (v1.0.0 – v1.1.1)

- 1 — Milestone: Scaffolding — project structure, Docker Compose, CI; Status: ✅
- 2 — Milestone: Backend core — async DB, JWT+Redis auth, LLM adapter; Status: ✅
- 3 — Milestone: Assessment — 3-step onboarding (BeginnerGate → adaptive quiz → duration/goals); Status: ✅
- 4 — Milestone: Study plan — Deterministic curriculum-driven plan using `curriculum.py`; Status: ✅
- 5 — Milestone: Lessons — LLM-generated content within CEFR constraints, free-write evaluation; Status: ✅
- 6 — Milestone: Flashcards — SM-2 spaced repetition with LLM generation and native-language translations; Status: ✅
- 7 — Milestone: Chat — AI tutor with SSE streaming, progress-aware system prompt; Status: ✅
- 8 — Milestone: Frontend — All screens connected: login, assessment, plan, lessons, flashcards, chat, settings; Status: ✅

**Completion criteria:**

- [x] `docker compose up -d` starts all services without errors
- [x] First registration creates admin user automatically
- [x] Login returns access_token + refresh_token in httpOnly cookie
- [x] Auto-refresh works without user noticing token expiration
- [x] Logout invalidates refresh token in Redis
- [x] `ALLOW_REGISTRATION=false` blocks public signups
- [x] Single-use invites work (48h expiry)
- [x] Admin panel only accessible to `role=admin`
- [x] Assessment completed and CEFR level returned
- [x] Study plan generated correctly
- [x] Lesson completed with exercises and feedback
- [x] SM-2 flashcards reviewed and updated correctly
- [x] Streaming chat works without UI glitches
- [x] Progress persists across sessions (PostgreSQL)

---

## Phase 1+ — Learning Resources Hub

✅ Status: Complete (v1.1.0)

> Delivered alongside Phase 1. All data is static TypeScript; no new infrastructure required.

- 1 — Milestone: Grammar Reference — data layer + `/grammar` index + `/grammar/[slug]` detail pages; Status: ✅
- 2 — Milestone: Vocabulary Hub — `vocabulary.ts` + `/vocabulary` + set detail pages with flashcard integration; Status: ✅
- 3 — Milestone: Phrasebook — `phrasebook.ts` + `/phrasebook` with level and register filters; Status: ✅
- 4 — Milestone: Skills Tracker — `/progress` competency checklist + vocabulary stats; Status: ✅
- 5 — Milestone: Level Completion Test — `/assessment/level-test` + result + recommendation (advance/extend/repeat); Status: ✅
- 6 — Milestone: Nav + routing — RESOURCES nav group, curriculum-driven `/plan` roadmap; Status: ✅

**Completion criteria:**

- [x] `/grammar` renders all topics with no API calls
- [x] `/grammar/[slug]` renders full detail; unknown slugs return 404
- [x] `/vocabulary` lists all sets grouped by level with flashcard-progress badges
- [x] `/vocabulary/[setId]` shows words + "Add to flashcards" button
- [x] `/phrasebook` lists situations with level and register filters
- [x] `/progress` shows per-unit competency checklist with scores
- [x] `/progress` shows vocabulary progress bars per set
- [x] Level test available only after all units in a level are completed
- [x] Level test recommendation: advance >= 75% / extend 55-74% / repeat < 55%
- [x] RESOURCES nav group works on desktop and mobile
- [x] `/plan` visual roadmap linked from dashboard
- [x] No regressions in Phase 1

---

## Phase 2 — Local TTS + STT

✅ Status: Complete (v1.1.0 – v1.2.0)

- 1 — Milestone: Kokoro TTS service + `/api/tts` proxy; Status: ✅
- 2 — Milestone: Whisper STT service + `/api/stt` proxy (`POST /asr`, not OpenAI API); Status: ✅
- 3 — Milestone: Audio playback (`AudioPlayer` component) and voice recording (`VoiceRecorder`); Status: ✅
- 4 — Milestone: Pronunciation evaluation via STT transcription; Status: ✅
- 5 — Milestone: Pronunciation exercise type in lessons; Status: ✅
- 6 — Milestone: Speaking mode in flashcards; Status: ✅

**Completion criteria:**

- [x] Kokoro returns audio correctly from backend
- [x] Whisper transcribes browser-recorded audio correctly
- [x] Audio button functional in flashcards and lessons
- [x] Pronunciation recording and evaluation operational
- [x] GPU used by both services (CPU-only hosts supported via compose changes)
- [x] STT endpoint uses `POST /asr?output=json&language=<iso>&task=transcribe` for local Whisper, with the ISO code derived from the user-owned study plan (not the OpenAI API path)
- [x] Default STT model upgraded to `large-v3-turbo`
- [x] `STT_ENGINE` variable added for engine selection
- [x] No regressions in Phase 1 features

---

## Phase 3 — Real-Time Voice Conversation

✅ Status: Complete (v1.2.0 – v1.2.1)

- 1 — Milestone: WebSocket `/ws/conversation` endpoint with TTS+STT guard; Status: ✅
- 2 — Milestone: Conversation pipeline (STT → LLM streaming → TTS chunking); Status: ✅
- 3 — Milestone: Sentence boundary detection for TTS flushing; Status: ✅
- 4 — Milestone: Frontend `ConversationMode` with VAD (`@ricky0123/vad-react`); Status: ✅
- 5 — Milestone: Gapless `AudioQueue` playback via Web Audio API; Status: ✅
- 6 — Milestone: Barge-in / interrupt support; Status: ✅
- 7 — Milestone: Configurable session timeouts (max duration + inactivity, 60s warnings); Status: ✅
- 8 — Milestone: Structured logging across the pipeline; Status: ✅

**Completion criteria:**

- [x] WebSocket accepts connections and full pipeline works
- [x] Barge-in functional: user can interrupt AI by speaking
- [x] Gapless audio without gaps between sentences
- [x] Automatic VAD operational with onnxruntime-web threaded WASM (COOP+COEP headers)
- [x] Conversation history maintained correctly during session
- [x] Session timeout watchers (max duration + inactivity) with 60s warning
- [x] Both configured speech services must be available for the WebSocket endpoint
- [x] `LOG_LEVEL` controls pipeline logging verbosity
- [x] No regressions in Phase 1 and 2

---

## Phase 4 — Multi-Language Support

✅ Status: Complete (v1.3.0)

> Expands the platform from English-only to a multi-target-language architecture.
> Initial launch supports American English (`en-US`) and British English (`en-GB`),
> with the data model and service layer ready for additional languages.

- 1 — Milestone: DB migration — `english_variant` → `target_language` (BCP-47); backfill existing rows to `en-US`; Status: ✅
- 2 — Milestone: Backend model + schema — `User.target_language`, `StudyPlan.target_language`, `SUPPORTED_TARGET_LANGUAGES`, `RegisterResponse`; Status: ✅
- 3 — Milestone: Auto-login on register — `POST /register` returns `access_token` + sets refresh cookie; frontend redirects to `/onboarding`; Status: ✅
- 4 — Milestone: Service layer — `language_helpers.py`; `target_language` propagated to lesson generator, flashcards, chat, conversation pipeline, STT, assessment; Status: ✅
- 5 — Milestone: Frontend — `TargetLanguageSelector` component, `/onboarding` page, auth store updated, settings cleaned up; Status: ✅
- 6 — Milestone: i18n — `targetLanguages` + `onboarding` namespaces added to all 6 locales; old `englishVariant` keys removed; Status: ✅
- 7 — Milestone: Additional target languages beyond English variants; Status: ⬜

**Completion criteria:**

- [x] Migration runs cleanly; `downgrade` restores previous schema
- [x] `POST /register` returns `access_token` and sets `refresh_token` cookie
- [x] New user is redirected to `/onboarding` and selects a target language before accessing the app
- [x] All services (LLM prompts, flashcard generation, STT) receive and respect `target_language`
- [x] `target_language` stored on `study_plans` rows
- [x] `PATCH /me` with an unsupported `target_language` returns 422
- [x] `TargetLanguageSelector` renders flags and correct translated labels
- [x] All 6 locales contain `targetLanguages` and `onboarding` namespaces
- [x] `tsc --noEmit` and `python3 -m compileall` pass clean
- [x] No regressions in Phases 1–3

---

## Phase 5 — Stripe Subscriptions & Paywall

✅ Status: **Complete (v1.4.0)**

> Optional subscription layer backed by Stripe. Fully gated by `STRIPE_ENABLED` env var — self-hosted deployments are unaffected when set to `false`.

- 1 — Milestone: Config + env vars + `docker-compose.yml` + `requirements.txt`; Status: ✅
- 2 — Milestone: User model fields (`stripe_customer_id`, `stripe_subscription_id`, `subscription_status`, `subscription_ends_at`); Status: ✅
- 3 — Milestone: Alembic migration `0016_stripe_subscription`; Status: ✅
- 4 — Milestone: `subscription_service.py` — `is_subscribed()` + `apply_subscription_quotas()`; Status: ✅
- 5 — Milestone: `require_subscription` FastAPI dependency; Status: ✅
- 6 — Milestone: `GET /api/config` public endpoint; Status: ✅
- 7 — Milestone: `POST /api/billing/checkout` — Stripe Checkout Session; Status: ✅
- 8 — Milestone: `POST /api/billing/portal` — Stripe Customer Portal; Status: ✅
- 9 — Milestone: `POST /api/billing/webhook` — 4 Stripe events; Status: ✅
- 10 — Milestone: Apply `require_subscription` to all AI endpoints; Status: ✅
- 11 — Milestone: Admin schema: expose + override subscription status; Status: ✅
- 12 — Milestone: Frontend config store (`stripeEnabled`); Status: ✅
- 13 — Milestone: `PaywallBanner` component; Status: ✅
- 14 — Milestone: Paywall applied to 6 protected pages; Status: ✅
- 15 — Milestone: Billing section in settings/profile; Status: ✅
- 16 — Milestone: Pricing section in landing page; Status: ✅
- 17 — Milestone: `/billing/success` and `/billing/canceled` pages; Status: ✅
- 18 — Milestone: i18n — `billing` namespace in 10 locales; Status: ✅
- 19 — Milestone: Tests — `test_billing.py` with Stripe SDK mocks; Status: ✅

**Plans:**

- Monthly: x €/month (temporal) · 7-day trial (card required)
- Yearly: x €/year (temporal, 2 months free) · 7-day trial (card required)

**Completion criteria:**

- [x] `STRIPE_ENABLED=false` → no paywall, no billing UI, all endpoints accessible
- [x] `STRIPE_ENABLED=true` → unsubscribed users see `PaywallBanner` on all AI pages
- [x] Stripe Checkout Session created correctly for monthly and yearly plans
- [x] Webhook verifies Stripe signature; rejects invalid signatures with 400
- [x] All 4 webhook events update `subscription_status` correctly
- [x] Webhook lifecycle events ignore stale Stripe subscription IDs once the current subscription is known
- [x] `require_subscription` returns 402 for unsubscribed users when enabled
- [x] Admin can manually override `subscription_status`
- [x] Pricing section visible on landing only when `STRIPE_ENABLED=true`
- [x] `tsc --noEmit` and `python3 -m compileall` pass clean
- [x] No regressions in Phases 1–4

---

## Phase 6 — Listening

✅ Status: Complete

> LLM-generated audio comprehension exercises. Text and MP3 are generated on demand and
> cached on disk so subsequent users at the same CEFR level share the same content at no
> extra cost. The user listens, answers 5 multiple-choice questions, then the transcript
> is revealed together with score and XP.

- 1 — Milestone: DB models — `listening_exercises` + `listening_attempts` + migration `0018`; Status: ✅
- 2 — Milestone: Backend service — LLM generation, TTS synthesis, MP3 storage, Redis generation lock; Status: ✅
- 3 — Milestone: Backend router — 5 endpoints: next, generate, audio, attempt, history; Status: ✅
- 4 — Milestone: Frontend page — 6 UI states: loading → generating → idle → exercise → results → history; Status: ✅
- 5 — Milestone: Frontend components — ExerciseAudioPlayer (blob URL via apiFetch), question cards, result reveal; Status: ✅
- 6 — Milestone: Audio served directly via `GET /api/listening/audio/{id}` (FileResponse, auth header via apiFetch); Status: ✅
- 7 — Milestone: Sidebar nav entry (between Conversation and Assessment); Status: ✅
- 8 — Milestone: i18n — `nav.listening` + `listening.*` (27 keys) in all 10 locale files; Status: ✅
- 9 — Milestone: `PaywallGate` on all AI endpoints (`require_subscription` dep); Status: ✅

**Completion criteria:**

- [x] `GET /api/listening/next` returns an uncompleted exercise for the user's level, or `{ "available": false }`
- [x] `POST /api/listening/generate` creates text + MP3 via LLM + TTS; Redis lock prevents duplicates
- [x] MP3 file persisted in Docker named volume and served via `GET /api/listening/audio/{id}`
- [x] Exercise cached and reused for all subsequent users at the same level + language
- [x] Completed exercises are not shown again as "new" for the same user
- [x] History tab shows past attempts with transcript and original answers
- [x] Replaying from history awards no additional XP
- [x] Score 0–5, XP 0–50 (10 per correct answer) saved correctly
- [x] Paywall returns 403 on AI endpoints when `STRIPE_ENABLED=true` and user is unsubscribed
- [x] `tsc --noEmit` and `python3 -m compileall` pass clean
- [x] No regressions in Phases 1–5

---

## Phase 7 — Reading

✅ Status: Complete (v1.5.3)

> LLM-generated reading comprehension exercises. Text is shown immediately alongside 5
> multiple-choice questions (no audio, no "I'm ready" gate). Exercises are cached per
> CEFR level and target language so multiple users share the same content. Score and XP
> are awarded on submission; completed exercises move to a personal history tab where
> they can be replayed without earning additional XP.

- 1 — Milestone: DB models — `reading_exercises` + `reading_attempts` + migration `0019`; Status: ✅
- 2 — Milestone: Backend service — LLM generation (no TTS), 7 exercise types, 6 topic sets, Redis generation lock; Status: ✅
- 3 — Milestone: Backend router — 4 endpoints: next, generate, attempt, history; Status: ✅
- 4 — Milestone: Reading/listening generation validated via `structured_output()` Pydantic schemas; Status: ✅
- 5 — Milestone: Frontend page — 6 UI states: loading → generating → idle → exercise → results → history; Status: ✅
- 6 — Milestone: Two-column layout (passage 55% / questions 45%) on desktop; stacked on mobile; Status: ✅
- 7 — Milestone: Sidebar nav entry (immediately after Listening); Status: ✅
- 8 — Milestone: i18n — `nav.reading` + `reading.*` namespace in all 10 locale files; Status: ✅
- 9 — Milestone: `PaywallGate` on AI endpoints; history accessible without subscription; Status: ✅
- 10 — Milestone: Answer count validation (`field_validator` — exactly 5 answers required); Status: ✅

**Completion criteria:**

- [x] `GET /api/reading/next` returns exercise with `text` included immediately, or `{ "available": false }`
- [x] `POST /api/reading/generate` enqueues background LLM task; Redis lock prevents duplicate generation
- [x] Exercise cached and reused for all users at the same level + language
- [x] `correct` field omitted from `QuestionOut`; only revealed after `POST /attempt`
- [x] Completed exercises excluded from "new" pool; accessible via history
- [x] `replay=true` scores correctly but forces `xp_earned = 0`
- [x] Score 0–5, XP 0–50 (10 per correct answer) saved correctly
- [x] History paginated (`skip` / `limit`, max 50); returns `total` count
- [x] Paywall returns 403 on AI endpoints when `STRIPE_ENABLED=true` and user is unsubscribed
- [x] `POST /attempt` with ≠ 5 answers returns 422 (Pydantic `field_validator`)
- [x] `tsc --noEmit` and `python3 -m compileall` pass clean
- [x] No regressions in Phases 1–6

---

## Phase 8 — Feedback Board

✅ Status: Complete (v1.5.7)

> Community feedback board where users submit feature requests and bug reports, vote on
> suggestions, discuss entries via flat comment threads, and see unread feedback activity
> in the app sidebar. Admins manage entry status and can delete any entry or comment.

- 1 — Milestone: DB models — `feedback_entries` + `feedback_votes` + `feedback_comments` + `feedback_read_states` + migrations `0020` and `0046`; Status: ✅
- 2 — Milestone: Backend router — 11 endpoints: list, create, unread summary, get, mark read, vote toggle, add comment, delete comment, delete entry, admin status update; Status: ✅
- 3 — Milestone: Admin frontend page — `/admin/feedback` with status management; Status: ✅
- 4 — Milestone: User frontend page — `/feedback` with list + detail view, tabs (feature/bug), sort, status filter, pagination; Status: ✅
- 5 — Milestone: Vote toggle inline on list cards and in detail view; Status: ✅
- 6 — Milestone: Flat comment thread in detail view with add/delete; Status: ✅
- 7 — Milestone: i18n — `feedback.*` namespace in all 10 locale files; Status: ✅

**Completion criteria:**

- [x] `GET /api/feedback` filters by `type`, `status`, `sort`, `order`, `skip`, `limit` correctly
- [x] `POST /api/feedback` creates entry with status `pending`; returns 201
- [x] Vote toggle increments/decrements `vote_count` atomically; only feature entries accept votes
- [x] Bug entries return 400 on vote attempt
- [x] `UNIQUE(entry_id, user_id)` constraint enforced — no duplicate votes
- [x] Admin can update status to any of: `pending`, `planned`, `in_progress`, `done`, `declined`
- [x] Author or admin can delete an entry; cascade removes all votes and comments
- [x] Author or admin can delete a comment
- [x] `voted_by_me` and `comment_count` correctly populated per authenticated user
- [x] Feedback unread counter counts threads with activity by other users and `POST /api/feedback/{entry_id}/read` clears only that thread for the current user
- [x] `tsc --noEmit` and `python3 -m compileall` pass clean
- [x] No regressions in Phases 1–7

---

## Phase 9 — LLM Memory

✅ Status: Complete (v1.6.0)

> The AI tutor autonomously remembers important details about the student (preferences,
> hobbies, profession, learning goals, struggles) as they emerge during chat or voice
> conversations. Lingu uses a native `save_user_memory` tool when a durable fact is worth
> persisting; the backend executes one tool round and continuation for text or voice.
> Saved memories are global per user and are injected into both tutor modes.

- **1** — DB model — `memories` table + migration `0022_memory`. Status: ✅
- **2** — `memory_service.py` — strict native tool, escaped context, per-user exact deduplication, 150-item FIFO cap, global get, manual create, delete, clear. Status: ✅
- **3** — Chat integration — one native tool round plus continuation, `{"memory_updated": true}` SSE signal before `done`. Status: ✅
- **4** — Voice integration — global memories refreshed every turn, tool payload excluded from TTS, `{"type": "memory_updated"}` before `turn_complete`. Status: ✅
- **5** — `MEMORY_SYSTEM_INSTRUCTION` injected into both chat and voice system prompts. Status: ✅
- **6** — REST API — authenticated list, manual create, delete single, and clear all; no subscription or maintenance gate. Status: ✅
- **7** — Frontend toast in chat and voice conversation on `memory_updated` signal. Status: ✅
- **8** — Settings → Memory subpage (`/settings/memories`) — manual add, full list, individual delete, clear all, and robust loading/error/busy states. Status: ✅
- **9** — i18n — `settings.sectionMemory`, `settings.memoryEmpty`, `settings.memoryClearAll*`, `chat.memoryUpdated`, `conversation.memoryUpdated` in all 10 locale files. Status: ✅
- **10** — Tests — backend and frontend coverage for native provider streams, memory APIs/services, cross-language preservation, and Settings states. Aggregate totals await the next full validation run. Status: ✅

**Completion criteria:**

- [x] Native tool payloads never reach frontend text, transcripts, or TTS
- [x] New memories are saved through one native `save_user_memory` tool round in text and voice
- [x] Exact-duplicate items skipped; FIFO eviction when `MAX_MEMORIES_PER_USER` (150) is exceeded
- [x] Up to `MAX_MEMORIES_CONTEXT` (20) most recent memories injected into system prompt per request
- [x] `GET /api/memories` returns all memories oldest-first
- [x] `DELETE /api/memories/{id}` returns 404 if wrong owner (IDOR guard)
- [x] `DELETE /api/memories` returns `{"deleted": N}`
- [x] Toast notification appears in chat and voice when new memories are saved
- [x] `/settings/memories` supports manual add, global list, individual delete, and clear-all
- [x] `tsc --noEmit` and `python3 -m compileall` pass clean
- [x] No regressions in Phases 1–8

---

## Phase 10 — Multi-Language Support (Multiple Simultaneous Languages)

✅ Status: Complete (v1.7.0)

> Each user can learn multiple languages simultaneously. Every language gets its own
> isolated study plan, progress, flashcards, conversations, and competencies. Memories
> are global per user so durable personal context follows the learner across languages.
> A sidebar language switcher lets the user pivot the entire experience to any of their
> active plans with one click. Phase 4 added `target_language` as a single value per
> user — Phase 10 extends it to a full per-language data model.
>
> See [`phase-10-multi-language.instructions.md`](phase-10-multi-language.instructions.md) for the sub-phase index and full spec.

- \***\*10.1\*\*** — Title: Database: `user_languages` table, `study_plan_id` columns, partial unique index, Alembic migration `0029`, conftest fixtures, isolation tests. Status: ✅
- \***\*10.2\*\*** — Title: Backend: `user_language_service`, `get_active_study_plan` dependency, multi-language LLM prompts, migration `0030` (placeholder — NOT NULL moved to 10.3); prompt tests. Status: ✅
- \***\*10.3\*\*** — Title: API: new `/api/languages` router, refactor assessment + study-plan endpoints, Pydantic schemas; backend tests. Status: ✅
- \***\*10.4\*\*** — Title: Frontend core: `target-languages.ts` config, language Zustand store, `LanguageSwitcher` component, sidebar integration. Status: ✅
- \***\*10.5\*\*** — Title: Frontend pages: Settings → My Languages, onboarding flow, dashboard, plan, chat, flashcards, progress adapted; i18n keys added per sub-phase; frontend tests. Status: ✅
- \***\*10.6\*\*** — Title: Curriculum and language data: Spanish, Italian, Portuguese curriculum files (backend + frontend); target language descriptions; curriculum tests. Status: ✅

**Completion criteria:**

- [x] A user can add a second language from Settings → My Languages
- [x] Language switcher appears in sidebar only when the user has ≥ 2 languages
- [x] Switching language pivots the entire experience (plan, flashcards, chat, progress) to that language's plan
- [x] Flashcards, progress, and competencies are isolated per `study_plan_id`; memories retain nullable plan provenance but are retrieved globally
- [x] Spanish (`es-ES`), Italian (`it-IT`), and Portuguese (`pt-PT`) curriculum data is complete and correct
- [x] All LLM prompts are language-agnostic (no hardcoded "English")
- [x] Migration `0029` runs cleanly; `downgrade` fully reverses it
- [x] Migration `0031` (NOT NULL on `progress`, `flashcards`, `user_competencies`) runs cleanly after 10.3 callers are deployed
- [x] Existing English-only users are unaffected after migration
- [x] `tsc --noEmit` and `python3 -m compileall` pass clean
- [x] No regressions in Phases 1–9

---

## Phase 11 — User Reviews

✅ Status: Complete (v1.8.9)

> One verified review per user, with mandatory 1–5 star rating, optional comment,
> active learning language snapshot, admin approval, and approved positive reviews
> displayed on the public landing page.
>
> See [`phase-11-reviews.instructions.md`](phase-11-reviews.instructions.md) for the full spec.

- 1 — Milestone: Spec and planning — functional rules, model contract, endpoints, frontend behaviour, test plan; Status: ✅
- 2 — Milestone: Backend model and migration — `reviews` table, one review per user, rating constraints; Status: ✅
- 3 — Milestone: Backend API — user review creation/state, public approved reviews, admin moderation; Status: ✅
- 4 — Milestone: Backend tests — validation, duplicate guard, public filtering, admin permissions; Status: ✅
- 5 — Milestone: Frontend API and reusable review prompt with local dismissal cooldown; Status: ✅
- 6 — Milestone: Landing reviews carousel — approved `rating >= 4` reviews, including rating-only reviews; Status: ✅
- 7 — Milestone: Admin reviews section — list, filters, approve/unapprove, delete; Status: ✅
- 8 — Milestone: Frontend tests — prompt, landing, admin interactions; Status: ✅

**Completion criteria:**

- [x] Database model enforces one review per user.
- [x] Database model constrains rating to 1–5.
- [x] Users can create exactly one review via API.
- [x] Rating is mandatory in API payloads and constrained to 1–5.
- [x] Comment is optional.
- [x] Reviews store display-name and active-learning-language snapshots.
- [x] New reviews are pending until admin approval.
- [x] Public reviews API returns only approved reviews with `rating >= 4`.
- [x] Rating-only reviews render cleanly on the landing page.
- [x] Admins can approve, unapprove, and delete reviews.
- [x] Non-admin users cannot access admin review endpoints.
- [x] Backend targeted tests cover the review API flows.
- [x] Frontend targeted tests cover the review UI flows.
- [x] `npm run lint`, `npx tsc --noEmit`, and `npm run test:run` pass clean for the frontend.
