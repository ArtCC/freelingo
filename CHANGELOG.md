# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.5] - 2026-05-19

### Changed
- **Freemium model restructured**: dashboard, flashcards, lessons, study plan, and level assessment are now available to all registered users at no cost. Chat with AI tutor, voice conversations, listening exercises, and reading exercises remain subscription-only features.
- **Backend**: `require_subscription` dependency removed from `/api/lessons`, `/api/flashcards`, `/api/study-plan`, and `/api/assessment` routers; all endpoints in these routers now use `get_current_user` only.
- **Frontend**: `PaywallGate` removed from `/dashboard`, `/flashcards`, and `/assessment/level-test` pages.
- **Landing page pricing section redesigned**: three cards instead of two — Free (lists all features available without subscription), Monthly (all free features plus paid features, 7-day free trial badge), and Yearly (same as monthly plus 2-months-free badge). CTA button updated from "Start X-day free trial" to a register invitation.
- **i18n**: `pricingLabel` updated to the native word for "Pricing" in all 10 locales. New keys added: `planFreeName`, `trialBadge`, `ctaRegister`, `everythingFree`, `freeFeature` (f1–f5). `planFeature.feature1–4` updated to reflect the actual paid-only features (AI chat tutor, voice conversations, listening exercises, reading exercises). All changes applied to all 10 locale files (en, es, de, fr, it, pl, pt, nl, ro, ru).

## [1.5.4] - 2026-05-18

### Fixed
- **Anthropic LLM provider**: resolved crash `'NoneType' object has no attribute 'beta'` in `structured_output` caused by routing Anthropic through `_do_structured_output`, which uses the OpenAI `beta.chat.completions.parse` API while `self.client` is `None` for Anthropic. All providers now go through `_structured_via_json`.
- **Anthropic — system prompt lost**: `_anthropic_chat` was extracting only the first system message via `next()`; extra instructions appended by `_structured_via_json` (JSON format hint) were silently dropped. All system messages are now combined with `\n\n` before the API call.
- **Anthropic — `system=None` API error**: passing `system=None` explicitly to `messages.create` could cause an SDK validation error; the parameter is now omitted when no system message is present.
- **Anthropic — missing timeout**: `messages.create` calls had no `timeout` guard; `REQUEST_TIMEOUT` (60 s) is now applied.
- **Anthropic — double retry**: `_anthropic_chat` wrapped the API call in its own `_call_with_retry`, nesting it inside the outer retry loop in `_do_chat` (up to 9 attempts). The inner retry was removed; the outer loop is sufficient.
- **Dead code removed**: `_do_structured_output` (referenced `self.client.beta` — broken for Anthropic, unreachable for all providers) deleted.

## [1.5.3] - 2026-05-17

### Added
- **Phase 7 — Reading exercises**: AI-generated reading comprehension exercises with multiple-choice questions, scoring, and XP rewards.
- **Backend**: two new DB tables (`reading_exercises`, `reading_attempts`) with Alembic migration `0019_reading.py`. LLM generates a passage + 5 questions graded to the user's CEFR level; no TTS synthesis. Text is stored directly and served to the client immediately.
- **Service layer** (`app/services/reading_service.py`): `get_available_exercise`, `generate_and_save_exercise` (LLM only), `calculate_score` (10 XP/correct), `submit_attempt` (duplicate guard, replay mode, XP via `update_daily_progress`), `get_user_history`. Exercises are shared across all users at the same level and language variant.
- **`parse_llm_json`** utility moved from `listening_service.py` to `llm_adapter.py` and shared by both services.
- **Router** (`GET /api/reading/next`, `POST /api/reading/generate`, `POST /api/reading/attempt`, `GET /api/reading/history`). Generation uses a per-(level, language) Redis lock with 60 s TTL and runs as a `BackgroundTask`. `GET /next?wait=true` long-polls up to 90 s.
- **Frontend** (`/reading`): two-column layout (passage left, questions right) on desktop; stacked on mobile. Five exercise types across CEFR levels: notice, email, article, news, blog post, review, essay. Wrapped in `PaywallGate`. Sidebar entry added after Listening.
- **i18n**: `reading` namespace added to all 10 locale files; nav label kept in English ("Reading") across all locales.
- **Voice selector in Settings**: new *Voice* section visible only when `TTS_PROVIDER=openai`. Users can preview all 9 OpenAI TTS voices (alloy, ash, coral, echo, fable, nova, onyx, sage, shimmer) with inline play/stop buttons and select their preferred voice. Selection is persisted in `localStorage` (key `tts_voice`); default is the server-configured `OPENAI_TTS_VOICE`.
- **`GET /api/tts/preview/{voice}`** backend endpoint (auth required, 10 req/min): generates a short preview clip for the requested voice and caches the MP3 to disk (`${DATA_PATH}/tts_previews/{voice}.mp3`). Subsequent requests are served from the local cache at zero API cost. Only available when `TTS_PROVIDER=openai`.
- **`GET /api/config`** now returns `tts_provider` and `openai_tts_voice` so the frontend can conditionally show the voice selector and resolve the server default.
- **`store/config.ts`** extended with `ttsProvider` and `openaiTtsVoice` fields.
- **Docker volume** `${DATA_PATH}/tts_previews:/app/tts_previews` added to the backend service so cached preview clips survive redeployments.
- **i18n**: `sectionVoice`, `voiceHint`, `voicePlay`, `voiceStop` keys added to all 10 locale files (en, es, de, fr, it, nl, pl, pt, ro, ru).

## [1.5.2] - 2026-05-17

### Fixed
- Minor bug fixes.

## [1.5.1] - 2026-05-17

### Changed
- Stripe Checkout Session now passes `locale="auto"` so the payment page and transactional emails are automatically displayed in the customer's browser language.

## [1.5.0] - 2026-05-15

### Added
- **Phase 6 — Listening exercises**: AI-generated listening comprehension exercises with text-to-speech audio, multiple-choice questions, scoring, and XP rewards.
- **Backend**: two new DB tables (`listening_exercises`, `listening_attempts`) with Alembic migration `0018_listening.py`. LLM generates exercise text + 5 questions; Kokoro/OpenAI TTS synthesises the audio; MP3 stored at `${DATA_PATH}/audio/listening/{id}.mp3` via bind mount.
- **Service layer** (`app/services/listening_service.py`): `get_available_exercise`, `generate_and_save_exercise` (LLM → TTS → disk), `calculate_score` (case-insensitive, 10 XP/correct), `submit_attempt` (duplicate guard, XP in `Progress`), `get_user_history`.
- **Router** (`GET /api/listening/next`, `POST /api/listening/generate`, `GET /api/listening/audio/{id}`, `POST /api/listening/attempt`, `GET /api/listening/history`). Generation uses a per-(level, language) Redis lock with 60 s TTL so concurrent requests don't spawn duplicate jobs. Audio served via `FileResponse`; path built from integer exercise ID — never from a DB string — to prevent path traversal.
- **Frontend** (`/listening`): single-page UI with audio scrubber, question cards, answer review with correct-answer reveal, transcript display, and history list. Polls `GET /next` every 3 s while generation is in progress. Wrapped in `PaywallGate`.
- **Nav**: `/listening` added between Conversation and Assessment in both desktop sidebar and mobile dropdown.
- **i18n**: `listening` namespace and `nav.listening` key added to all 10 locale files (en, es, de, fr, it, nl, pl, pt, ro, ru).
- **Tests**: 20 tests in `backend/tests/test_listening.py` — unit tests for `calculate_score`, HTTP tests for all 5 endpoints including lock semantics, audio serving with `tmp_path`, duplicate-attempt rejection (409), and security (transcript/correct answers never leaked before submission).
- **Config**: `AUDIO_STORAGE_PATH` default `"/data/audio"` in `Settings`; Docker bind mount `${DATA_PATH}/audio:/data/audio` added to backend service.

## [1.4.17] - 2026-05-14

### Fixed
- Security update: frontend dependencies `next` and `eslint-config-next` upgraded from `16.2.4` to `16.2.6` to include the latest Next.js patch.

## [1.4.16] - 2026-05-14

### Added
- Backend logging architecture now includes a shared logger wrapper (`app/core/app_logger.py`). Routers and services use `get_logger(__name__)` for consistent log formatting while preserving compatibility with standard `%s` placeholder messages.
- TTS observability for diagnostics: `POST /api/tts` now supports trace correlation via `X-TTS-Trace-ID` and returns backend timing headers (`X-TTS-Backend-Synth-Ms`, `X-TTS-Backend-Total-Ms`). The Next.js TTS proxy forwards trace information and exposes proxy timing headers (`X-TTS-Proxy-Fetch-Ms`, `X-TTS-Proxy-Buffer-Ms`, `X-TTS-Proxy-Total-Ms`).

