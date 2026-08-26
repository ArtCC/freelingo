---
description: "Phase 5 specification for FreeLingo: Stripe-backed subscription system with monthly/yearly plans, 7-day trial, Customer Portal, webhook handler, full paywall when STRIPE_ENABLED=true, and zero impact on self-hosted deployments when STRIPE_ENABLED=false."
applyTo: "backend/**, frontend/**, messages/**, docker-compose.yml, .env.example"
---

# Phase 5 — Stripe Subscriptions, Freemium & Paywall

## Objective

Introduce an optional, fully configurable subscription layer backed by Stripe, plus a freemium tier with daily/weekly usage quotas and a 7-day no-card trial. When `STRIPE_ENABLED=false` (the default for self-hosted deployments) the entire billing and freemium system is invisible — no paywall, no pricing page, no billing UI, no quota checks. When `STRIPE_ENABLED=true` users must have an active subscription, be in a freemium trial, or have remaining freemium quota to access AI-powered features.

The same visibility rule applies to administration. With Stripe disabled, the admin overview omits active/trialing metrics and past-due alerts; the user list omits and ignores subscription filtering and hides subscription values; and user detail omits subscription status, details, and override controls. Quota administration remains available independently.

---

## Plans

- Monthly — Price: x €/month; Billing: Monthly recurring; Trial: 7 days free (card required)
- Yearly — Price: x €/year (≈ x €/month, 2 months free); Billing: Annual recurring; Trial: 7 days free (card required)

### Quotas applied on subscription activation

Subscription activation applies the environment-configured defaults from `DEFAULT_CONVERSATION_*` and `DEFAULT_MONTHLY_TOKENS_LIMIT`:

- `conversation_weekly_sessions` — default `0` (unlimited)
- `conversation_weekly_minutes` — default `90`
- `conversation_daily_minutes` — default `30`
- `monthly_tokens_limit` — default `1 000 000`

Admin can still override any quota field per user via the admin panel regardless of subscription status.

---

## Freemium model

When `STRIPE_ENABLED=true`, users who have never subscribed get limited free access through a freemium tier. The model has two components:

### 7-day no-card trial

Set via `FREEMIUM_TRIAL_ENABLED=true` (default) and `FREEMIUM_TRIAL_DAYS=7` (default). On registration, new users receive `freemium_trial_ends_at = now + FREEMIUM_TRIAL_DAYS` days and `freemium_trial_used = true`. During the trial period, all 5 gated features are unlimited — the user experiences the full product without entering payment details. After the trial expires, daily/weekly quotas take over. `freemium_trial_used` prevents the trial from being granted again.

### Daily/weekly quotas (post-trial)

After the trial ends (or when `FREEMIUM_TRIAL_ENABLED=false`), free-tier usage is capped by per-feature quotas stored in Redis (not DB):

- **Chat** — `FREEMIUM_CHAT_DAILY_MESSAGES` (default `5`) AI chat messages per calendar day.
- **Lessons** — `FREEMIUM_LESSONS_DAILY` (default `3`) lesson completions per calendar day. Viewing lessons and exercises is always free.
- **Listening** — `FREEMIUM_LISTENING_WEEKLY` (default `3`) listening exercises per ISO week.
- **Reading** — `FREEMIUM_READING_WEEKLY` (default `3`) reading exercises per ISO week.
- **Voice** — `FREEMIUM_VOICE_WEEKLY_MINUTES` (default `5`) voice conversation minutes per ISO week.

Setting any quota variable to `0` blocks that feature entirely for free-tier users (shown as "Premium only" in the UI). Quota counters use Redis keys `freemium:{feature}:{user_id}:{date_or_week}` with auto-expiring TTL and atomic increment via a Lua script to prevent race conditions.

### Freemium status endpoint

`GET /api/freemium/status` (60/min, authenticated) returns trial status and remaining quotas for all 5 features in a single response, consumed by the frontend `FreemiumQuotaBanner` component.

