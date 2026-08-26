---
description: "Canonical checklist for adding a new FreeLingo target language, based on the British English data package structure and current language dispatchers."
applyTo: "backend/app/data/**, backend/app/schemas/auth.py, backend/app/core/config.py, frontend/src/lib/target-languages.ts, messages/**, specs/**"
---

# Add Target Language

This is the current standard for adding a new learning language to FreeLingo. The structural reference is **British English (`en-GB`)**, the original complete backend data package.

Use `backend/app/data/en_GB/` as the baseline when creating a new package. Adapt the linguistic content to the new language; do not copy English pedagogy where it does not fit.

## No English Visible Content

For a non-English target language, **all learner-facing didactic content must be in the target language**. Do not leave English text in visible learning data just because `en_GB` is the structural reference.

Target-language fields include, without exception:

- Curriculum `title` and `competency_checklist`.
- Grammar `title`, `category`, `summary`, `explanation`, `structure`, `rules`, examples, and common mistake notes.
- Vocabulary `topic`, `word`, `definition`, and `example`.
- Phrasebook `situation`, phrase `text`, and phrase `context`.
- Assessment `question`, `options`, and reading snippets.

English/ASCII is acceptable for code, technical comments, internal identifiers, and cross-language/general constants, such as `id`, `slug`, `grammar_points`, `vocabulary_set_ids`, `unit_ref`, module names, and enum values (`grammar`, `vocabulary`, `reading`, `formal`, `neutral`, `informal`).

If a field intentionally stores a translation or learner aid, make that purpose explicit in the data model or field name. Do not use English as a silent fallback for missing didactic content.

## Activation Rule

Do not add a language code to backend `SUPPORTED_TARGET_LANGUAGES` until the backend data package is complete:

- Curriculum
- Grammar
- Vocabulary
- Phrasebook
- Assessment bank

`AVAILABLE_TARGET_LANGUAGES` may contain operator-ready codes, but the backend filters that list through `SUPPORTED_TARGET_LANGUAGES`. A language becomes selectable only when both are true: the code is allowed by backend and present in the operator-visible list.

## Canonical Baseline: `en-GB`

Current `en-GB` inventory:

- Curriculum — 48 units: 8 per CEFR level A1-C2
- Grammar — 135 topics
- Vocabulary — 96 sets
- Phrasebook — 28 categories
- Assessment bank — 119 questions

These are target ranges, not exact hard requirements. A new language should be comparable in depth and must not ship with placeholder/empty content.

## Backend Data Package Structure

Create `backend/app/data/<iso639>/` using the `en_GB` shape as reference.

Required files:

- `__init__.py` — Package marker
- `curriculum.py` — Assembles `curriculum_a1.py` ... `curriculum_c2.py`
- `curriculum_a1.py` ... `curriculum_c2.py` — Per-level curriculum units
- `grammar.py` — Assembler only; imports grammar modules and exports the flattened topic list
- `grammar_*` modules — Required; split by CEFR level or topic group, matching the `en_GB` modular pattern
- `vocabulary.py` — Assembler only; imports `vocabulary_a1.py` ... `vocabulary_c2.py`
- `vocabulary_a1.py` ... `vocabulary_c2.py` — Per-level vocabulary sets
- `phrasebook.py` — Assembles `phrasebook_a1.py` ... `phrasebook_c2.py`
- `phrasebook_a1.py` ... `phrasebook_c2.py` — Per-level phrasebook categories
- `assessment_bank.py` — Static assessment question list

Required exports:

- `CURRICULUM` — `dict[str, list[CurriculumUnit]]`
- `GRAMMAR_TOPICS` — `list[GrammarTopic]`
- `VOCABULARY_SETS` — `list[VocabularySet]`
- `PHRASEBOOK_CATEGORIES` — `list[PhrasebookCategory]`
- `ASSESSMENT_BANK` — `list[AssessmentQuestion]`

## Curriculum Standard

