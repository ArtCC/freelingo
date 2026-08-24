---
description: "Frontend architecture reference for FreeLingo: directory structure, pages, components, state management, utilities, code standards, page content width convention, and test configuration."
applyTo: "frontend/**"
---

# Architecture — Frontend

> The general architecture overview (repository structure, data flows, auth design) lives in [architecture.instructions.md](architecture.instructions.md). Backend-specific architecture lives in [architecture-backend.instructions.md](architecture-backend.instructions.md).

## Directory structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── (auth)/              # Public routes (7 pages)
│   │   │   ├── billing/         # Stripe-managed billing (redirect)
│   │   │   ├── forgot-password/
│   │   │   ├── login/
│   │   │   ├── onboarding/      # Post-registration language + level setup
│   │   │   ├── register/
│   │   │   ├── reset-password/
│   │   │   └── verify-email/
│   │   │
│   │   ├── (app)/               # Authenticated routes — sidebar layout
│   │   │   ├── layout.tsx       # Sidebar + global layout shell
│   │   │   ├── loading.tsx
│   │   │   ├── admin/           # Admin overview + admin-only management routes
│   │   │   ├── admin/users/     # User list + [id] detail: tabs, quotas, subscription override
│   │   │   ├── admin/feedback/  # Feedback queue admin panel: search, filters, responsive table/cards
│   │   │   ├── admin/reviews/   # Review moderation: filters, approve/unapprove, delete
│   │   │   ├── admin/system/    # Maintenance mode + dashboard announcement editor
│   │   │   ├── assessment/      # Level test: BeginnerGate → AdaptiveQuizCard → DurationSelector → optional/persistent voice trial offer
│   │   │   ├── chat/            # AI tutor SSE chat + conversation history
│   │   │   ├── conversation/    # Real-time voice conversation (WebSocket + VAD) + post-assessment trial entry/profile sync
│   │   │   ├── dashboard/       # Home: announcement, next step, progress stats, plan summary, daily lessons
│   │   │   ├── faq/             # Frequently asked questions
│   │   │   ├── feedback/        # Feature requests & bug reports board
│   │   │   ├── flashcards/      # Spaced-repetition flashcard review
│   │   │   ├── grammar/         # Grammar reference (index + [slug] detail)
│   │   │   ├── lesson/[id]/     # Lesson player with exercises
│   │   │   ├── listening/       # AI-generated listening exercises
│   │   │   ├── phrasebook/      # Common phrases by category
│   │   │   ├── plan/            # Study plan overview + unit drawer
│   │   │   ├── progress/        # Skills tracker with radar chart
│   │   │   ├── reading/         # AI-generated reading comprehension
│   │   │   ├── settings/        # Settings hub: account, learning, voice, plan/usage, review
│   │   │   └── vocabulary/      # Vocabulary hub (index + [setId] detail)
│   │   │
│   │   ├── (legal)/             # Minimal layout (2 pages)
│   │   │   ├── layout.tsx
│   │   │   ├── privacy/
│   │   │   └── terms/
│   │   │
│   │   └── api/                 # Next.js Route Handlers (proxies to backend)
│   │       ├── chat/route.ts    # SSE chat streaming proxy
│   │       ├── stt/route.ts     # STT proxy
│   │       └── tts/route.ts     # TTS proxy
│   │
│   ├── components/              # 14 directories + 7 standalone files
│   │   ├── assessment/          # AdaptiveQuizCard, BeginnerGate, DurationSelector
│   │   ├── admin/               # AdminNav + AdminShell primitives shared across admin pages
│   │   ├── billing/             # Stripe subscription UI components
│   │   ├── chat/                # Chat message components
│   │   ├── conversation/        # ConversationMode, MicButton, StatusIndicator, TranscriptBubble...
│   │   ├── dashboard/           # Locale-aware dismissible DashboardAnnouncement
│   │   ├── flashcard/           # Flashcard review components
│   │   ├── lesson/              # Lesson exercise components
│   │   ├── plan/                # LevelTestBanner, UnitCard, UnitDrawer
│   │   ├── reviews/             # ReviewPrompt, reusable ReviewForm, landing reviews carousel
│   │   ├── settings/            # Settings shell primitives and form sections
│   │   ├── tour/                # OnboardingTour components
│   │   ├── ui/                  # shadcn/ui + custom: AudioPlayer, VoiceRecorder, confirm-dialog...
│   │   ├── whats-new/           # What's New changelog modal
│   │   ├── CookieBanner.tsx
│   │   ├── AuthAvatarImage.tsx   # Private current-user avatar fetch/render helper with caller-provided placeholder fallback
│   │   ├── LanguageSwitcher.tsx
│   │   ├── TargetLanguageText.tsx # Language-aware typography wrapper for learned-language content
│   │   ├── TargetLanguageSelector.tsx
│   │   └── ThemeProvider.tsx
│   │
│   ├── data/                    # Static content: curriculum, grammar, phrasebook — vocabulary + assessment now in backend
│   │   ├── types.ts              # Shared TypeScript types (CEFRLevel, AssessmentQuestion, VocabularyEntry, VocabularySet, etc.)
│   │   ├── curriculum.ts         # Curriculum definitions — language-aware dispatcher (API-backed)
│   │   ├── grammar.ts            # Grammar reference — language-aware dispatcher
│   │   ├── phrasebook.ts         # Phrasebook — language-aware dispatcher
│   │   ├── en/                   # English (3 files: curriculum, grammar, phrasebook)
│   │   ├── es/                   # Spanish (3 files)
│   │   ├── it/                   # Italian (3 files)
│   │   └── pt/                   # Portuguese (3 files)
│   │
│   ├── store/                   # Zustand stores (7)
│   │   ├── auth.ts              # Access token, user info, login/refresh/logout, banner dismissal revision
│   │   ├── config.ts            # Public config: runtime flags, prices, maintenance, active dashboard banner
│   │   ├── freemium.ts          # Freemium quota status, fetchStatus(), decrement per-feature
│   │   ├── language.ts          # UI locale + target language state
│   │   ├── loading.ts           # Global loading spinner state
│   │   ├── progress.ts          # XP, streak, skill scores, dashboard data
│   │   └── theme.ts             # Dark/light/system theme
│   │
│   ├── lib/                     # Utility modules (12)
│   │   ├── api.ts               # apiFetch: auth interceptor, 401 → silent refresh → retry
│   │   ├── audio.ts             # Audio player, audio queue, gapless playback helpers
│   │   ├── billing-copy.ts      # Billing CTA copy helpers and shared BillingInterval type
│   │   ├── conversation-vad.ts  # End-of-turn silence window for voice conversation (user setting + CEFR fallback)
│   │   ├── conversation-ws.ts   # WebSocket client for voice conversation
│   │   ├── landing-subscription.ts # Shared landing subscription-status check
│   │   ├── locales.ts           # Locale utilities for next-intl
│   │   ├── mappers.ts           # Data transformation / mapping utilities
│   │   ├── reviews.ts           # Review API client helpers
│   │   ├── target-languages.ts  # Target language definitions and helpers
│   │   ├── utils.ts             # General utility functions
│   │   └── review-prompt-triggers.ts # Review prompt trigger rules for voice sessions, unit completion, and exercise completion
│   │
│   ├── i18n/
│   │   └── request.ts           # next-intl request locale resolver
│   │
│   └── middleware.ts            # Auth guard (redirect to /login) + locale detection
│
├── tests/                       # Vitest suite (43 test files, 460 tests; coverage not configured)
│   ├── setup.ts                 # Global mocks: localStorage, next/navigation, next-intl
│   ├── middleware.test.ts
│   ├── components/
│   │   ├── LanguageBubbles.test.tsx
│   │   ├── LanguageSwitcher.test.tsx
│   │   └── TargetLanguageSelector.test.tsx
│   ├── data/
│   │   └── curriculum.test.ts
│   ├── lib/
│   │   ├── api.test.ts
│   │   ├── audio.test.ts
│   │   ├── conversation-ws.test.ts
│   │   ├── mappers.test.ts
│   │   └── target-languages.test.ts
│   └── store/
│       ├── auth.test.ts
│       ├── config.test.ts
│       └── language.test.ts
│
├── public/                      # Static assets
│   ├── apple-touch-icon.png
│   ├── favicon.ico
│   ├── favicon.png
│   ├── github.svg
│   ├── github_white.svg
│   ├── logo.png
│   ├── og-image-v2.png
│   ├── flags/                   # Language flag SVGs
│   └── vad/                     # Silero VAD ONNX models for browser WASM
│
├── messages/                    # i18n message bundles (en, es, fr, pt, de, it, nl, pl, ro, ru)
│   ├── en.json
│   ├── es.json
│   └── ...
│
└── scripts/
    └── copy-vad-models.js       # Postinstall: copies VAD WASM models to public/
