---
description: "Database models reference for FreeLingo: 23 SQLAlchemy ORM models with full schema details, relationships, constraints, and business rules."
applyTo: "backend/app/models/**, backend/alembic/**"
---

# Database Models — FreeLingo

All models use SQLAlchemy 2.0 declarative style with `Mapped[T]` type annotations and async engine (`asyncpg` driver). PostgreSQL JSON columns store structured content for lessons, plans, exercises, and skill scores.

## User (`users`)

Registration, authentication, and user preferences.

**Columns:**

- `id` — integer primary key.
- `username` — unique string used for login.
- `email` — unique string; nullable at DB level for legacy rows, but required by public registration and admin user creation.
- `display_name` — string shown in the UI.
- `hashed_password` — bcrypt hash.
- `role` — string: `"admin"` or `"user"`.
- `native_language` — string such as `"es"` or `"fr"`; used for flashcard translations and tutor feedback.
- `target_language` — BCP-47 tag such as `"en-GB"` (default) or `"en-US"`; the language the user is learning.
- `is_active` — boolean; `false` means the account is disabled by an admin.
- `is_verified` — boolean; `false` until email verification. Existing users were set to `true` on migration.
- `conversation_max_duration` — integer max voice session duration in seconds. Default comes from `DEFAULT_CONVERSATION_MAX_DURATION` (`1800`).
- `conversation_inactivity_timeout` — integer seconds of silence before disconnect. Default comes from `DEFAULT_CONVERSATION_INACTIVITY_TIMEOUT` (`180`).
- `conversation_speech_pause` — integer milliseconds of silence that end a spoken turn in voice conversation. Allowed values are `0`, `1000`, `2000`, and `3000`; `0` (the default) means the window is derived from the learner's CEFR level.
- `conversation_weekly_sessions` — integer weekly session counter. Default comes from `DEFAULT_CONVERSATION_WEEKLY_SESSIONS` (`0`, unlimited).
- `conversation_daily_minutes` — integer daily voice limit in minutes. Default comes from `DEFAULT_CONVERSATION_DAILY_MINUTES` (`30`).
- `conversation_weekly_minutes` — integer weekly voice limit in minutes. Default comes from `DEFAULT_CONVERSATION_WEEKLY_MINUTES` (`90`).
- `monthly_tokens_limit` — integer max LLM tokens per billing period. Default comes from `DEFAULT_MONTHLY_TOKENS_LIMIT` (`1 000 000`; `0` means unlimited).
- `stripe_customer_id` — nullable string Stripe customer ID, set when a subscription is created.
- `stripe_subscription_id` — nullable string current Stripe subscription ID. Used to ignore stale webhook events from older subscriptions for the same customer.
- `subscription_status` — string subscription state: `none` by default, plus Stripe states `trialing`, `active`, `past_due`, `canceled`, `incomplete`, `incomplete_expired`, `unpaid`, and `paused`.
- `subscription_ends_at` — nullable datetime for the current subscription period end.
- `trial_used` — boolean; `true` once the user has started or completed a trial, preventing repeated free trials. Default: `false`.
- `assessment_voice_trial_used` — boolean; `true` once the one-time post-assessment voice conversation demo has been consumed. Default: `false`.
- `freemium_trial_ends_at` — nullable datetime; when the freemium 7-day trial expires. Set on registration when `STRIPE_ENABLED=true` and `FREEMIUM_TRIAL_ENABLED=true`.
- `freemium_trial_used` — boolean; `true` once the user has ever used a freemium trial, preventing repeated trials. Default: `false`.
- `avatar` — nullable text cache-busted internal avatar reference, for example `/api/avatars/{uuid}.{ext}?v={ms}`. Files are stored under `/app/avatars` and retrieved through authenticated profile endpoints with private no-store responses, not public static serving. Legacy base64 data URLs may still exist until replaced.
- `bio` — nullable text profile bio.
- `learning_goals` — nullable text JSON-encoded array of learning goal strings.
- `dismissed_dashboard_banner_revision` — nullable integer storing the last global dashboard-banner revision dismissed by this account. A new content revision differs from this marker and becomes visible again.
- `created_at` — datetime set automatically on creation.
- `last_login` — nullable datetime updated on each successful login.

