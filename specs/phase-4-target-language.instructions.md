---
description: "Phase 4 specification for FreeLingo: replace english_variant with a generic target_language field (BCP-47), add post-registration language-selection onboarding screen, remove language selector from Settings, auto-login on register, and lay the extensible architecture for future target languages."
applyTo: "backend/**, frontend/**, messages/**"
---

# Phase 4 — Target Language Selection

## Objective

Replace the narrow `english_variant` field (`"american"` / `"british"`) with a generic `target_language` field that uses BCP-47 language tags (`"en-US"`, `"en-GB"`, ...). Introduce a dedicated post-registration onboarding screen where new users choose the language variant they want to learn. Remove the language selector from `/settings` (the choice is made at registration and treated as immutable in the UI, though it can still be changed via API if needed). Make the entire service layer parameterised by `target_language` so that adding a new target language in the future only requires: adding content data and one entry in `SUPPORTED_TARGET_LANGUAGES`.

**Languages available at launch:** American English (`en-US`) and British English (`en-GB`).

---

## Architecture changes at a glance

```
BEFORE                              AFTER
──────────────────────────────────  ──────────────────────────────────────────
users.english_variant               users.target_language
  "american" | "british"              "en-US" | "en-GB"  (BCP-47)

POST /api/auth/register             POST /api/auth/register
  returns { id, username, role }      returns { id, username, role,
  → redirects to /login               access_token }  +  refresh cookie
                                      → redirects to /onboarding

/register  (one-step form)          /register  (step 1: personal data)
                                    /onboarding  (step 2: language selection,
                                                  (auth) group, no sidebar)

/settings  includes english          /settings  language selector removed
  variant selector
```

---

## Milestone 1 — Backend: field rename + migration

### 1.1 Alembic migration (`0007_target_language.py`)

New migration that:

1. Adds column `target_language VARCHAR(10)` to `users` with temporary `NULL` allowed.
2. Back-fills existing rows:
   - `english_variant = 'american'` → `target_language = 'en-US'`
   - `english_variant = 'british'` → `target_language = 'en-GB'`
   - Any other value (should not exist) → `target_language = 'en-US'`
3. Sets `NOT NULL DEFAULT 'en-GB'` on the column.
4. Drops the old `english_variant` column.

### 1.2 SQLAlchemy model (`app/models/user.py`)

Replace:

```python
english_variant: Mapped[str] = mapped_column(String(10), nullable=False, default="american")
```

With:

```python
target_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en-GB")
```

All other fields remain unchanged.

### 1.3 Pydantic schemas (`app/schemas/auth.py`)

**`SUPPORTED_TARGET_LANGUAGES`** constant (module-level, not in settings — languages are a code concern, not ops config):

```python
SUPPORTED_TARGET_LANGUAGES: set[str] = {"en-US", "en-GB"}
```

**`RegisterRequest`**: replace `english_variant` field:

```python
# Before
english_variant: Literal["american", "british"] = "american"

# After
target_language: str = "en-US"

@field_validator("target_language")
@classmethod
def validate_target_language(cls, v: str) -> str:
    if v not in SUPPORTED_TARGET_LANGUAGES:
        raise ValueError(f"Unsupported target language. Choose from: {SUPPORTED_TARGET_LANGUAGES}")
    return v
```

**`UserUpdateRequest`**: apply the same replacement. The `target_language` field remains updatable via `PATCH /api/auth/me` in case users change their mind after registration, but the UI no longer surfaces this control.

**`UserResponse`**: replace `english_variant: str` with `target_language: str`.

### 1.4 Auth router (`app/routers/auth.py`)

**Auto-login on register**: after creating the user, issue a JWT access_token and set a refresh_token cookie — exactly the same logic as `POST /login`. Return:

```json
{
  "id": 1,
  "username": "alice",
  "role": "user",
  "access_token": "<jwt>"
}
```

The refresh_token httpOnly cookie is also set in the same response (identical to the login endpoint). This allows the frontend to redirect directly to `/onboarding` without requiring an intermediate manual login step.