```

## Page routes

### Background policy

- Public surfaces use `bg-dot-grid` over `bg-fl-bg`: the `/` landing page, `(auth)` routes, and `(legal)` routes.
- The authenticated `(app)` shell uses a solid `bg-fl-bg` without `bg-dot-grid`. Its route-level loading fallback and session-initialization loading state follow the same solid treatment so hydration and authentication do not flash a different background pattern.

### Public (auth) routes — `(auth)/`

- `/login` — Email + password login.
- `/register` — Registration form with native language selection. Optional `plan=monthly|yearly` is preserved into onboarding.
- `/onboarding` — Post-registration language preferences and level setup. Optional `plan=monthly|yearly` highlights the selected billing interval before Stripe Checkout. Without a monthly preselection, the yearly plan is the primary trial CTA and monthly is the flexible alternative. If onboarding is reloaded after registration and the refresh cookie exists but no access token is in memory, it refreshes `/api/auth/refresh` before creating the Stripe Checkout session.
- `/verify-email` — Email verification token handler.
- `/forgot-password` — Request password reset email.
- `/reset-password` — Reset password with token.
- `/billing` — Stripe Customer Portal redirect managed by Stripe.
- `/billing/success` — Stripe Checkout return page. Refreshes session when needed, confirms `/api/auth/me` reports `active` or `trialing` before showing Premium-active copy, and otherwise shows subscription-confirmation pending copy.
- `/billing/canceled` — Stripe Checkout cancellation page with no-charge copy and links back to app billing surfaces.

### Authenticated routes — `(app)/`

- `/dashboard` — Home: action-oriented overview using existing progress and study-plan data. An active global announcement is inserted above the next-step card, selects the current UI-locale translation with English fallback, and hides when the authenticated user's dismissed revision matches the server revision; dismissing persists through `PUT /api/dashboard-banner/dismiss` and updates auth state without a reload. The page also shows the active language/level, a primary next-step card, streak/XP/lesson/accuracy stats, plan-progress summary with compact current-level vocabulary progress, today's lessons with completion count and next pending lesson highlight, recent-performance areas derived from `skills`, pending-lesson link, a freemium trial countdown banner when the trial is active, a compact Premium banner for unsubscribed users when Stripe is enabled, and shortcuts to plan, flashcards, tutor, and assessment. The Premium banner presents trial-focused messaging and the shared subscription buttons directly, recommending yearly first and keeping monthly as the flexible alternative. If the user's subscription is `past_due`, `unpaid`, or `paused`, the banner instead shows payment-recovery copy and opens the Stripe Customer Portal to update payment details.
- `/assessment` — Level placement test (`BeginnerGate` → `AdaptiveQuiz` → `DurationSelector`).
- `/plan` — Study plan overview: unit cards, `LevelTestBanner`, and `UnitDrawer`. Scheduled slots are merged with generated lesson metadata, today's lessons, and skipped pending lessons so the drawer offers Start, Resume, or Review according to persisted state while leaving future ungenerated slots unavailable. Drawer actions reuse the overview's solid primary button treatment; its moderately wider desktop layout adds a localized lesson-count heading, roomier actionable rows, and a sticky close footer without changing the mobile full-width presentation.
- `/lesson/[id]` — Lesson player: content + interactive exercises. If `content.native_explanation` exists, it is shown below the target-language explanation in a collapsible section that opens by default for A1/A2 and stays collapsed by default for B1+. The section renders translated text, key points, examples, common traps, and a mini-glossary when present. If it is missing, the expanded section shows a native-language button that calls `POST /api/lessons/{id}/native-explanation` and stores the returned explanation in local lesson state. Before an unanswered exercise, the page can show a native-language hint button; if the exercise response includes `native_hint`, it renders immediately when requested, otherwise the button calls `POST /api/lessons/exercises/{id}/native-hint` and patches the exercise in local state. The exercise card header also includes a small `Regenerate exercise` action for unanswered exercises; it calls `POST /api/lessons/exercises/{id}/regenerate`, replaces the current exercise in local state when the backend confirms a technical issue, and shows a small inline error if regeneration is rejected or fails. Exercise feedback still shows the target-language explanation first; when an exercise response includes `native_explanation`, the lesson page renders that native-language clarification directly below the target-language exercise explanation. When the exercise has a target-language explanation but lacks native text, the same button pattern calls `POST /api/lessons/exercises/{id}/native-explanation` and patches the exercise in local state. The lesson vocabulary block renders target-language word, definition, example audio, and example text, plus optional reading, native-language translation, example translation, and usage note when present; older vocabulary items without those optional fields still render normally. Completing a lesson may open the reusable review prompt when it advances the user out of the completed curriculum unit, subject to duplicate-review checks and local dismissal cooldown.
- Completed lessons reuse `/lesson/[id]` in read-only review mode. Saved responses and feedback remain visible, answer/regeneration and quota controls are unavailable, and the final action returns to `/plan` without completing or rewarding the lesson again.
- First-time lesson completion disables duplicate submissions immediately and force-refreshes the freemium status after success instead of decrementing cached quota optimistically.
- `/chat` — AI tutor text chat with SSE streaming. Free-tier users see a `FreemiumQuotaBanner` with daily chat message counter; when the quota is exhausted, a compact `PaywallBanner` replaces the chat input. Premium users see the normal chat interface.
- `/conversation` — Real-time voice conversation with WebSocket + VAD. Free-tier users see a `FreemiumQuotaBanner` with weekly voice minutes counter; when quota is exhausted, a compact `PaywallBanner` is shown. When the user manually stops a connected voice session after at least 5 minutes, the page may open the reusable review prompt, subject to duplicate-review checks and local dismissal cooldown.
- `/flashcards` — Spaced-repetition flashcard review.
- `/grammar` — Grammar reference index using the active learning language, with `en-GB` fallback.
- `/grammar/[slug]` — Grammar topic detail page. Includes a native-language helper section below the target-language explanation: A1/A2 opens and generates automatically, while B1-C2 stays collapsed and generates only when opened. The section calls `POST /api/grammar/{slug}/native-help`, then renders summary, explanation, key points, examples, common traps, and mini-glossary entries.
- `/vocabulary` — Vocabulary hub overview.
- `/vocabulary/[setId]` — Vocabulary set detail. Includes an on-demand native-language helper section that calls `POST /api/vocabulary/{set_id}/native-help`, then renders a summary, study tips, selected word notes, common traps, mini-glossary entries, and practice prompts. The section stays collapsed until requested to avoid LLM calls on page load.
- `/phrasebook` — Common phrases by category. Each category can show native-language study help generated through `POST /api/phrasebook/{category_id}/native-help`: A1/A2 categories open the helper panel by default but still require a click to generate, while B1-C2 categories stay collapsed until requested. The helper renders summary, usage tips, register notes, phrase notes, common traps, and mini-glossary entries.
- `/listening` — AI-generated listening comprehension exercises. During an active exercise, selecting one word in a question prompt opens the shared vocabulary-save tooltip and submits the prompt as lookup context; answer options remain normal selection controls. Its attempt history uses the shared pagination component with 10 results per page and sends `skip`/`limit` to the backend. Free-tier users see a `FreemiumQuotaBanner` with weekly exercise counter; when quota is exhausted, a compact `PaywallBanner` is shown. Completing a new listening attempt may open the reusable review prompt, subject to duplicate-review checks and local dismissal cooldown; replay attempts from history do not trigger it.
- `/reading` — AI-generated reading comprehension exercises. During an active exercise, the passage and question prompts allow one selected word to be saved through the shared vocabulary-save tooltip; answer options remain normal selection controls. Its attempt history uses the shared pagination component with 10 results per page and sends `skip`/`limit` to the backend. Free-tier users see a `FreemiumQuotaBanner` with weekly exercise counter; when quota is exhausted, a compact `PaywallBanner` is shown. Completing a new reading attempt may open the reusable review prompt, subject to duplicate-review checks and local dismissal cooldown; replay attempts from history do not trigger it.
- `/progress` — Skills tracker with radar chart and multi-level vocabulary progress toggle.
- `/settings` — Settings hub with an admin-inspired header/nav, quick action cards, and grouped panels. Account contains profile/avatar/password plus legal/session actions; avatars are uploaded/deleted through authenticated profile endpoints and rendered through the authenticated `/api/auth/me/avatar-file` endpoint with a shared client-side blob cache. Avatar fetches retry once through the refresh-token flow after a 401, and UI surfaces use the same initial-letter placeholder while the private image blob is loading or unavailable. Avatar file references are not public static URLs. Learning links to My Languages and Memory; `/settings/memories` explains global cross-language memory and supports authenticated manual add, list, individual delete, and clear-all with explicit loading, retry, duplicate, busy, success, and error states. Voice contains conversation and TTS voice preferences; Plan contains billing and usage limits with shared subscription buttons that recommend yearly first for unsubscribed users; `past_due`, `unpaid`, and `paused` subscriptions show payment-recovery copy and a Stripe Customer Portal action instead of new plan buttons. `none`, `incomplete`, `incomplete_expired`, and `canceled` show normal monthly/yearly plan buttons. Community contains review creation/editing.
- `/faq` — Frequently asked questions.
- `/admin/reviews` — Admin-only review moderation with 10 reviews per page, status/rating filters, approve/unapprove, and delete confirmation.
- Onboarding Checkout — If a user reloads onboarding after registration and the refresh cookie exists but no access token is in memory, onboarding refreshes `/api/auth/refresh` before creating the Stripe Checkout session for the selected monthly/yearly plan.
- Landing page — The primary CTA sends anonymous visitors to registration and authenticated visitors to the dashboard. Pricing plan CTAs for hosted subscriptions preserve monthly/yearly intent with `plan=monthly|yearly` through registration and onboarding before Stripe Checkout for anonymous visitors; authenticated unsubscribed visitors start Stripe Checkout directly from the selected monthly/yearly pricing button, refreshing the access token from the session cookie first when needed. The pricing and trial copy separates the free-trial promise from the later paid price, highlights yearly as the best-value option with two months free, labels monthly as the flexible alternative, and repeats no-charge-today/cancel-anytime reassurance only when trial eligibility is unknown or `trial_used=false`; authenticated users with `trial_used=true` see neutral plan-selection and amount-confirmation copy instead. The bottom pricing CTA defaults to yearly intent and starts yearly Checkout directly for authenticated unsubscribed users. `/billing/canceled` uses neutral no-charge-in-this-session copy and sends users back to the dashboard or settings plans without promising future trial availability. The shared paywall detects premium-gated route context for chat, voice conversation, listening, and reading so the upgrade message matches the user's attempted action; its free-path exit remains available but visually secondary. The top navigation includes a Reviews anchor between Features and Pricing when approved public reviews are available; the same conditional link appears in the mobile menu. The Features, Reviews, Pricing, and FAQ anchor targets use `scroll-mt-16` so their content clears the sticky `h-14` navigation bar. Public landing sections for features, reviews, pricing, open source, and FAQ share `max-w-5xl` content width for consistent horizontal rhythm; the hero and footer keep their own composition. The reviews section requests up to 100 approved reviews, shows a compact average-rating and total-review-count badge below the subtitle, uses localized formatting and public-facing copy, and presents the results in an unpaginated carousel. Review cards keep a consistent height and clamp long comments to 6 lines.
- `/feedback` — Feature requests and bug reports board (community), paginated at 10 entries per page. Entry list metadata, entry detail metadata, and comment headers render the shared gold `AdminAuthorBadge` beside the display name only when the embedded author role is `admin`.
- `/admin` — Admin overview with aggregated metrics including pending feedback and pending review approvals, operational alerts, quick links to users/feedback/reviews, and a read-only maintenance-mode status whose System Controls action links to `/admin/system` (admin only).
- `/admin/users` — User management with responsive table/cards, search, filters, invite copy workflow, and a create-user sheet with required email (admin only). The desktop table uses fixed column widths: user 25%, email 25%, role 12.5%, status 12.5%, subscription 15%, actions 10%; subscription badges stay on one line and truncate with an ellipsis when localized labels exceed the available width. Invite and create-user action buttons rely on their icons for the leading action affordance and do not include a duplicate `+` in localized labels.
- `/admin/users/[id]` — Admin user detail with summary header and tabs for Profile, Languages, Activity, Quotas, and Subscription. Quotas separate current usage from configured limits; email verification and subscription overrides use confirmation dialogs.
- `/admin/feedback` — Feedback queue admin panel with 10 entries per page, search, type/status/sort filters, filtered metrics by feedback type, desktop table, mobile cards, status updates, delete confirmation, and the same administrator-author badge used by the community board. Status updates refresh the queue when the updated entry no longer matches the active filter (admin only).
- `/admin/system` — Dedicated system-controls page. It preserves the explicit `PUT /api/admin/maintenance` flow and also loads `GET /api/admin/dashboard-banner`, lets an admin compose source text in any of the ten UI locales, previews LLM-generated translations, edits each locale, selects active/inactive state, and saves the complete map with `PUT /api/admin/dashboard-banner`. Translation is preview-only until Save, and the editor keeps source content when generation fails.

### Legal routes — `(legal)/`

- `/privacy` — Privacy policy, including global/manual memory storage and preservation when a learning language is deleted
- `/terms` — Terms of service

### API route handlers

These are Next.js Route Handlers that proxy requests to the backend:

- `/api/chat` — Method: POST; Purpose: SSE chat streaming proxy
- `/api/tts` — Method: POST; Purpose: Text-to-speech proxy
- `/api/stt` — Method: POST; Purpose: Speech-to-text proxy

## State management (Zustand)

Seven Zustand stores hold all client-side state. No React Context is used for global state.

- `auth` — Persisted?: No (JS memory); Key state: `accessToken`, `user` including `dismissed_dashboard_banner_revision`, `setDismissedDashboardBannerRevision()`, `isAuthenticated`, `login()`, `refresh()`, `logout()`, `isFreemiumTrialActive()`
- `config` — Persisted?: No; Key state: `maintenanceMode`, `availableLanguages`, `stripeEnabled`, `freemiumTrialEnabled`, `dashboardBanner`, and other public values from `GET /api/config`
- `freemium` — Persisted?: No; Key state: `status: FreemiumStatus | null`, `fetchStatus()`, `decrement(feature: string)` — tracks trial state and per-feature remaining quotas
- `language` — Persisted?: Yes (localStorage); Key state: `targetLanguage` (BCP-47), `uiLocale`, language switcher state
- `loading` — Persisted?: No; Key state: `isLoading`, `startLoading()`, `stopLoading()` — global spinner control
- `progress` — Persisted?: No; Key state: `xp`, `streak`, `skillScores`, `planSummary` — fetched from backend
- `theme` — Persisted?: Yes (localStorage); Key state: `"light"` / `"dark"` / `"system"`

## Utility modules (`lib/`)

- **`api.ts`** — Fetch wrapper with auth interceptor: injects `Authorization` header, catches 401 → silent refresh → retry, redirects to `/login` on refresh failure
- **`audio.ts`** — Audio playback queue for voice conversation; tracks real queue idle state so the UI clears "speaking" only after playback drains
- **`conversation-ws.ts`** — WebSocket client for the voice conversation pipeline, handles WAV chunk sending and MP3 reception
- **`landing-subscription.ts`** — Shared landing-page subscription check used by `LandingNav` and `PricingSection`; deduplicates refresh + `/api/auth/me` so the nav hides `Pricing` whenever the pricing section is hidden for active/trialing subscribers
- **`locales.ts`** — next-intl locale detection and routing utilities
- **`mappers.ts`** — Data transformation helpers between API responses and frontend models. `mapUser()` carries subscription metadata, freemium state, and `dismissed_dashboard_banner_revision` into the auth store, with safe fallbacks for partial PATCH responses.
- **`billing-copy.ts`** — Shared billing CTA helpers and `BillingInterval` type; splits yearly CTA copy so the savings label renders on a stable second line instead of orphaning the trailing arrow in long locales.
- **`target-languages.ts`** — Target language definitions: BCP-47 codes, display names, flag mappings, ISO codes, script/romanisation metadata, word-spacing capability, and language-specific font class helpers. `TARGET_LANGUAGE_CATALOG` and `SUPPORTED_TARGET_LANGUAGES` contain all 10 frontend-known target languages, including Japanese, Korean, and Mainland Chinese. User-visible options are constrained by backend `availableLanguageCodes` when provided.
- **`utils.ts`** — General-purpose utilities: formatting, date helpers, class name merging

## Components overview

### Page-specific components

- `assessment/` — `AdaptiveQuizCard`, `BeginnerGate`, `DurationSelector`
- `admin/` — `AdminNav`, `AdminPageHeader`, `AdminPanel`, `AdminMetric`, `AdminBadge` shared across admin pages
- `billing/` — Stripe subscription management UI; landing `PricingSection` hides for active/trialing subscribers; `MaintenanceGate` hides gated pages from non-admin users during maintenance. `FreemiumQuotaBanner` displays quota counters and trial badge for free-tier users. `PaywallBanner` supports a `compact` prop for inline upsell on freemium-exhausted pages; the `PaywallGate` wrapper component has been removed in favor of per-page freemium checks.
- `chat/` — Message display, input, SSE stream handling
- `conversation/` — `ConversationMode`, `MicButton`, `StatusIndicator`, `TranscriptBubble`, VAD integration
- `memory/` — Shared accessible `MemorySavedToast` used by text and voice tutoring
- `feedback/` — `AdminAuthorBadge`, a compact gold `ADMIN` marker rendered only for feedback authors whose embedded API role is `admin`
- `flashcard/` — Flashcard flip animation, SM-2 rating buttons
- `lesson/` — Exercise renderers (multiple choice, fill-in-blank, listening, reading)
- `plan/` — `LevelTestBanner`, `UnitCard`, `UnitDrawer`
- `settings/` — `SettingsShell` primitives plus profile/avatar, appearance, billing, usage, conversation, voice, memory/language links, and review sections
- `tour/` — `OnboardingTour` step-by-step walkthrough
- `whats-new/` — Version-aware changelog overlay modal

### App shell notifications

- `frontend/src/app/(app)/layout.tsx` fetches `GET /api/feedback/unread-summary` after authenticated initialization and renders a fixed circular red badge on the Feedback navigation item in both desktop and mobile menus. The display is capped at `99+` and hidden at zero. The sidebar also shows a trial countdown badge when the user has an active freemium trial.
- `frontend/src/app/(app)/feedback/page.tsx` shows a red unread label beside the entry status badge when `unread_by_me` is true. It marks only the opened feedback detail thread as read with `POST /api/feedback/{entry_id}/read`, updates the visible list item, then dispatches `freelingo:feedback-read` so the app shell refreshes the sidebar badge.

### Shared/generic components

- **`ThemeProvider.tsx`** — Dark/light/system theme via the persisted Zustand `theme` store. The root `src/app/layout.tsx` also injects a small head script that reads `localStorage.fl-theme` and `prefers-color-scheme` before first paint, applying `html[data-theme='light']` when needed so light-system users do not see a dark initial flash on public or authenticated pages.
- **`TargetLanguageSelector.tsx`** — Language picker dropdown with flags. It renders entries from `TARGET_LANGUAGE_CATALOG` after filtering by `availableCodes` when that operator-provided list is present.
- **`TargetLanguageText.tsx`** — Reusable wrapper for content in the learner's target language. It applies `lang`, language-aware typography classes from `target-languages.ts`, and optional secondary reading/translation lines for future romanisation/pinyin support.
- **`LanguageSwitcher.tsx`** — UI locale switcher
- **`CookieBanner.tsx`** — GDPR cookie consent banner
- **`ui/`** — shadcn/ui primitives (`button`, `card`, `input`, `progress`, `badge`, `separator`, `sheet`, `tabs`) + custom: `AudioPlayer`, `VoiceRecorder`, `confirm-dialog`
- **Memory notification** — `useTransientToast` owns one resettable, unmount-safe timer and increments an announcement ID for every confirmed save. `MemorySavedToast` remounts its `role="status"`/`aria-live="polite"` region for consecutive announcements and tells the user the memory can be reviewed in Settings without exposing stored content or presenting a timed action. Failed, skipped, duplicate, or unsupported automatic memory work produces no user-facing message.

---

## Code standards (TypeScript / Next.js 16)

- ESLint — TypeScript linting + Next.js rules
- Prettier — Code formatting + `prettier-plugin-tailwindcss`

- No semicolons, single quotes, 2-space tabs, trailing commas "es5".
- shadcn/ui components installed: `button card input progress badge separator sheet tabs`.

### Page content width convention

Page wrappers use `mx-auto` plus the canonical widths below. Avoid introducing new sizes unless a page has a distinct interaction model or public marketing composition.

- `max-w-6xl` (`1152 px`) — Dense admin data pages, operational admin overview, and settings hub layouts such as admin, admin users, admin feedback, and settings.
- `max-w-5xl` (`1024 px`) — Public landing content sections such as features, reviews, pricing, open source, and FAQ; also lighter admin overview card layouts.
- `max-w-4xl` (`896 px`) — Standard private learning/content pages and resource views: dashboard, plan, progress, flashcards, listening, lessons, grammar, vocabulary, phrasebook, feedback, FAQ, language settings, memory settings, and reading non-exercise states.
- `max-w-3xl` (`768 px`) — Compact detail pages or legacy admin list pages.
- `max-w-2xl` (`672 px`) — Legacy/error-state wrappers only. Do not use for new private page shells.

Full-screen interactive experiences (conversation, chat, listening, reading, assessment), auth cards, legal pages, the landing hero, and the landing footer are exempt because they manage their own layout internally.

### Target-language typography

The global FreeLingo visual language remains mono-heavy: `Geist`/`Geist_Mono` are loaded in `src/app/layout.tsx`, and `globals.css` maps the default theme fonts to the mono variable. Do not change this globally when adding non-Latin target languages.

Content that is part of the language being learned must use the language-aware rendering path instead of raw `font-mono` text:

- `frontend/src/lib/target-languages.ts` stores `script`, `fontClass`, `usesWordSpacing`, and optional `romanization` metadata.
- `getTargetLanguageTextClass(code)` returns Latin-compatible mono styling for current Latin-script languages and CJK-friendly `font-target-ja`, `font-target-ko`, or `font-target-zh` classes for `ja-JP`, `ko-KR`, and `zh-CN` content.
- `TARGET_LANGUAGE_CATALOG` and `SUPPORTED_TARGET_LANGUAGES` include display metadata and flag paths for all 10 target languages, including `ja-JP`, `ko-KR`, and `zh-CN`. `TargetLanguageSelector`, Settings → My Languages, and Admin → Create User filter through operator-provided `availableCodes` / `availableLanguageCodes` when those values are available.
- `frontend/src/components/TargetLanguageText.tsx` applies the correct class and `lang` attribute. Use it for lesson content, exercise prompts/options, flashcards, reading/listening transcripts, phrasebook entries, vocabulary examples, assessment questions, and chat/conversation transcript text.
- `globals.css` defines `font-target-latin`, `font-target-ja`, `font-target-ko`, and `font-target-zh`. CJK classes use Noto variables when available plus platform fallbacks (`Hiragino Sans`/`Yu Gothic`/`Meiryo`, `Apple SD Gothic Neo`/`Malgun Gothic`, `PingFang SC`/`Microsoft YaHei`/`Noto Sans CJK SC`).

UI labels, levels, controls, navigation, and admin chrome may continue using `font-mono`, `uppercase`, and wide tracking. Do not apply `uppercase`, `tracking-widest`, or small mono text to learned-language CJK content.

---

## State flow — Auth interceptor

```
Any fetch via apiFetch()
    ↓