**Registration rules:**

- First registered user becomes admin automatically when `FIRST_USER_IS_ADMIN=true` (default).
- `ALLOW_REGISTRATION=false` blocks public signups; admin creates users with a required email address or generates single-use invite links (48h expiry in Redis).
- `BLOCKED_EMAIL_DOMAINS` is a JSON array of lowercase domain strings (e.g. `["yopmail.com","mailinator.com"]`). Registrations using an email from any listed domain are rejected with HTTP 422 before any DB access. Defaults to `[]` (no blocking).
- `POST /register` returns an `access_token` + sets the refresh token cookie so the frontend can redirect directly to `/onboarding` without an intermediate login.
- On `/onboarding` the user chooses their `target_language`; the choice is saved via `PATCH /me` before accessing the app.
- `trial_used` is surfaced through authenticated user profile responses and remains backend-authoritative: Stripe Checkout only receives `trial_period_days` when `STRIPE_TRIAL_DAYS > 0` and `trial_used=false`; webhooks set it to `true` once a trialing subscription starts.
- `assessment_voice_trial_used` is surfaced through authenticated user profile responses and is separate from Stripe trial eligibility. It gates only the one-time post-assessment voice demo shown for unsubscribed hosted users; demo duration comes from `ASSESSMENT_VOICE_TRIAL_DURATION_SECONDS` (`300`, 5 minutes by default).
- `freemium_trial_ends_at` and `freemium_trial_used` are surfaced through authenticated user profile responses. When `STRIPE_ENABLED=true` and `FREEMIUM_TRIAL_ENABLED=true`, new users are granted a 7-day freemium trial on registration (`freemium_trial_ends_at` = `now + FREEMIUM_TRIAL_DAYS` days, `freemium_trial_used` = `true`). After the trial expires, freemium quota limits apply. Freemium quotas (chat messages, lesson completions, listening/reading exercises, voice minutes) are stored in Redis with keys like `freemium:{feature}:{user_id}:{date/week}` and auto-expiring TTL, managed by an atomic Lua script — they are not stored in the database.
- `stripe_subscription_id` is set from `checkout.session.completed` and backfilled from `customer.subscription.updated` for existing users when missing. Once present, subscription update/delete and invoice payment-failed webhooks whose subscription ID does not match are ignored as stale events.
- Only `trialing` and `active` grant premium access. `past_due`, `unpaid`, and `paused` route users to payment recovery through Stripe Customer Portal. `none`, `incomplete`, `incomplete_expired`, and `canceled` show normal monthly/yearly plan-selection UI.

## DashboardBanner (`dashboard_banners`)

Singleton global announcement managed by administrators and displayed on authenticated dashboards.

- `id` — integer primary key constrained to `1` by `ck_dashboard_banners_singleton`.
- `translations` — required PostgreSQL JSONB object containing `title`, `subtitle`, and `description` for exactly the ten UI locales: `en`, `es`, `fr`, `pt`, `de`, `it`, `ru`, `nl`, `pl`, and `ro`.
- `source_locale` — required two-character UI locale used to create the translation set.
- `is_active` — required boolean controlling public visibility; default `false` at the ORM level.
- `revision` — required integer server revision, initially `1`. It increments when the source locale or translated content changes, but not for an active-state-only change.
- `created_at` — datetime set on singleton creation.
- `updated_at` — datetime set on creation and updated on modification.

Migration `0050_dashboard_banner` creates the singleton table and adds `users.dismissed_dashboard_banner_revision`. Dismissal is valid only for the currently active revision.

## UserLanguage (`user_languages`)

Relates users to the languages they are learning. One row per user per language. Added in Phase 10.