---

## Access rules

- Register / Profile / Stats — `STRIPE_ENABLED=false`: pass; `STRIPE_ENABLED=true` + any: pass
- Progress / Streak — `STRIPE_ENABLED=false`: pass; `STRIPE_ENABLED=true` + any: pass
- Lessons (viewing/exercises) / Assessment / Flashcards — `STRIPE_ENABLED=false`: pass; `STRIPE_ENABLED=true` + any: pass
- Lesson completion (`POST /{lesson_id}/complete`) — `STRIPE_ENABLED=false`: pass; `STRIPE_ENABLED=true` + subscribed: pass; `STRIPE_ENABLED=true` + freemium trial: pass; `STRIPE_ENABLED=true` + freemium quota: pass (up to `FREEMIUM_LESSONS_DAILY`/day); `STRIPE_ENABLED=true` + no subscription + quota exhausted: 402 `freemium_exhausted`
- Chat con tutor — `STRIPE_ENABLED=false`: pass; `STRIPE_ENABLED=true` + subscribed: pass; `STRIPE_ENABLED=true` + freemium trial: pass; `STRIPE_ENABLED=true` + freemium quota: pass (up to `FREEMIUM_CHAT_DAILY_MESSAGES`/day); `STRIPE_ENABLED=true` + no subscription + quota exhausted: 402 `freemium_exhausted`
- Conversación por voz — `STRIPE_ENABLED=false`: pass; `STRIPE_ENABLED=true` + subscribed: pass; `STRIPE_ENABLED=true` + freemium trial: pass; `STRIPE_ENABLED=true` + post-assessment voice trial: pass; `STRIPE_ENABLED=true` + freemium quota: pass (up to `FREEMIUM_VOICE_WEEKLY_MINUTES`/week); `STRIPE_ENABLED=true` + no subscription + quota exhausted: 402 `freemium_exhausted`
- Listening exercises — `STRIPE_ENABLED=false`: pass; `STRIPE_ENABLED=true` + subscribed: pass; `STRIPE_ENABLED=true` + freemium trial: pass; `STRIPE_ENABLED=true` + freemium quota: pass (up to `FREEMIUM_LISTENING_WEEKLY`/week); `STRIPE_ENABLED=true` + no subscription + quota exhausted: 402 `freemium_exhausted`
- Reading exercises — `STRIPE_ENABLED=false`: pass; `STRIPE_ENABLED=true` + subscribed: pass; `STRIPE_ENABLED=true` + freemium trial: pass; `STRIPE_ENABLED=true` + freemium quota: pass (up to `FREEMIUM_READING_WEEKLY`/week); `STRIPE_ENABLED=true` + no subscription + quota exhausted: 402 `freemium_exhausted`
- Memory management — Authenticated users: pass in every Stripe/subscription state; users retain access to their stored personal context

**Access control:** `is_subscribed(user) = True` when `STRIPE_ENABLED=false` OR when `subscription_status in ("trialing", "active")`. The `require_subscription_or_freemium(feature)` dependency factory wraps this: if not subscribed, it checks for an active freemium trial or remaining quota for the given feature. If neither applies, it returns HTTP 402 with `{reason: "freemium_exhausted"}`.

Memory-management endpoints use `get_current_user` only. Listing, manually adding, deleting, and clearing memories are not subscription benefits and remain available to unsubscribed users.

**Post-assessment voice demo exception:** When `STRIPE_ENABLED=true`, unsubscribed users can use exactly one voice conversation demo after completing the placement assessment. The demo duration comes from `ASSESSMENT_VOICE_TRIAL_DURATION_SECONDS` (default `300`, 5 minutes). This does not change `is_subscribed()`, does not grant access to chat/listening/reading, and is tracked separately with `users.assessment_voice_trial_used` plus a Redis `assessment_voice_trial:{user_id}:{token}` credential. The token may expire and be regenerated while unused, including from the assessment page when the user already has a plan but previously skipped the demo; the durable right is consumed only when `/ws/conversation` starts.

