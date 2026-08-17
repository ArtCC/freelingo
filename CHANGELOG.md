# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.8.40] - 2026-08-17

### Fixed

- **Listening lesson labels**: study-plan, dashboard, unit-drawer, and lesson-player views now show the localized listening lesson type instead of the untranslated `plan.lessonTypes.listening` key or raw backend value.

## [1.8.35] - 2026-08-07

### Added

- **Global dashboard announcement**: administrators can compose an announcement in any supported source language, use the LLM to translate it into all ten UI locales, edit every translation, and save it as active or inactive from the System page.
- **Persistent announcement dismissal**: active announcements appear on the dashboard above the next-step card and can be dismissed per account, while a server-managed content revision makes updated announcements visible again.
- **Question vocabulary saving**: words selected in active Reading and Listening question prompts can now be saved to the learner's flashcards through the existing word lookup flow.

### Changed

- **Simplified legal copy**: all ten locales now clarify hosted-service closure and deletion, the absence of automated data export, Stripe's independent payment-data retention, subscription cancellation and closure terms, and bcrypt password-hash wording.

## [1.8.30] - 2026-08-05

### Added

- **Manual memory control**: every authenticated user can add a concise memory from Settings, alongside listing, deleting, and clearing stored memories. The page now provides explicit loading, retry, duplicate, busy, success, and error states in all ten UI languages.
- **Native memory tool calling**: text and voice tutoring can save durable learner facts through normalized OpenAI-compatible and Anthropic streaming tool calls, with one tool round and a visible-response continuation.
- **Memory integrity**: migration `0049_memory_user_content_unique` removes later exact duplicates and enforces one exact `(user_id, content)` pair per user.

### Changed

- **Global memories across languages**: memories now follow the user across every learning language. `study_plan_id` remains nullable creation provenance only, and deleting a language preserves linked memories by setting that provenance to `NULL`.
- **User-controlled access**: memory list, manual creation, individual deletion, and clear-all require authentication but are no longer subscription-gated.
- **Voice memory freshness**: voice conversation reloads the user's global memories every turn, so manual and newly saved context is available without reconnecting.
- **Memory limits and safety**: memory items remain limited to 200 characters, storage is capped at 150 items per user with deterministic oldest-first eviction, and injected memory text is escaped and treated as untrusted prompt data.
- **Privacy and deletion copy**: all ten locales now explain manual/global memories and clarify that removing a learning language does not remove account memories.
- **What's New version marker**: bumped to `v1.8.35` with localized memory redesign highlights.
- **Memory save notification**: text and voice now share an accessible informational toast that confirms Lingu saved a memory, points users to Settings without a timed action, safely restarts and re-announces consecutive saves, and survives SSE events split across network chunks.
- **Native-language memories**: Lingu now writes new automatic memories in the user's configured native language, independently of the language being studied, so saved facts remain directly readable in Settings. Manual and existing memories are left unchanged.

### Fixed

- **Study-plan lesson actions**: unit drawers now use persisted lesson state to offer Start for the current lesson, Resume for skipped pending lessons, and read-only Review for completed lessons. Their action buttons now match the plan overview, while a lesson-count heading, roomier rows, wider desktop layout, and sticky close footer improve readability without changing the drawer structure. Reviewing preserves saved answers and feedback without consuming quota or awarding progress again. Lesson completion now serializes concurrent requests, atomically commits completion with progress and competencies, permits quota-exhausted retries, blocks duplicate frontend submissions, and refreshes displayed freemium quota from the server.
- **Progressive chat streaming with memory tools**: visible text from the initial response and the post-tool continuation is forwarded as soon as the provider emits it instead of being buffered until each generation completes. If a known tool incompatibility or failed tool continuation appears after partial text, chat discards that partial response before streaming one complete no-tools fallback; an empty fallback is reported as an error and is never persisted as a successful assistant message.
- **Serialized memory deletion**: individual deletion and clear-all now use the same per-user database lock as memory creation, so an already-running save completes before the deletion transaction decides what to remove.
- **Provider-safe memory tools**: OpenAI GPT-5.6 Chat Completions now use `reasoning_effort="none"` during the native memory-tool round, as required by the provider. OpenAI, Anthropic, DeepSeek, and Ollama tool incompatibilities or tool-stream failures fall back to the same turn with a prompt that does not advertise unavailable memory tools. Explicit incompatibility is recognized through wrapped provider errors and remembered only for the current voice session; transient failures are retried with tools on later turns.
- **Durable memory confirmation**: a committed automatic memory save now emits its confirmation before any later continuation failure, including voice barge-in cancellation, without exposing failed or duplicate saves. Memory reads remain best-effort and cannot block text or voice tutoring.

## [1.8.27] - 2026-06-28

### Fixed

- Minor bug fixes and improvements.

## [1.8.26] - 2026-06-24

### Fixed

- Minor bug fixes and improvements.

## [1.8.25] - 2026-07-24

### Added

- **Freemium access to AI features**: unsubscribed users on the hosted service now get limited daily quotas for chat and lessons, plus weekly quotas for listening, reading, and voice conversations, replacing the previous hard paywall. New users also receive a 7-day full-access trial without entering payment details. Self-hosted deployments are unaffected.

### Changed

- **Quota-based paywall**: chat, listening, reading, conversation, and lesson endpoints now use `require_subscription_or_freemium` instead of the previous hard `require_subscription` dependency. Unsubscribed users can access these features within their quotas; when a quota is exhausted the endpoint returns 402 with a structured `freemium_exhausted` detail.
- **Dashboard and sidebar**: the premium banner and sidebar trial countdown now support the freemium trial state. Feature pages show a `FreemiumQuotaBanner` with remaining quota counts.
- **New `GET /api/freemium/status`** endpoint returns per-user quota status and trial details.
- **Seven new environment variables**: `FREEMIUM_CHAT_DAILY_MESSAGES`, `FREEMIUM_LESSONS_DAILY`, `FREEMIUM_LISTENING_WEEKLY`, `FREEMIUM_READING_WEEKLY`, `FREEMIUM_VOICE_WEEKLY_MINUTES`, `FREEMIUM_TRIAL_ENABLED`, `FREEMIUM_TRIAL_DAYS` — all settable in `.env` and docker-compose. A quota value of 0 blocks the feature entirely for free users.
- **Terms of Service** updated to reflect the free plan and 7-day no-card trial.
- **What's New version marker**: bumped to `v1.8.25`.