- id — Type: integer; Notes: Primary key, autoincrement
- user_id — Type: integer; Notes: FK → users (CASCADE), NOT NULL
- target_language — Type: string(10); Notes: BCP-47 tag, NOT NULL
- is_active — Type: boolean; Notes: `true` = current active language. Only one `true` per user. Default `true`.
- created_at — Type: datetime; Notes: Auto-set

**Constraints:**

- `UNIQUE(user_id, target_language)` — a user cannot have the same language duplicated.
- Composite index `ix_user_language_user_active` on `(user_id, is_active)` for fast active language lookups.

## StudyPlan (`study_plans`)

One active plan per user per language. Generated after CEFR assessment. Added in Phase 4 (`target_language`), updated in Phase 10 (`user_language_id`, partial unique index).

- **id** — Type: integer. Notes: Primary key
- **user_id** — Type: integer. Notes: FK → users
- **user_language_id** — Type: integer. Notes: FK → user_languages (CASCADE). Added in Phase 10.
- **cefr_level** — Type: string. Notes: A1, A2, B1, B2, C1, C2
- **goals** — Type: JSON. Notes: List of goal strings (grammar, vocabulary, reading, writing, conversation)
- **duration_weeks** — Type: integer. Notes: 4, 8, 12, or 16 (maps to intensity)
- **days_per_week** — Type: integer. Notes: Derived: 5, 5, 4, or 3
- **current_unit** — Type: string. Notes: Curriculum unit ID, e.g. `"a1-unit-3"`
- **progress_day** — Type: integer. Notes: 0-indexed count of days completed. `N` means N days done; user is on day index N. Default 0. See `specs/study-plan.instructions.md` for full semantics.
- **generated_plan** — Type: JSON. Notes: Full week-by-week plan (WeekPlan → DayPlan → Unit assignments)
- **is_active** — Type: boolean. Notes: True for the current plan
- **completion_test_taken** — Type: boolean. Notes: Whether end-of-level test was completed
- **completion_test_score** — Type: float (nullable). Notes: 0.0 – 1.0
- **completion_test_recommendation** — Type: string (nullable). Notes: `"advance"`, `"extend"`, or `"repeat"`
- **target_language** — Type: string. Notes: BCP-47 tag at plan creation (e.g. `"en-US"`). Denormalised from `user_languages`.
- **created_at** — Type: datetime. Notes: Auto-set

**Constraints:**

- Partial unique index `uq_active_plan_per_lang` on `(user_language_id)` WHERE `is_active = true` — enforces one active plan per user per language.

**Intensity / duration mapping:**

- Intensive — Weeks: 4; Days/week: 5; Total lessons: ~20
- Standard — Weeks: 8; Days/week: 5; Total lessons: ~40
- Relaxed (default) — Weeks: 12; Days/week: 4; Total lessons: ~48
- Very relaxed — Weeks: 16; Days/week: 3; Total lessons: ~48

One lesson per day slot in the study plan.

**Columns:**

- `id` — integer primary key.
- `study_plan_id` — integer FK to `study_plans`.
- `title` — lesson title.
- `lesson_type` — string: `grammar`, `vocabulary`, `reading`, `writing`, `listening`, `speaking`, or `review`.
- `cefr_level` — CEFR level string.
- `week_number` — integer week in the plan.
- `day_number` — integer day in the week.
- `unit_id` — nullable string curriculum unit this lesson belongs to.
- `content` — JSON structured lesson content generated by the LLM. Includes target-language `explanation`, optional native-language `native_explanation` with `text`, `key_points`, `examples`, `common_traps`, and `mini_glossary`, plus exercises, vocabulary, grammar refs, and unit metadata.
- `is_completed` — boolean completion flag.
- `completed_at` — datetime set when the lesson is completed.

## Exercise (`exercises`)

Exercises belong to a lesson (1 lesson → many exercises).

