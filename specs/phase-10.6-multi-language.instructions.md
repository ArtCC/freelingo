---
description: "Phase 10.6 spec — Multi-language: curriculum data for Spanish, Italian and Portuguese (backend + frontend)."
applyTo: "backend/**, frontend/**"
---

# Phase 10.6 — Curriculum and language data

## Goal

Create curriculum data files for the 3 new languages (Spanish, Italian, Portuguese) on both backend and frontend, and update the curriculum entry points to dispatch by language.

**Prerequisite:** Phase 10.3 must be merged before starting this phase (backend). Phase 10.4 must be merged before starting the frontend part.

---

## 10.6.1 Backend: curriculum dispatcher

**File:** `backend/app/data/curriculum.py` (update)

Replace the current English-only curriculum import with a language-aware dispatcher:

```python
from app.services.language_helpers import get_iso639


def get_curriculum(target_language: str) -> list:
    iso = get_iso639(target_language)
    if iso == "en":
        from app.data.en.curriculum import CURRICULUM
    elif iso == "es":
        from app.data.es.curriculum import CURRICULUM
    elif iso == "it":
        from app.data.it.curriculum import CURRICULUM
    elif iso == "pt":
        from app.data.pt.curriculum import CURRICULUM
    else:
        from app.data.en.curriculum import CURRICULUM  # fallback
    return CURRICULUM
```

---

## 10.6.2 New backend curriculum directories

A directory with the same structure as `backend/app/data/en/` is created for each new language. The English curriculum is **not modified**.

### Structure (identical for `es/`, `it/`, `pt/`)

- `__init__.py` — Python package marker
- `_types.py` — Types — can re-export from `en/_types.py` if identical
- `curriculum.py` — Entry point: assembles and exports `CURRICULUM`
- `curriculum_a1.py` — CEFR A1 units in the target language
- `curriculum_a2.py` — CEFR A2 units
- `curriculum_b1.py` — CEFR B1 units
- `curriculum_b2.py` — CEFR B2 units
- `curriculum_c1.py` — CEFR C1 units
- `curriculum_c2.py` — CEFR C2 units

### Directories to create

- `backend/app/data/es/` — Spanish curriculum (8 files)
- `backend/app/data/it/` — Italian curriculum (8 files)
- `backend/app/data/pt/` — Portuguese curriculum (8 files)

### Content guidelines

Curriculum units are **language-specific, not translations of English**. Each unit must use:

- Grammar slugs appropriate for the target language (e.g. Spanish: `"ser-vs-estar"`, `"subjuntivo-presente"`).
- Vocabulary topics appropriate for learning that language from scratch (A1 → C2).
- Unit titles in English (used in the admin/internal UI) but content labels that make sense for learners.

---

## 10.6.3 Frontend: curriculum dispatcher

**File:** `frontend/src/data/curriculum.ts` (update)

```typescript
import { enCurriculum } from "./en/curriculum";
import { esCurriculum } from "./es/curriculum";
import { itCurriculum } from "./it/curriculum";
import { ptCurriculum } from "./pt/curriculum";

export function getCurriculum(targetLanguage: string): CurriculumData {
  const iso = targetLanguage.split("-")[0];
  switch (iso) {
    case "en":
      return enCurriculum;
    case "es":
      return esCurriculum;
    case "it":
      return itCurriculum;
    case "pt":
      return ptCurriculum;
    default:
      return enCurriculum;
  }
}
```

---

## 10.6.4 New frontend curriculum directories

### Structure (identical for `es/`, `it/`, `pt/`)

- `curriculum.ts` — Curriculum units (A1–C2)
- `grammar.ts` — Grammar reference entries
- `vocabulary.ts` — Vocabulary sets — migrated to backend in v1.7.4 (`app/data/{lang}/vocabulary_{a1-c2}.py`), served via `/api/vocabulary`
- `phrasebook.ts` — Phrasebook entries
- `assessment-bank` — Assessment question bank (now in `backend/app/data/{lang}/assessment_bank.py`)

### Directories to create

- `frontend/src/data/es/` (3 files: curriculum, grammar, phrasebook)
- `frontend/src/data/it/` (3 files)
- `frontend/src/data/pt/` (3 files)

---

## 10.6.5 Flag images

Already present in `frontend/public/flags/`:

- `spain.jpg` ✅
- `italy.jpg` ✅
- `portugal.jpg` ✅
- `usa.jpg` ✅ (existing)
- `uk.jpg` ✅ (existing)

No action needed.

---

## 10.6.6 i18n keys (add in this phase)

**Files:** all 10 locale files under `messages/`

Add entries for the 3 new languages to the existing `targetLanguages` namespace (do not remove the existing `en-US` and `en-GB` entries):

```json
"targetLanguages": {
  "es-ES": "Spanish",
  "es-ES-description": "Spanish spoken in Spain, one of the most widely spoken languages in the world.",
  "it-IT": "Italian",
  "it-IT-description": "Standard Italian, the language of culture, art and gastronomy.",
  "pt-PT": "Portuguese",
  "pt-PT-description": "European Portuguese, official language of Portugal."
}
```

The English values above are the reference. Add the equivalent translations in all 10 locale files.

---

## Tests

### New tests (`backend/tests/test_multi_language.py`)

- `test_curriculum_per_language` — `get_curriculum()` returns the correct curriculum for each language (en, es, it, pt)

### Frontend tests (Vitest)

- **`frontend/tests/data/curriculum.test.ts`** — `getCurriculum('es-ES')` returns Spanish curriculum; all 5 languages have complete data; dispatcher falls back for unsupported languages

## New files in this phase

- `backend/app/data/es/__init__.py` — Package
- `backend/app/data/es/_types.py` — Types
- `backend/app/data/es/curriculum.py` — Entry point
- `backend/app/data/es/curriculum_a1.py` ... `curriculum_c2.py` — 6 CEFR files
- `backend/app/data/it/` — Same structure (8 files + vocabulary migrated from frontend in v1.7.4)
- `backend/app/data/pt/` — Same structure (8 files + vocabulary migrated from frontend in v1.7.4)
- `frontend/src/data/es/curriculum.ts` — ES curriculum
- `frontend/src/data/es/grammar.ts` — ES grammar
- `backend/app/data/es/vocabulary_a1.py`...`c2.py` — ES vocabulary (migrated from frontend in v1.7.4)
- `frontend/src/data/es/phrasebook.ts` — ES phrasebook
- `backend/app/data/es/assessment_bank.py` — ES assessment bank
- `frontend/src/data/it/` — Same structure (3 files)
- `frontend/src/data/pt/` — Same structure (3 files)

## Modified files in this phase

- `backend/app/data/curriculum.py` — Language-aware dispatcher
- `frontend/src/data/curriculum.ts` — Language-aware dispatcher

---

## Cosmetic cleanup completed from Phase 10.2

The prompt cleanup is complete: target-language words and examples stay in the learning language, while definitions and translations use the learner's native language.

### `backend/app/services/flashcard_sm2.py`

`FLASHCARD_GEN_PROMPT` and `WORD_LOOKUP_PROMPT` use these native-language definition fields:

```
"definition": "Simple definition in {native_language}"
"definition": "Simple definition in {native_language} (max 20 words)"
```

### `backend/app/services/lesson_generator.py`

The pronunciation exercise JSON schema inside `LESSON_GENERATION_PROMPT` uses the current target-language form:

```
"correct": "The exact {target_language_name} phrase the student must pronounce."
```