### Fixed

- **Freemium trial persistence**: the 7-day trial is now committed to the database on registration (previously it was set in memory but never persisted).
- **Docker multi-architecture builds**: CI/CD now publishes backend and frontend images for both `linux/amd64` and `linux/arm64`, resolving "no matching manifest for linux/arm64/v8" on Apple Silicon. Each architecture builds on its own native GitHub Actions runner (`ubuntu-latest` for amd64, `ubuntu-24.04-arm` for arm64), eliminating unreliable QEMU emulation.
- **Docker actions upgraded**: `docker/login-action` (v3→v4), `docker/setup-buildx-action` (v3→v4), and `docker/build-push-action` (v5→v7) to remove Node.js 20 deprecation warnings.
- **Backend Dockerfile**: CMD converted to JSON exec form to silence Docker build check warnings.

## [1.8.24] - 2026-07-10

### Changed

- **Consistent list pagination**: the community Feedback board, admin Feedback queue, and admin review moderation now show 10 results per page, matching admin users and saved vocabulary.
- **Complete exercise histories**: Listening and Reading histories now use the shared Previous/Next pagination controls to expose every attempt in pages of 10 instead of showing only the first page with a passive remaining-count label.
- **Landing review carousel**: the public reviews carousel now requests up to 100 approved positive reviews instead of limiting the landing page to 12.
- **What's New version marker**: bumped to `v1.8.24` while keeping the existing What's New entry text unchanged.

### Fixed

- **Stable Feedback pages**: Feedback ordering now uses the entry ID as a deterministic tie-breaker, preventing tied vote or date values from shuffling entries between offset pages.

## [1.8.23] - 2026-07-10

### Changed

- **Consistent page backgrounds**: public pages now use the dot-grid background, while the authenticated application and all of its loading states use a solid background without a visual flash between patterns.
- **Landing anchor navigation**: Features, Reviews, Pricing, and FAQ anchor links now reserve space for the sticky navigation bar so section content remains fully visible after scrolling.
- **Official feedback authors**: suggestions, bug reports, and replies written by an administrator now show a compact gold `ADMIN` badge beside the author's display name in the community board and admin queue.
- **Admin system controls**: maintenance mode now lives in a dedicated System section instead of the Users page, the overview shortcut opens that section directly, and the enable action uses the standard accent button colour while active maintenance status remains yellow.
- **What's New version marker**: bumped to `v1.8.23` while keeping the existing What's New entry text unchanged.

## [1.8.22] - 2026-07-04

### Added

- **Feedback unread labels**: feedback list items now expose and display a red `Unread` label next to the status badge when that specific suggestion or bug report has unread activity for the current user.

## [1.8.21] - 2026-07-04

### Added

- **Feedback unread counter**: the authenticated app sidebar now shows a red circular unread counter on the Feedback item for all users, including admins. The counter tracks feedback threads with new entries or comments from other users, caps the display at `99+`, and marks only the opened thread as read from the feedback detail view. New authenticated endpoints expose the unread summary and per-thread read marker, backed by the new `feedback_read_states` table.

## [1.8.20] - 2026-06-28

### Added

- **Post-assessment voice demo**: unsubscribed hosted users who complete the placement assessment now get a one-time 5-minute real-time voice conversation with Lingu. The demo is granted after the study plan is created, uses a Redis-backed token plus the new `users.assessment_voice_trial_used` flag, bypasses the conversation paywall only for that trial session, enforces a backend 300-second max duration, and shows monthly/yearly Premium checkout CTAs when the session ends.
- **Review prompt after exercises**: users who have not submitted a review yet may now be asked for one after completing a new Reading or Listening exercise, reusing the existing duplicate-review check and local dismissal cooldown. Replays from history do not trigger the prompt.

## [1.8.19] - 2026-06-27

### Fixed

- **Logged-in pricing checkout**: authenticated users who select a monthly or yearly plan from the public landing-page pricing section now start Stripe Checkout directly instead of being sent back to the dashboard. The landing pricing CTA refreshes the session token when needed before creating the checkout session.
- **Past-due subscription recovery**: users with a pending Stripe payment now see payment-recovery copy and a Customer Portal action in Settings and the dashboard Premium banner instead of new subscription plan buttons.
- **Stripe subscription states**: real Stripe states such as `unpaid`, `paused`, `incomplete`, and `incomplete_expired` are now preserved for accurate status labels while only `active` and `trialing` grant Premium access. `past_due`, `unpaid`, and `paused` route users to payment recovery; `none`, `incomplete`, `incomplete_expired`, and `canceled` show normal plan-selection buttons.
- **Checkout success verification**: the Stripe success page now confirms `/api/auth/me` reports an active or trialing subscription before showing Premium-active copy. If the webhook has not synced yet, it shows subscription-confirmation copy instead of claiming access is already active.
- **Stripe webhook subscription matching**: billing webhooks now persist the current `stripe_subscription_id` and ignore subscription lifecycle events for older Stripe subscriptions once the current subscription is known, preventing stale `deleted`, `updated`, or `payment_failed` events from incorrectly changing current Premium access.
- **Onboarding checkout session recovery**: onboarding now refreshes the access token from the session cookie before starting Stripe Checkout, so users who reload onboarding after registration can still continue to payment without a failed checkout request.

## [1.8.18] - 2026-06-26

### Added