- id — Type: integer; Notes: Primary key
- lesson_id — Type: integer; Notes: FK → lessons
- exercise_type — Type: string; Notes: `multiple_choice`, `fill_blank`, `free_write`, `pronunciation`
- question — Type: text; Notes: Exercise prompt
- options — Type: JSON; Notes: Array of options (for multiple_choice)
- correct_answer — Type: text; Notes: Expected answer
- user_answer — Type: text (nullable); Notes: User's submitted answer
- score — Type: float (nullable); Notes: 0.0 – 1.0
- feedback — Type: text (nullable); Notes: LLM-generated feedback
- answered_at — Type: datetime; Notes: —

Exercise rows do not have a dedicated native-language explanation column. New lesson-generation output may include per-exercise `native_explanation` values inside `lessons.content.exercises[*]`; `GET /api/lessons/{id}` merges that optional JSON text into each exercise response by exercise order. The on-demand endpoint `POST /api/lessons/exercises/{id}/native-explanation` writes missing exercise-level native explanations back into the same JSON array.

## Flashcard (`flashcards`)

SM-2 spaced repetition cards, per user per language.

- id — Type: integer; Notes: Primary key
- user_id — Type: integer; Notes: FK → users
- study_plan_id — Type: integer; Notes: FK → study_plans (CASCADE), NOT NULL, indexed. Added in Phase 10.
- word — Type: string; Notes: Target language word/phrase
- definition — Type: text; Notes: Simple definition in the user's native language
- example_sentence — Type: text; Notes: Usage example
- translation — Type: text; Notes: Translation to user's native language
- source — Type: varchar(20); Notes: Origin of the card: `NULL` (generated), `"from_text"` (saved from reading exercise)
- ease_factor — Type: float; Notes: SM-2 ease factor (default 2.5)
- interval — Type: integer; Notes: Days until next review (default 0)
- repetitions — Type: integer; Notes: Consecutive correct reviews (default 0)
- next_review — Type: date; Notes: Date of next review (default today)
- created_at — Type: datetime; Notes: —

## Progress (`progress`)

Daily progress record, one row per user per day per plan. Added `study_plan_id` in Phase 10.

- id — Type: integer; Notes: Primary key
- user_id — Type: integer; Notes: FK → users
- study_plan_id — Type: integer; Notes: FK → study_plans (CASCADE), NOT NULL, indexed
- date — Type: date; Notes: —
- xp_earned — Type: integer; Notes: XP gained that day
- lessons_completed — Type: integer; Notes: —
- exercises_correct — Type: integer; Notes: —
- exercises_total — Type: integer; Notes: —
- streak_day — Type: integer; Notes: Consecutive day count
- skills — Type: JSON; Notes: Skill scores: `{"grammar": 0.6, "vocabulary": 0.4, ...}`

**Constraint:** `UNIQUE(user_id, study_plan_id, date)` — one progress row per user per plan per day.

## Conversation (`conversations`)

Grouping of chat messages (text and voice) into named conversations. Added `study_plan_id` in Phase 10.

- id — Type: integer; Notes: Primary key
- user_id — Type: integer; Notes: FK → users (CASCADE)
- study_plan_id — Type: integer (nullable); Notes: FK → study_plans (SET NULL), indexed
- title — Type: string; Notes: Auto-generated or user-set
- source — Type: string; Notes: `'chat'` or `'voice'` (default `'chat'`)
- created_at — Type: datetime; Notes: —
- updated_at — Type: datetime; Notes: —

## ChatHistory (`chat_history`)

Individual messages within text chat and voice conversations. Added `study_plan_id` in Phase 10.

- id — Type: integer; Notes: Primary key
- user_id — Type: integer; Notes: FK → users
- conversation_id — Type: integer (nullable); Notes: FK → conversations (CASCADE)
- study_plan_id — Type: integer (nullable); Notes: FK → study_plans (SET NULL), indexed
- role — Type: string; Notes: `"user"` or `"assistant"`
- content — Type: text; Notes: Message body
- created_at — Type: datetime; Notes: —

