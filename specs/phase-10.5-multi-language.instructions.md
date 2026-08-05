---
description: "Phase 10.5 spec — Multi-language: frontend pages (onboarding, My Languages settings, dashboard, plan, chat, flashcards, progress)."
applyTo: "frontend/**"
---

# Phase 10.5 — Frontend: pages

## Goal

Update all frontend pages to reflect the active language and build the "My Languages" settings page for managing multiple languages.

**Prerequisite:** Phase 10.4 must be merged before starting this phase.

---

## 10.5.1 Onboarding (update)

**File:** `frontend/src/app/(auth)/onboarding/page.tsx`

The `TargetLanguageSelector` already shows all 5 supported languages (via `availableLanguageCodes` from the backend). No UI changes needed to the selector itself.

When onboarding is triggered for a new language (`?language=it-IT&new=true`):

- The headline changes to `newLanguageHeadline` translation key.
- The subtitle changes to `newLanguageSubtitle`.
- The pre-selected language is the one from the query param.
- The selector still uses `availableLanguageCodes` — for a new language flow, the backend returns only languages not yet added.

---

## 10.5.2 "My Languages" Settings page

**File:** `frontend/src/app/(app)/settings/languages/page.tsx`

New sub-page at `/settings/languages`. Same layout pattern as `/settings/memories` (breadcrumb back to `/settings`).

### Layout

```
← Back to Settings

MY LANGUAGES                   [+ Add new language]

┌─────────────────────────────────────────────┐
│ 🇺🇸 English (US)                   [ACTIVE]  │
│ Level: B1 · 87% completed                   │
│ Total XP: 12,500 · Streak: 23 days          │
│ Lessons: 38/48                              │
│                              [View details] │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ 🇮🇹 Italiano                         A1      │
│ Level: A1 · 12% completed                   │
│ Total XP: 850 · Streak: 3 days              │
│ Lessons: 3/40                               │
│             [Switch to this] [Delete]       │
└─────────────────────────────────────────────┘
```

### "Add new language" button

Opens a modal with the language selector showing only languages the user has **not yet added**. On selection:

1. `POST /api/languages` → creates `UserLanguage` row
2. Redirects to `/onboarding?language=it-IT&new=true`
3. Assessment creates the `StudyPlan` with the correct `target_language`

### "Switch to this" button

1. Calls `switchLanguage(code)` from the language store
2. Refreshes the store and redirects to dashboard
3. Toast: "Switched to Italian (A2)"

### "Delete" button

- Not shown if the user has only one language.
- Not shown for the currently active language (user must switch first).
- Shows a confirmation modal explaining that language-scoped progress, lessons, flashcards, and conversations are removed while global account memories are preserved.
- On confirm: `DELETE /api/languages/{code}` → `fetchLanguages()`

---

## 10.5.3 Plan page (update)

**File:** `frontend/src/app/(app)/plan/page.tsx`

- Header shows language name and CEFR level: `"Italian — B1"`.
- All API calls already filter by active `study_plan_id` (transparent — no endpoint changes needed in frontend).

---

## 10.5.4 Dashboard (update)

**File:** `frontend/src/app/(app)/dashboard/page.tsx`

- Header: `"Hello, Maria — you are learning Italian (B1)"`.
- All stats (XP, streak, progress) correspond to the active language.
- If the user just switched to a new language with 0 progress, show the normal empty state for that language.

---

## 10.5.5 Chat page (update)

**File:** `frontend/src/app/(app)/chat/page.tsx`

- Conversation list is filtered by the active plan's `study_plan_id` (backend handles it, frontend just calls the endpoint as usual).
- History shows only conversations from the active language.

---

## 10.5.6 Conversation page (update)

**File:** `frontend/src/components/conversation/ConversationMode.tsx`

- Filtered by active language (same as chat — transparent to frontend).

---

## 10.5.7 Flashcard page (update)

**File:** `frontend/src/app/(app)/flashcards/page.tsx`

- Flashcards shown are only from the active `study_plan_id` (backend filters — transparent).
- Generation automatically assigns the correct `study_plan_id` (backend handles it).

---

## 10.5.8 Progress page (update)

**File:** `frontend/src/app/(app)/progress/page.tsx`

- Competencies and stats are filtered by the active language's `study_plan_id` (transparent).
- Header shows the active language name.

---

## 10.5.9 i18n keys (add in this phase)

**Files:** all 10 locale files under `messages/`

### New namespace `languages`

```json
"languages": {
  "myLanguages": "My Languages",
  "addLanguage": "Add new language",
  "selectLanguage": "Select the language you want to learn",
  "activeLanguage": "Active",
  "switchTo": "Switch to this",
  "switching": "Switching to {language}...",
  "switched": "Switched to {language} ({level})",
  "removeLanguage": "Remove language",
  "removeConfirmTitle": "Remove {language}?",
  "removeConfirmMessage": "All progress, lessons, flashcards and conversations associated with this language will be permanently deleted. Your account memories will be preserved. This action cannot be undone.",
  "removeConfirmButton": "Remove",
  "noLanguages": "You have no languages configured.",
  "progressLabel": "Progress",
  "levelLabel": "Level",
  "xpLabel": "Total XP",
  "streakLabel": "Streak",
  "lessonsLabel": "Lessons",
  "flashcardsLabel": "Flashcards",
  "viewDetails": "View details",
  "supportedLanguages": "Available languages"
}
```

### Update `onboarding` namespace

Add to the existing `onboarding` object:

```json
"onboarding": {
  "newLanguageHeadline": "What new language do you want to learn?",
  "newLanguageSubtitle": "A new study plan will be created for this language."
}
```

The English values above are the reference. Add the equivalent translations in all 10 locale files.

---

## Tests

### Frontend tests (Vitest)

- `frontend/tests/components/LanguageSwitcher.test.tsx` — Renders when multiple languages exist; hidden when only 1 language; switch triggers API call and toast
- `frontend/tests/store/language.test.ts` — Extend 10.4 tests: language switching triggers page redirect; `isSwitching` state during transition

## New files in this phase

- `frontend/src/app/(app)/settings/languages/page.tsx` — My Languages settings page

## Modified files in this phase

- `frontend/src/app/(auth)/onboarding/page.tsx` — Show all 5 languages, handle `?new=true` flow
- `frontend/src/app/(app)/plan/page.tsx` — Show active language in header
- `frontend/src/app/(app)/dashboard/page.tsx` — Show active language in header
- `frontend/src/app/(app)/chat/page.tsx` — Language-filtered history
- `frontend/src/components/conversation/ConversationMode.tsx` — Language-filtered conversations
- `frontend/src/app/(app)/flashcards/page.tsx` — Language-filtered flashcards
- `frontend/src/app/(app)/progress/page.tsx` — Language-filtered progress, language name in header
- `messages/*.json` (all 10) — Add `languages` namespace, update `onboarding`