> **Why**: the onboarding page needs an authenticated session to call `PATCH /api/auth/me`. Auto-login on register is the cleanest solution and avoids workarounds (sessionStorage passing, one-time onboarding tokens, etc.).

Update `PATCH /api/auth/me` description in the architecture doc: replaces `english_variant` with `target_language`.

### 1.5 Config (`app/core/config.py`)

No new env variables are added for language control — `SUPPORTED_TARGET_LANGUAGES` is a code constant in `schemas/auth.py`. This is intentional: activating a new target language is a development task (it requires new content data), not an ops configuration change.

---

## Milestone 2 — Backend: service layer parameterisation

All services that previously consumed `english_variant` are updated to consume `target_language`. Two private helper functions are introduced in a new shared module or at the top of each service:

### Helper: `_get_english_variant(target_language: str) -> str`

Converts BCP-47 tag to the legacy "american"/"british" string still used in prose prompts:

```python
_ENGLISH_VARIANTS = {"en-US": "american", "en-GB": "british"}

def _get_english_variant(target_language: str) -> str:
    """Return 'american' or 'british' for English variants; empty string otherwise."""
    return _ENGLISH_VARIANTS.get(target_language, "")
```

### Helper: `_get_iso639(target_language: str) -> str`

Strips the region subtag for services (Whisper) that only accept ISO 639-1:

```python
def _get_iso639(target_language: str) -> str:
    """'en-US' → 'en', 'it-IT' → 'it'"""
    return target_language.split("-")[0].lower()
```

### 2.1 `app/services/lesson_generator.py`

Replace all occurrences of `english_variant` variable / prompt placeholder with `target_language`. When constructing the prompt, derive the display string with `_get_english_variant(target_language)` for existing English-specific wording. The `LESSON_GENERATION_PROMPT` keeps its `{english_variant}` placeholder internally; the caller passes `_get_english_variant(current_user.target_language)`.

For forward-compatibility: if `_get_english_variant` returns an empty string (non-English target language), the prompt omits the variant instruction line and the LLM generates content in the target language.

### 2.2 `app/services/flashcard_sm2.py`

Same pattern: pass `_get_english_variant(current_user.target_language)` to the existing `{english_variant}` slot in `FLASHCARD_GEN_PROMPT`. The `native_language` source is unchanged (still from `current_user.native_language` via the router, not from the request body).

> **Bug fixes included**: `native_language` in flashcard generation is always sourced from `current_user.native_language`, while `target_language` is always sourced from the active persisted study plan. Both fields are removed from `FlashcardGenerateRequest`; the backend ignores client-supplied values for these authoritative contexts.

### 2.3 `app/routers/chat.py`

Replace `current_user.english_variant` with `current_user.target_language`. Pass `_get_english_variant(current_user.target_language)` to the `{english_variant}` slot in `TUTOR_SYSTEM_PROMPT`.

### 2.4 `app/services/conversation_pipeline.py`

**Bug fix included**: `english_variant` and `native_language` were missing from the voice conversation system prompt. Add both:

- `_get_english_variant(user.target_language)` → `{english_variant}` in `CONVERSATION_SYSTEM_PROMPT`
- `user.native_language` → `{native_language}` in `CONVERSATION_SYSTEM_PROMPT`

Mirror the same "brief corrections in native language allowed" guideline that the text chat tutor uses.

The pipeline initialisation (`on WebSocket connect`) already reads `conversation_max_duration` and `conversation_inactivity_timeout` from the User model; add `target_language` and `native_language` to the same read.

### 2.5 `app/services/stt_service.py`

Make the `language` parameter in the Whisper URL dynamic:

```python
# Before
params={"output": "json", "language": "en", "task": "transcribe"}

# After
params={"output": "json", "language": _get_iso639(target_language), "task": "transcribe"}
```

The current `transcribe` contract requires a keyword-only ISO `language` with no default. Conversation derives it from the session's selected `target_language`. Generic pronunciation and flashcard STT uploads carry their resource-owned `study_plan_id`; `stt.py` verifies plan ownership and derives the language from `StudyPlan.target_language`, avoiding both the obsolete global user field and stale frontend active-language state.

### 2.6 `app/routers/assessment.py`

