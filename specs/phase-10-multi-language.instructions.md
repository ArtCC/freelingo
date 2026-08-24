---
description: "Phase 10 spec — Multi-language support (index). See individual phase-10.X files for implementation details."
applyTo: "backend/**, frontend/**, messages/**, specs/**"
---

# Phase 10 — Multi-Language Support (Index)

This is the index file for Phase 10. Each sub-phase has its own dedicated spec file with full implementation details.

---

## Overview

FreeLingo moves from "one user = one language = one study plan" to an architecture where **each user can have multiple active study plans, one per language**. Progress, flashcards, conversations, and competencies are isolated by language; memories are intentionally global per user.

### User flow

1. **Registration**: the user chooses their target language (`target_language`) during onboarding (same as now).
2. **Normal use**: the entire interface (dashboard, plan, lessons, flashcards, chat, exercises, etc.) corresponds to the active plan.
3. **Switch language**: a quick selector in the sidebar (flag + language name) allows switching between the languages the user is learning with a single click. When switching, the entire experience pivots to that language's plan. If the user only has one language, the selector is not shown.
4. **Add new language**: from Settings → "My Languages", the user sees a dedicated page with per-language cards (summarised progress) and an "Add new language" button that starts the language selection flow to create a new study plan.
5. **Settings management**: the "My Languages" page shows all the user's languages with their CEFR level, streak, % completed, and allows switching the active language. The current active language and the last language cannot be deleted.
6. **Change confirmation**: toast "Switching to Italian (A2)..." so the user always knows what changed.
7. **Scoped and global data**: each language has its own progress, flashcards, conversations, and competencies. Memories are shared across languages; `study_plan_id` is nullable provenance only.
8. **Language-specific curriculum**: curriculum for each language is different and adapted to that language.
9. **Adapted prompts**: system prompts use the target language name and never hardcode "English".
10. **Supported languages**: Spanish, Italian, Portuguese, French, German, Japanese, Korean, and Mainland Chinese have backend learning data in addition to the existing English variants.
11. **Flashcard and spoken-practice isolation**: flashcard generation derives its target language from the active persisted plan. Pronunciation lessons and flashcard speaking mode capture and submit the resource's `study_plan_id`; the backend verifies ownership and derives the STT ISO language from that persisted plan instead of client active-language state.

### Current backend learning-data languages

- `en-GB` — English (British)
- `en-US` — English (American)
- `de-DE` — German
- `es-ES` — Spanish (Spain)
- `fr-FR` — French
- `it-IT` — Italian
- `ja-JP` — Japanese
- `ko-KR` — Korean (South Korea)
- `pt-PT` — Portuguese (Portugal)
- `zh-CN` — Chinese (Mainland China)

### Japanese backend data

Japanese (`ja-JP`) is enabled in backend schemas, `AVAILABLE_TARGET_LANGUAGES` defaults, language dispatchers, and static learning data. The `backend/app/data/ja/` package contains A1-C2 curriculum, grammar, vocabulary, phrasebook, and assessment content:

- Curriculum — 48 units across A1-C2, with Japanese unit titles, competency checklists, and listening lesson slots from A2-C2
- Grammar — 130 topics matching all curriculum `grammar_points` slugs
- Vocabulary — 152 sets matching all curriculum `vocabulary_set_ids`, with 1,112 words across A1-C2
- Phrasebook — 44 A1-C2 categories with 318 Japanese phrases, contexts, registers, and unit references, split by CEFR level modules
- Assessment bank — 120 static questions across grammar, vocabulary, and reading

### Korean backend data

Korean (`ko-KR`) is enabled in backend schemas, `AVAILABLE_TARGET_LANGUAGES` defaults, language dispatchers, and static learning data. The `backend/app/data/ko/` package contains A1-C2 curriculum, grammar, vocabulary, phrasebook, and assessment content:

- Curriculum — 48 units across A1-C2, with Korean unit titles, competency checklists, and listening lesson slots from A2-C2
- Grammar — 126 topics matching all curriculum `grammar_points` slugs
- Vocabulary — 155 sets matching all curriculum `vocabulary_set_ids`, with 1,226 words across A1-C2
- Phrasebook — 34 A1-C2 categories with 318 Korean phrases, contexts, registers, and unit references
- Assessment bank — 120 static questions across grammar, vocabulary, and reading

### Mainland Chinese backend data

Mainland Chinese (`zh-CN`) is enabled in backend schemas, `AVAILABLE_TARGET_LANGUAGES` defaults, language dispatchers, and static learning data. The `backend/app/data/zh/` package contains A1-C2 curriculum, grammar, vocabulary, phrasebook, and assessment content in Simplified Chinese with pinyin-aware metadata:

- Curriculum — 48 units across A1-C2, with Simplified Chinese unit titles, competency checklists, and listening lesson slots from A2-C2
- Grammar — 126 topics matching all curriculum `grammar_points` slugs
- Vocabulary — 155 sets matching all curriculum `vocabulary_set_ids`, with 1,226 words across A1-C2
- Phrasebook — 24 A1-C2 categories with 318 Chinese phrases, contexts, registers, and unit references
- Assessment bank — 120 static questions across grammar, vocabulary, and reading

### CJK frontend catalog readiness

The frontend catalog includes Japanese, Korean, and Mainland Chinese metadata. All three CJK languages now have backend learning data, and selectable surfaces use `TARGET_LANGUAGE_CATALOG` filtered by backend-provided `availableCodes` / `availableLanguageCodes`.

Prepared capabilities and catalog entries live in `frontend/src/lib/target-languages.ts`:

- `ja-JP` — `name=日本語`, `nameEn=Japanese`, `flagPath=/flags/japan.jpg`, `script=hiragana-katakana-kanji`, `romanization=romaji`
- `ko-KR` — `name=한국어`, `nameEn=Korean`, `flagPath=/flags/south_korea.jpg`, `script=hangul`, `romanization=revised-romanization`
- `zh-CN` — `name=中文（中国）`, `nameEn=Chinese (Mainland China)`, `flagPath=/flags/china.jpg`, `script=simplified-hanzi`, `romanization=pinyin`

Learned-language content should render through `TargetLanguageText` rather than direct `font-mono` text. Current Latin-script languages keep the existing mono visual style via `font-target-latin`; CJK content receives larger, looser, non-uppercase typography with Noto/system CJK font fallbacks.

All 10 `messages/*.json` locale files include `targetLanguages` names, ISO aliases, descriptions, and landing greetings for `ja-JP`, `ko-KR`, and `zh-CN`.

### CJK backend readiness

The backend service layer includes prompt, metadata, registration-schema, environment default, dispatcher, and static-content support for Japanese, Korean, and Mainland Chinese.

`.env.example`, `.env.dev`, and backend defaults include `ja-JP`, `ko-KR`, and `zh-CN` in `AVAILABLE_TARGET_LANGUAGES`. Backend `get_available_languages()` filters that list through `SUPPORTED_TARGET_LANGUAGES`; all three CJK codes are now accepted.

Prepared capabilities live in `backend/app/services/language_helpers.py`:

- `ja-JP` — `name=Japanese`, `iso639=ja`, `script=hiragana-katakana-kanji`, `romanization=romaji`, length unit `characters`
- `ko-KR` — `name=Korean (South Korea)`, `iso639=ko`, `script=hangul`, `romanization=revised-romanization`, length unit `words`
- `zh-CN` — `name=Chinese (Mainland China)`, `iso639=zh`, `script=simplified-hanzi`, `romanization=pinyin`, length unit `characters`

Prompt overlays live in `backend/app/services/prompts/common.py` and include aliases for `ja`, `ko`, and `zh`. Reading and listening generation use `get_comprehension_length_guidance()` so Japanese and Mainland Chinese prompts request character ranges while word-spaced languages keep word-count guidance. Reading generation also has dedicated cultural topic pools for Japanese, Korean, and Mainland Chinese.

---