- **Lesson exercise regeneration**: unanswered lesson exercises that have a technical generation issue can now be regenerated on demand from the exercise card. The backend only regenerates exercises that fail validation, preserves the existing lesson, updates both the exercise row and lesson JSON, and blocks regeneration for answered or completed exercises.

### Fixed

- **Multiple-choice lesson validation**: LLM-generated multiple-choice lesson exercises now require usable options and an exact matching correct answer, preventing empty-option exercises that leave the submit button disabled.
- **Admin user creation**: the admin create-user flow now consistently treats email as required in both frontend validation and the backend schema, and the admin action buttons no longer duplicate the leading plus sign when an icon is already shown.
- **Admin users table layout**: the desktop users table now gives more room to the subscription column and truncates long subscription labels with an ellipsis instead of wrapping them onto multiple lines.

## [1.8.17] - 2026-06-25

### Fixed

- Minor bug fixes and improvements.

## [1.8.16] - 2026-06-25

### Changed

- **Subscription conversion funnel**: the landing-page primary CTA now sends new visitors to registration, pricing plan clicks preserve monthly/yearly intent through registration, and onboarding highlights the selected billing interval before Stripe Checkout. Subscription CTAs now separate the free trial from the later paid price when the user is trial-eligible, emphasize the yearly plan as the best-value option with two months free, position monthly as the flexible alternative, and use `trial_used` to switch authenticated users who already used a trial to neutral plan-selection and amount-confirmation copy.
- **Canceled checkout recovery**: `/billing/canceled` now confirms that no charge was made in the canceled Stripe session and routes users back to the dashboard or settings plans without promising future trial availability.
- **Premium upgrade surfaces**: premium-gated routes now show contextual paywall copy for chat, voice conversation, listening, and reading, while the dashboard Premium banner exposes the yearly-first subscription buttons directly and uses clearer trial-focused messaging.
- **Trial-aware subscription copy**: authenticated upgrade surfaces now use the exposed `trial_used` flag to show free-trial copy only when the user is eligible, falling back to neutral plan-selection and amount-confirmation copy after a trial has already been used.
- **Landing layout consistency**: public landing sections for features, open source, and FAQ now use the same `max-w-5xl` content width as reviews and pricing for a more consistent horizontal rhythm.
- **Private app layout consistency**: private learning/content sections that previously used `max-w-2xl` now align to the wider `max-w-4xl` content width, and reading non-exercise states match that width while preserving the wider two-column exercise layout.

## [1.8.15] - 2026-06-24

### Changed

- **Lesson vocabulary support**: newly generated lesson vocabulary can now include native-language translations, translated example sentences, usage notes, and optional reading/pronunciation guidance while keeping older lesson vocabulary compatible.
- **Lesson exercise hints**: lesson exercises can now include native-language pre-answer hints, and older exercises can generate them on demand without revealing the correct answer.
- **Settings UI organization**: the Settings page now uses a wider, admin-inspired layout with section navigation, quick action cards, clearer account grouping, and legal/session actions kept under Account without changing settings functionality.

### Fixed

- Minor bug fixes and improvements.

## [1.8.14] - 2026-06-23

### Fixed

- **Mobile word saving**: selectable learning text now uses pointer-based selection handling so mobile users can select a single word in lessons, reading, listening, and assistant chat replies and save it to My Vocabulary.
- **My Vocabulary empty search state**: searching saved vocabulary with no matches now shows a localized flashcards message instead of the raw `common.noResults` key.
- **Mobile sidebar profile summary**: the mobile menu now shows the user's display name above their `@username`, matching the desktop sidebar.
- **Lesson exercise results**: evaluated exercise answers now show subtle green checkmarks and red crosses where the answer state is visually useful.

## [1.8.13] - 2026-06-23

### Changed

- **Dashboard progress refinements**: `/api/progress/summary` now includes current-level vocabulary progress for the active study language, and `/dashboard` shows it compactly inside the plan-progress card without adding a dashboard request. The dashboard's former skills section is now presented as recent performance with clearer labels and explanatory copy.
- **Dashboard Premium banner**: unsubscribed users now see a compact FreeLingo Premium banner above quick actions when Stripe is enabled, linking to pricing and highlighting Reading, Listening, text chat with Lingu, and voice conversation.
- **Landing reviews signal**: the public reviews section now shows the average rating and total review count below the section subtitle, using localized number formatting and public-facing copy such as "reseñas en total" rather than moderation terminology.
- **Maintenance access control**: maintenance mode now blocks the four gated learning sections only for non-admin users, allowing admins to verify chat, voice conversation, listening, and reading while maintenance is active. Memory-management endpoints remain subscription-gated but are no longer blocked by maintenance mode. The admin toggle now uses `PUT /api/admin/maintenance` with an explicit `maintenance_mode` value instead of relying on a state-flipping request from the UI.

## [1.8.12] - 2026-06-23

### Changed

- **Dashboard UX refresh**: `/dashboard` now emphasizes the student's next action with a primary next-step card, richer progress stats from existing summary data, a clearer plan-progress block, and a reorganized daily lesson section that highlights the next pending lesson and shows how many lessons are completed today. No dashboard endpoints or request flow changed.

## [1.8.11] - 2026-06-22

### Added

- **Native-language exercise explanations**: newly generated lesson exercises can now include a concise `native_explanation` alongside the target-language `explanation`, giving students an immediate clarification in their native language directly under each exercise explanation. Existing lessons remain compatible; when an exercise has a target-language explanation but no native text yet, the lesson UI shows the same native-explanation button pattern and generates/caches the exercise-level clarification on demand.

## [1.8.10] - 2026-06-22

### Added

