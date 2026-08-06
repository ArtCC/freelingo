---
description: "Rate limiting strategy for FreeLingo: slowapi with Redis storage, IP-based keys, per-endpoint limits for auth, admin, LLM-heavy operations, TTS/STT, and a default global limit."
applyTo: "backend/app/main.py, backend/app/core/config.py, backend/app/core/limiter.py, backend/app/routers/**/*.py"
---

# Rate Limiting — FreeLingo

## Approach

FreeLingo uses [**slowapi**](https://github.com/laurentS/slowapi), backed by Redis via `settings.REDIS_URL`. Redis is already required for refresh tokens, so rate limiting shares the existing infrastructure and works across backend restarts or multiple backend instances.

### Configuration

- `RATE_LIMIT_ENABLED` — Default: `true`; Purpose: Enable or disable rate limiting globally

The global default limit is `60/minute` for endpoints without an explicit `@limiter.limit()` decorator.

### Key Strategy

All configured limits are currently **IP-based**. The limiter is initialized with `key_func=_get_real_ip`, which resolves the client key in this order:

1. `X-Real-IP`
2. First value from `X-Forwarded-For`
3. Socket client host fallback

This means authenticated users do not get separate per-user rate buckets. Multiple users behind one IP share a bucket, and one user changing IP gets a different bucket.

---

## Explicit Endpoint Limits

Only endpoints with explicit `@limiter.limit()` decorators are listed here. Everything else falls back to the global default `60/minute`.

- `GET /health` — Limit: 60/minute; Access: Public; Rationale: Public liveness probe with explicit protection
- `GET /api/config` — Limit: 60/minute; Access: Public; Rationale: Public runtime flags
- `POST /api/contact` — Limit: 5/hour; Access: Public; Rationale: Contact-form email abuse protection
- `POST /api/auth/register` — Limit: 5/minute; Access: Public; Rationale: Account-creation abuse protection; registration may also require invite
- `POST /api/auth/login` — Limit: 10/minute; Access: Public; Rationale: Credential brute-force protection
- `POST /api/auth/refresh` — Limit: 60/minute; Access: Refresh cookie; Rationale: Normal SPA token rotation
- `POST /api/auth/logout` — Limit: 60/minute; Access: Refresh cookie; Rationale: Logout endpoint protection
- `GET /api/auth/me` — Limit: 60/minute; Access: Authenticated; Rationale: Profile fetch
- `PATCH /api/auth/me` — Limit: 60/minute; Access: Authenticated; Rationale: Profile updates. Native-language validation does not change this limit; unsupported codes return 422.
- `POST /api/auth/me/avatar` — Limit: 60/minute; Access: Authenticated; Rationale: Avatar upload
- `GET /api/auth/me/avatar-file` — Limit: 60/minute; Access: Authenticated; Rationale: Private avatar retrieval
- `DELETE /api/auth/me/avatar` — Limit: 60/minute; Access: Authenticated; Rationale: Avatar deletion
- `DELETE /api/auth/me` — Limit: 5/minute; Access: Authenticated; Rationale: Destructive account deletion
- `GET /api/auth/quota` — Limit: 60/minute; Access: Authenticated; Rationale: Quota status
- `GET /api/auth/verify-email` — Limit: 60/minute; Access: Public token; Rationale: Email verification token endpoint
- `POST /api/auth/resend-verification` — Limit: 3/minute; Access: Authenticated; Rationale: Email-sending abuse protection
- `POST /api/auth/forgot-password` — Limit: 5/minute; Access: Public; Rationale: Email-sending and enumeration protection
- `POST /api/auth/reset-password` — Limit: 5/minute; Access: Public token; Rationale: Reset-token brute-force protection
- `GET /api/admin/health` — Limit: 60/minute; Access: Admin; Rationale: Dependency diagnostics
- `GET /api/admin/stats` — Limit: 60/minute; Access: Admin; Rationale: Operational overview
- `GET /api/admin/users` — Limit: 60/minute; Access: Admin; Rationale: User listing
- `POST /api/admin/users` — Limit: 60/minute; Access: Admin; Rationale: User creation
- `GET /api/admin/users/{user_id}` — Limit: 60/minute; Access: Admin; Rationale: User detail
- `PATCH /api/admin/users/{user_id}` — Limit: 60/minute; Access: Admin; Rationale: User edit
- `GET /api/admin/users/{user_id}/stats` — Limit: 60/minute; Access: Admin; Rationale: User stats
- `GET /api/admin/users/{user_id}/quota` — Limit: 60/minute; Access: Admin; Rationale: User quota
- `DELETE /api/admin/users/{user_id}` — Limit: 5/minute; Access: Admin; Rationale: Destructive account deletion
- `POST /api/admin/invite` — Limit: 60/minute; Access: Admin; Rationale: Invite generation
- `GET /api/admin/maintenance` — Limit: 60/minute; Access: Admin; Rationale: Maintenance state
- `PATCH /api/admin/maintenance` — Limit: 60/minute; Access: Admin; Rationale: Maintenance toggle
- `PUT /api/admin/maintenance` — Limit: 60/minute; Access: Admin; Rationale: Maintenance set
- `GET /api/admin/reviews` — Limit: 60/minute; Access: Admin; Rationale: Review moderation list
- `PATCH /api/admin/reviews/{review_id}` — Limit: 60/minute; Access: Admin; Rationale: Review moderation update
- `DELETE /api/admin/reviews/{review_id}` — Limit: 60/minute; Access: Admin; Rationale: Review deletion
- `GET /api/admin/dashboard-banner` — Limit: 60/minute; Access: Admin; Rationale: Announcement editor load
- `POST /api/admin/dashboard-banner/translate` — Limit: 10/minute; Access: Admin; Rationale: LLM-backed translation generation
- `PUT /api/admin/dashboard-banner` — Limit: 60/minute; Access: Admin; Rationale: Global announcement create/update
- `PUT /api/dashboard-banner/dismiss` — Limit: 60/minute; Access: Authenticated; Rationale: Persist current announcement revision dismissal
- `POST /api/billing/checkout` — Limit: 60/minute; Access: Authenticated; Rationale: Stripe Checkout creation
- `POST /api/billing/portal` — Limit: 60/minute; Access: Authenticated; Rationale: Stripe Customer Portal creation
- `POST /api/billing/webhook` — Limit: 200/minute; Access: Stripe signature; Rationale: Stripe webhook burst tolerance
- `GET /api/freemium/status` — Limit: 60/minute; Access: Authenticated; Rationale: Freemium trial status and quota remaining
- `GET /api/assessment/start` — Limit: 10/minute; Access: Authenticated; Rationale: Placement assessment start
- `GET /api/assessment/bank` — Limit: 60/minute; Access: Authenticated; Rationale: Static bank fetch
- `POST /api/assessment/submit` — Limit: 10/minute; Access: Authenticated; Rationale: Legacy placement submission
- `POST /api/assessment/evaluate` — Limit: 60/minute; Access: Authenticated; Rationale: Deterministic quiz evaluation
- `POST /api/assessment/free-write` — Limit: 10/minute; Access: Authenticated; Rationale: LLM-backed writing evaluation
- `POST /api/assessment/complete` — Limit: 10/minute; Access: Authenticated; Rationale: Study plan creation flow
- `GET /api/assessment/level-test/questions/{plan_id}` — Limit: 5/minute; Access: Authenticated; Rationale: LLM-backed level test generation
- `POST /api/assessment/level-test/submit` — Limit: 10/minute; Access: Authenticated; Rationale: Level test submission
- `GET /api/assessment/level-test/result/{plan_id}` — Limit: 60/minute; Access: Authenticated; Rationale: Level test result retrieval
- `GET /api/languages` — Limit: 60/minute; Access: Authenticated; Rationale: Language list
- `GET /api/languages/active` — Limit: 60/minute; Access: Authenticated; Rationale: Active language
- `POST /api/languages` — Limit: 60/minute; Access: Authenticated; Rationale: Add learning language
- `PUT /api/languages/active` — Limit: 60/minute; Access: Authenticated; Rationale: Switch active language
- `DELETE /api/languages/{target_language}` — Limit: 5/minute; Access: Authenticated; Rationale: Destructive language deletion
- `GET /api/study-plan/current` — Limit: 60/minute; Access: Authenticated; Rationale: Current plan
- `POST /api/study-plan/generate` — Limit: 10/minute; Access: Authenticated; Rationale: Plan generation
- `GET /api/study-plan/today` — Limit: 20/minute; Access: Authenticated; Rationale: May generate missing lesson content
- `POST /api/study-plan/skip-day` — Limit: 60/minute; Access: Authenticated; Rationale: Plan progress mutation
- `GET /api/study-plan/pending-lessons` — Limit: 60/minute; Access: Authenticated; Rationale: Pending lessons
- `GET /api/study-plan/lessons` — Limit: 60/minute; Access: Authenticated; Rationale: Generated lesson metadata for the active plan
- `GET /api/lessons/{lesson_id}` — Limit: 60/minute; Access: Authenticated; Rationale: Lesson detail
- `POST /api/lessons/{lesson_id}/start` — Limit: 60/minute; Access: Authenticated; Rationale: Lesson status mutation
- `POST /api/lessons/{lesson_id}/complete` — Limit: 60/minute; Access: Subscription or freemium; Rationale: Lesson completion
- `POST /api/lessons/exercises/{exercise_id}/answer` — Limit: 20/minute; Access: Authenticated; Rationale: Exercise answer evaluation
- `POST /api/lessons/exercises/{exercise_id}/regenerate` — Limit: 5/hour; Access: Authenticated; Rationale: LLM-backed exercise repair
- `POST /api/lessons/exercises/{exercise_id}/native-explanation` — Limit: 10/minute; Access: Authenticated; Rationale: LLM-backed native explanation
- `POST /api/lessons/exercises/{exercise_id}/native-hint` — Limit: 10/minute; Access: Authenticated; Rationale: LLM-backed native hint
- `POST /api/lessons/{lesson_id}/native-explanation` — Limit: 10/minute; Access: Authenticated; Rationale: LLM-backed lesson explanation
- `GET /api/curriculum` — Limit: 60/minute; Access: Authenticated; Rationale: Curriculum fetch
- `GET /api/curriculum/{level}` — Limit: 60/minute; Access: Authenticated; Rationale: Curriculum by level
- `GET /api/grammar` — Limit: 60/minute; Access: Authenticated; Rationale: Grammar list
- `GET /api/grammar/{slug}` — Limit: 60/minute; Access: Authenticated; Rationale: Grammar detail
- `POST /api/grammar/{slug}/native-help` — Limit: 10/minute; Access: Authenticated; Rationale: LLM-backed grammar helper
- `GET /api/vocabulary` — Limit: 60/minute; Access: Authenticated; Rationale: Vocabulary list
- `GET /api/vocabulary/level/{level}` — Limit: 60/minute; Access: Authenticated; Rationale: Vocabulary by level
- `GET /api/vocabulary/{set_id}` — Limit: 60/minute; Access: Authenticated; Rationale: Vocabulary detail
- `POST /api/vocabulary/{set_id}/native-help` — Limit: 10/minute; Access: Authenticated; Rationale: LLM-backed vocabulary helper
- `GET /api/phrasebook` — Limit: 60/minute; Access: Authenticated; Rationale: Phrasebook list
- `GET /api/phrasebook/level/{level}` — Limit: 60/minute; Access: Authenticated; Rationale: Phrasebook by level
- `GET /api/phrasebook/{category_id}` — Limit: 60/minute; Access: Authenticated; Rationale: Phrasebook detail
- `POST /api/phrasebook/{category_id}/native-help` — Limit: 10/minute; Access: Authenticated; Rationale: LLM-backed phrasebook helper
- `GET /api/phrasebook/audio/{category_id}/{phrase_index}` — Limit: 30/minute; Access: Authenticated; Rationale: TTS phrase audio
- `GET /api/flashcards/due` — Limit: 60/minute; Access: Authenticated; Rationale: Due cards
- `GET /api/flashcards/all` — Limit: 60/minute; Access: Authenticated; Rationale: All cards
- `POST /api/flashcards` — Limit: 60/minute; Access: Authenticated; Rationale: Manual card creation
- `POST /api/flashcards/bulk` — Limit: 60/minute; Access: Authenticated; Rationale: Bulk card creation
- `POST /api/flashcards/{card_id}/review` — Limit: 60/minute; Access: Authenticated; Rationale: SM-2 review
- `POST /api/flashcards/generate` — Limit: 20/minute; Access: Authenticated; Rationale: LLM-backed card generation
- `POST /api/flashcards/from-word` — Limit: 30/minute; Access: Authenticated; Rationale: LLM-backed word lookup
- `GET /api/flashcards/vocabulary` — Limit: 60/minute; Access: Authenticated; Rationale: Saved vocabulary cards
- `DELETE /api/flashcards/{card_id}` — Limit: 60/minute; Access: Authenticated; Rationale: Card deletion
- `GET /api/progress/summary` — Limit: 60/minute; Access: Authenticated; Rationale: Progress summary
- `GET /api/progress/history` — Limit: 60/minute; Access: Authenticated; Rationale: Progress history
- `GET /api/progress/competencies` — Limit: 60/minute; Access: Authenticated; Rationale: Competencies
- `GET /api/chat/conversations` — Limit: 60/minute; Access: Subscription or freemium + no maintenance; Rationale: Conversations list
- `POST /api/chat/conversations` — Limit: 60/minute; Access: Subscription or freemium + no maintenance; Rationale: Conversation creation
- `DELETE /api/chat/conversations/{conversation_id}` — Limit: 60/minute; Access: Subscription or freemium + no maintenance; Rationale: Conversation deletion
- `GET /api/chat/conversations/{conversation_id}/messages` — Limit: 60/minute; Access: Subscription or freemium + no maintenance; Rationale: Conversation messages
- `POST /api/chat` — Limit: 30/minute; Access: Subscription or freemium + no maintenance; Rationale: SSE chat generation
- `GET /api/chat/history` — Limit: 60/minute; Access: Subscription or freemium + no maintenance; Rationale: Legacy chat history
- `POST /api/conversation/warmup` — Limit: 20/minute; Access: Subscription or freemium + no maintenance; Rationale: TTS/STT warmup
- `POST /api/tts` — Limit: 20/minute; Access: Authenticated; Rationale: Audio generation
- `GET /api/tts/preview/{voice}` — Limit: 60/minute; Access: Authenticated; Rationale: Voice preview
- `POST /api/stt` — Limit: 20/minute; Access: Authenticated; Rationale: Audio transcription
- `GET /api/listening/next` — Limit: 10/minute; Access: Subscription or freemium + no maintenance; Rationale: Listening exercise pool
- `POST /api/listening/generate` — Limit: 5/minute; Access: Subscription or freemium + no maintenance; Rationale: LLM+TTS exercise generation
- `GET /api/listening/audio/{exercise_id}` — Limit: 60/minute; Access: Subscription or freemium + no maintenance; Rationale: Exercise audio
- `POST /api/listening/attempt` — Limit: 20/minute; Access: Subscription or freemium + no maintenance; Rationale: Attempt scoring
- `GET /api/listening/history` — Limit: 60/minute; Access: Subscription or freemium + no maintenance; Rationale: Attempt history
- `GET /api/reading/next` — Limit: 10/minute; Access: Subscription or freemium + no maintenance; Rationale: Reading exercise pool
- `POST /api/reading/generate` — Limit: 5/minute; Access: Subscription or freemium + no maintenance; Rationale: LLM exercise generation
- `POST /api/reading/attempt` — Limit: 20/minute; Access: Subscription or freemium + no maintenance; Rationale: Attempt scoring
- `GET /api/reading/history` — Limit: 60/minute; Access: Subscription or freemium + no maintenance; Rationale: Attempt history
- `GET /api/memories` — Limit: 60/minute; Access: Authenticated; Rationale: Global memory list
- `POST /api/memories` — Limit: 10/minute; Access: Authenticated; Rationale: Manual memory creation
- `DELETE /api/memories/{memory_id}` — Limit: 60/minute; Access: Authenticated; Rationale: Single memory deletion
- `DELETE /api/memories` — Limit: 10/minute; Access: Authenticated; Rationale: Bulk global memory deletion
- `GET /api/feedback` — Limit: 60/minute; Access: Authenticated; Rationale: Feedback list
- `POST /api/feedback` — Limit: 10/hour; Access: Authenticated; Rationale: Feedback creation
- `GET /api/feedback/unread-summary` — Limit: 60/minute; Access: Authenticated; Rationale: Feedback unread thread counter
- `GET /api/feedback/{entry_id}` — Limit: 60/minute; Access: Authenticated; Rationale: Feedback detail
- `POST /api/feedback/{entry_id}/read` — Limit: 60/minute; Access: Authenticated; Rationale: Mark one feedback thread as read
- `DELETE /api/feedback/{entry_id}` — Limit: 60/minute; Access: Authenticated; Rationale: Feedback deletion
- `POST /api/feedback/{entry_id}/vote` — Limit: 60/minute; Access: Authenticated; Rationale: Vote toggle
- `PATCH /api/feedback/{entry_id}/status` — Limit: 60/minute; Access: Admin; Rationale: Status update
- `GET /api/feedback/{entry_id}/comments` — Limit: 60/minute; Access: Authenticated; Rationale: Comment list
- `POST /api/feedback/{entry_id}/comments` — Limit: 20/hour; Access: Authenticated; Rationale: Comment creation
- `DELETE /api/feedback/{entry_id}/comments/{comment_id}` — Limit: 60/minute; Access: Authenticated; Rationale: Comment deletion
- `GET /api/reviews/me` — Limit: 60/minute; Access: Authenticated; Rationale: Current user's review
- `POST /api/reviews` — Limit: 5/hour; Access: Authenticated; Rationale: Review creation
- `PATCH /api/reviews/me` — Limit: 10/hour; Access: Authenticated; Rationale: Review update
- `DELETE /api/reviews/me` — Limit: 10/hour; Access: Authenticated; Rationale: Review deletion
- `GET /api/reviews/public` — Limit: 60/minute; Access: Public; Rationale: Landing reviews

---

## WebSocket Rate Limiting

The WebSocket conversation endpoint (`/ws/conversation`) is **not decorated with slowapi**. Protection is handled by:

- JWT authentication in the first JSON message after connection accept
- Subscription checks when Stripe is enabled
- Maintenance-mode rejection for non-admin users
- Session max-duration and inactivity timeouts
- Conversation quota checks in the voice pipeline

---

## Error Response Format

On rate limit exceed, slowapi returns:

- **HTTP status**: `429 Too Many Requests`
- **Header**: `Retry-After: <seconds>` when provided by the limiter backend
- **Body**: `{ "detail": "Rate limit exceeded: ..." }`

Frontend code should not trigger token refresh for `429` responses; only `401` should attempt silent refresh.

---

## Self-hosted Considerations

- Defaults are intended to prevent accidental or malicious bursts without blocking normal self-hosted usage.
- Because the key is IP-based, users behind one NAT share limits.
- Set `RATE_LIMIT_ENABLED=false` only for trusted development or private deployments where limits are undesirable.