Follow `backend/app/data/en_GB/curriculum.py` and its level modules.

Target shape:

- 6 level modules: A1, A2, B1, B2, C1, C2.
- 8 units per level.
- 48 units total.

Each `CurriculumUnit` must include:

- `id`: stable, level-scoped ID such as `a1-unit-1`.
- `level`: `A1`, `A2`, `B1`, `B2`, `C1`, or `C2`.
- `unit_number`: 1-8 within the level.
- `title`: learner-facing text in the target language; never English for non-English languages.
- `grammar_points`: internal slugs used by lesson generation and grammar references.
- `vocabulary_set_ids`: IDs that exist in that language's vocabulary package.
- `lesson_types`: valid `LessonType` values.
- `competency_checklist`: learner-facing objectives in the target language; never English for non-English languages.
- `default_weeks`.
- `prerequisite_unit`.

`curriculum.py` should:

- Import shared types from `app.data._types` with `# noqa: F401`.
- Import A1-C2 unit lists.
- Define `CEFR_LEVELS`.
- Define `CURRICULUM`.

Some non-English packages still include legacy `INTENSITY_CONFIG`, `get_curriculum_units`, and `distribute_units` helpers. The runtime uses `backend/app/data/curriculum.py`, but new packages should keep these helpers if matching the existing non-English package pattern is useful for consistency.

## Grammar Standard

Use `en_GB` as the depth reference: about 130+ topics.

Rules:

- Every curriculum `grammar_points` slug must exist as a `GrammarTopic.slug` in that language.
- Slugs must be unique within the language.
- `title`, `category`, `summary`, `explanation`, `structure`, `rules`, examples, and mistake notes must be in the target language unless the field intentionally stores a translation.
- `related` entries must point to existing slugs in the same language.
- Structure must be split into grammar modules by CEFR level or topic group, matching `en_GB` (`grammar_base.py`, `grammar_extras_*`). `grammar.py` must be an assembler only and export one flattened `GRAMMAR_TOPICS` list.

## Vocabulary Standard

Use `en_GB` as the depth reference: about 95-100 sets.

Rules:

- Every curriculum `vocabulary_set_ids` entry must exist as a `VocabularySet.id`.
- IDs must be unique within the language.
- `level` must be valid CEFR.
- `topic`, `definition`, and `example` must be in the target language.
- `unit_ref` should point to the associated curriculum unit.
- Each set must contain real entries; no empty sets.
- Use per-level modules (`vocabulary_a1.py` ... `vocabulary_c2.py`) and an assembler-only `vocabulary.py`, matching `en_GB`.

## Phrasebook Standard

Use `en_GB` as the depth reference: about 28 categories.

Rules:

- Categories should cover practical situations from A1-C2.
- `situation` must be in the target language.
- `text` must be a phrase in the target language.
- `context` must explain when to use it in the target language.
- `register` must be `formal`, `neutral`, or `informal`.
- `unit_ref` should point to a related curriculum unit where possible.
- Prefer per-level modules (`phrasebook_a1.py` ... `phrasebook_c2.py`) and an assembler `phrasebook.py`, matching `en_GB`.

## Assessment Bank Standard

Use `en_GB` as the depth reference: about 120 questions.

Current `en-GB` distribution:

- Grammar — 47
- Vocabulary — 47
- Reading — 25

Current `en-GB` level distribution:

- A1 — 24
- A2 — 24
- B1 — 24
- B2 — 17
- C1 — 16
- C2 — 14

Rules:

- Every question must have exactly 4 unique options.
- `correct` must match one option exactly.
- IDs must be unique and stable.
- `grammar_slug`, when present, must point to a grammar topic in the same language.
- Question text, options, and reading snippets should be in the target language.
- Prefer explicit `AssessmentQuestion(...)` objects, matching `en_GB`, unless there is a strong maintainability reason to use generated data.

## Dispatchers And Allow-Lists

After the data package is complete, update:

- `backend/app/data/curriculum.py`
- `backend/app/data/grammar.py`
- `backend/app/data/vocabulary.py`
- `backend/app/data/phrasebook.py`
- `backend/app/data/assessment_bank.py`
- `backend/app/schemas/auth.py` `SUPPORTED_TARGET_LANGUAGES`
- `backend/app/core/config.py` default `AVAILABLE_TARGET_LANGUAGES`, when the language should be visible by default
- `.env.example` and `.env.dev`, when operator defaults should include the language

Unknown language fallback remains `en-GB` unless a future strict-resolution feature changes it.

## Frontend And i18n

Update:

- `frontend/src/lib/target-languages.ts`: code, names, flag path, ISO code, script metadata, romanization, word-spacing behaviour, text class.
- `messages/*.json`: `targetLanguages` names, aliases, descriptions, and landing greetings in all 10 UI locales.
- CJK or non-Latin languages: ensure learned-language content uses `TargetLanguageText` in UI surfaces.

Selectable frontend options must come from backend-provided available codes. Do not make a language selectable just because it exists in the frontend catalog.

## Prompt And Service Readiness

Update or verify:

- `backend/app/services/language_helpers.py`: display name, ISO-639 code, script, romanization, word-spacing, reading length unit.
- `backend/app/services/prompts/common.py`: language overlay and ISO alias.
- Reading/listening length guidance, especially for character-based scripts.
- TTS/STT provider compatibility. Kokoro is English-only; non-English languages generally require `TTS_PROVIDER=openai`.
- STT language propagation: add the BCP-47 → ISO mapping and include the language in the parameterized `/api/stt` plan-context test. Never add a provider-level English default for a new language.

## Tests

Add or update tests so the new language cannot silently fall back to English:

- `backend/tests/test_multi_language.py`: allow-list, add-language, curriculum resolution.
- `backend/tests/test_grammar.py`: grammar endpoint returns language-specific topics.
- `backend/tests/test_vocabulary.py`: vocabulary endpoint returns language-specific sets.
- `backend/tests/test_phrasebook.py`: phrasebook endpoint returns language-specific categories.
- `backend/tests/test_assessment_bank.py`: assessment dispatcher returns a non-empty bank.
- `backend/tests/test_frontend_data_integrity.py`: grammar slug refs, vocabulary refs, related refs, uniqueness checks.
- `backend/tests/test_stt.py`: the owned study plan maps the new BCP-47 language to the expected provider ISO code without an English fallback.
- Prompt tests if language helper or overlay metadata changes.

Minimum targeted validation:

```bash
python3 -m compileall app/ alembic/ -q
ruff check app/data/<iso639> app/data/curriculum.py app/data/grammar.py app/data/vocabulary.py app/data/phrasebook.py app/data/assessment_bank.py tests/test_multi_language.py tests/test_grammar.py tests/test_vocabulary.py tests/test_phrasebook.py tests/test_assessment_bank.py tests/test_frontend_data_integrity.py tests/test_stt.py
pytest tests/test_multi_language.py tests/test_grammar.py tests/test_vocabulary.py tests/test_phrasebook.py tests/test_assessment_bank.py tests/test_frontend_data_integrity.py tests/test_stt.py -q --no-cov
```

Run the full `pre-push` skill before pushing.

## Documentation Updates

Always ask before updating documentation. State exactly which spec/MD/version files will change and wait for explicit user approval before editing them.

After implementation and validation, update affected docs:

- `CHANGELOG.md`
- `specs/version.md` for version bumps
- `specs/architecture-backend.instructions.md`
- `specs/services.instructions.md`
- `specs/api-endpoints.instructions.md`
- `specs/study-plan.instructions.md`
- `specs/phase-10-multi-language.instructions.md`
- `specs/testing.instructions.md`
- `README.md` and `AGENTS.md` if they list current project state or supported languages

Per `AGENTS.md`, a language task is not complete until affected docs are synced or the user explicitly opts out.