- **Japanese learning data**: `ja-JP` now has a complete backend learning package with A1-C2 curriculum, grammar, vocabulary, phrasebook, assessment, listening-enabled study plan coverage, and Japanese-specific reading generation topics.
- **Korean learning data**: `ko-KR` now has a complete backend learning package with A1-C2 curriculum, grammar, vocabulary, phrasebook, assessment, listening-enabled study plan coverage, and Korean-specific reading generation topics.
- **Mainland Chinese learning data**: `zh-CN` now has a complete backend learning package with A1-C2 curriculum, grammar, vocabulary, phrasebook, assessment, listening-enabled study plan coverage, and Mainland Chinese-specific reading generation topics.
- **CJK data integrity coverage**: grammar, vocabulary, phrasebook, assessment, curriculum, allow-list, and cross-reference tests assert that Japanese, Korean, and Mainland Chinese resolve to explicit target-language data rather than falling back to English.
- **Native-language lesson explanations**: lessons at every CEFR level can now include a native-language `native_explanation` alongside the target-language explanation. New lessons generate it automatically, while existing lessons expose an on-demand "show in native language" action that translates and caches the explanation without regenerating exercises. Native explanations now also include common traps and a mini-glossary to make each generated lesson easier to study.
- **Native-language grammar help**: grammar topic detail pages now offer native-language study help generated on demand and cached globally per topic, target language, native language, and source hash. A1/A2 help opens automatically, while B1-C2 remains collapsed until requested.
- **Native-language phrasebook help**: phrasebook categories now offer native-language usage support generated on demand and cached globally per category, target language, native language, and source hash. The helper focuses on when to use phrases, register/formality, common traps, and useful expressions.
- **Native-language vocabulary help**: vocabulary set detail pages now offer native-language study support generated on demand and cached globally per set, target language, native language, and source hash. The helper focuses on study tips, word notes, common traps, glossary meanings, and practice prompts.
- **Native explanation test coverage**: backend coverage now includes native-explanation endpoint generation/caching, grammar, phrasebook, and vocabulary native-help generation/cache refresh, and native-language propagation during lazy lesson generation. Backend suite: 887 tests, 85.39% last measured coverage.

### Changed

- **What's New language entry**: bumped to `v1.8.10` and expanded the main language entry to mention Japanese, Korean, and Mainland Chinese alongside the existing language set so the copy does not need another update when the remaining CJK language data lands.
- **Target-language data organization**: Japanese, Korean, and Mainland Chinese grammar/vocabulary data now follow the British English package structure with level modules and assembler files; the add-language spec now requires that organization for future target languages.
- **Lesson native-explanation UX**: lesson native explanations now appear in a collapsible section that is open by default for A1/A2 and collapsed by default for B1+.
- **Default target-language fallbacks**: frontend resource pages now consistently fall back to `en-GB` instead of `en-US` when no active learning language is loaded.

## [1.8.9] - 2026-06-20

### Changed

- **Admin email localization**: admin-facing contact-form and feedback-board notification emails now use the native language of the first admin user (`id ASC`), with English as fallback if the locale is unsupported. The What's New marker was bumped to `v1.8.9` while keeping the existing What's New entry text unchanged.
- **Review moderation emails**: creating a product review now sends a localized admin notification to `CONTACT_EMAIL`, linking to `/admin/reviews` for approval.
- **Voice conversation audio latency**: tutor replies are now synthesized and streamed to the browser sentence by sentence, so playback can start after the first sentence is ready instead of waiting for the full response audio. The frontend still ignores user speech while the tutor turn is active, keeping stable non-interrupting voice sessions. If every sentence-level TTS attempt fails, the tutor response is shown as text and the turn completes normally.

## [1.8.8] - 2026-06-19

### Added

- **User reviews**: Phase 11 adds one moderated product review per user with required 1-5 star ratings, optional comments, learning-language snapshots, admin approval/deletion, a reusable in-app review prompt, public approved-review listings, a landing page reviews carousel, and an admin review moderation section. The prompt is now triggered after manually stopping a voice conversation session that has been connected for at least 5 minutes, and after completing a curriculum unit, subject to duplicate-review checks and local dismissal cooldown.
- **Profile review management**: users can now add, edit, or delete their FreeLingo review from Settings below the subscription section. Existing reviews load prefilled, edited reviews return to pending admin approval before public display, and deletion requires confirmation.
- **Language-specific prompt guidance**: chat, voice, lessons, exercise evaluation, flashcards, reading, listening, and assessment prompts now include concise guidance for each supported learning language, preserving regional variants such as American/British English, Spanish from Spain, and European Portuguese.

### Changed

- **AI tutor persona**: the tutor is now consistently named Lingu in text tutor prompts, voice conversation prompts, and TTS voice previews.
- **Feedback queue noise reduction**: feedback entries marked as Done are now hidden from default public and admin listings, and only appear when the Done status filter is selected.
- **Review moderation UX**: deleting a review in the admin queue now reloads the active page so remaining reviews fill the list, and the in-app review prompt no longer allows submission if the existing-review status check fails.
- **Admin review signals**: the admin overview now shows reviews pending approval and includes a quick-link card to review moderation.
- **Landing reviews navigation**: when approved public reviews are available, the landing page navigation now includes a Reviews link in desktop and mobile menus.
- **Landing reviews layout**: review carousel cards now keep a consistent height and truncate long comments after 6 lines.
- **Reading/listening generation robustness**: AI-generated reading and listening exercises now use structured Pydantic output validation instead of raw JSON parsing.
- **Native-language prompt clarity**: stored native-language codes such as `es` and `fr` are converted to human-readable names before being injected into LLM prompts.
- **What's New version marker**: bumped to `v1.8.8` while keeping the existing What's New entry text unchanged.

## [1.8.7] - 2026-06-17

### Added