When creating the `StudyPlan` in `POST /api/assessment/complete`, record `target_language` from the authenticated user:

```python
plan.target_language = current_user.target_language
```

### 2.7 `app/models/study_plan.py`

Add column `target_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en-GB")` to `StudyPlan`. Existing plans are back-filled with their stored target language where available.

This field is informational in Phase 4 (the curriculum is still English-only) but is the correct place to store it for future multi-language plan generation.

---

## Milestone 3 — Backend: auth flow update

### 3.1 `POST /api/auth/register` — auto-login

After persisting the user:

1. Call the same token-creation logic as `POST /login`:
   - Create JWT access_token (15 min)
   - Generate opaque refresh_token UUID4, store in Redis (`refresh:{token}` → user_id, TTL 30 days)
   - Set `refresh_token` httpOnly cookie in the response
2. Return response body `{ id, username, role, access_token }` (add `access_token` to the existing response schema `RegisterResponse`).

The existing `/login` endpoint is unchanged — users who arrive at `/login` directly (e.g. returning users, direct URL) still work as before.

---

## Milestone 4 — Frontend: onboarding screen

### 4.1 New page: `src/app/(auth)/onboarding/page.tsx`

Placed in the `(auth)` route group (no sidebar, no authenticated app shell). Displayed immediately after a successful registration.

**Behaviour**:

- Reads the `access_token` from the Zustand auth store. If the store has no token (user navigated here directly without registering first), redirect to `/register`.
- Shows the `TargetLanguageSelector` component (see 4.3).
- On language confirmed: calls `PATCH /api/auth/me` with `{ target_language: selectedLanguage }`.
- On success: redirect to `/dashboard`.

**UI guidelines**:

- Full-screen centred card, no sidebar.
- Headline from `t('onboarding.headline')`.
- Subheadline from `t('onboarding.subtitle')`.
- The `TargetLanguageSelector` fills the card body.
- Single "Start learning" / `t('onboarding.cta')` button below the selector.

### 4.2 Updated page: `src/app/(auth)/register/page.tsx`

Single change: after a successful `POST /api/auth/register`, the response now includes `access_token`. Store it with `useAuthStore.setTokens(data.access_token)` and redirect to `/onboarding` instead of `/login?registered=true`.

No other changes to the register form — `target_language` is NOT collected during registration; it is collected on the onboarding screen immediately after.

> **Why not collect it in the register form?** The registration form already has 5 fields (username, email, password, confirm password, native language). Adding a sixth field creates visual clutter. A dedicated screen gives the language choice the prominence it deserves — it is the central decision that shapes the entire learning experience.

### 4.3 New component: `src/components/onboarding/TargetLanguageSelector.tsx`

Reusable selector used in the onboarding screen. Receives:

```typescript
interface TargetLanguageSelectorProps {
  value: string; // BCP-47 code e.g. "en-US"
  onChange: (lang: string) => void;
}
```

Renders one card per supported language. Each card shows:

- Flag image (`/flags/usa.jpg` for `en-US`, `/flags/uk.jpg` for `en-GB`)
- Language display name from i18n: `t('targetLanguages.en-US')`, `t('targetLanguages.en-GB')`
- Short description: `t('targetLanguages.en-US-description')`, `t('targetLanguages.en-GB-description')`
- Selected state (accent border + background, same visual style as the existing variant buttons in Settings)

The list of available languages is sourced from a `SUPPORTED_TARGET_LANGUAGES` constant on the frontend — a TypeScript array defined in `src/lib/target-languages.ts`. This mirrors the backend constant and is the single place to add a new language on the frontend side.

### 4.4 `src/lib/target-languages.ts` (new file)

```typescript
export interface TargetLanguage {
  code: string; // BCP-47 e.g. "en-US"
  flagPath: string; // Path under /public/flags/
}

export const SUPPORTED_TARGET_LANGUAGES: TargetLanguage[] = [
  { code: "en-US", flagPath: "/flags/usa.jpg" },
  { code: "en-GB", flagPath: "/flags/uk.jpg" },
];
```

Adding a future language means appending one entry here and providing the flag image under `public/flags/`.

### 4.5 Updated store: `src/store/auth.ts`