## [1.4.15] - 2026-05-14

### Fixed
- Minor bug fixes.

## [1.4.14] - 2026-05-14

### Added

- **In-app contact form**: the Contact button in the landing-page footer and in Settings → Author now opens an in-app modal instead of launching the system mail client. The form collects the sender's email, a subject, and a free-text message. On submit the backend forwards the message to `CONTACT_EMAIL` via the existing SMTP service (`send_contact_email`), setting `Reply-To` to the sender's address. On success the modal shows a "Message sent" confirmation and closes automatically; on error the message is shown inline and the form remains open. Rate-limited to 5 requests/hour per IP. No authentication required (works from the public landing page too).
- **docker-compose — missing `CONTACT_EMAIL`**: the `CONTACT_EMAIL` env var introduced in 1.4.14 was not forwarded to the backend container in `docker-compose.yml`. Added `CONTACT_EMAIL: ${CONTACT_EMAIL:-}` to the backend service environment block so the variable is now properly passed through from the host `.env` file.
- **New env var `CONTACT_EMAIL`**: destination address for contact-form submissions. Must be set alongside `EMAIL_ENABLED=true` for the form to deliver emails.
- **New endpoint `POST /api/contact`**: accepts `{ email, subject, description }`, validates input (subject max 200 chars, description max 5000 chars), forwards via SMTP. Returns 204 on success, 502 on SMTP failure.
- **New email template `contact.html`**: plain HTML template matching the existing transactional email design, displaying sender email, subject, and message body.
- **i18n**: `contact` namespace added to all 10 locale files (en, es, fr, de, pt, it, nl, pl, ro, ru) with keys for title, field labels, placeholders, send/sending/sent, and error message.
- **FAQ — voice conversation**: new Q&A entry ("How does the voice conversation work?") added to the FAQ page, positioned after the AI Tutor entry. Covers real-time speech interaction, automatic voice activity detection (VAD), synthesised AI speech, barge-in support, session time limit, and microphone permission requirement. Translated into all 10 supported locales (en, es, fr, pt, de, it, nl, pl, ro, ru).
- **Tests — avatar**: 23 new tests in `backend/tests/test_avatar.py` covering JPEG and PNG upload, file content written to disk, URL format and cache-buster, invalid type rejection (400), oversized file rejection (400), auth guard (401), re-upload with same and different format (old file deleted), legacy base64 avatar handled gracefully, deletion clearing the DB field and removing the file, deletion with no prior avatar, and `GET /api/auth/me` reflecting avatar state after upload and delete.
- **Study Plan — Start button**: active unit card in `/plan` now shows a direct Start button without requiring the user to open the unit drawer first. The button appears only when today's lesson has been generated; if no lesson is available the card behaves as before. Fetches `/api/study-plan/today` in parallel with the existing plan and competency requests.
- **Lesson — Exit button**: a `✕` button in the lesson header lets users leave a lesson mid-way. Clicking it shows a confirmation dialog (using the shared `ConfirmDialog` component with `danger` styling) warning that progress will be lost; confirming navigates to `/dashboard`. Three new i18n keys added to the `lesson` namespace across all 10 locale files: `exit`, `exitConfirmTitle`, `exitConfirmMessage`.

### Changed
- **Avatar storage**: profile photos are no longer stored as base64 data URIs inside the `users.avatar` database column. On upload the image is now written to disk at `/app/avatars/{user_id}.{ext}`, persisted via a Docker volume (`${DATA_PATH}/avatars:/app/avatars`), and the column stores only the relative URL (`/api/avatars/{id}.ext?v={ts}`). The `?v=` cache-buster is refreshed on every re-upload. Existing base64 avatars remain visible and are replaced transparently on the user's next upload. `StaticFiles` mounted at `/api/avatars` in FastAPI; served to the browser through the existing Next.js `/api/:path*` rewrite proxy.

## [1.4.13] - 2026-05-13

### Fixed
- **Evaluation — critical bug**: last answer was silently dropped from the level-test submission due to a stale React closure. `handleNext` now reads from a `useRef` (`answersRef`) that is updated eagerly alongside state in `handleConfirmAnswer`, guaranteeing all N answers are always included in the payload sent to the backend.
- **Evaluation — DB consistency**: added missing `await db.refresh(plan)` after `db.commit()` in the `/api/assessment/level-test/submit` endpoint, consistent with every other endpoint in the router.
- **Evaluation — LLM error handling**: `json.JSONDecodeError` raised by `json.loads()` on a malformed LLM response was not caught in `generate_level_test_questions` or `evaluate_free_write`, causing a generic 500. Both functions now catch it and re-raise as `LLMError` → 502, while still letting `LLMTimeoutError` / `LLMUnavailableError` propagate for their specific HTTP status codes.
- **Evaluation — plan ID validation**: `planId` from the URL query string is now validated as a positive integer before being sent to the backend. Invalid values (`null`, `"abc"`, `0`) are caught client-side with a clear error message instead of sending `NaN` to the API.
- **Evaluation — subscription check order**: `loadQuestions` in the level-test page now bails out early when the user is not subscribed, preventing a spurious 402 network error from showing an opaque error panel instead of the `PaywallBanner`.

### Added
- **Evaluation — start warning dialog**: a `ConfirmDialog` is shown before starting both the initial placement assessment and the level-completion test, warning the user that leaving mid-evaluation will lose all progress and require a restart. Uses the shared `ConfirmDialog` component and follows the same UX pattern as the logout confirmation. Four new i18n keys added to the `assessment` namespace across all 10 locale files (en, es, de, fr, it, pt, nl, pl, ru, ro): `startWarningTitle`, `startWarningMessage`, `startWarningMessageLevelTest`, `startWarningConfirm`.

## [1.4.12] - 2026-05-13

### Added
- **Conversation starters**: 30 curated English-practice topics displayed as clickable chips in the voice conversation section. Six topics are chosen randomly on each component mount. Chips are hidden as soon as a session becomes active and reappear when it ends. Clicking a chip injects a synthetic `initialContext` message so the tutor opens naturally on that topic — no backend changes required.
- **i18n**: `startersHint` key added to the `conversation` namespace in all 10 locale files (en, es, de, fr, it, pt, pl, nl, ro, ru).
- **Assessment bank** expanded to 100 questions (A1–C2). New items cover B2, C1, and C2 levels across grammar, vocabulary, and reading comprehension. `MAX_QUESTIONS` per placement test raised from 12 to 15.
- **Usage Limits section in Settings**: read-only panel showing four progress bars — sessions/week, minutes/day, minutes/week, and tokens/month (in k-units). Data is fetched live from `GET /api/auth/quota` on page load; animate-pulse skeleton shown while loading; bars turn red when a limit is reached; unlimited metrics display a localised "Unlimited" label.
- **Terms of Service — section 5** updated across all 10 locales (en, es, de, fr, it, pt, pl, nl, ro, ru): added a sentence noting that the hosted service applies usage limits to AI tutoring features and that current usage is visible in account settings (no specific quantities stated).
- 8 new i18n keys added to the `settings` namespace in all 10 locale files: `sectionUsageLimits`, `quotaSessions`, `quotaMinutesDay`, `quotaMinutesWeek`, `quotaTokens`, `quotaUnlimited`, `quotaLoading`, `quotaHint`.

## [1.4.11] - 2026-05-12

### Added
- What's New modal: version-aware changelog overlay shown automatically on the dashboard on the first visit after an update. Follows the same pattern as OnboardingTour — localStorage-based, no backend required. Tour takes priority for new users; returning users see What's New only.

### Changed
- Legal texts updated across all 10 locales (en, es, de, fr, it, nl, pl, pt, ro, ru):
- Terms of Service: section 5 now mentions monthly **and** yearly subscription plans; section 6 clarifies the free trial period (payment details required; no charge until trial ends), annual billing cycle, and that current prices are displayed at checkout — no fixed prices are stated in the legal text.
- Privacy Policy: new data item `s2i8` discloses subscription status, plan type, and Stripe customer identifier stored for paid subscribers; section 4 (External Services) now explicitly names Stripe, Inc. (USA) as payment processor and links to its Privacy Policy; section 6 (GDPR rights) extends the international transfers disclosure to include Stripe alongside OpenAI, both covered by Standard Contractual Clauses (Art. 46 GDPR).
- Privacy Policy page component (`privacy/page.tsx`): `s2Items` array extended to render the new `s2i8` data item.
- Real-time voice conversation: improved with a new voice for a more natural and engaging experience.