- **Admin overview page**: `/admin` now acts as the admin entry point with quick access to Users, Feedback, and system controls, plus a clear maintenance-mode status panel.
- **Shared admin navigation**: admin pages now use a consistent tab-style navigation between Overview, Users, and Feedback.
- **Shared admin layout primitives**: admin pages now share header, panel, metric, and badge primitives for more consistent spacing, labels, and states.
- **Tabbed admin user detail**: `/admin/users/{id}` now separates Profile, Languages, Activity, Quotas, and Subscription into focused tabs with a summary header.
- **Admin overview metrics**: `GET /api/admin/stats` powers aggregate admin KPIs for users, subscriptions, pending feedback, and pending bugs.
- **Admin user filters**: `GET /api/admin/users` now supports optional `role` and `is_active` query filters in addition to pagination, search, and subscription filtering.
- **Feedback search**: `GET /api/feedback` now supports optional `q` search across title, description, username, and display name.
- **Invite copy workflow**: generated invite links now include a copy button, copied state, clipboard failure handling, and visible 48-hour expiry guidance.

### Changed

- **Admin users UX refresh**: `/admin/users` now uses a responsive desktop table and mobile cards, with clearer badges, action icons, loading states, empty/error states, and resettable filters.
- **Admin user detail UX refresh**: quotas now separate current usage from configured limits, quota inputs show units and validation, and email verification/subscription changes require confirmation.
- **Admin feedback UX refresh**: `/admin/feedback` now uses a wider responsive queue with search, type/status/sort filters, filtered summary metrics, desktop table, mobile cards, inline status changes, clearer loading/error states, and delete confirmation. Status changes refresh the queue when the updated entry no longer matches the active filter.
- **Admin overview UX refresh**: `/admin` now shows operational metrics, pending bug alerts, past-due subscription alerts, and quick links that open pre-filtered admin views.
- **Create user flow**: admin user creation moved from an inline expanding form to a side panel with labelled fields and a clearer submission state.
- **Admin sidebar target**: the main Admin navigation item now opens `/admin` instead of jumping directly into the users list.
- **Default target language**: admin-created users now default to `en-GB`, matching the project-wide fallback.

## [1.8.6] - 2026-06-17

### Added

- **Onboarding subscription step**: after selecting language and learning goals, new users who haven't subscribed and where Stripe is enabled now see a trial offer step with monthly/yearly checkout buttons and a "Continue with free features" skip link. Subscribed users bypass this step automatically and go straight to the dashboard.
- **Sidebar premium indicators**: Chat, Voice, Listening, and Reading navigation items now show a ★ badge when the user is unsubscribed and Stripe is enabled, clearly distinguishing premium features from free ones. Self-hosted deployments (Stripe disabled) see no badges.
- **Paywall escape link**: the paywall banner now includes a "Continue with free features" link that returns users to the dashboard, so they aren't forced to subscribe or leave the page.
- **Tour premium indicators**: the onboarding tour now shows a ★ on steps covering premium features (Chat, Voice, Listening & Reading) when Stripe is enabled. Tour step icons upgraded from unicode symbols to lucide-react SVG icons (Sparkles, MessageSquare, Mic, Layers, BookOpen, Headphones, Zap).
- **Trial days counter**: users with an active trial now see their remaining trial days (e.g. "★ 5 days of trial") in the sidebar below their username. The counter appears only when Stripe is enabled and the user is in `trialing` status.
- **Onboarding enforcement**: users who close the browser before completing onboarding are now redirected back to the onboarding flow on their next visit. The onboarding PATCH now always persists `learning_goals` so the frontend can detect incomplete onboarding via a `null` value. Existing users who completed onboarding but skipped the goals step are backfilled via migration `0041_backfill_learning_goals`.

### Changed

- **Settings billing section**: moved from the bottom of the Settings page to right after Profile, making subscription status and management immediately visible.

### Fixed

- Landing navigation now hides the `Pricing` link for signed-in users with an active or trialing subscription, matching the pricing section visibility. The landing nav and pricing section share one subscription-status check to avoid duplicate refresh requests.
- Minor bug fixes and improvements.

## [1.8.5] - 2026-06-17

### Changed

- New logo

### Fixed

- Minor bug fixes and improvements.

## [1.8.4] - 2026-06-16

### Added

- **German and French curricula completed**: all didactic content for German (`de-DE`) and French (`fr-FR`) is now fully translated — assessment question banks, phrasebook contexts, and curriculum competency checklists are entirely in the target language with no English remnants.
- **Expanded test coverage**: 10 new test files (5 backend + 5 frontend) adding 97 new tests.
- Backend: `test_flashcard_sm2.py` (57%→100%), `test_assessment_bank.py` (0%→100%), `test_limiter.py` (42%→100%), `test_lesson_generator.py` (51%→100%), `test_listening_service.py` (63%→64%).
- Frontend: `tests/lib/utils.test.ts`, `tests/lib/logger.test.ts`, `tests/hooks/useLogout.test.tsx`, `tests/store/theme.test.ts`, `tests/store/loading.test.ts`.
- Backend: 721 → 783 tests, coverage 81.41% → 82.54%.
- Frontend: 329 → 364 tests, 16 → 21 test files.

### Fixed

- German assessment bank: 2 vocabulary questions had options in English → translated to German.
- German phrasebook: ~300 phrase contexts corrected from mixed English/German to pure German.
- German curriculum: all 46 competency checklists across A1–C2 corrected to German (removed mixed language, hanging particles, grammar errors, and typos).

## [1.8.3] - 2026-06-14

### Fixed

- Minor bug fixes and improvements.

## [1.8.2] - 2026-06-13

### Changed

- Redesigned landing page: improved hero section with larger typography and double CTA, section anchor navigation, SVG icons, mixed font hierarchy (sans for headings, mono for data), scroll-triggered fade-in animations, comparison table for pricing, highlighted free plan, standalone open-source banner, and footer restructured into columns.
- Added FAQ section to the landing page using existing app questions.

## [1.8.1] - 2026-06-13

### Fixed

- Minor bug fixes and improvements.

## [1.8.0] - 2026-06-10

### Added

- **New learning languages enabled in production**: Spanish (`es-ES`), Italian (`it-IT`), and Portuguese (`pt-PT`) are now live and available for all users. Each language includes a complete CEFR-aligned curriculum (A1–C2), grammar guides (130+ topics), vocabulary sets (~1,000 words), phrasebooks (280–305 phrases with TTS audio pronunciation), assessment question banks, and dedicated lesson generators. The multi-language infrastructure (Phase 10) is now fully active in the hosted service.