Replace `english_variant?: string` with `target_language?: string` in the `User` interface.

Update all consumer sites:

- `src/app/layout.tsx` — mapping from `me.english_variant` → `me.target_language`
- Any conditional rendering that previously checked `english_variant`

### 4.6 Updated page: `src/app/(app)/settings/page.tsx`

Remove the English variant selector section entirely (the `<div>` containing the flag buttons for `american`/`british`, the `englishVariant` state, and the corresponding entry in the `handleSave` PATCH body).

The `PATCH /api/auth/me` call in `handleSave` no longer sends `english_variant` (it does not need to send `target_language` either — that field is set during onboarding and is not exposed in Settings).

---

## Milestone 5 — i18n messages

### 5.1 New namespace: `onboarding`

Add to all message files (`messages/en.json`, `es.json`, `fr.json`, `pt.json`, `de.json`, `it.json`):

```json
"onboarding": {
  "headline": "What are you going to learn?",
  "subtitle": "Choose the variant of English you want to study. You can always contact support if you wish to change it later.",
  "cta": "Start learning"
}
```

Translate appropriately in each locale file.

### 5.2 New namespace: `targetLanguages`

```json
"targetLanguages": {
  "en-US": "American English",
  "en-US-description": "Standard US English, widely used in international business and media.",
  "en-GB": "British English",
  "en-GB-description": "UK English, the reference for many international examinations (IELTS, Cambridge)."
}
```

Translate appropriately in each locale file.

### 5.3 Remove from `settings` namespace

Remove the following keys from all message files (they become unused after the Settings selector is removed):

- `settings.englishVariant`
- `settings.american`
- `settings.british`

### 5.4 Remove from `auth.register` namespace

Remove the following orphaned keys (they were defined but never rendered in the register form):

- `auth.register.englishVariant`
- `auth.register.american`
- `auth.register.british`

---

## Milestone 6 — Tests

### 6.1 `backend/tests/test_auth.py`

- Update all fixture user creation calls: replace `english_variant="american"` with `target_language="en-US"` and `english_variant="british"` with `target_language="en-GB"`.
- Update the register endpoint test: assert the response body now contains `access_token`.
- Add test: register with `target_language="en-GB"` → user's `target_language` column is `"en-GB"`.
- Add test: register with unsupported `target_language="xx-XX"` → 422.
- Add test: register → response includes `access_token` and the refresh_token cookie is set.

### 6.2 `backend/tests/test_flashcards.py`

Update `generate` endpoint test: remove `native_language` from request body (field is removed from `FlashcardGenerateRequest`); assert the generated card's translation uses the user's `native_language` from profile.

### 6.3 `backend/tests/test_conversation.py`

Add test: verify that `CONVERSATION_SYSTEM_PROMPT` is built with `native_language` and the derived `english_variant` for `"en-US"` and `"en-GB"` users.

---

## Extensibility contract

When adding a new target language in the future (e.g. Italian `it-IT`), the following checklist must be completed. **No other files require modification**.

### Backend

- `backend/app/schemas/auth.py` — Add `"it-IT"` to `SUPPORTED_TARGET_LANGUAGES`
- `backend/app/data/curriculum.py` — Add `CurriculumUnit` entries for the new language under a new key
- `backend/app/services/lesson_generator.py` — The prompt already uses `_get_english_variant` which returns `""` for non-English; add language-specific prompt logic if needed
- `backend/app/services/stt_service.py` — No change needed — `_get_iso639` already handles any BCP-47 tag

### Frontend

- `src/lib/target-languages.ts` — Add `{ code: 'it-IT', flagPath: '/flags/it.jpg' }` to `SUPPORTED_TARGET_LANGUAGES`
- `src/data/curriculum.ts` — Add Italian curriculum data
- `src/data/grammar.ts` — Add Italian grammar reference data
- `backend/app/data/it/vocabulary.py` — Add Italian vocabulary sets (migrated from frontend in v1.7.4)
- `src/data/phrasebook.ts` — Add Italian phrasebook entries
- `backend/app/data/it/assessment_bank.py` — Add Italian assessment questions
- `public/flags/it.jpg` — Add Italian flag image