## UserCompetency (`user_competencies`)

Per-unit competency tracking (Phase 1+). Added `study_plan_id` in Phase 10.

- id — Type: integer; Notes: Primary key
- user_id — Type: integer; Notes: FK → users (CASCADE)
- study_plan_id — Type: integer; Notes: FK → study_plans (CASCADE), NOT NULL, indexed
- unit_id — Type: string; Notes: Curriculum unit ID (indexed)
- competency_text — Type: text; Notes: Name of the competency
- score — Type: float; Notes: 0.0 – 1.0, exponential moving average
- mastered — Type: boolean; Notes: True when score >= 0.80
- updated_at — Type: datetime; Notes: —

**Constraint:** `UNIQUE(user_id, study_plan_id, unit_id, competency_text)`.

## ListeningExercise (`listening_exercises`)

AI-generated listening comprehension exercises (Phase 6). Shared across all users at the same CEFR level and target language.

- id — Type: integer; Notes: Primary key
- level — Type: string; Notes: CEFR level: A1–C2
- target_language — Type: string; Notes: BCP-47 tag, e.g. `"en-US"`
- exercise_type — Type: string; Notes: E.g. `"story"`, `"dialogue"`, `"news_report"` — varies by level
- topic — Type: string; Notes: Short topic description
- text — Type: text; Notes: Full transcript (never returned to client before submission)
- audio_path — Type: string; Notes: Absolute path to MP3 on disk, e.g. `/data/audio/listening/42.mp3`
- duration_seconds — Type: integer; Notes: Audio length in seconds
- questions — Type: JSON; Notes: List of `{question, options: [str×4], correct}` objects (5 questions per exercise)
- play_count — Type: integer; Notes: How many times this exercise has been served (server default 0)
- created_at — Type: datetime; Notes: Auto-set on creation

Composite index: `ix_listening_exercises_level_lang` on `(level, target_language)`.

## ListeningAttempt (`listening_attempts`)

Records each user submission for a listening exercise. Added `study_plan_id` in Phase 10.

- id — Type: integer; Notes: Primary key
- user_id — Type: integer; Notes: FK → users (CASCADE DELETE)
- exercise_id — Type: integer; Notes: FK → listening_exercises (CASCADE DELETE)
- study_plan_id — Type: integer; Notes: FK → study_plans (CASCADE), NOT NULL, indexed
- answers — Type: JSON; Notes: List of strings — the user's selected option per question
- score — Type: integer; Notes: 0–5 (number of correct answers)
- xp_earned — Type: integer; Notes: 0–50 (10 per correct answer)
- completed_at — Type: datetime; Notes: Auto-set on creation

Unique constraint: one attempt per `(user_id, exercise_id)` — enforced at service level (409 on duplicate).

## ReadingExercise (`reading_exercises`)

AI-generated reading comprehension exercises (Phase 7). Shared across all users at the same CEFR level and target language. Unlike listening, no audio is produced — the text is served directly to the client.

- id — Type: integer; Notes: Primary key
- level — Type: string; Notes: CEFR level: A1–C2
- target_language — Type: string; Notes: BCP-47 tag, e.g. `"en-US"`
- exercise_type — Type: string; Notes: `notice`, `email`, `article`, `news`, `blog_post`, `review`, `essay`
- topic — Type: string; Notes: Short topic description
- text — Type: text; Notes: Full passage text — **included in exercise response** (unlike listening)
- questions — Type: JSON; Notes: List of `{index, question, options: {A,B,C,D}, correct}` objects (5 per exercise)
- view_count — Type: integer; Notes: How many times this exercise has been served (server default 0)
- created_at — Type: datetime; Notes: Auto-set on creation

Composite index: `ix_reading_exercises_level_lang` on `(level, target_language)`.

## ReadingAttempt (`reading_attempts`)