## [1.7.7] - 2026-06-10

### Fixed

- Minor bug fixes and improvements.

## [1.7.6] - 2026-06-10

### Fixed

- Minor bug fixes and improvements.

## [1.7.5] - 2026-06-09

### Fixed

- Minor bug fixes and improvements.

## [1.7.4] - 2026-06-09

### Added

- **Phrasebook migrated to backend**: all phrasebook data (~280-305 phrases per language × 4 languages, 25 categories each) moved from frontend static files to the backend, organized per CEFR level. New endpoints `GET /api/phrasebook`, `GET /api/phrasebook/level/{level}`, `GET /api/phrasebook/{category_id}`, and `GET /api/phrasebook/audio/{category_id}/{phrase_index}` serve the data with auth required and cached TTS audio. The frontend phrasebook page now fetches via API with loading states and a search bar.
- **Phrasebook TTS audio caching**: each phrase's pronunciation is generated once on first request and cached to disk (`/data/audio/phrasebook/{lang}/{hash}.mp3`), so subsequent plays are instant and free. A play button (▶) appears next to each phrase alongside the copy button.
- **Phrasebook search**: a search bar filters phrases by text content, combinable with the existing level and register filters.
- **English grammar expanded**: 75 new topics added, bringing English from 55 to 130 topics across A1–C2, matching the depth of the other languages. New topics cover areas like question tags, indirect questions, subjunctive mood, narrative tenses, collocations, hedging, rhetorical devices, pragmatic competence, and more. Categories previously sparse or empty (Phrasal Verbs 0→4, Articles 1→4, Questions 1→4) are now properly represented.
- **Grammar migrated to backend**: all grammar topics (~125-131 per language × 4 languages) moved from frontend static files to the backend, organized per CEFR level. New endpoints `GET /api/grammar` and `GET /api/grammar/{slug}` serve the data with auth required. The frontend grammar index and detail pages now fetch via API with loading/error states. The lesson page's grammar references also use the API.
- **Grammar audio button renamed field**: the `english` field in `GrammarExample` and `Phrase` interfaces was renamed to `text` for accuracy (it contains the target language phrase, not necessarily English).

### Fixed

- Two broken `related[]` cross-references in grammar data: Italian `si-impersonale` referencing `pronomin-indiretti` → `pronomi-indiretti`, Portuguese `horas` referencing `numeros` → `numeros-ordinais`.

### Changed

- **Phrasebook copy button**: fixed clipboard emoji rendering by using correct JavaScript Unicode escape (`\\u{1f4cb}`).

## [1.7.3] - 2026-06-08

### Added

- **Multi-level vocabulary progress toggle**: the progress page now includes a toggle to view vocabulary progress for the current CEFR level only or across all levels. This allows users to see their accumulated vocabulary knowledge beyond their current study level. The toggle defaults to "Current level only" for focused tracking.

### Changed

- **Assessment bank migrated to backend**: the static assessment question bank (~100 questions per language × 4 languages) has been moved from the frontend (`data/assessment-bank.ts` and per-language files) to the backend (`app/data/{en,es,it,pt}/assessment_bank.py`), following the same dispatcher pattern as the curriculum. A new endpoint `GET /api/assessment/bank?language=` serves the questions to the frontend, which now fetches them via API instead of bundling them statically. The adaptive quiz logic (`pickNextQuestion`, `adjustLevel`) remains client-side. This is a pure architectural refactor — no user-facing changes.
- **Vocabulary content migrated to backend**: 330 vocabulary sets (~3,940 words across 4 languages) moved from frontend static files to the backend, organized per CEFR level (same pattern as curriculum). New endpoints `GET /api/vocabulary`, `GET /api/vocabulary/level/{level}`, and `GET /api/vocabulary/{set_id}` serve the data with auth required. The frontend vocabulary hub, set detail, and progress pages now consume the API. This is a pure architectural refactor — no user-facing content changes.
- **Curriculum endpoints now require authentication** (`GET /api/curriculum` and `GET /api/curriculum/{level}`).

## [1.7.2] - 2026-06-07

### Fixed

- Minor bug fixes and improvements.

## [1.7.1] - 2026-06-07

### Changed

- **Updated Terms of Service**: added intellectual property clause (§4 — AI-generated content belongs to the user), indemnification clause (§8), severability clause (§11), and contact information.
- **Updated Privacy Policy**: added LLM Memories (§2), feedback board data (§2), corresponding data usage items (§3), and severability clause (§9).

### Fixed

- Minor bug fixes and improvements.

## [1.7.0] - 2026-06-05

### Added

- **Phase 10 — Multi-Language**: users can now learn multiple languages simultaneously. Every language gets its own isolated study plan, progress, flashcards, conversations, memories, and competencies. A sidebar language switcher pivots the entire experience to any active language with one click.
- **New supported target languages**: Spanish (`es-ES`), Italian (`it-IT`), and Portuguese (`pt-PT`) join the existing American English (`en-US`) and British English (`en-GB`).
- **Backend**: new `user_languages` table with `study_plan_id` columns across 8 tables for full data isolation per language. New `user_language_service.py` handles plan creation, activation, and deletion. New `/api/languages` router with 4 endpoints (list, add, set active, delete).
- **Frontend**: `LanguageSwitcher` component in sidebar (visible when ≥ 2 languages), `language` Zustand store, My Languages page in Settings, onboarding refactored for multi-language flow, all pages (dashboard, plan, chat, flashcards, progress) adapted to use the active study plan.
- **Curriculum data**: complete Spanish, Italian, and Portuguese curriculum files (backend + frontend) with language-specific lesson content, vocabulary, and competency definitions.

### Fixed