## Sub-phase index

- **10.1** — Title: Database: migrations and new models; Spec file: [phase-10.1-multi-language.instructions.md](phase-10.1-multi-language.instructions.md)
- **10.2** — Title: Backend: services and multi-language prompts; Spec file: [phase-10.2-multi-language.instructions.md](phase-10.2-multi-language.instructions.md)
- **10.3** — Title: API: new endpoints and refactor of existing ones; Spec file: [phase-10.3-multi-language.instructions.md](phase-10.3-multi-language.instructions.md)
- **10.4** — Title: Frontend: core infrastructure; Spec file: [phase-10.4-multi-language.instructions.md](phase-10.4-multi-language.instructions.md)
- **10.5** — Title: Frontend: pages and i18n keys; Spec file: [phase-10.5-multi-language.instructions.md](phase-10.5-multi-language.instructions.md)
- **10.6** — Title: Curriculum and language data; Spec file: [phase-10.6-multi-language.instructions.md](phase-10.6-multi-language.instructions.md)

---

## New files summary

- `backend/app/models/user_language.py` — 10.1
- `backend/alembic/versions/0029_multi_language.py` — 10.1
- `backend/app/services/user_language_service.py` — 10.2
- `backend/app/routers/languages.py` — 10.3
- `backend/app/schemas/language.py` — 10.3
- `backend/tests/test_multi_language.py` — 10.1–10.6
- `backend/app/data/es/` (8 files) — 10.6
- `backend/app/data/it/` (8 files) — 10.6
- `backend/app/data/pt/` (8 files) — 10.6
- `backend/app/data/ja/` (30 files) — Japanese data phase
- `backend/app/data/ko/` (30 files) — Korean data phase
- `backend/app/data/zh/` (33 files) — Mainland Chinese data phase
- `frontend/src/config/target-languages.ts` — 10.4
- `frontend/src/store/language.ts` — 10.4
- `frontend/src/components/LanguageSwitcher.tsx` — 10.4
- `frontend/src/components/TargetLanguageText.tsx` — CJK readiness
- `frontend/src/app/(app)/settings/languages/page.tsx` — 10.5
- `frontend/src/data/es/` (5 files) — 10.6
- `frontend/src/data/it/` (5 files) — 10.6
- `frontend/src/data/pt/` (5 files) — 10.6
- `frontend/public/flags/spain.jpg` — 10.6 (already exists ✅)
- `frontend/public/flags/italy.jpg` — 10.6 (already exists ✅)
- `frontend/public/flags/portugal.jpg` — 10.6 (already exists ✅)
- `frontend/public/flags/japan.jpg` — CJK frontend catalog
- `frontend/public/flags/south_korea.jpg` — CJK frontend catalog
- `frontend/public/flags/china.jpg` — CJK frontend catalog

---

## Modified files summary