Records each user submission for a reading exercise. Added `study_plan_id` in Phase 10.

- id — Type: integer; Notes: Primary key
- user_id — Type: integer; Notes: FK → users (CASCADE DELETE)
- exercise_id — Type: integer; Notes: FK → reading_exercises (CASCADE DELETE)
- study_plan_id — Type: integer; Notes: FK → study_plans (CASCADE), NOT NULL, indexed
- answers — Type: JSON; Notes: `{ "0": "B", "1": "A", ... }` — the user's selected option per question
- score — Type: integer; Notes: 0–5 (number of correct answers)
- xp_earned — Type: integer; Notes: 0–50 (10 per correct answer)
- completed_at — Type: datetime; Notes: Auto-set on creation

Unique constraint: one attempt per `(user_id, exercise_id)` — enforced at service level (409 on duplicate).

## FeedbackEntry (`feedback_entries`)

A feature request or bug report submitted by a user.

- id — Type: integer; Notes: Primary key
- type — Type: string(10); Notes: `"feature"` or `"bug"`
- title — Type: string(200); Notes: Short title
- description — Type: text; Notes: Full description (max 5000 chars via schema)
- status — Type: string(20); Notes: `pending` (default) \
- author_id — Type: integer; Notes: FK → users (CASCADE DELETE)
- vote_count — Type: integer; Notes: Denormalised sum of votes (default 0)
- created_at — Type: datetime; Notes: Auto-set on creation

Indexes: `type`, `status`, `author_id`, `created_at`.

## FeedbackVote (`feedback_votes`)

One vote per user per feature request. Bugs are not voteable.

- id — Type: integer; Notes: Primary key
- entry_id — Type: integer; Notes: FK → feedback_entries (CASCADE DELETE)
- user_id — Type: integer; Notes: FK → users (CASCADE DELETE)
- created_at — Type: datetime; Notes: Auto-set on creation

Unique constraint: `UNIQUE(entry_id, user_id)` — enforced at DB level (`uq_feedback_vote`).

## FeedbackComment (`feedback_comments`)

A flat comment on a feedback entry. No nesting.

- id — Type: integer; Notes: Primary key
- entry_id — Type: integer; Notes: FK → feedback_entries (CASCADE DELETE)
- author_id — Type: integer; Notes: FK → users (CASCADE DELETE)
- body — Type: text; Notes: Comment body (max 2000 chars via schema)
- created_at — Type: datetime; Notes: Auto-set on creation

## FeedbackReadState (`feedback_read_states`)

Per-user read marker for feedback thread activity. Used by the sidebar unread counter.

- id — Type: integer; Notes: Primary key
- entry_id — Type: integer; Notes: FK → feedback_entries (CASCADE DELETE), indexed
- user_id — Type: integer; Notes: FK → users (CASCADE DELETE), indexed
- last_read_at — Type: datetime; Notes: Last time this user opened or created activity in this thread

Unique constraint: `UNIQUE(entry_id, user_id)` — enforced at DB level (`uq_feedback_read_state`). Read state is private to each user and is never exposed for other users.

## Review (`reviews`)

One moderated product review per user. Added in Phase 11.

- id — Type: integer; Notes: Primary key
- user_id — Type: integer; Notes: FK -> users (CASCADE DELETE), unique, indexed
- user_display_name — Type: string(150); Notes: Snapshot of the user's visible name when the review is created
- target_language — Type: string(10); Notes: Active learning language when the review is created, indexed
- rating — Type: integer; Notes: Required 1-5 star rating
- comment — Type: text; Notes: Optional review comment
- is_approved — Type: boolean; Notes: Admin moderation flag, default `false`, indexed
- created_at — Type: datetime; Notes: Auto-set on creation, indexed
- updated_at — Type: datetime; Notes: Auto-set on creation; updated when ORM updates the row

**Constraints and indexes:**