- **Firefox iOS locale detection**: Firefox on iOS always sends `Accept-Language: en-US` regardless of device language settings (Apple WebKit restriction). Added client-side `navigator.language` fallback that detects the actual browser language and sets the correct locale on first visit.

## [1.6.13] - 2026-06-03

### Fixed

- Minor bug fixes and improvements.

## [1.6.12] - 2026-06-02

### Fixed

- **Critical — Stripe trial abuse**: users who canceled a subscription could re-subscribe and receive another free 7-day trial indefinitely. Added `trial_used` boolean field to `User` model; the Stripe Checkout session only includes `trial_period_days` when `trial_used = False`. The field is set to `True` when a `trialing` subscription is first activated and is never reset. Migration `0028_trial_used` backfills existing subscribers to `trial_used = True`.

## [1.6.11] - 2026-06-02

### Fixed

- Minor bug fixes and improvements.

## [1.6.10] - 2026-06-01

### Added

- **Interface language selector**: users can now choose their preferred platform language (menus, buttons, labels) independently of their native language, from the Settings page. The preference is persisted in the database and applied immediately on save.
- **Save word to vocabulary** (reading exercises): selecting a single word in a reading text shows a floating tooltip; clicking "Save" uses AI to generate a definition, example sentence, and translation, then saves the card with `source="from_text"`. A new **My Vocabulary** panel on the Flashcards page lists all saved words with delete support. Saved words flow into the normal SM-2 review queue.

### Fixed

- Minor bug fixes and improvements.

## [1.6.9] - 2026-05-31

### Added

- **Flashcards bulk endpoint**: new `POST /api/flashcards/bulk` endpoint to create multiple flashcards in a single request; duplicates (by word) are silently skipped.

### Fixed

- Billing section no longer shows a stale next-billing date for subscriptions that have already expired after cancellation.
- Flashcard bulk import correctly skips duplicate words within the same request payload.

## [1.6.8] - 2026-05-31

### Fixed

- Minor bug fixes and improvements.

## [1.6.7] - 2026-05-31

### Fixed

- Minor bug fixes and improvements.

## [1.6.6] - 2026-05-30

### Changed

- **Username normalization**: spaces in usernames are now automatically replaced with underscores and stored in lowercase on registration and admin user creation. Allowed characters remain letters, numbers, hyphens, underscores, and dots.
- **Username display**: usernames are now shown in lowercase across the sidebar, admin users list, and admin user detail page (existing values in the database are not modified).

### Fixed

- Minor bug fixes and improvements.

## [1.6.5] - 2026-05-28

### Fixed

- Minor bug fixes and improvements.

## [1.6.4] - 2026-05-25

### Changed

- **Kokoro TTS**: switched to official upstream image `ghcr.io/remsky/kokoro-fastapi-gpu:v0.4.0-cu128` which now properly ships Blackwell/RTX 50-series (sm_120) kernels. Documented GPU compatibility tiers for all NVIDIA architectures.
- **TTS router**: ignore client voice param when `TTS_PROVIDER=local` to prevent 400 errors from stale OpenAI voice names in localStorage.

## [1.6.3] - 2026-05-24

### Fixed

- Minor bug fixes and improvements.

## [1.6.2] - 2026-05-24

### Fixed

- Minor bug fixes and improvements.

## [1.6.1] - 2026-05-24

### Added

- **Progress-based study plan advancement**: the study plan now tracks progress with a dedicated `progress_day` counter instead of calendar dates. `progress_day` is a 0-indexed integer counting completed days; the current day is always derived from it regardless of when the user last logged in.
- **Auto-advance**: `GET /api/study-plan/today` automatically moves `progress_day` forward whenever all lessons for the current day are marked complete, so users are always presented with the next pending day without any manual action.
- **Skip day** (`POST /api/study-plan/skip-day`): users can skip the current day's lessons and move straight to the next one. Skipped but unfinished lessons become _pending_.
- **Pending lessons** (`GET /api/study-plan/pending-lessons`): returns incomplete lessons from days that have already been passed (via completion or skip). The dashboard shows a pending-lessons counter and a quick-access button linking to `/plan`.
- **Day-complete celebration**: the lesson player detects when completing a lesson triggers an auto-advance and shows a "Day complete" banner on the completion screen.
- **Dashboard progress bar**: a thin progress bar and "Day X of Y" label reflect the user's position in the plan at a glance.
- **DB migration** `0025_plan_progress_day`: adds `progress_day INTEGER NOT NULL DEFAULT 0` to `study_plans`; existing plans are back-filled based on the furthest completed lesson.
- **i18n**: `dashboard.dayProgress`, `dashboard.skipDay`, `dashboard.pendingLessons`, `lesson.dayComplete`, `lesson.dayCompleteMsg` keys added to all 10 locale files.

### Fixed

- Minor bug fixes and improvements.

## [1.6.0] - 2026-05-23

### Added