### Fixed
- Various minor bug fixes and stability improvements.

## [1.4.10] - 2026-05-12

### Added
- What's New modal: version-aware changelog overlay shown automatically on the dashboard on the first visit after an update. Follows the same pattern as OnboardingTour — localStorage-based, no backend required. Tour takes priority for new users; returning users see What's New only.

### Changed
- Real-time voice conversation: improved with a new voice for a more natural and engaging experience.

### Fixed
- Various minor bug fixes and stability improvements.

## [1.4.9] - 2026-05-12

### Fixed
- Voice conversation: fixed out-of-order TTS playback caused by a race condition in `decodeAudioData`. Audio chunks are now serialized via a promise chain so they are always decoded and scheduled in the exact order they were enqueued, regardless of individual decoding time.

## [1.4.8] - 2026-05-12

### Added
- Pricing section: crossed-out original prices (19.95 €/month, 199.50 €/year) shown above current launch prices using `text-fl-muted-2 line-through`.
- `pricingLabel` i18n key updated to "Launch Offer" in all 10 locales (es, en, de, fr, it, pt, nl, pl, ro, ru).

### Changed
- `conversation_weekly_sessions` reset to `0` (unlimited) in `apply_subscription_quotas` — session count is not used as a quota; time limits (daily/weekly minutes) are the only active constraints.
- docs/index.html: hero CTA updated to feature hosted service link (freelingo.app); "Open Source" section now mentions the managed hosted option.

### Fixed
- Locale detection in `middleware.ts` now splits on `/[-_]/` instead of `'-'` so mobile browsers that send `Accept-Language` values like `es_ES` (underscore) are correctly resolved instead of falling back to English.
- Admin user detail page: saving quota limits now immediately refetches `/api/admin/users/{id}/quota` so the "Cuotas de conversación" display reflects the new limits without requiring a page reload.
- System prompts (chat and voice): added `SCOPE`, `CONTENT POLICY`, and `PERSONA LOCK` as top-priority mandatory rules to prevent the LLM from writing code, doing homework, producing harmful content, or being jailbroken via roleplay/persona requests. User-supplied context (`bio`, `learning_goals`) is now explicitly labelled as non-authoritative data that cannot override system rules. Chat prompt also gains `ALWAYS respond in English` parity with the voice prompt.

## [1.4.7] - 2026-05-11

### Fixed
- Alembic migration `0017` revision ID shortened from 38 to 23 characters to fit the `varchar(32)` limit of the `alembic_version` table; migration file renamed to `0017_fix_tokens_default.py`.
- Stripe Checkout Session now passes `allow_promotion_codes=True` so the promo code field is visible to users.

## [1.4.6] - 2026-05-11

### Fixed
- `monthly_tokens_limit` server-default in PostgreSQL corrected from `0` (unlimited) to `1000000`, aligning it with the ORM default; new migration `0017_fix_monthly_tokens_server_default`.