- `uq_reviews_user_id` - enforces exactly one review per user.
- `ck_reviews_rating_range` - enforces `rating >= 1 AND rating <= 5`.
- Indexes: `user_id`, `target_language`, `is_approved`, `created_at`.

**Business rules:**

- New reviews start as unapproved and must be approved by an admin before public display.
- Landing/public queries must show only approved reviews with `rating >= 4`.
- Rating-only reviews are valid; `comment` may be null.
- Deleting a user cascades and deletes their review.

## ResourceNativeHelp (`resource_native_helps`)

Global cache for native-language study help generated for static learning resources. Added in v1.8.10 for grammar, phrasebook, and vocabulary native help.

- id — Type: integer; Notes: Primary key
- resource_type — Type: string; Notes: Resource namespace, currently `"grammar"` or `"phrasebook"`; reserved for `"vocabulary"`
- resource_key — Type: string; Notes: Stable resource identifier, e.g. grammar topic slug
- target_language — Type: string; Notes: BCP-47 learning language for the source content
- native_language — Type: string; Notes: User native-language code used for the generated help
- source_hash — Type: string; Notes: SHA-256 hash of the source static content used to generate `content`
- content — Type: JSONB; Notes: Generated native-language help JSON
- created_at — Type: datetime; Notes: Auto-set on creation
- updated_at — Type: datetime; Notes: Updated whenever stale cached help is regenerated

**Constraints and indexes:**

- `uq_resource_native_helps_resource_lang` enforces one cache row per `(resource_type, resource_key, target_language, native_language)`.
- Indexes: `resource_type`, `resource_key`, `target_language`, `native_language`, and composite `ix_resource_native_helps_lookup` on `(resource_type, target_language)`.

**Business rules:**

- Cache entries are shared by all users with the same native language and learning target language.
- If the static source content changes, the computed `source_hash` changes and the next request regenerates the cached help.
- Grammar native help keeps target-language example sentences unchanged while translating explanations, notes, traps, and glossary support into the user's native language.
- Phrasebook native help keeps target-language phrases unchanged while generating native-language usage tips, register notes, phrase notes, traps, and glossary support.
- Vocabulary native help keeps target-language words and example phrases unchanged while generating native-language study tips, word notes, traps, glossary support, and practice prompts.

## Memory (`memories`)

Global user-specific context persisted by Lingu or manually by the user. Memories are shared across learning languages. `study_plan_id` is nullable creation provenance only and never scopes retrieval; deleting its study plan preserves the row through `SET NULL`.

- id — Type: integer; Notes: Primary key
- user_id — Type: integer; Notes: FK → users (CASCADE DELETE)
- study_plan_id — Type: integer (nullable); Notes: FK → study_plans (SET NULL), indexed provenance only
- content — Type: text; Notes: Memory text, max 200 chars enforced at service layer
- source — Type: varchar(10); Notes: `"chat"`, `"voice"`, or `"manual"`
- created_at — Type: datetime; Notes: Auto-set on creation
- Unique constraint: `uq_memories_user_content` on `(user_id, content)` for exact per-user deduplication; migration `0049_memory_user_content_unique` removes later duplicates before creating it

## LLMUsage (`llm_usage`)

Token-usage audit trail, one row per LLM call. Used to track consumption against `monthly_tokens_limit`. Added `study_plan_id` in Phase 10.

- id — Type: integer; Notes: Primary key
- user_id — Type: integer; Notes: FK → users (CASCADE DELETE), indexed
- study_plan_id — Type: integer (nullable); Notes: FK → study_plans (SET NULL), indexed
- source — Type: varchar(20); Notes: Feature that triggered the call: `"chat"`, `"lesson"`, `"assessment"`, etc.
- prompt_tokens — Type: integer (nullable); Notes: Input token count
- completion_tokens — Type: integer (nullable); Notes: Output token count
- total_tokens — Type: integer (nullable); Notes: Total tokens (may differ from prompt + completion for some providers)
- created_at — Type: datetime; Notes: Auto-set on creation