### Messages

- All `messages/*.json` — Add `"it-IT"` and `"it-IT-description"` keys in `targetLanguages` namespace

> **TTS note**: Kokoro FastAPI ships with English voices only. Adding a non-English target language requires verifying that the selected TTS service supports the target language's voice synthesis, and updating `TTS_VOICE` configuration or adding per-language voice mapping in `tts_service.py`.

---

## Auth flow comparison

### Before Phase 4

```
/register → POST /api/auth/register
    ↓ { id, username, role }
/login?registered=true
    ↓ user fills in credentials again
POST /api/auth/login → access_token + cookie
    ↓
/dashboard
```

### After Phase 4

```
/register → POST /api/auth/register
    ↓ { id, username, role, access_token } + refresh cookie
store access_token → redirect /onboarding
    ↓ user selects target language (en-US or en-GB)
PATCH /api/auth/me → { target_language }
    ↓
/dashboard
```

Returning users (second login) and admin-created users are unaffected — their path is still `/login → /dashboard`.

---

## Data model changes summary

### `users` table

- `english_variant` — Before: `"american"` \; After: `"british"`
- `target_language` — Before: —; After: `"en-GB"` \

### `study_plans` table

- `target_language` — Before: —; After: `"en-GB"` \

### Migration chain

```
0001_initial
0002_conversations
0003_curriculum_studyplan
0004_lesson_unit_id
0005_english_variant
0006_conversation_timeouts
0007_target_language   ← new (renames english_variant, adds study_plans.target_language)
```

---

## API changes summary

### `POST /api/auth/register`

- Request body — Before: `english_variant: "american" \; After: "british"`
- Response body — Before: `{ id, username, role }`; After: `{ id, username, role, access_token }`
- Cookie — Before: Not set; After: Sets `refresh_token` httpOnly cookie

### `PATCH /api/auth/me`

- Updatable fields — Before: `english_variant`; After: `target_language`

### `GET /api/auth/me`

- Response fields — Before: `english_variant: str`; After: `target_language: str`

### `POST /api/flashcards/generate`

- Request body — Before: `native_language` and optional `target_language` could be client-supplied; After: both fields removed — native language comes from the user profile and target language from the active study plan

---

## Frontend routing changes

- `/(auth)/register` — Before: Redirects to `/login?registered=true` on success; After: Redirects to `/onboarding` on success
- `/(auth)/onboarding` — Before: Does not exist; After: New — language selection screen (requires valid access_token in store)
- `/(app)/settings` — Before: Includes English variant selector; After: English variant selector removed

---

## Phase 4 completion criteria

- [x] Migration `0007_target_language` runs without error on a database with pre-existing rows — `english_variant` values are correctly back-filled to BCP-47 codes
- [x] `POST /api/auth/register` returns `access_token` in the response body and sets the refresh_token httpOnly cookie
- [x] Registering with `target_language="en-GB"` stores `"en-GB"` in the database (not the old `"british"`)
- [x] Registering with an unsupported `target_language` value returns HTTP 422
- [x] After registration, the frontend is automatically authenticated (access_token stored) and redirected to `/onboarding`
- [x] `/onboarding` shows the `TargetLanguageSelector` with both `en-US` and `en-GB` options
- [x] Selecting a language and clicking "Start learning" calls `PATCH /api/auth/me` and redirects to `/dashboard`
- [x] Navigating to `/onboarding` directly without a valid access_token redirects to `/register`
- [x] `/settings` no longer shows the English variant selector
- [x] LLM-generated lessons and flashcards use the correct English variant derived from `target_language`
- [x] Voice conversation pipeline builds the system prompt with the correct `native_language` and `english_variant` (previously missing)
- [x] STT transcription requires the ISO language code derived from the selected or resource-owning study plan's `target_language` (`en` for both English variants, `it` for Italian, and equivalent mappings for every supported language)
- [x] `FlashcardGenerateRequest` accepts neither native nor target language fields — translation language comes from the user profile and learning language from the active persisted plan
- [x] All backend tests pass with `target_language` replacing `english_variant`
- [x] No regressions in Phases 1, 2, and 3