- **Voice transcript history**: voice conversations are now persisted as text transcripts alongside chat conversations. Every user utterance (STT) and assistant response is saved incrementally to `chat_history` during the session, grouped under a `Conversation` record with `source='voice'`. This means:
- Voice sessions appear in the tutor chat sidebar (with a mic icon) alongside regular text conversations.
- Users can click a past voice session to review the full transcript as text, exactly like a chat history.
- Clicking "Continue in Voice" from the chat appends new voice messages to the same conversation rather than starting a separate session.
- **Backend**: `Conversation` model gains a `source` column (`VARCHAR(10)`, default `'chat'`, values `'chat'`|`'voice'`). Alembic migration `0021_conversation_source.py`. `ConversationPipeline` now accepts `conversation_id` and calls `_save_message()` (fire-and-forget via `asyncio.create_task`) after each STT transcription and each completed LLM response. The WebSocket handler creates a `Conversation` row on session start with a localized title ("Sesión de voz — 23 de mayo de 2026", etc.) and reuses an existing `conversation_id` when provided by the frontend.
- **Title translation**: `voice_session_title()` in `language_helpers.py` maps "Voice session" to all 9 supported native languages with localized month names and date formatting.
- **Frontend**: `ConversationResponse` and the React `Conversation` interface now include `source`. The sidebar shows a mic icon (🎤) for voice-originated conversations. The `voice_context` sessionStorage payload was upgraded from a plain array to `{messages, conversation_id}` so the WebSocket can append to the same conversation.
- **LLM Memory**: the AI tutor can now autonomously remember important details about the student (preferences, goals, profession, interests, learning struggles) across conversations. The LLM appends a `<<MEMORY>>...<<ENDMEMORY>>` marker to its response when it learns something noteworthy; the backend strips it before the student sees the reply and persists the fact to a new `memories` table. Memories are injected into the system prompt for both text chat and voice conversation, giving the tutor persistent context across sessions. Cero extra coste de tokens — no hay llamadas adicionales al LLM.
- **Backend**: new `Memory` model (`memories` table via Alembic `0022_memory.py`). `memory_service.py` handles marker parsing, stripping, deduplication, and system-prompt formatting (max 20 memories × 200 chars). `chat.py` and `conversation_pipeline.py` detect the marker during streaming and never expose it to the user. `GET /api/memories`, `DELETE /api/memories/{id}`, `DELETE /api/memories` endpoints for user management.
- **Frontend**: new _Memory_ section in Settings where users can view and delete individual saved memories or clear all. A "Memory updated" toast appears briefly (3.5 s) in both chat and voice when new memories are persisted.
- **i18n**: `settings.sectionMemory`, `settings.memoryEmpty`, `settings.memoryClearAll`, `settings.memoryClearAllTitle`, `settings.memoryClearAllMessage`, `settings.memoryClearAllConfirm`, `chat.memoryUpdated`, `conversation.memoryUpdated` keys added to all 10 locale files.

## [1.5.7] - 2026-05-22

### Added

- **Phase 8 — Feedback board**: users can submit feature requests and bug reports, vote on suggestions, and leave comments. Entries are visible to all logged-in users. Admins can update entry status and delete any entry from a dedicated admin panel.
- **Backend**: three new DB tables (`feedback_entries`, `feedback_votes`, `feedback_comments`) with Alembic migration `0020_feedback.py`. `FeedbackEntry` stores type (`feature`|`bug`), title, description, status, author and a denormalised `vote_count`. `FeedbackVote` enforces one vote per user per feature (`UNIQUE(entry_id, user_id)`). `FeedbackComment` stores flat comment threads with cascade delete from the parent entry.
- **Router** (`app/routers/feedback.py`): 9 endpoints under `/api/feedback` — list (paginated, sortable by votes or date, filterable by type and status), create, get detail, delete (author or admin), toggle vote (features only), update status (admin only), list comments, add comment, delete comment.
- **Rate limits**: 10/hour for entry creation, 20/hour for comments, 60/min for reads, 30/min for votes and status updates.
- **Frontend** (`/feedback`): two-tab layout (Suggestions / Bug reports). Each tab shows a paginated list sorted by votes (default) or date, with inline vote toggle (▲), status badge, author, date, and comment count. Clicking an entry opens a detail view with the full description, a flat comment thread, and forms to add/delete comments. Admin users see a delete button on all entries; regular users see it only on their own. Pagination pattern identical to the admin users list.
- **Admin panel** (`/admin/feedback`): paginated table with filter by type and status. Status can be changed inline (click the badge → dropdown → auto-save). Entries can be deleted with confirmation. Accessible at `/admin/feedback`.
- **Status workflow**: `pending` → `planned` → `in_progress` → `done` / `declined`. Each status has a distinct colour badge consistent with the existing design system (grey / blue / yellow / green / red).
- **Navigation**: `/feedback` added to `bottomNavItems` in the sidebar (alongside Settings and FAQ) and to `PROTECTED_ROUTES` in `middleware.ts`.
- **i18n**: `feedback` namespace (44 keys) added to all 10 locale files (en, es, fr, de, it, nl, pl, pt, ro, ru) with full translations. `nav.feedback` key added to all locales.
- **Maintenance mode**: admin can toggle a maintenance mode from the admin users panel (`/admin/users`) via `PATCH /api/admin/maintenance`. When active, the four subscription-gated features (tutor chat, voice conversation, listening, reading) are blocked with a 503 backend response and a static maintenance banner in the frontend. No restart required — stored in Redis (`maintenance_mode` key). The toggle does not affect free features (lessons, flashcards, assessment, progress, etc.). Backend: `get_redis()` centralized in `deps.py`, `check_maintenance_mode()` plus explicit maintenance guards separate from subscription checks. Frontend: `MaintenanceGate` component, `config.ts` extended with `maintenanceMode`, `PaywallGate` unchanged.

### Fixed

- **`lesson/[id]` no longer paywalled**: removed `PaywallGate` wrapper from the lesson page. Lessons are free features and were incorrectly gated on the frontend (the backend never required subscription for lessons).

## [1.5.6] - 2026-05-20

### Fixed

- Minor bug fixes and improvements.

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
- **Voice selector in Settings**: new _Voice_ section visible only when `TTS_PROVIDER=openai`. Users can preview all 9 OpenAI TTS voices (alloy, ash, coral, echo, fable, nova, onyx, sage, shimmer) with inline play/stop buttons and select their preferred voice. Selection is persisted in `localStorage` (key `tts_voice`); default is the server-configured `OPENAI_TTS_VOICE`.
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

- Pricing section: crossed-out original prices (x €/month, x €/year) shown above current launch prices using `text-fl-muted-2 line-through`.
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
- `PaywallBanner` and `PaywallGate` components: paywall overlay with monthly and yearly plan buttons; renders nothing when Stripe is disabled
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
- `docker-compose.yml` updated to use fork image `ghcr.io/artcc/kokoro-fastapi-gpu:v0.2.4-master` with full Blackwell support
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
