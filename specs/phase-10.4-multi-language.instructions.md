---
description: "Phase 10.4 spec — Multi-language: frontend core infrastructure (stores, types, language switcher)."
applyTo: "frontend/**"
---

# Phase 10.4 — Frontend: core infrastructure

## Goal

Build the frontend foundation for multi-language: supported language config, Zustand store, sidebar language switcher, and updated API mappers. No new pages yet — those come in Phase 10.5.

**Prerequisite:** Phase 10.3 must be merged and deployed before starting this phase.

---

## 10.4.1 Supported languages configuration

**File:** `frontend/src/lib/target-languages.ts`

```typescript
export interface TargetLanguage {
  code: string; // BCP-47, e.g. "it-IT"
  name: string; // In its own language: "Italiano", "Español"
  nameEn: string; // In English: "Italian", "Spanish"
  flagPath: string; // Path under /public/flags/: "/flags/italy.jpg"
  iso639: string; // ISO 639-1: "it", "es"
}

export const SUPPORTED_TARGET_LANGUAGES: TargetLanguage[] = [
  {
    code: "en-US",
    name: "English (US)",
    nameEn: "English (US)",
    flagPath: "/flags/usa.jpg",
    iso639: "en",
  },
  {
    code: "en-GB",
    name: "English (UK)",
    nameEn: "English (UK)",
    flagPath: "/flags/uk.jpg",
    iso639: "en",
  },
  {
    code: "es-ES",
    name: "Español",
    nameEn: "Spanish",
    flagPath: "/flags/spain.jpg",
    iso639: "es",
  },
  {
    code: "it-IT",
    name: "Italiano",
    nameEn: "Italian",
    flagPath: "/flags/italy.jpg",
    iso639: "it",
  },
  {
    code: "pt-PT",
    name: "Português",
    nameEn: "Portuguese",
    flagPath: "/flags/portugal.jpg",
    iso639: "pt",
  },
];

export function getLanguageByCode(code: string): TargetLanguage | undefined {
  return SUPPORTED_TARGET_LANGUAGES.find((l) => l.code === code);
}

export const DEFAULT_TARGET_LANGUAGE = "en-GB";
```

---

## 10.4.2 Language store

**File:** `frontend/src/store/language.ts` (new)

A dedicated Zustand store for language state, separate from the auth store to keep concerns isolated:

```typescript
import { create } from "zustand";
import { TargetLanguage, getLanguageByCode } from "@/lib/target-languages";
import { apiFetch } from "@/lib/api";

export interface UserLanguageInfo {
  target_language: string;
  is_active: boolean;
  plan: {
    id: number;
    cefr_level: string | null;
    progress_day: number;
    total_days: number;
    completion_pct: number;
  } | null;
  progress: {
    total_xp: number;
    current_streak: number;
    lessons_completed: number;
  } | null;
}

interface LanguageStore {
  activeLanguage: TargetLanguage | null;
  userLanguages: UserLanguageInfo[];
  supportedLanguages: TargetLanguage[]; // always the full static SUPPORTED_TARGET_LANGUAGES list
  availableLanguageCodes: string[]; // operator-filtered subset, from all_supported_languages in API response
  isSwitching: boolean;
  fetchLanguages: () => Promise<void>;
  switchLanguage: (code: string) => Promise<void>;
  addLanguage: (code: string) => Promise<void>;
  removeLanguage: (code: string) => Promise<void>;
}
```

**`fetchLanguages`:** calls `GET /api/languages` and populates `userLanguages`, `activeLanguage`, and `availableLanguageCodes` (from `all_supported_languages` in the response). Phase 10.5 uses `availableLanguageCodes` to filter the "Add new language" modal so only operator-enabled languages are shown.

**`switchLanguage`:** calls `PUT /api/languages/active`, sets `isSwitching=true` during the request. Always resets `isSwitching=false` in a `finally` block — including on error — so the spinner never freezes. On success, calls `fetchLanguages()`. The calling component (LanguageSwitcher) is responsible for calling `router.refresh()` after the store call resolves, so server components re-render with the new active language. After the switch, study plan, progress, flashcards, lessons, competencies, and conversations reflect the new active language; the same global memory collection remains available.

**`addLanguage`:** calls `POST /api/languages`, then `fetchLanguages()`.

**`removeLanguage`:** calls `DELETE /api/languages/{code}`, then `fetchLanguages()`. The **component** calling `removeLanguage` is responsible for showing a `ConfirmDialog` before invoking it (same pattern as the logout confirmation in `layout.tsx`), warning that language-specific study data and conversations will be deleted while account memories are preserved. The study-plan FK uses `SET NULL` for memory provenance. The store method itself does not show any UI.

`supportedLanguages` is always the static `SUPPORTED_TARGET_LANGUAGES` list — no API call needed. `availableLanguageCodes` is the operator-configured subset and is populated from the API.

---

## 10.4.3 Language Switcher in sidebar

**Component:** `frontend/src/components/LanguageSwitcher.tsx`

```tsx
// Behaviour:
// - Shows the flag image (via <Image> from flagPath) + name of the active language
// - If only 1 language: no dropdown, just an indicator (no chevron)
// - If 2+ languages: dropdown listing all user languages
// - On switch: calls switchLanguage() from the language store, awaits it, then calls router.refresh()
// - Confirmation toast during switch (state-based positioned <div>, same pattern as chat/page.tsx)
// - Loading spinner while isSwitching=true
```

Visual design:

- Compact button: flag image + name + chevron icon.
- Style: `text-fl-muted hover:text-fl-fg` with subtle hover background.
- Dropdown: each item shows flag image + name + CEFR level badge (e.g. `B1`). If `plan` is null or `cefr_level` is null (language added but assessment not yet done), omit the badge entirely. Active language has a checkmark.

The flag image uses `<Image>` from `next/image` with `lang.flagPath`, matching the existing `TargetLanguageSelector` pattern.

**File:** `frontend/src/app/(app)/layout.tsx`

Add `<LanguageSwitcher />` at the top of the sidebar (desktop), below the app logo/name and before the navigation items. Also add it to the mobile dropdown menu, at the top before the main navigation items. The component calls `fetchLanguages()` on mount if `userLanguages` is empty.

---

## 10.4.4 Updated mappers

**File:** `frontend/src/lib/mappers.ts`

Add `mapUserLanguageInfo` — a mapper from the API response shape to the frontend `UserLanguageInfo` type, including the plan summary and progress data:

```typescript
import type { UserLanguageInfo } from "@/store/language";

export function mapUserLanguageInfo(
  data: Record<string, any>,
): UserLanguageInfo {
  return {
    target_language: data.target_language,
    is_active: data.is_active,
    plan: data.plan
      ? {
          id: data.plan.id,
          cefr_level: data.plan.cefr_level ?? null,
          progress_day: data.plan.progress_day,
          total_days: data.plan.total_days,
          completion_pct: data.plan.completion_pct,
        }
      : null,
    progress: data.progress
      ? {
          total_xp: data.progress.total_xp,
          current_streak: data.progress.current_streak,
          lessons_completed: data.progress.lessons_completed,
        }
      : null,
  };
}
```

`import type` is required to avoid a circular dependency (`store/language.ts` must not import from `lib/mappers.ts`). This mapper is intended for use by **components and pages** (Phase 10.5+), not by the store itself.

**Inside `fetchLanguages`:** the store maps the response inline rather than calling `mapUserLanguageInfo`, preserving the established pattern where stores never import from `lib/mappers.ts` (consistent with `auth.ts`). `mapUserLanguageInfo` is available for components that need to work with language data outside the store.

---

## 10.4.5 i18n keys (add in this phase)

**Files:** all 10 locale files under `messages/`

### `nav` namespace — new key

```json
"nav": {
  "switchLanguage": "Switch language"
}
```

### `common` namespace — remove-language confirmation dialog

```json
"common": {
  "removeLanguageConfirmTitle": "Remove language",
  "removeLanguageConfirmMessage": "All language-specific data (study plan, progress, flashcards, and conversations) will be permanently deleted. Your account memories will be preserved. This action cannot be undone.",
  "removeLanguageConfirmLabel": "Remove"
}
```

### `targetLanguages` namespace — expand with new languages

The existing namespace already has `en-US` and `en-GB` in all 10 locales. Add the 3 new languages:

```json
"targetLanguages": {
  "en-US": "American English",
  "en-GB": "British English",
  "es-ES": "Spanish",
  "it-IT": "Italian",
  "pt-PT": "Portuguese"
}
```

The English values above are the reference. Add the equivalent translation in each of the other 9 locale files.

> **Design rationale:** target language names are shown translated into the user's UI language (a Russian user reads "Американский английский", a Spanish user reads "Inglés americano"). This is used by `TargetLanguageSelector` via `t(lang.code)` where `lang.code` is the BCP-47 code (`"en-US"`, `"es-ES"`, etc.) — no separate `labelKey` field is needed.
>
> `LanguageSwitcher` (the compact sidebar button) uses `lang.name` (the language's own name: "Español", "Italiano") since in that context the user has already chosen the language and self-identification is clearer.

---

## Tests

### Frontend tests (Vitest)

- **`frontend/tests/lib/target-languages.test.ts`** — `getLanguageByCode` returns correct language for all 5 codes; `SUPPORTED_TARGET_LANGUAGES` has expected structure; `DEFAULT_TARGET_LANGUAGE` is valid
- **`frontend/tests/store/language.test.ts`** — `fetchLanguages` populates store; `switchLanguage` calls API and updates active language; `addLanguage`/`removeLanguage` call correct endpoints

## New files in this phase

- `frontend/src/lib/target-languages.ts` — Language config and helpers
- `frontend/src/store/language.ts` — Zustand language store
- `frontend/src/components/LanguageSwitcher.tsx` — Sidebar switcher component

## Modified files in this phase

- **`frontend/src/app/(app)/layout.tsx`** — Add `LanguageSwitcher` to sidebar (desktop) and mobile menu
- **`frontend/src/lib/mappers.ts`** — Add `UserLanguageInfo` mapper
- **`frontend/src/components/TargetLanguageSelector.tsx`** — Update to new `TargetLanguage` interface: change import from `TARGET_LANGUAGES` → `SUPPORTED_TARGET_LANGUAGES`; replace `lang.flag` → `lang.flagPath`; replace `t(lang.labelKey)` → `t(lang.code)` (same `targetLanguages` namespace, `code` is the key); make `availableCodes: string[]` a **required** prop — filter `SUPPORTED_TARGET_LANGUAGES` to only those codes before rendering. TypeScript enforces that any caller must pass the operator-configured list explicitly
- **`frontend/src/app/(auth)/onboarding/page.tsx`** — Call `fetchLanguages()` from the language store on mount; pass `availableLanguageCodes` from the store to `<TargetLanguageSelector availableCodes={availableLanguageCodes} />` so only operator-enabled languages are shown
- **`messages/*.json` (all 10)** — Add `nav.switchLanguage`, `common.removeLanguageConfirm*` keys; expand `targetLanguages` with `es-ES`, `it-IT`, `pt-PT`