### Maintenance mode

A runtime toggle (Redis flag `maintenance_mode`) that blocks all subscription-gated and freemium-gated features for non-admin users regardless of subscription or freemium status. This allows the admin to preventively disable LLM-dependent features (chat, voice conversation, listening, reading) without revoking API keys or changing environment variables, while admins can still access the gated sections to verify service health.

- **Backend**: `require_subscription` checks only subscription status. `require_subscription_or_freemium(feature)` checks subscription, then freemium trial, then freemium quota — all before the maintenance check. `require_not_maintenance` checks only `maintenance_mode` for non-admin users and returns HTTP 503 when active. Chat, listening, reading, and conversation warmup endpoints use `require_subscription_or_freemium` + `require_not_maintenance`; the WebSocket (`/ws/conversation`) checks the flag manually with the same admin bypass. Memory-management endpoints use authentication only, so subscription and maintenance state do not block user control of saved memories.
- **Frontend**: `MaintenanceGate` component renders a static banner for non-admin users. Applied on the four gated pages (`/chat`, `/conversation`, `/listening`, `/reading`). Lessons, flashcards, memory settings, and other free features are unaffected.
- **Admin toggle**: `/admin/system` shows the current state and sets it explicitly through `PUT /api/admin/maintenance` with `{maintenance_mode: boolean}` — no restart required. The overview retains a status summary that links to System; the Users page contains only user-management controls.

### Lesson completion is now freemium-gated

As of v1.8.25, lesson viewing and exercise answering remain free (`get_current_user`), but `POST /api/lessons/{lesson_id}/complete` now uses `require_subscription_or_freemium("lessons")`. This means free-tier users can complete up to `FREEMIUM_LESSONS_DAILY` lessons per day; viewing lesson content and answering exercises is always free regardless of subscription or freemium status.

---

## Environment variables

```env
# ── Stripe
# Set STRIPE_ENABLED=true to activate the subscription system.
# When false (default), all billing features are disabled and no paywall is shown.
# Self-hosted deployments should leave this false.
STRIPE_ENABLED=false

# Stripe secret key (sk_live_... or sk_test_... for development)
STRIPE_SECRET_KEY=sk_test_CHANGE_ME

# Webhook signing secret (whsec_...) — obtained from Stripe Dashboard → Webhooks
STRIPE_WEBHOOK_SECRET=whsec_CHANGE_ME

# Price IDs from Stripe Dashboard → Product catalog.
# Required when STRIPE_ENABLED=true; the app does not create Stripe products or prices.
STRIPE_PRICE_MONTHLY=price_CHANGE_ME
STRIPE_PRICE_YEARLY=price_CHANGE_ME

# Trial period in days (default 7). Set to 0 to disable trial.
STRIPE_TRIAL_DAYS=7

# ── Freemium (only active when STRIPE_ENABLED=true; self-hosted deployments ignore these)
# Daily AI chat messages for free-tier users. 0 = blocked.
FREEMIUM_CHAT_DAILY_MESSAGES=5

# Daily lesson completions for free-tier users. 0 = blocked.
FREEMIUM_LESSONS_DAILY=3

# Weekly listening exercises for free-tier users. 0 = blocked.
FREEMIUM_LISTENING_WEEKLY=3

# Weekly reading exercises for free-tier users. 0 = blocked.
FREEMIUM_READING_WEEKLY=3

# Weekly voice conversation minutes for free-tier users. 0 = blocked.
FREEMIUM_VOICE_WEEKLY_MINUTES=5

# Enable 7-day no-card trial for new users.
FREEMIUM_TRIAL_ENABLED=true

# Duration of freemium trial in days.
FREEMIUM_TRIAL_DAYS=7
```