Add Authorization: Bearer <accessToken>
    ↓
Request succeeds? → return response
    ↓ 401 received
Silent call to POST /api/auth/refresh
    ↓
Refresh succeeds? → store new accessToken, retry original request
    ↓
Refresh fails? → clear auth store, redirect to /login
```

---

## State flow — SSE chat streaming

```
User sends message → POST /api/chat (SSE proxy)
    ↓
Next.js Route Handler forwards to backend SSE endpoint
    ↓
Backend: LLM Adapter streams tokens and memory status → SSE events
    ↓
Buffered `readSseData()` reassembles events across arbitrary network chunks:
  - token events → append to message accumulator
  - response_reset event → dismiss any word tooltip and clear the current assistant accumulator before fallback tokens arrive
  - memory_updated event → show the shared accessible memory toast
  - done event → finalize message, add to ChatHistory
  - error event → show error, stop streaming
  - missing terminal done/error or truncated final JSON → show a generic interrupted-conversation error
```

Word selection is disabled on the active assistant placeholder while a response is streaming and restored once that turn reaches `done` or `error`, preventing tooltips from retaining text invalidated by a reset.

---

## State flow — WebSocket voice conversation

```
User opens /conversation → load VAD WASM models
    ↓
WebSocket connects: new WebSocket(`/ws/conversation`)
    ↓