### Changed
- README: added **Hosted service** section with link to [freelingo.app](https://freelingo.app) to make the managed subscription option visible.

## [1.4.5] - 2026-05-11

### Added
- `BLOCKED_EMAIL_DOMAINS` env var: JSON array of blocked email domain strings (e.g. disposable/temporary providers like `yopmail.com`). Registrations using a blocked domain are rejected with HTTP 422 before any DB access. Defaults to `[]` (no blocking). Configurable via `.env` and `docker-compose.yml`.
- Password strength policy upgraded: minimum 10 characters, maximum 25, requires at least one uppercase letter, one number, and one symbol. Enforced in backend schemas (`RegisterRequest`, `UserUpdateRequest`, `ResetPasswordRequest`, `AdminUserCreate`) and client-side in the register form. `invalidPassword` i18n key updated in all 10 locales.
- Landing footer: added GitHub link pointing to the project repository (`https://github.com/ArtCC/freelingo`), opens in a new tab. `github` i18n key added to all 10 locales.

### Changed
- Landing footer: removed "Open source · Self-host free or subscribe to the hosted service" tagline from the copyright line.
- Register error handling: blocked email domain (`Email domain not allowed`) now maps to the existing `invalidEmail` i18n key instead of showing a raw backend message.

### Fixed
- Onboarding tour resets on logout: `logout()` in the auth store now removes `fl_tour_done` from `localStorage`, so the tour is shown again on the next login regardless of which logout path is used (sidebar, settings, or silent 401 redirect).

## [1.4.4] - 2026-05-10

### Fixed
- Landing page: pricing section now shows immediately for unauthenticated users (no loading state); authenticated users see a full-screen loading overlay (backdrop blur, same pattern as onboarding tour) while subscription status is verified, avoiding layout shifts or premature reveals
- Middleware: inverted auth logic from public-routes whitelist to protected-routes list; unknown URLs now reach the Next.js 404 handler instead of being redirected to `/login`

## [1.4.3] - 2026-05-10

### Added
- Onboarding tour modal on first dashboard visit: 6-step guided walkthrough covering chat, voice, flashcards, study plan, and getting started; shown once per browser via `localStorage` (`fl_tour_done`); dismissible at any step with skip or navigation arrows; `tour` i18n namespace added in all 10 supported locales

### Fixed
- Landing pricing section (`PricingSection`) now uses server-side `stripeEnabled` prop directly (removed dependency on `useConfigStore` which was always `false` before hydration, causing the section to never render for anonymous users)
- Users with an active or trialing subscription are now correctly identified via `/api/auth/refresh` + `/api/auth/me` on the landing page, hiding the pricing section when already subscribed

## [1.4.2] - 2026-05-10

### Fixed
- Admin users list: subscription status tags (`active`, `trial`, `past due`) now use i18n keys via `tBilling` instead of hardcoded English strings
- Stripe webhook handlers: replaced `getattr()` with `_sget()` helper that handles both `StripeObject` (production, SDK v15+) and plain dicts (test mocks); fixes 4 failing CI tests

### Changed
- Landing page pricing section extracted to `PricingSection` client component; section is now hidden for users who already have an active or trialing subscription
- Restored `pricingLabel` heading above `pricingTitle` in the pricing section

## [1.4.1] - 2026-05-10

### Fixed
- Stripe webhook handler: replaced `.get()` calls with `getattr()` on `StripeObject` instances, required since SDK v15.0.0 where `StripeObject` no longer inherits from `dict`
- `current_period_end` now read from `SubscriptionItem` (via `sub.items.data[0].current_period_end`) in addition to the subscription root, as the field moved to `SubscriptionItem` in Stripe API v2025-03-31 (SDK v12+); both locations are tried for forward and backward compatibility
- Added `_subscription_period_end()` helper used by both `_handle_checkout_completed` and `_handle_subscription_updated` handlers
- Separated `STRIPE_BASE_URL` from `APP_BASE_URL` so Stripe redirect URLs can point to a different domain than email links

## [1.4.0] - 2026-05-10

### Added
- **Phase 5: Stripe subscriptions & paywall** — optional hosted subscription layer; self-hosted deployments are unaffected (`STRIPE_ENABLED=false` default)
- Six new environment variables: `STRIPE_ENABLED`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_MONTHLY`, `STRIPE_PRICE_YEARLY`, `STRIPE_TRIAL_DAYS` (default 7)
- Alembic migration `0016_stripe_subscription`: adds `stripe_customer_id`, `subscription_status` (default `'none'`), `subscription_ends_at` to `users`
- `subscription_service.py`: `is_subscribed()` helper and `apply_subscription_quotas()` (sets 3 sessions / 90 min/week / 1M tokens on activation)
- `require_subscription` FastAPI dependency (HTTP 402 `subscription_required` when paywall is active and user lacks a valid plan)
- Six backend routers protected by `require_subscription`: chat, lessons, flashcards, study_plan, conversation (WebSocket inline check), assessment level-test
- Assessment onboarding endpoints (`/start`, `/submit`, `/evaluate`, `/free-write`, `/complete`) remain public so new users can complete initial assessment before subscribing
- `GET /api/config` — public endpoint returning `stripe_enabled` and `stripe_trial_days`
- Billing router (`POST /api/billing/checkout`, `POST /api/billing/portal`, `POST /api/billing/webhook`) registered only when `STRIPE_ENABLED=true`; webhook verifies Stripe signature before processing
- Webhook handlers for four Stripe events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`
- Admin can manually override `subscription_status` and `subscription_ends_at` via `PATCH /api/admin/users/{id}`
- `store/config.ts` (frontend): fetches `/api/config` on app load, exposes `stripeEnabled` and `stripeTrialDays`
- `store/auth.ts`: `User` type extended with `subscription_status` and `subscription_ends_at`; exported `isSubscribed()` helper
- `PaywallBanner` and `PaywallGate` components: paywall overlay with monthly (14.95€) and yearly (149.50€) plan buttons; renders nothing when Stripe is disabled
- `PaywallGate` applied to six frontend pages: `/chat`, `/conversation`, `/flashcards`, `/dashboard`, `/lesson/[id]`, `/assessment/level-test`
- Settings page: subscription status badge, next billing date, "Manage subscription" portal link, "Subscribe" CTA — section hidden when Stripe is disabled
- Landing page: pricing section (two plan cards) conditionally rendered when `STRIPE_ENABLED=true`
- `/billing/success` page: refreshes auth state, auto-redirects to dashboard after 5 s
- `/billing/canceled` page: "no charge made" message with links to dashboard and settings
- `billing` i18n namespace in all 10 supported locales (en, es, de, fr, it, nl, pl, pt, ro, ru)
- `tests/test_billing.py`: 14 tests covering `is_subscribed`, config endpoint, paywall dependency, checkout, portal, and all four webhook events (Stripe SDK fully mocked)

## [1.3.19] - 2026-05-10

### Added
- Account deletion confirmation email: when a user deletes their own account via `DELETE /api/auth/me`, a transactional email is sent in the user's native language confirming the deletion and including a security notice; admin-initiated deletions do not trigger this email
- `send_account_deleted_email` function in `email_service.py` with `_DELETION_I18N` translations for all 10 supported locales
- `account_deleted.html` email template (no CTA button, plain confirmation + security footer)

### Fixed
- Romanian `link_fallback` in `_VERIFY_I18N` and `_RESET_I18N`: `lipirii` (noun genitive) corrected to `lipește` (imperative verb)
- Romanian `step1` in `_WELCOME_I18N`: `Faci` (indicative) corrected to `Fă` (imperative), consistent with the other steps
- `welcome.html` email template: added `margin-bottom: 20px` to `.btn` so the CTA button has breathing room before the footer divider

## [1.3.18] - 2026-05-10

### Added
- Learning goals selection in onboarding step 2: 8 goal categories (travel, work, academic, daily, media, emigration, exams, social) stored as JSON in `users.learning_goals`; injected into LLM system prompt for both text chat and voice conversation
- User bio field in settings (max 500 chars): free-text context injected into LLM prompts alongside learning goals
- Alembic migration `0015_user_learning_profile`: adds `bio TEXT` and `learning_goals TEXT` columns to `users`
- `PATCH /api/auth/me` now accepts `bio` and `learning_goals`; both fields included in `UserResponse`
- Onboarding page rewritten as a 2-step flow: step 1 = English variant selector, step 2 = learning goals grid
- i18n keys `onboarding.goals.*` and `settings.bio/bioPlaceholder/bioHint` added in all 10 locales

### Fixed
- Animated avatar halos in voice conversation: halo is always visible (subtle `animate-halo-idle`) and intensifies when speaking (`animate-halo-speaking`); `px-2` on transcript container prevents horizontal scrollbar from halo overflow
- Quota widget in voice conversation replaced with a collapsible `QuotaPill` pill (single summary line, expands to detail bars on click)
- `validate_inactivity_timeout` validator in `UserUpdateRequest` was missing `return v` and had incorrect type hint `Optional[str]` instead of `Optional[int]`, causing the field to always be set to `None`; both corrected

## [1.3.17] - 2026-05-10

### Fixed
- Alembic migration `0014_monthly_token_quota` had incorrect `down_revision = "0013"` — corrected to `"0013_email_verification"` to match the actual revision ID pattern used across all migrations; was causing `KeyError: '0013'` on startup, blocking login

## [1.3.16] - 2026-05-10

### Added
- Monthly token quota per user (`monthly_tokens_limit` field on `User`, 0 = unlimited); admin can set it per-user via PATCH; chat and voice conversation are blocked with a clear error when the monthly limit is exceeded
- `get_monthly_tokens_used()` and `check_monthly_tokens()` helpers in `quota_service`; `GET /api/auth/quota` now includes `tokens_this_month`, `tokens_monthly_limit`, `tokens_unlimited`
- Voice conversation `ConversationMode` shows a monthly-token progress bar alongside sessions and minutes; handles `quota_exceeded_tokens` WebSocket error code
- Admin user-edit page includes a "Monthly tokens limit" field (0 = unlimited)
- i18n keys `quotaTokens`, `quotaExceededTokens`, `quotaMonthlyTokens` added in all 10 locales

## [1.3.15] - 2026-05-09

### Fixed
- `Strict-Transport-Security` header removed from backend middleware — the header was emitted over plain HTTP internally (Cloudflare tunnel terminates TLS), causing browsers to cache an HSTS policy that blocked subsequent visits with a hard security error. HSTS should be configured at the Cloudflare edge (SSL/TLS → Edge Certificates → HSTS), not by the origin server

## [1.3.14] - 2026-05-09

### Added
- `/health` endpoint now checks DB, Redis, TTS, and STT dependencies; returns HTTP 503 with `{"status": "degraded", "checks": {...}}` if any dependency is unreachable (previously always returned 200)
- `health()` method added to `KokoroTTSService`, `OpenAITTSService`, `WhisperSTTService`, and `OpenAISTTService`
- `SECRET_KEY` startup validation in `lifespan`: server refuses to start if the value contains `CHANGE_ME` or is shorter than 32 characters
- `error.tsx` (global error boundary) and `not-found.tsx` (404) pages with FreeLingo branded design — monospaced layout consistent with the rest of the app; i18n in all 10 locales (`error.*`, `notFound.*`)
- Cookie consent banner (`CookieBanner` component) fixed to the bottom of every page; persists acceptance in `localStorage`; links to Privacy Policy; i18n in all 10 locales (`cookieBanner.*`)
- Welcome email sent on registration (`send_welcome_email`): 3-step onboarding guide (Assessment → Study Plan → first lesson); HTML template `welcome.html` follows the same design as `verify_email.html` and `reset_password.html`; i18n in all 10 locales
- `UVICORN_WORKERS` environment variable (default `4` in `docker-compose.yml`, `1` in `Dockerfile`); documented in `.env.example` with sizing guidance (`2 × CPU cores + 1`)

## [1.3.13] - 2026-05-09

### Fixed
- `/forgot-password`, `/reset-password`, and `/verify-email` added to `PUBLIC_ROUTES` in Next.js middleware — unauthenticated users were redirected back to `/login` before reaching these pages, making "Forgot your password?" appear to do nothing
- Redundant Redis delete of invite token in `POST /api/auth/register` removed — the token was already deleted during validation; the second `await redis.delete(...)` call was unreachable when `ALLOW_REGISTRATION=true` and a no-op otherwise

### Added
- 4 edge-case tests for email system: `test_resend_verification_no_email` (→ 400), `test_resend_verification_email_disabled` (→ 503), `test_verify_email_token_consumed_after_use` (second call → 400), `test_reset_password_token_consumed_after_use` (second call → 400)

## [1.3.12] - 2026-05-09

### Added
- Email verification system: `is_verified` column on `User`, `GET /api/auth/verify-email`, `POST /api/auth/resend-verification` endpoints
- Password reset flow: `POST /api/auth/forgot-password` (anti-enumeration, always 200) and `POST /api/auth/reset-password` endpoints
- Verification and reset tokens stored in Redis with TTL (24h / 1h respectively)
- Transactional emails sent via SMTP using `fastapi-mail` + `aiosmtplib`; email body localised to the user's native language (10 locales)
- Generic SMTP configuration: `EMAIL_ENABLED`, `SMTP_HOST/PORT/USER/PASSWORD/FROM/TLS/SSL`, `APP_BASE_URL` — works with Gmail, Brevo, Resend, Google Workspace, etc.
- Non-blocking email verification banner in the app layout with "Resend verification email" button
- Frontend pages: `/verify-email`, `/forgot-password`, `/reset-password`
- "Forgot your password?" link on the login page
- DB migration `0013_email_verification` — adds `is_verified` column (existing users set to `true`)
- Admin can toggle `is_verified` for any user via `PATCH /api/admin/users/{id}` and the user detail page
- All new i18n keys added to all 10 locale files (`verifyEmailBanner`, `verifyEmailSent`, `resendVerification`, `forgotPassword`, `verifyEmail.*`, `forgotPassword.*`, `resetPassword.*`, admin keys)
- SMTP and registration env vars (`ALLOW_REGISTRATION`, `FIRST_USER_IS_ADMIN`) now explicitly declared in `docker-compose.yml`

## [1.3.11] - 2026-05-09

### Added
- `POST /api/conversation/warmup` endpoint: pre-heats TTS and STT models synchronously before a session starts; frontend awaits it before opening the WebSocket so the first transcription/synthesis is instant
- New `warming` status in `ConversationMode` — sidebar shows "Loading models..." while warmup runs, with pulsing indicator
- `statusWarming` i18n key added to all 10 locale files
- Contact link added to landing page footer and docs landing nav
- "Sobre mí" / "About me" link added to landing page footer (new tab)
- Footer link order in landing: Contact · About me · Privacy · Terms
- Author section in Settings now includes website link and Contact (`mailto:`) alongside GitHub, with `websiteLink` and `contactLink` i18n keys in all 10 locales

### Fixed
- Version number misalignment between desktop and mobile sidebar (both now show `v1.3.11`)

## [1.3.10] - 2026-05-09

### Added
- `conversation_weekly_minutes` quota field visible and editable in admin user detail page
- `quotaWeeklyMinutes` and `quotaUsedWeeklyMinutes` i18n keys added to all 10 locale files
- Native language selector now sorted alphabetically by translated name in register, settings, and admin pages

### Fixed
- `ro` (Romanian) missing from `SUPPORTED_LANGUAGES` whitelist in `schemas/auth.py` and `schemas/admin.py` — registration with Romanian as native language returned 422

## [1.3.9] - 2026-05-09

### Added
- Interface languages: Polish (pl), Dutch (nl), Romanian (ro), Russian (ru)
- Native language options expanded to include pl, nl, ro, ru
- New `conversation_weekly_minutes` quota field (default 90 min/week, 0 = unlimited) — tracks total voice conversation time per week independently of session count

### Changed
- Conversation quota defaults: `weekly_sessions` set to 0 (unlimited); `daily_minutes` 30; `weekly_minutes` 90
- `conversation_weekly_sessions` default reverted to 0 (unlimited) — use `weekly_minutes` to control weekly usage

## [1.3.8] - 2026-05-09

### Fixed
- Conversation quota: daily minutes now checked before incrementing the weekly session counter, preventing a wasted session slot when the daily limit is already exhausted

## [1.3.7] - 2026-05-09

### Changed
- Landing page CTA button for authenticated users changed from "Dashboard" / "Panel" / "Tableau de bord" / "Painel" to "Continue" / "Continuar" / "Continuer" / "Continuar" / "Weiter" / "Continua" across all 6 locales

## [1.3.6] - 2026-05-09

### Added
- Public landing page at `/` with sticky nav, hero, feature cards, and footer; i18n in 6 languages (en, es, fr, pt, de, it)
- `landing` i18n section in all 6 locale files
- Legal documents completely rewritten for dual-mode operation (self-hosted + hosted service):
- Terms of Service: 10 sections covering both modalities, subscription & billing, governing law (Spain), 14-day EU withdrawal right
- Privacy Policy: 8 sections including data controller identification, external AI services (OpenAI + Standard Contractual Clauses), GDPR rights, right to lodge complaint with supervisory authority (AEPD/CNIL/BfDI/Garante/CNPD), legal basis of processing (Art. 6(1)(b) GDPR), international transfers
- Minimum age requirement (16 years, GDPR Art. 8) added to Terms s3 and Privacy s2 in all 6 locales
- `landing.footer` updated to reflect dual-mode availability (open source · self-host free or subscribe to hosted service)
- `common.tagline` updated: removed "self-hosted" qualifier

### Changed
- TTS/STT refactored to provider pattern: `TTS_PROVIDER=local|openai` and `STT_PROVIDER=local|openai`; each resolved independently at startup
- `TTS_ENABLED` / `STT_ENABLED` env vars removed; provider selection replaces them
- `RATE_LIMIT_STORAGE` env var removed; Redis is now mandatory and always used for rate limiting
- `backend/app/core/limiter.py` hardcoded to `REDIS_URL`
- Middleware updated: `/` is now an exact-match public route (not prefix), preventing all authenticated routes from being treated as public
- README updated to reflect dual-mode operation, provider pattern for TTS/STT, and new badge

### Fixed
- Contact email updated in Privacy Policy s8 across all 6 locales
- German typo in Privacy s6Body: `auszuuüben` → `auszuüben`

## [1.3.5] - 2026-05-06

### Fixed
- Admin user detail page crashed with 500 error for users with a study plan: `AdminUserStatsResponse.current_unit` was typed `Optional[int]` but the database stores it as a string (e.g. `'a1-unit-1'`); changed to `Optional[str]`
- Admin user detail page: "Lang" label and "XP & Progreso" section title were hardcoded; now use i18n keys `admin.fieldNativeLanguage` and `admin.sectionXpProgress`; language code value now displays the full translated language name via `languages.*`
- Admin user detail page: error messages "Failed to load user data" and "User not found" were hardcoded in English; now use i18n keys `admin.loadError` and `admin.userNotFound`
- Admin users list: `nav.admin` sidebar label was already wired to i18n but confirmed working across all 6 locales

### Added
- i18n keys added to all 6 locales: `admin.fieldNativeLanguage`, `admin.sectionXpProgress`, `admin.loadError`, `admin.userNotFound`

## [1.3.4] - 2026-05-06

### Added
- Token consumption tracking: new `llm_usage` table (Alembic migration `0010_llm_usage`) stores `prompt_tokens`, `completion_tokens`, `total_tokens` per user per call with `source` (`chat`/`conversation`). Capture is fully optional — if the provider does not return usage data the row is simply not created and nothing fails
- `LLMStream` wrapper in `llm_adapter.py` captures token usage from the final stream chunk for Ollama, OpenAI and DeepSeek (`stream_options={"include_usage": True}`); Anthropic usage is wired but remains `None` until its SDK path is refactored
- `GET /api/admin/users/{user_id}/stats` endpoint returns aggregated stats per user: current CEFR level and unit, plan duration, completion test score, total XP, streak, active days, lessons completed, exercises correct/total, tutor chat messages sent, and token consumption by source
- `AdminUserStatsResponse` Pydantic schema
- Admin user detail page (`/admin/users/[id]`) showing all stats in labelled sections
- User ID (`#id`) shown in each row of the admin users list
- "View stats" button per row linking to the detail page
- Search/filter input in the admin users list (filters by username or email, debounced 300 ms, resets pagination)
- i18n keys in all 6 locales: `admin.statsTitle`, `admin.statsCefr`, `admin.statsUnit`, `admin.statsPlanWeeks`, `admin.statsXp`, `admin.statsStreak`, `admin.statsActiveDays`, `admin.statsLessons`, `admin.statsExercises`, `admin.statsMessages`, `admin.statsTokensTotal`, `admin.statsTokensChat`, `admin.statsTokensConversation`, `admin.statsTokensNote`, `admin.statsNoData`, `admin.viewStats`, `admin.weeks`, `admin.statsDays`, `admin.statsTestScore`, `admin.searchPlaceholder`

### Changed
- Admin users list ordered alphabetically by `username` (was `created_at DESC`)

## [1.3.3] - 2026-05-05

### Added
- Button "Continue in voice" in the AI tutor chat header: appears when a conversation has messages and is idle (not sending). Clicking it serialises up to the last 20 non-empty messages into `sessionStorage` and navigates to the real-time voice conversation page
- Voice conversation page reads and clears the `voice_context` key from `sessionStorage` on mount and passes it to `ConversationMode` as `initialContext`
- `ConversationMode` accepts optional `initialContext` prop and includes it in the WebSocket auth handshake payload when present
- Backend WebSocket endpoint extracts and sanitises the optional `context` field from the auth message (max 20 entries, valid roles, non-empty content) and passes it to `ConversationPipeline`
- `ConversationPipeline` accepts `initial_context` parameter and pre-populates `self.history` with up to the last 10 valid turns, so the AI continues the text-based tutoring session seamlessly in voice
- `ChatContextItem` TypeScript interface exported from `lib/conversation-ws.ts`
- i18n key `chat.continueInVoice` added to all 6 locale files (EN, ES, FR, DE, IT, PT)
- 8 new unit tests for `ConversationPipeline.initial_context`: covers empty/None input, valid population, truncation to 10, invalid-role filtering, empty-content filtering, non-dict entry filtering, and extra-key stripping

## [1.3.2] - 2026-05-05

### Added
- Content policy rule added to tutor chat and real-time conversation system prompts: the AI must decline and redirect any sexual, violent, hateful, or otherwise inappropriate content
- Terms of Use and Privacy Policy pages added to the platform
- i18n keys `admin.fieldUsername`, `admin.fieldEmail`, `admin.fieldPassword`, `admin.fieldDisplayName`, `admin.submitCreate` added to all 6 locale files

### Changed
- Admin create-user form: placeholder labels (Username, Email, Password, Display Name) and submit button (Create) now use i18n keys instead of hardcoded English strings

## [1.3.1] - 2026-05-04

### Added
- User avatar: upload (JPEG/PNG, max 2 MB), client-side resize to 1024×1024 via Canvas API, stored as base64 data URI in DB; circular avatar shown in settings, sidebar (desktop 32×32 and mobile 28×28) and chat bubbles (28×28)
- Avatar placeholder with user initial shown when no avatar is set
- Tutor logo (`/logo.png`) shown as avatar in chat message bubbles
- `POST /api/auth/me/avatar` and `DELETE /api/auth/me/avatar` endpoints (FastAPI `UploadFile`, type+size validation, base64 encoding)
- Alembic migration `0009_user_avatar.py`: adds `avatar TEXT NULL` column to `users`
- Alembic migration `0008_cascade_delete_user.py`: adds `ON DELETE CASCADE` to all user-owned FK constraints (`flashcards`, `study_plans`, `progress`, `chat_history`, `lessons`, `exercises`), fixing silent failures when deleting a user from admin
- Logout confirmation dialog in settings page (reuses existing `logoutConfirmTitle/Message` keys)
- i18n keys in all 6 locales: `settings.avatarChange`, `settings.avatarRemove`, `settings.avatarUploading`, `settings.avatarTypeError`, `settings.avatarSizeError`
- i18n keys in all 6 locales: `flashcards.refresh`, `flashcards.generateBtn`, `flashcards.cards` (for card count options: "5 cards", "10 cards", etc.)
- i18n keys in all 6 locales: `admin.roleUser`, `admin.roleAdmin`
- `avatar?: string | null` field added to `User` interface (frontend Zustand store) and `UserResponse` schema (backend)

### Changed
- `flashcards.noDue` translation updated to "No cards due for review" (and equivalents in all locales)
- Flashcards page: `+ Generate` button, `{n} cards` option labels, "No cards due for review" text and "Refresh" button now use i18n keys
- Chat sidebar: `+ New` button now uses `t('newConversation')` i18n key
- Admin users list: role badge (`user`/`admin`) and `inactive` badge now use i18n keys instead of hardcoded English strings

### Fixed
- Admin: deleting a user now correctly removes all associated data thanks to `ON DELETE CASCADE`; delete error was previously only visible inside the create-user form panel — now shown globally
- Login/register: raw backend validation errors (e.g. Pydantic email format messages) no longer shown to the user; all errors mapped to translated strings (`invalidEmail`, `usernameTaken`, `emailTaken`, `registrationClosed`, `invalidInvite`, generic fallback)
- i18n keys `auth.register.usernameTaken`, `auth.register.emailTaken`, `auth.register.invalidInvite`, `auth.login.invalidEmail` added to all 6 locale files

## [1.3.0] - 2026-05-04

### Added
- Phase 4 — Target language selection: `english_variant` field replaced by generic `target_language` (BCP-47) across the entire stack
- Alembic migration `0007_target_language.py`: adds `target_language` column to `users` and `study_plans`, back-fills existing rows (`american` → `en-US`, `british` → `en-GB`), drops `english_variant`
- `SUPPORTED_TARGET_LANGUAGES: set[str] = {"en-US", "en-GB"}` constant in `app/schemas/auth.py`; new `target_language` field with validator on `RegisterRequest` and `UserUpdateRequest`; `UserResponse` exposes `target_language`
- `app/services/language_helpers.py`: `get_english_variant(target_language)` and `get_iso639(target_language)` helpers used across the service layer
- `target_language` column added to `StudyPlan` model and recorded from the authenticated user at `POST /api/assessment/complete`
- Auto-login on register: `POST /api/auth/register` now issues a JWT access token and sets the refresh token cookie in the same response, returning `{ id, username, role, access_token }`
- `/onboarding` page (`src/app/(auth)/onboarding/page.tsx`): post-registration screen where new users choose their English variant; placed in the `(auth)` route group (no sidebar)
- `TargetLanguageSelector` component (`src/components/onboarding/TargetLanguageSelector.tsx`): flag cards for `en-US` and `en-GB` with i18n display names and descriptions
- `src/lib/target-languages.ts`: `SUPPORTED_TARGET_LANGUAGES` constant on the frontend — single place to add a new target language
- i18n namespaces `onboarding` (`headline`, `subtitle`, `cta`) and `targetLanguages` (`en-US`, `en-US-description`, `en-GB`, `en-GB-description`) added to all six locale files (en, es, fr, pt, de, it)

### Changed
- Register flow: after successful registration the frontend stores the returned `access_token` and redirects to `/onboarding` instead of `/login?registered=true`
- `FlashcardGenerateRequest`: `native_language` field removed — the backend now always reads `native_language` from the authenticated user's profile, ignoring any client-supplied value
- `ConversationPipeline`: `native_language` and `english_variant` (derived from `target_language`) are now injected into `CONVERSATION_SYSTEM_PROMPT`; previously both were absent from the voice tutor context
- All services (`lesson_generator`, `flashcard_sm2`, `chat`, `conversation_pipeline`, `stt_service`) updated to consume `target_language` instead of `english_variant`; STT `language` parameter derived dynamically via `get_iso639`
- Settings page: English variant selector removed — the choice is made during onboarding and is not surfaced in the UI afterwards

### Removed
- i18n keys `settings.englishVariant`, `settings.american`, `settings.british`, `auth.register.englishVariant`, `auth.register.american`, `auth.register.british` removed from all locale files

## [1.2.6] - 2026-05-03

### Changed
- Conversation mode: LLM now always responds in English regardless of the language the student uses; if the student speaks in another language the tutor replies in English and gently encourages them to try in English
- License changed from Apache 2.0 to GNU Affero General Public License v3 (AGPL v3)
- `DurationOption` interface cleaned up: `label`, `sublabel`, and `approxLessons` string fields removed; `intensity` typed as `'intensive' | 'standard' | 'relaxed' | 'very_relaxed'`; `GOAL_OPTIONS` entries no longer carry a `label` field — all display strings are now derived from translations at render time

### Added
- Full i18n coverage for all previously hardcoded UI strings across 6 locale files (en, es, fr, pt, de, it):
- `common.close`
- `grammar.explanation`, `grammar.backLink`
- `plan.unitLabel`, `plan.grammarCovered`, `plan.noLessons`, `plan.weekDay`, `plan.lessonTypes.*` (grammar / vocabulary / reading / writing / conversation / review / level_test), `plan.levelComplete`, `plan.levelCompleteDesc`, `plan.levelCompleteHint`, `plan.beginLevelTest`, `plan.nLessons`, `plan.nGrammar`, `plan.levelTestLabel`, `plan.unitAriaLabel`
- `assessment.step1/2/3`, `assessment.studiedBefore`, `assessment.studiedBeforeHint`, `assessment.beginnerOption/Hint`, `assessment.hasExperienceOption/Hint`, `assessment.skills.*`, `assessment.howManyWeeks`, `assessment.nWeeks`, `assessment.intensity.*` (intensive / standard / relaxed / veryRelaxed), `assessment.approxLessons`, `assessment.daysPerWeek`, `assessment.mainGoals`, `assessment.goals.*`, `assessment.summaryLevel/Duration/Goals`, `assessment.noneSelected`, `assessment.buildingPlan`, `assessment.startMyPlan`
- `common.tagline`, `voiceRecorder.*` (6 keys), `audioPlayer.*` (4 keys), `languages.*` (5 language names per locale)
- `grammar/[slug]/page.tsx`, `UnitDrawer.tsx`, `LevelTestBanner.tsx`, `UnitCard.tsx`, `BeginnerGate.tsx`, `AdaptiveQuizCard.tsx`, `DurationSelector.tsx` now use `useTranslations` — no hardcoded English strings remain in these components
- `VoiceRecorder.tsx` and `AudioPlayer.tsx` use `useTranslations('voiceRecorder')` / `useTranslations('audioPlayer')`
- Login and register pages render the app tagline via `tCommon('tagline')`
- ADMIN nav badge rendered via `tNav('admin')`
- Phrasebook register badge rendered via `t(phrase.register)` using existing `phrasebook.formal/neutral/informal` keys
- `LANGUAGES` constant simplified to `['es','fr','pt','de','it'] as const`; display names resolved at render time via `useTranslations('languages')` in register, settings, and admin pages

### Fixed
- Email, password, and confirm-password inputs across login, register, settings, and admin pages now set `autoCorrect="off"`, `autoCapitalize="none"`, and `spellCheck={false}` to prevent mobile keyboards from corrupting typed values

## [1.2.5] - 2026-05-03

### Fixed
- `Content-Security-Policy` corrected to add `'wasm-unsafe-eval'` to `script-src`, allowing onnxruntime-web WASM modules (VAD / Silero model) to instantiate without breaking other CSP restrictions
- `script-src` extended with `'unsafe-inline'` required for Next.js hydration; `style-src 'unsafe-inline'` added for Tailwind inline styles; `connect-src 'self' ws: wss:` for API and WebSocket calls; `media-src blob:` and `worker-src blob:` for TTS audio playback and VAD workers; `img-src data: blob:` for flag images
- Login regression introduced by the restrictive CSP is resolved

## [1.2.4] - 2026-05-03

### Security
- Rate limit 5/min added to `POST /api/auth/register` to prevent account enumeration and resource abuse (A-01)
- WebSocket authentication token now sent as first JSON message after `accept()` instead of as URL query parameter, preventing token exposure in server logs and browser history (A-02)
- Audio uploads to STT endpoint capped at 50 MB; requests exceeding the limit return HTTP 413 (A-03)
- `max_length=5000` enforced on TTS text and chat message fields via Pydantic (A-04)
- `RATE_LIMIT_STORAGE=redis` set as default in `docker-compose.yml` and `.env.example` so rate limit counters are shared across workers in production (M-01)
- `Content-Security-Policy: default-src 'self'; object-src 'none'; base-uri 'self'` header added to backend middleware and Next.js config (M-02)
- `PATCH /api/auth/me` now returns HTTP 409 instead of 500 when the requested email is already used by another account (M-03)
- `AdminUserCreate` schema validates email with `EmailStr` and restricts `native_language` to the `SUPPORTED_LANGUAGES` whitelist (M-04)
- Assessment quiz sessions migrated from in-process dict (`_sessions`) to Redis with 30-minute TTL, fixing multi-worker inconsistency and memory leak (M-05)
- Rate limit 20/min added to `POST /api/auth/refresh` (M-06)
- `GET /api/admin/users` supports `skip`/`limit` pagination (default 20/page) with `total` count; frontend renders Previous/Next controls (M-07)
- Rate limiter `key_func` updated to read `X-Real-IP` header set by nginx before falling back to socket address, ensuring per-client limits work correctly behind a reverse proxy (B-01)
- `correct_answer` and `correct` fields stripped from assessment quiz responses before sending to the client (B-03)
- `bcrypt` version constraint relaxed to `>=4.0.0` (removed `<4.0.0` upper bound) to allow security patches in future major versions (B-04)
- CORS `allow_methods` restricted to explicit list (`GET POST PUT PATCH DELETE OPTIONS`) instead of `"*"` (I-04)

### Added
- Pagination controls (Previous / Next) on the admin users page
- `prevPage` and `nextPage` i18n keys added to all six translation files (en, es, fr, pt, de, it)
- `PaginatedAdminUsersResponse` schema with `items`, `total`, `skip`, `limit` fields

### Fixed
- `RATE_LIMIT_ENABLED=false` set in test conftest so rate limits do not interfere with integration tests running under the same IP
- `test_list_users_as_admin` updated to assert on paginated response shape (`items`, `total`) instead of a flat list

## [1.2.3] - 2026-05-03

### Fixed
- WebSocket URL now always derived from `window.location` (same-origin) — `NEXT_PUBLIC_API_URL` removed from CI build args, Dockerfile, and `next.config.ts`; the variable was being baked into the public Docker image with a private domain, breaking WebSocket connections for all external users
- `NEXT_PUBLIC_API_URL` removed from `.env.example` — it is no longer a configurable variable

## [1.2.2] - 2026-05-03

### Added
- Author section in Settings page (between Appearance and Logout) showing "Arturo Carretero Calvo" with GitHub link to `github.com/artcc`
- Version display (`v1.2.2`) in sidebar (desktop + mobile) above the logout button
- `specs/version.md` — canonical version file with sync rules (must match CHANGELOG and sidebar)
- `specs/version.md` listed in AGENTS.md spec files table

### Changed
- All spec files in `specs/` rewritten as proper specifications — removed embedded implementation code (~60-70% reduction), corrected outdated information, and aligned with the actual v1.2.1 codebase
- `AGENTS.md`: removed "Planning stage — zero source code", updated to reflect v1.2.1 with all phases complete, Next.js 16, Python 3.12, simplified TTS/STT section
- `architecture.instructions.md`: complete rewrite — lists all 9 models (was 6), all 11 routers (was 9), all 9 services, all endpoints, correct STT API (`/asr` not OpenAI), environment variables
- `roadmap.instructions.md`: all phases marked as ✅ Complete (Phase 1, 1+, 2, 3 were all frozen as ⬜ Planned), updated Phase 3 milestones to include structured logging
- `phase-1-platform.instructions.md`: rewritten from 880 to ~280 lines — removed all Python/TypeScript implementation code, kept architectural description and design decisions
- `phase-1-plus.instructions.md`: rewritten from 1082 to ~300 lines — removed ~600 lines of embedded grammar/vocabulary data code, kept data model descriptions
- `phase-2-tts-stt.instructions.md`: corrected STT endpoint to `POST /asr?output=json&language=en&task=transcribe` (was wrong OpenAI API), default model to `large-v3-turbo`, added `STT_ENGINE` variable, removed all implementation code
- `phase-3-conversation.instructions.md`: corrected VAD library to `@ricky0123/vad-react` (was `vad-web`), corrected COOP/COEP headers (were documented as "not needed" but are actually required), added structured logging and `LOG_LEVEL`, removed all implementation code
- `docker.instructions.md`: uncommented kokoro/whisper services, corrected STT endpoint, added `LOG_LEVEL`, `STT_ENGINE`, `COOKIE_SECURE` to .env example, removed "no Docker locally" contradiction
- `testing.instructions.md`: removed Docker commands (no Docker locally), documented SQLite in-memory DB for tests (not PostgreSQL), updated test file list to match actual 10 test files, marked frontend/E2E tests as "pending"
- `llm-error-handling.instructions.md` and `rate-limiting.instructions.md`: removed all implementation code blocks, kept strategy descriptions, error taxonomies, and HTTP status mappings

## [1.2.1] - 2026-05-02

### Added
- Structured logging across the voice conversation pipeline (`[conversation]`, `[pipeline]`, `[stt]` prefixes) at INFO / DEBUG / ERROR levels
- `LOG_LEVEL` configuration variable (default `INFO`) in `config.py`, `docker-compose.yml`, and `.env.example`; applied via `logging.basicConfig` at startup
- `STT_ENGINE` variable in `.env.example` and `docker-compose.yml` (`${STT_ENGINE:-faster_whisper}`) so the Whisper inference engine is configurable without editing the compose file
- TTS voice reference table and STT model/engine reference table added to README

### Changed
- `STT_MODEL` in `docker-compose.yml` now reads from `.env` via `${STT_MODEL:-large-v3-turbo}` instead of being hardcoded
- Default STT model upgraded from `tiny.en` / `medium` to `large-v3-turbo` — best speed/accuracy ratio on GPU (≥6 GB VRAM), ~8× faster than `large-v3` with near-identical accuracy
- Conversation system prompt: added explicit prohibition on emojis and emoticons (same rule as chat tutor — TTS reads them aloud)
- README "Enabling TTS & STT" notes updated to reflect that `STT_MODEL` and `STT_ENGINE` are now controlled from `.env`

## [1.2.0] - 2026-05-02

### Added
- Phase 3 voice conversation mode: WebSocket pipeline orchestrating VAD → STT → LLM → TTS with barge-in support and gapless audio streaming
- `ConversationMode` frontend component (dynamic, SSR disabled) using `@ricky0123/vad-react` for in-browser voice activity detection
- COOP + COEP headers globally in Next.js config (`same-origin` / `credentialless`) to enable `SharedArrayBuffer` required by onnxruntime-web 1.25.1 threaded WASM
- `copy-vad-models.js` postinstall script copies ORT WASM + VAD model files (`.wasm` and `.mjs`) to `public/vad/`; re-run in Docker builder stage after `COPY frontend/` to preserve generated files
- `NEXT_PUBLIC_API_URL` passed as Docker build ARG and baked at `next build` so WebSocket connections resolve correctly on separate-subdomain deployments
- `NEXT_PUBLIC_API_URL` CI secret wired into GitHub Actions `docker-publish.yml` frontend build step
- Session timeout watchers: configurable `CONVERSATION_MAX_DURATION` and `CONVERSATION_INACTIVITY_TIMEOUT` per user, with 60 s warning messages before disconnect
- Structured logging across the voice conversation pipeline (`[conversation]`, `[pipeline]`, `[stt]` prefixes) at INFO / DEBUG / ERROR levels
- `LOG_LEVEL` configuration variable (default `INFO`) in `config.py`, `.env.example`, and `docker-compose.yml`; applied via `logging.basicConfig` at startup

### Changed
- `STTService` endpoint corrected from `/v1/audio/transcriptions` (OpenAI API, unsupported) to `POST /asr?output=json&language=en&task=transcribe` with `audio_file` form field, matching the actual `onerahmet/openai-whisper-asr-webservice` API
- Conversation system prompt: added explicit prohibition on emojis and emoticons (same rule as chat tutor — TTS reads them aloud)
- `ConversationPipeline.run()` loop now catches `RuntimeError` from `ws.receive()` on client disconnect (triggered when the frontend auto-closes the WS after receiving an error message)
- Settings page section order: Perfil → Conversación → Apariencia → Cerrar sesión

## [1.1.1] - 2026-05-02

### Added
- Theme mode selector in Settings: three explicit options — Auto (system), Dark, Light — replacing the previous toggle; Auto is the default and follows the OS `prefers-color-scheme` preference in real time

### Fixed
- Chat tutor system prompt: added instruction to never use emojis or emoticons (TTS reads them aloud)
- Chat sidebar on mobile and narrow viewports: sidebar now hidden by default on screens below `md` breakpoint; opens as a fixed overlay with a semi-transparent backdrop instead of a side-by-side column, preventing the chat area from becoming unusably narrow

## [1.1.0] - 2026-05-02

### Added
- TTS (Kokoro-FastAPI) integration: `AudioPlayer` component reads flashcard words, lesson exercise sentences, correct answers, and tutor chat responses aloud
- STT (faster-whisper) integration: `VoiceRecorder` component allows dictating answers in flashcards and lesson exercises
- `POST /api/tts` backend proxy to Kokoro-FastAPI service (returns `audio/mpeg`)
- `POST /api/stt` backend proxy to faster-whisper service (returns transcription text)
- `TTS_ENABLED` and `STT_ENABLED` feature flags in `.env` — both services are disabled by default
- Kokoro and Whisper services defined in `docker-compose.yml` with NVIDIA GPU `deploy` block
- Custom `docker/kokoro.Dockerfile` upgrading PyTorch to 2.7+ (cu128) for Blackwell GPU support (RTX 5000 series, sm_120), compatible with all previous NVIDIA architectures (sm_50+)
- `docker-compose.yml` updated to use fork image `ghcr.io/artcc/kokoro-fastapi-gpu` with full Blackwell support
- `AudioPlayer` added to tutor chat messages — button appears after streaming completes

### Fixed
- Kokoro container crash on NVIDIA Blackwell GPUs (`CUDA error: no kernel image is available`) caused by PyTorch ≤ 2.5 lacking sm_120 support

## [1.0.0] - 2026-05-01

### Added
- Docker Compose setup with PostgreSQL 16, Redis 7, backend, and frontend services
- `.env.example` with all configuration variables for phases 1–3
- FastAPI backend with async SQLAlchemy engine and asyncpg driver
- JWT access token (15 min, HS256) and opaque refresh token (30 days, httpOnly cookie) auth flow
- Refresh token rotation with replay detection via Redis
- User registration with optional single-use invite token support
- First registered user is automatically assigned the admin role when `FIRST_USER_IS_ADMIN=true`
- `ALLOW_REGISTRATION` flag to gate public signups
- Admin panel API: full user CRUD and single-use invite link generation (48 h TTL in Redis)
- LLM adapter singleton supporting Ollama, OpenAI, Anthropic, and DeepSeek providers
- LLM retry logic with exponential backoff and structured output with JSON fallback
- CEFR assessment: 20-question quiz generation and answer evaluation via LLM structured output
- Study plan generation from CEFR level and user goals, with active-plan management
- Lesson generation with multiple exercise types (MCQ, fill-in-the-blank, free-write)
- Free-write exercise evaluation with LLM-generated feedback and score
- Flashcard SM-2 spaced-repetition algorithm with quality score 0–5
- Flashcard generation via LLM with translations in the user's native language
- SSE streaming chat with progress-aware tutor system prompt and persistent history
- Chat history persisted in `chat_history` table, loaded per user (last 30 messages)
- Progress tracking: XP, streak, accuracy, skills breakdown, and 90-day history
- Alembic initial migration covering all Phase 1 models
- Next.js 14 App Router frontend with login, register, dashboard, assessment, chat, flashcards, lesson, settings, and admin pages
- Zustand stores for auth (access token, user) and progress (streak, XP, today's lessons)
- `apiFetch` utility with silent 401 → refresh → retry interceptor and redirect on failure
- Next.js middleware protecting all routes via `refresh_token` cookie check
- `CONTRIBUTING.md` with contribution workflow, coding standards, and test requirements
- Grammar Reference hub: searchable index page with CEFR-level grouping and category filters
- Grammar topic detail pages with structure formula, key rules, examples, common mistakes, and related topics
- Vocabulary Hub: level-filtered word set index with word count per set
- Vocabulary set detail pages with IPA, POS, definitions, examples, and "Add All to Flashcards" bulk action
- Phrasebook with level and register (formal / neutral / informal) filters and one-click clipboard copy
- Skills Tracker page showing XP, streak, accuracy stats, per-unit competency checklist, and skill accuracy bars
- Level Completion Test: LLM-generated adaptive quiz per study-plan unit, with skill breakdown and level recommendation on completion
- `grammar_refs` field on lesson content, populated by LLM and validated against 24 known CEFR grammar slugs
- Related Grammar section on lesson pages linking to Grammar Reference topic detail pages
- `GET /api/progress/competencies` endpoint returning per-unit competency scores for the active study plan
- Unit competency upsert endpoint and `unit_competencies` table migration
- Sidebar navigation reorganised into MAIN and collapsible RESOURCES groups (desktop and mobile)
- i18n infrastructure via `next-intl` v4: cookie-based locale (`NEXT_LOCALE`) derived from `native_language`, no URL routing changes
- Translation files for 6 locales: `en`, `es`, `fr`, `pt`, `de`, `it` under `messages/` with 16 namespaces (common, nav, auth, settings, dashboard, assessment, plan, lesson, flashcards, chat, progress, grammar, vocabulary, phrasebook, admin, errors)
- `src/i18n/request.ts` server-side locale resolver reading `NEXT_LOCALE` cookie
- `NextIntlClientProvider` wrapping the root layout to hydrate all client components
- `english_variant` preference (`american` / `british`) on the User model, surfaced in Settings with flag selector
- `english_variant` propagated to lesson generator, flashcard generator, and chat tutor system prompt
- Alembic migration `0005_english_variant` adding `english_variant VARCHAR(10) NOT NULL DEFAULT 'american'`
- Amber accent colour design token (`--fl-accent: #C9943A` dark / `#B07E28` light) applied to all CTA buttons, selected states, nav active indicators, and progress bars

### Fixed
- Alembic migration chain broken by mismatched revision IDs in `0004_lesson_unit_id` (`"0003"` → `"0003_curriculum_studyplan"`)
- Backend container no longer requires a manual `alembic upgrade head` step — migrations run automatically in the container `command`