All variables must also be added to `docker-compose.yml` under the `backend` service environment block (with empty/default values so self-hosters see them clearly).

---

## Milestone 1 — Configuration & dependency

### 1.1 `requirements.txt`

Add `stripe>=10.0.0`.

### 1.2 `app/core/config.py`

Add to `Settings`:

```python
STRIPE_ENABLED: bool = False
STRIPE_SECRET_KEY: str = ""
STRIPE_WEBHOOK_SECRET: str = ""
STRIPE_PRICE_MONTHLY: str = ""
STRIPE_PRICE_YEARLY: str = ""
STRIPE_TRIAL_DAYS: int = 7
```

### 1.3 `docker-compose.yml`

Add under `backend.environment`:

```yaml
STRIPE_ENABLED: ${STRIPE_ENABLED:-false}
STRIPE_SECRET_KEY: ${STRIPE_SECRET_KEY:-}
STRIPE_WEBHOOK_SECRET: ${STRIPE_WEBHOOK_SECRET:-}
STRIPE_PRICE_MONTHLY: ${STRIPE_PRICE_MONTHLY:-}
STRIPE_PRICE_YEARLY: ${STRIPE_PRICE_YEARLY:-}
STRIPE_TRIAL_DAYS: ${STRIPE_TRIAL_DAYS:-7}
```

### 1.4 `.env.example`

Add the full block above with comments.

---

## Milestone 2 — Database

### 2.1 `app/models/user.py`

Add subscription fields (placed after `monthly_tokens_limit`):

```python
stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
subscription_status: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
# Values: "none" plus Stripe Subscription.status values used by Checkout:
# "trialing" | "active" | "past_due" | "canceled" | "incomplete" |
# "incomplete_expired" | "unpaid" | "paused"
subscription_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

### 2.2 Alembic migration `0015_stripe_subscription.py`

```
revision = "0015_stripe_subscription"
down_revision = "0014_monthly_token_quota"
```

Adds:

- `stripe_customer_id VARCHAR(255) NULL`
- `stripe_subscription_id VARCHAR(255) NULL`
- `subscription_status VARCHAR(20) NOT NULL DEFAULT 'none'`
- `subscription_ends_at TIMESTAMP NULL`

---

## Milestone 3 — Backend services & endpoints

### 3.1 `app/services/subscription_service.py` (new file)

```python
def is_subscribed(user: User, stripe_enabled: bool) -> bool:
    """Returns True if the user has access to all features."""
    if not stripe_enabled:
        return True
    return user.subscription_status in ("trialing", "active")

async def apply_subscription_quotas(user: User, db: AsyncSession) -> None:
    """Set default quotas when a subscription becomes active."""
    user.conversation_weekly_sessions = settings.DEFAULT_CONVERSATION_WEEKLY_SESSIONS
    user.conversation_weekly_minutes = settings.DEFAULT_CONVERSATION_WEEKLY_MINUTES
    user.conversation_daily_minutes = settings.DEFAULT_CONVERSATION_DAILY_MINUTES
    user.monthly_tokens_limit = settings.DEFAULT_MONTHLY_TOKENS_LIMIT
    await db.commit()
```

### 3.2 `app/core/deps.py`

Add dependency:

```python
async def require_subscription(current_user: User = Depends(get_current_user)) -> User:
    if not is_subscribed(current_user, settings.STRIPE_ENABLED):
        raise HTTPException(status_code=402, detail="subscription_required")
    return current_user