- `backend/app/models/__init__.py` — 10.1
- `backend/alembic/env.py` — 10.1
- `backend/app/models/study_plan.py` — 10.1
- `backend/app/models/progress.py` — 10.1
- `backend/app/models/flashcard.py` — 10.1
- `backend/app/models/conversation.py` — 10.1
- `backend/app/models/chat_history.py` — 10.1
- `backend/app/models/competency.py` — 10.1
- `backend/app/models/memory.py` — 10.1
- `backend/app/models/llm_usage.py` — 10.1
- `backend/app/services/llm_service.py` — 10.2
- `backend/app/services/progress_service.py` — 10.2
- `backend/app/services/memory_service.py` — 10.2
- `backend/app/services/language_helpers.py` — 10.2
- `backend/app/services/prompts/common.py` — CJK backend readiness
- `backend/app/services/prompts/comprehension.py` — CJK backend readiness
- `backend/app/services/listening_service.py` — CJK backend readiness
- `backend/app/services/reading_service.py` — CJK backend readiness
- `backend/app/routers/assessment.py` — 10.3
- `backend/app/routers/study_plan.py` — 10.3
- `backend/app/schemas/study_plan.py` — 10.3
- `backend/app/schemas/auth.py` — 10.3
- `backend/app/main.py` — 10.3
- `frontend/src/data/curriculum.ts` — 10.6
- `frontend/src/app/(app)/layout.tsx` — 10.4
- `frontend/src/app/(auth)/onboarding/page.tsx` — 10.5
- `frontend/src/app/(app)/admin/users/page.tsx` — CJK frontend catalog
- `frontend/src/app/(app)/settings/languages/page.tsx` — CJK frontend catalog
- `frontend/src/app/(app)/plan/page.tsx` — 10.5
- `frontend/src/app/(app)/dashboard/page.tsx` — 10.5
- `frontend/src/app/(app)/chat/page.tsx` — 10.5
- `frontend/src/app/(app)/flashcards/page.tsx` — 10.5
- `frontend/src/app/(app)/lesson/[id]/page.tsx` — CJK readiness
- `frontend/src/app/(app)/listening/page.tsx` — CJK readiness
- `frontend/src/app/(app)/reading/page.tsx` — CJK readiness
- `frontend/src/app/(app)/vocabulary/[setId]/page.tsx` — CJK readiness
- `frontend/src/app/(app)/phrasebook/page.tsx` — CJK readiness
- `frontend/src/app/(app)/assessment/page.tsx` — CJK readiness
- `frontend/src/components/LanguageBubbles.tsx` — CJK readiness
- `frontend/src/components/TargetLanguageSelector.tsx` — CJK frontend catalog
- `frontend/src/components/assessment/AdaptiveQuizCard.tsx` — CJK readiness
- `frontend/src/components/conversation/TranscriptBubble.tsx` — CJK readiness
- `frontend/src/components/conversation/ConversationMode.tsx` — CJK readiness
- `frontend/src/app/layout.tsx` — CJK readiness
- `frontend/src/app/globals.css` — CJK readiness
- `frontend/src/lib/target-languages.ts` — 10.4, CJK readiness, CJK frontend catalog
- `frontend/src/app/(app)/progress/page.tsx` — 10.5
- `messages/*.json` (all 10 locale files) — 10.4, 10.5, 10.6, CJK frontend catalog
- `backend/tests/conftest.py` — 10.1
- `backend/tests/test_auth.py` — 10.3
- `backend/tests/test_study_plan.py` — 10.1, 10.3
- `backend/tests/test_flashcards.py` — 10.3
- `backend/tests/test_lessons.py` — 10.3
- `backend/tests/test_chat.py` — 10.3
- `backend/tests/test_conversation.py` — 10.3
- `backend/tests/test_listening.py` — 10.3
- `backend/tests/test_reading.py` — 10.3, CJK backend readiness
- `backend/tests/test_progress.py` — 10.3
- `backend/tests/test_memories.py` — 10.3
- `backend/tests/test_assessment.py` — 10.3
- `backend/tests/test_multi_language.py` — 10.1, 10.2, 10.3, 10.6
- `backend/tests/test_prompts.py` — CJK backend readiness
- `backend/tests/test_listening_service.py` — CJK backend readiness
- `frontend/tests/lib/target-languages.test.ts` — 10.4
- `frontend/tests/components/LanguageBubbles.test.tsx` — CJK readiness
- `frontend/tests/components/TargetLanguageSelector.test.tsx` — CJK frontend catalog
- `frontend/tests/store/language.test.ts` — 10.4
- `frontend/tests/components/LanguageSwitcher.test.tsx` — 10.5
- `frontend/tests/store/language.test.ts` — 10.5 (My Languages page)
- `specs/database-models.instructions.md` — 10.1
- `specs/api-endpoints.instructions.md` — 10.3
- `specs/services.instructions.md` — 10.2
- `specs/architecture-backend.instructions.md` — 10.2
- `specs/study-plan.instructions.md` — 10.1
- `specs/phase-4-target-language.instructions.md` — 10.2
- `specs/version.md` — completion
- `CHANGELOG.md` — completion
- `AGENTS.md` — completion