Client sends first JSON auth frame with access token, voice preference, target language, and optional chat context
    ↓
VAD detects speech → send WAV chunks via WS
    ↓
Server: STT → full LLM response → sentence-level TTS chunks
    ↓
Receive MP3 binary frames via WS → AudioQueue schedules playback in order
    ↓
AudioQueue drains → clear assistant speaking state from playback `onIdle`
```

`ConversationMode` guards the session lifecycle with a per-start attempt id. If microphone startup fails, the user stops the session, or the component unmounts while the warmup request is still pending, the pending attempt is invalidated so it cannot open a stale WebSocket afterwards.

The voice UI does not clear `assistantSpeaking` from `turn_complete` or `status=listening`; it waits for the audio queue idle callback so the visible speaking state follows actual playback. A separate assistant-turn guard ignores VAD detections while the tutor is generating or sending chunked audio, so automatic frontend barge-in remains disabled for stable turn completion while the backend `barge_in` protocol stays available.

## Tests

Testing infrastructure and strategy are documented in [testing.instructions.md](testing.instructions.md).

**Summary:**

- **Framework**: Vitest with jsdom environment
- **Test files**: 30 (plus setup.ts) covering critical logic only
- **Setup**: Global mocks for `localStorage`, `next/navigation`, `next-intl`
- **Coverage areas**: API fetch interceptor, auth store, audio queue, conversation WebSocket, target language utilities, mapper functions, middleware, component rendering
- **Coverage**: Not configured/reported (`@vitest/coverage-v8` is not installed)