```

### 3.3 `GET /api/config` (new public endpoint, no auth)

Returns runtime flags the frontend needs:

```json
{
  "stripe_enabled": true,
  "stripe_trial_days": 7
}
```

No sensitive keys exposed. Rate limit: 60/minute.

### 3.4 `app/routers/billing.py` (new router, only registered when `STRIPE_ENABLED=true`)

#### `POST /api/billing/checkout`

- Auth required.
- Body: `{ "plan": "monthly" | "yearly" }`
- Creates or retrieves Stripe Customer for the user.
- Creates Stripe Checkout Session with:
  - `mode: "subscription"`
  - `trial_period_days: settings.STRIPE_TRIAL_DAYS` — **only included when `STRIPE_TRIAL_DAYS > 0` AND `user.trial_used == False`**. Once a user has trialed, subsequent subscriptions start immediately at full price.
  - `success_url: {FRONTEND_URL}/billing/success`
  - `cancel_url: {FRONTEND_URL}/billing/canceled`
- Returns `{ "url": "https://checkout.stripe.com/..." }`.
- Rate limit: 10/minute.

#### `POST /api/billing/portal`

- Auth required.
- Creates Stripe Customer Portal Session for the user's `stripe_customer_id`.
- Returns `{ "url": "https://billing.stripe.com/..." }`.
- Returns 400 if user has no `stripe_customer_id`.
- Rate limit: 10/minute.

#### `POST /api/billing/webhook` (no auth — verified by Stripe signature)

- Reads raw request body and verifies with `stripe.Webhook.construct_event()`.
- Returns 400 immediately if signature invalid.
- Handles these events:

- `checkout.session.completed` — Set `stripe_customer_id` and `stripe_subscription_id`, retrieve the Stripe Subscription before granting access, sync `subscription_status = "trialing"` or `"active"`, apply quotas; set `trial_used = True` when status is `trialing`. If the Subscription cannot be retrieved, processing fails with HTTP 500 so Stripe retries the webhook instead of granting access from an unverified checkout event.
- `customer.subscription.updated` — Ignore stale events whose subscription ID differs from `stripe_subscription_id`; otherwise sync `subscription_status` and `subscription_ends_at`; accepts real Stripe subscription statuses (`trialing`, `active`, `past_due`, `canceled`, `incomplete`, `incomplete_expired`, `unpaid`, `paused`) and keeps the previous status for unknown values while logging a warning. Existing users without `stripe_subscription_id` are backfilled from this event.
- `customer.subscription.deleted` — Ignore stale events whose subscription ID differs from `stripe_subscription_id`; otherwise set `subscription_status = "canceled"`
- `invoice.payment_failed` — Extract the subscription ID from legacy `invoice.subscription` or current `invoice.parent.subscription_details.subscription`; ignore stale invoice events whose subscription ID differs from `stripe_subscription_id`; otherwise set `subscription_status = "past_due"`

- Returns HTTP 200 only after successful processing or for unsupported event types; invalid payload/signature returns HTTP 400; internal processing failures return HTTP 500 so Stripe retries the event.
- Rate limit: 200/minute (Stripe can burst).

### 3.5 Apply `require_subscription` to protected endpoints

Add `current_user: User = Depends(require_subscription)` replacing `Depends(get_current_user)` in:

- `POST /api/chat` (chat streaming)
- `WS /api/conversation/ws` (voice conversation)
- `POST /api/lessons/*` (all lesson endpoints)
- `POST /api/assessment/*` (assessment endpoints)
- `POST /api/flashcards/*` (flashcard generation)
- `POST /api/study-plan/*` (study plan generation)

### 3.6 Admin schema updates

Add to `AdminUserResponse`:

```python
stripe_customer_id: Optional[str] = None
stripe_subscription_id: Optional[str] = None
subscription_status: str = "none"
subscription_ends_at: Optional[datetime] = None
```

Add to `AdminUserUpdate`:

```python
subscription_status: Optional[
    Literal[
        "none",
        "trialing",
        "active",
        "past_due",
        "canceled",
        "incomplete",
        "incomplete_expired",
        "unpaid",
        "paused",
    ]
] = None
subscription_ends_at: Optional[datetime] = None
```

Admin can manually override subscription status — useful for `STRIPE_ENABLED=false` deployments that manage access manually.

---

## Milestone 4 — Frontend

### 4.1 App config store

Fetch `GET /api/config` once on app load (in root layout or a dedicated hook). Store `stripeEnabled: boolean` and `stripeTrialDays: number` in a lightweight Zustand slice or React context.

### 4.2 User type

Add to the auth store user type:

```typescript
subscription_status:
  | "none"
  | "incomplete"
  | "incomplete_expired"
  | "trialing"
  | "active"
  | "past_due"
  | "canceled"
  | "unpaid"
  | "paused";
subscription_ends_at: string | null;
```

Helper:

```typescript
function isSubscribed(user: User, stripeEnabled: boolean): boolean {
  if (!stripeEnabled) return true;
  return (
    user.subscription_status === "trialing" ||
    user.subscription_status === "active"
  );
}
```

### 4.3 `PaywallBanner` component (updated for freemium)

Shown in place of protected page content when `stripeEnabled && !isSubscribed` and freemium quota is exhausted.

- The `PaywallGate` wrapper component has been removed. Pages check freemium status individually and render inline.
- `compact` prop renders a smaller inline upsell banner suitable for placing inside page content (e.g., replacing the chat input or exercise generation button) rather than taking over the full page area.
- Two buttons: "Monthly — x €/month" and "Yearly — x €/year (2 months free)"
- Each button calls `POST /api/billing/checkout` with the corresponding plan, then `router.push(url)`
- Small link "Already a subscriber? Refresh your session" (calls `/api/auth/refresh` to re-sync status)

### 4.3b `FreemiumQuotaBanner` component

Shown for free-tier users on gated pages. Displays:

- Trial badge with remaining days when the freemium trial is active
- Per-feature X/Y quota counters (e.g., "3/5 chat messages today")
- "Premium only" label when the quota limit is `0` (feature blocked for free tier)
- When quota reaches 0, the page renders the compact `PaywallBanner`

### 4.4 Apply freemium checks to protected pages

In each protected page component, check freemium status via the `freemium` Zustand store:

- `/chat` — show `FreemiumQuotaBanner` with daily chat counter; when quota is 0, replace chat input with compact `PaywallBanner`
- `/conversation` — show `FreemiumQuotaBanner` with weekly voice minutes counter; when quota is 0, show compact `PaywallBanner`
- `/listening` — show `FreemiumQuotaBanner` with weekly exercise counter; when quota is 0, show compact `PaywallBanner`
- `/reading` — show `FreemiumQuotaBanner` with weekly exercise counter; when quota is 0, show compact `PaywallBanner`
- `/dashboard` — show freemium trial countdown banner when trial is active
- `/settings` — show trial status and quota summary in the Plan section

The rest of the page (sidebar, header) remains visible — only the main content area adapts. The sidebar renders a trial countdown badge when the user has an active freemium trial.

### 4.5 Billing section in Settings/Profile

Only rendered when `stripeEnabled`. Shows:

- Current plan: "Monthly" / "Yearly" / "Trial" / "No subscription"
- Status badge: active (green) / trialing (blue) / past_due (amber) / canceled (red)
- Next billing date (from `subscription_ends_at`)
- For unsubscribed users, monthly and yearly plan buttons are shown before checkout; each posts `POST /api/billing/checkout` with the selected plan.
- For `past_due`, `unpaid`, and `paused` users, access remains blocked by `is_subscribed`, but Settings and gated-page paywalls show payment-recovery copy and an "Update payment" action that opens `POST /api/billing/portal` instead of showing new subscription plan buttons.
- For `none`, `incomplete`, `incomplete_expired`, and `canceled` users, Settings and gated-page paywalls show monthly/yearly plan buttons.
- Button "Manage subscription" → `POST /api/billing/portal` → `router.push(url)`

### 4.6 Pricing section in landing page (`/`)

Only rendered when `stripeEnabled`. Positioned after the features section.

Layout:

```
┌─────────────────────────┐  ┌─────────────────────────┐
│  Monthly                │  │  Yearly  ★ Best value   │
│  x €/month (temp).      │  │  x €/year (temp).       │
│                         │  │                         │
│  7 days free            │  │  7 days free            │
│                         │  │  2 months free          │
│  ✓ 3 voice sessions     │  │  ✓ 3 voice sessions     │
│  ✓ 30 min per session   │  │  ✓ 30 min per session   │
│  ✓ AI tutor chat        │  │  ✓ AI tutor chat        │
│  ✓ Personalised plan    │  │  ✓ Personalised plan    │
│  ✓ Lessons &            │  │  ✓ Lessons &            │
│    flashcards           │  │    flashcards           │
│                         │  │                         │
│  [Start for free]       │  │  [Start for free]       │
└─────────────────────────┘  └─────────────────────────┘
              Cancel anytime · No commitment
```

Anonymous visitors selecting a paid plan are sent to `/register?plan=monthly|yearly`, preserving the selected billing interval through onboarding before Stripe Checkout. Onboarding refreshes the access token from the session cookie before creating Checkout when the page was reloaded after registration and no in-memory token is available. Authenticated unsubscribed visitors selecting a monthly/yearly plan call `POST /api/billing/checkout` directly from the landing pricing section; the frontend first refreshes the access token from the session cookie when the landing page has a session cookie but no in-memory token. The bottom pricing CTA defaults to yearly and uses the same direct Checkout path for authenticated unsubscribed visitors.

### 4.7 `/billing/success` page

- Shown after successful Stripe Checkout.
- Refreshes the access token from `/api/auth/refresh` when the user returns from Stripe without an in-memory access token.
- Polls `/api/auth/me` briefly and only shows Premium-active copy when `subscription_status` is `active` or `trialing`.
- While verification is running, shows subscription-confirmation copy. If the webhook has not synced after the short polling window, it shows a pending-confirmation message instead of claiming Premium access is already active.
- Auto-redirects to `/dashboard` only after the subscription is confirmed active/trialing.

### 4.8 `/billing/canceled` page

- Shown if user abandons Stripe Checkout.
- Message: "No se ha realizado ningún cargo."
- Link back to dashboard or pricing section.

---

## Milestone 5 — i18n

Add keys in all 10 locales (`en`, `es`, `de`, `fr`, `it`, `nl`, `pl`, `pt`, `ro`, `ru`) for the following namespaces:

**`billing` namespace (new):**

- `trialHeadline`, `trialSubtext`
- `planMonthly`, `planYearly`, `planMonthlyPrice`, `planYearlyPrice`, `planYearlySavings`
- `featuredPlan`
- `featureSessions`, `featureMinutes`, `featureChat`, `featurePlan`, `featureLessons`
- `ctaManage`
- `alreadySubscriber`
- `statusActive`, `statusTrialing`, `statusPastDue`, `statusUnpaid`, `statusPaused`, `statusIncomplete`, `statusIncompleteExpired`, `statusCanceled`, `statusNone`
- `nextBilling`, `cancelAnytime`
- `successTitle`, `successSubtext`, `canceledTitle`, `canceledSubtext`
- `sectionTitle`, `sectionSubtitle`

---

## Milestone 6 — Testing & docs

### 6.1 Backend tests

- `test_billing.py`: mock Stripe SDK, test checkout session creation, portal session, webhook signature verification, all 4 webhook events, real Stripe subscription status persistence, unknown-status fallback, `stripe_subscription_id` persistence/backfill, and stale subscription-event ignoring.
- Test that `require_subscription` returns 402 when `STRIPE_ENABLED=true` and user has `subscription_status="none"`.
- Test that `require_subscription` passes through when `STRIPE_ENABLED=false`.

### 6.2 Stripe CLI (local development)

To test webhooks locally:

```bash
stripe listen --forward-to localhost:8000/api/billing/webhook
stripe trigger checkout.session.completed
```

### 6.3 Docs

- `CHANGELOG.md` + `specs/version.md`: version bump
- `specs/api-endpoints.instructions.md`: add 3 new billing endpoints
- `specs/architecture-backend.instructions.md`: add subscription fields to User model section
- `specs/docker.instructions.md`: add Stripe env vars
- `README.md`: add Stripe configuration section
- `AGENTS.md`: update architecture section

---

## Implementation order summary

> **Status: COMPLETE (v1.8.25 — freemium added)**

- 1 — Task: Config + env vars; File(s): `config.py`, `.env.example`, `docker-compose.yml`; Status: ✅
- 2 — Task: `requirements.txt`; File(s): `requirements.txt`; Status: ✅
- 3 — Task: User model fields (incl. `freemium_trial_ends_at`, `freemium_trial_used`); File(s): `models/user.py`; Status: ✅
- 4 — Task: Alembic migration 0016 + freemium migration; File(s): `alembic/versions/`; Status: ✅
- 5 — Task: `subscription_service.py` + `freemium_service.py`; File(s): `services/subscription_service.py`, `services/freemium_service.py`; Status: ✅
- 6 — Task: `require_subscription` + `require_subscription_or_freemium` deps; File(s): `core/deps.py`; Status: ✅
- 7 — Task: `GET /api/config` (incl. `freemium_trial_enabled`); File(s): `routers/config.py`; Status: ✅
- 8 — Task: `POST /api/billing/checkout`; File(s): `routers/billing.py`; Status: ✅
- 9 — Task: `POST /api/billing/portal`; File(s): `routers/billing.py`; Status: ✅
- 10 — Task: `POST /api/billing/webhook`; File(s): `routers/billing.py`; Status: ✅
- 11 — Task: `GET /api/freemium/status`; File(s): `routers/freemium.py`; Status: ✅
- 12 — Task: Apply `require_subscription_or_freemium` to chat/listening/reading/conversation/lessons; memory management remains authenticated and ungated; File(s): `routers/chat.py`, `conversation.py`, `listening.py`, `reading.py`, `lessons.py`, `memories.py`; Status: ✅
- 13 — Task: Admin schema update; File(s): `schemas/admin.py`, `routers/admin.py`; Status: ✅
- 14 — Task: Frontend config store (+ `freemiumTrialEnabled`); File(s): `store/config.ts`; Status: ✅
- 15 — Task: User type update (+ `isFreemiumTrialActive`, freemium fields in `mapUser()`); File(s): `store/auth.ts`, `lib/mappers.ts`; Status: ✅
- 16 — Task: `FreemiumQuotaBanner` component; File(s): `components/billing/FreemiumQuotaBanner.tsx`; Status: ✅
- 17 — Task: `PaywallBanner` update (+ `compact` prop, remove `PaywallGate`); File(s): `components/billing/PaywallBanner.tsx`; Status: ✅
- 18 — Task: Freemium store; File(s): `store/freemium.ts`; Status: ✅
- 19 — Task: Freemium checks in protected pages (chat, listening, reading, conversation, dashboard, layout); File(s): 6 page/layout files; Status: ✅
- 20 — Task: Billing section in settings; File(s): `app/(app)/settings/page.tsx`; Status: ✅
- 21 — Task: Pricing section in landing; File(s): `app/page.tsx`; Status: ✅
- 22 — Task: `/billing/success` page; File(s): `app/(auth)/billing/success/page.tsx`; Status: ✅
- 23 — Task: `/billing/canceled` page; File(s): `app/(auth)/billing/canceled/page.tsx`; Status: ✅
- 24 — Task: i18n keys (10 locales); File(s): `messages/*.json`; Status: ✅
- 25 — Task: Tests; File(s): `tests/test_billing.py`; Status: ✅
- 26 — Task: Docs + version bump; File(s): Various; Status: ✅
