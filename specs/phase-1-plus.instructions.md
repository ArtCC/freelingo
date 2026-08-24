---
description: "Phase 1+ specification for FreeLingo: Learning Resources Hub with Grammar Reference, Vocabulary Hub, Phrasebook, Skills Tracker, and Level Completion Test — all static content, integrated with the curriculum and ai tutor."
applyTo: "frontend/src/**"
---

# Phase 1+ — Learning Resources Hub

## Objective

A unified resource centre delivering five complementary features: a grammar reference, vocabulary explorer, situational phrasebook, skills tracker with competency monitoring, and end-of-level completion tests. All reference content is static TypeScript — no database, no API calls needed for content browsing. The hub is tightly integrated with the curriculum roadmap, lessons, flashcards, and the AI tutor.

---

## Milestones

- 1 — Milestone: Grammar Reference; What was built: Static grammar data file + `/grammar` index + `/grammar/[slug]` detail pages
- 2 — Milestone: Vocabulary Hub; What was built: Backend vocabulary data per language + `/vocabulary` index via API + set detail pages with flashcard integration
- 3 — Milestone: Phrasebook; What was built: Static phrasebook data file + `/phrasebook` page with level and register filters
- 4 — Milestone: Skills Tracker; What was built: `/progress` page showing unit competencies, vocabulary progress, XP history
- 5 — Milestone: Level Completion Test; What was built: End-of-level exam at `/assessment/level-test` with auto-generated questions and scoring
- 6 — Milestone: Navigation & routing; What was built: RESOURCES nav group in sidebar, curriculum-driven `/plan` roadmap

---

## Milestone 1 — Grammar Reference

### Data model (`backend/app/data/_types.py` + per-language `grammar.py`)

Grammar content is served from backend Python dataclasses organized per target language and CEFR level. The frontend consumes `GET /api/grammar` and falls back to `en-GB` when no active learning language is available.

Each grammar topic has:

- **`slug`** — Type: string. Description: URL-safe identifier (e.g. `"present-simple"`, `"past-continuous"`)
- **`title`** — Type: string. Description: Display title
- **`level`** — Type: CEFRLevel. Description: A1, A2, B1, B2, C1, C2
- **`category`** — Type: GrammarCategory. Description: One of 14 categories (Tenses, Questions, Nouns, Pronouns, Adjectives & Adverbs, Modals, Conditionals, Passive Voice, Reported Speech, Clauses, Articles, Prepositions, Phrasal Verbs, Advanced)
- **`summary`** — Type: string. Description: One-line description for index cards
- **`explanation`** — Type: string. Description: Full explanation in Markdown-lite format
- **`structure`** — Type: string (optional). Description: Formula/pattern (e.g. "Subject + base verb + s/es")
- **`rules`** — Type: string[]. Description: Key rules as bullet points
- **`examples`** — Type: array. Description: Objects with `english`, optional `translation` (rendered in user's native language), and optional `note`
- **`common_mistakes`** — Type: array. Description: Objects with `wrong`, `correct`, and `note` fields
- **`related`** — Type: string[]. Description: Slugs of related grammar topics for cross-linking

**Categories**: 14 categories provide structure for the index page, allowing users to filter by grammatical category in addition to CEFR level.

### Grammar index page (`/grammar`)

Renders all grammar topics organized by CEFR level. Each topic appears as a card showing:

- Title and category badge
- Summary paragraph
- "View details →" link

Features a search bar that filters topics by title and content. Category filter tabs allow narrowing by grammatical category.

### Grammar detail page (`/grammar/[slug]`)

Dynamic route rendering a single grammar topic. The `[slug]` parameter maps directly to a `GrammarTopic.slug`:

- Unknown slugs return a 404 page (Next.js `notFound()`)
- Renders: title, level badge, explanation (formatted Markdown-lite), structure pattern, rules list, example sentences with optional translations, common mistakes table, and related topics links
- Related topics are linked to their own detail pages
- Renders native-language study support below the target-language explanation. A1/A2 opens by default and generates on page load; B1-C2 stays collapsed and generates only when opened. The generated support includes summary, explanation, key points, target-language examples with native notes, common traps, and a mini-glossary.
- The AI tutor's system prompt references the current grammar slug to provide contextual corrections during chat

### Native-language grammar help

`POST /api/grammar/{slug}/native-help?language=<target>` generates grammar support in the authenticated user's native language. Results are cached globally in `resource_native_helps` by `resource_type="grammar"`, grammar slug, target language, native language, and source-content hash, so the same native-language help is generated only once per static topic version and reused for later users.

### Integration with other features

- **Lessons**: lesson content includes `grammar_refs` — slugs from this data file for cross-linking
- **Assessment**: quiz questions have optional `grammar_slug` to map wrong answers to grammar topics
- **Curriculum**: each `CurriculumUnit` declares `grammar_points` — the set of slugs covered
- **Level test**: questions are constrained to grammar slugs studied during the level
- **Validation**: the backend validates that LLM-generated grammar slugs belong to a known set of 24 slugs (`VALID_GRAMMAR_SLUGS`)

---

## Milestone 2 — Vocabulary Hub

### Data model (`backend/app/data/_types.py` + per-language `vocabulary.py`)

> **Migrated to backend in v1.7.4.** Originally static TypeScript (`frontend/src/data/vocabulary.ts`); now served via `GET /api/vocabulary` from Python dataclasses organized per CEFR level (A1–C2) across backend language modules, including Japanese (`ja-JP`), Korean (`ko-KR`), and Mainland Chinese (`zh-CN`). The CJK language packages follow the same per-level module and assembler organization as the other backend language packages. The frontend vocabulary hub and set detail pages consume the API instead of importing static data.

**VocabularyEntry** (per word):

- `word` — Type: string; Description: Target-language word
- `pos` — Type: PartOfSpeech; Description: Noun, verb, adjective, adverb, phrase, conjunction, preposition, numeral, pronoun
- `definition` — Type: string; Description: Simple definition in the target language
- `example` — Type: string; Description: Natural usage example
- `ipa` — Type: string (optional); Description: IPA pronunciation
- `frequency_rank` — Type: number (optional); Description: Usage frequency ranking

**VocabularySet** (per topic):

- `id` — Type: string; Description: Unique identifier (e.g. `"identity"`, `"greetings"`)
- `level` — Type: CEFRLevel; Description: CEFR level
- `topic` — Type: string; Description: Human-readable topic name
- `unit_ref` — Type: string; Description: Curriculum unit this set belongs to (e.g. `"a1-unit-1"`)
- `words` — Type: VocabularyEntry[]; Description: The vocabulary items

### Vocabulary index page (`/vocabulary`)

Lists all vocabulary sets grouped by CEFR level. Each set card shows:

- Topic name and level badge
- Word count (e.g. "15 words")
- Flashcard progress: how many words from this set the user has as flashcards ("3/15 in flashcards")

Search bar filters sets by topic name or words within.

### Vocabulary set detail page (`/vocabulary/[setId]`)

Dynamic route for a single vocabulary set. The `[setId]` parameter maps to a `VocabularySet.id`. Shows:

- Topic title, level badge, word count
- Full word table: word, part of speech badge, definition, example, IPA pronunciation, frequency rank
- "Add to flashcards" button: sends the word to the flashcards API for SM-2 review
- A native-language helper panel that stays collapsed until requested. Generated support includes a topic summary, study tips, selected word notes, common traps, a mini-glossary, and practice prompts.

### Native-language vocabulary help

`POST /api/vocabulary/{set_id}/native-help?language=<target>` generates vocabulary study support in the authenticated user's native language. Results are cached globally in `resource_native_helps` by `resource_type="vocabulary"`, set ID, target language, native language, and source-content hash. The generated help keeps target-language words and examples unchanged while explaining memory tips, usage notes, common traps, glossary meanings, and practice prompts in the learner's native language.

### Integration with flashcards

The vocabulary hub and flashcard system are connected:

- Users can add individual words or whole sets to their flashcards
- The progress page shows per-set flashcard coverage
- When the LLM generates flashcards, it can draw from the user's current vocabulary set

---

## Milestone 3 — Phrasebook

### Data model (`backend/app/data/_types.py` + per-language `phrasebook.py`)

> **Migrated to backend.** Phrasebook content is served via `GET /api/phrasebook` from Python dataclasses organized per CEFR level (A1-C2) across backend language modules, including Japanese (`ja-JP`), Korean (`ko-KR`), and Mainland Chinese (`zh-CN`). Japanese, Korean, and Mainland Chinese phrasebooks each contain 318 target-language phrases across A1-C2.

**Phrase** (per entry):

- `text` — Type: string; Description: The phrase in the target language
- `context` — Type: string; Description: When/where to use the phrase
- `register` — Type: Register; Description: `"formal"`, `"neutral"`, or `"informal"`
- `unit_ref` — Type: string (optional); Description: Curriculum unit this phrase relates to

**PhrasebookCategory** (per situation):

- `id` — Type: string; Description: Unique identifier
- `level` — Type: CEFRLevel; Description: Minimum level for this situation
- `situation` — Type: string; Description: Real-world scenario (e.g. "At the restaurant")
- `icon` — Type: string; Description: Emoji representing the situation (for visual indexing)
- `phrases` — Type: Phrase[]; Description: The phrases for this situation

### Phrasebook page (`/phrasebook`)

Lists all phrasebook categories. Filterable by:

- **CEFR level**: checkboxes or tabs for A1, A2, B1, B2, C1
- **Register**: formal, neutral, informal

Each category card shows:

- Icon (emoji) and situation name
- Level badge
- Phrase count
- Expand to see all phrases with context and register badges
- Phrase entries are selectable (tap to copy to clipboard)
- A native-language helper panel. A1/A2 panels open by default but generate only when the user clicks the helper button; B1-C2 panels stay collapsed until requested. Generated support includes usage tips, register notes, phrase notes, common traps, and a mini-glossary.

### Native-language phrasebook help

`POST /api/phrasebook/{category_id}/native-help?language=<target>` generates practical usage support in the authenticated user's native language. Results are cached globally in `resource_native_helps` by `resource_type="phrasebook"`, category ID, target language, native language, and source-content hash. The generated help keeps target-language phrases unchanged and explains when to use them, register/formality, common traps, and useful expressions in the learner's native language.

### Usage

The phrasebook is designed as a quick reference for real-world use of the selected learning language. It complements the grammar and vocabulary references by focusing on complete, usable expressions rather than isolated words or rules.

---

## Milestone 4 — Skills Tracker

### Progress page (`/progress`)

A comprehensive skills dashboard replacing the simpler progress summary. Shows three main sections:

**Unit Competency Checklist**

Per-unit progress derived from `UserCompetency` records (Phase 1+ backend model). Each unit displays:

- Unit name and CEFR level
- List of competencies with individual scores (0.0–1.0) and mastery status (>= 0.80)
- Overall unit percentage (average of competency scores)
- Progress bar with color coding: red (< 0.40), yellow (0.40–0.79), green (>= 0.80)

Competencies are updated via exponential moving average each time a related lesson is completed. The EMA formula: `new_score = (0.7 × previous_score) + (0.3 × latest_score)`.

**Vocabulary Progress**

Per-set vocabulary progress:

- Which vocabulary sets have been added to flashcards
- How many words from each set are in the user's flashcard deck
- Progress bars showing coverage per set

**XP and Streak History**

- Current streak (consecutive active days)
- Total XP
- Daily XP breakdown (last 90 days)
- Skill scores: grammar, vocabulary, reading, writing (also EMA-based)

### Backend endpoint

`GET /api/progress/competencies` — returns per-unit competency data from `user_competencies` table, aggregated by unit and ordered by curriculum sequence.

---

## Milestone 5 — Level Completion Test

### Purpose

When a user completes all curriculum units in their current CEFR level, an end-of-level test becomes available. This test evaluates whether the student has truly mastered the level's content before advancing.

### Trigger

- The `LevelTestBanner` component appears on the dashboard when `current_unit` surpasses the last unit of the level
- The `/plan` roadmap shows a gold "Level Test" node at the end of the timeline
- Both are only clickable after ALL units in the level are completed

### Question generation

Test questions are generated by the LLM (backend) and constrained to:

- Grammar points studied during the level (from the curriculum unit's `grammar_points`)
- Vocabulary sets studied during the level (from `vocabulary_set_ids`)
- 20 questions total, mixing grammar, vocabulary, and reading comprehension
- No content from the next CEFR level

The prompt (`END_OF_LEVEL_TEST_PROMPT` in `services/assessment.py`) instructs the LLM to generate questions using the same schema as the placement test but strictly scoped to studied material.

### Scoring and recommendations

- >= 0.75 — Recommendation: `"advance"`; Action: Unlock next CEFR level, create new study plan
- 0.55 – 0.74 — Recommendation: `"extend"`; Action: Recommend 4-week extension focusing on weak units
- < 0.55 — Recommendation: `"repeat"`; Action: Recommend repeating the full level

The recommendation is stored in the StudyPlan model (`completion_test_score`, `completion_test_recommendation`) and displayed in the `TestResultSummary` component.

### User flow

```
Dashboard → LevelTestBanner ("You've completed all A1 units!")
    ↓
/assessment/level-test → 20 questions (LLM-generated, curriculum-constrained)
    ↓
Submission → Backend scores → returns result + recommendation
    ↓
TestResultSummary: score, competency breakdown, recommendation
    ↓
If "advance": unlock next level plan creation
If "extend": extend current plan by 4 weeks, focus on weak units
If "repeat": archive current plan, enable creating a new plan for same level
```

---

## Milestone 6 — Navigation & Routing

### Sidebar navigation

The sidebar nav groups routes under logical sections:

```
┌─────────────────────┐
│ 📊 LEARNING          │
│   Dashboard          │
│   Study Plan         │
│   Progress           │
│                      │
│ 📚 RESOURCES         │
│   Grammar            │
│   Vocabulary         │
│   Phrasebook         │
│                      │
│ 🎯 PRACTICE          │
│   Lessons            │
│   Flashcards         │
│   Chat with Tutor    │
│   Conversation       │
│                      │
│ ⚙️ SETTINGS          │
│   Settings           │
│   FAQ                │
│   Admin Panel        │ ← admin only
└─────────────────────┘
```

The RESOURCES nav group was added in Phase 1+ to give grammar, vocabulary, and phrasebook prominent placement.

### Mobile navigation

On mobile (below `md` breakpoint), the sidebar collapses into a hamburger menu. The chat sidebar (conversation list) opens as a fixed overlay with a semi-transparent backdrop rather than a side-by-side column.

### Route protection

Next.js middleware at `src/middleware.ts`:

- Detects `refresh_token` cookie for auth gating
- Redirects unauthenticated users to `/login`
- Handles locale detection via `next-intl` (cookie-based, falls back to Accept-Language header)
- Matcher excludes static assets, `_next`, and API routes

---

## Technical design decisions

### Static reference content

Grammar, vocabulary, phrasebook, and assessment reference content is served from backend Python dataclasses via API endpoints (`/api/grammar`, `/api/vocabulary`, `/api/phrasebook`, `/api/assessment/bank`). Curriculum data (unit definitions, grammar points, vocabulary set IDs) lives in backend Python files for plan generation and in frontend data/API consumers for roadmap rendering.

Reasons for the current approach:

1. **Reference data (backend API)**: large multi-language datasets benefit from server-side serving, per-language dispatching, and shared integrity checks without bloating the client bundle
2. **Curriculum (backend + frontend consumers)**: backend data drives plan generation and lesson constraints; frontend surfaces fetch/render the current curriculum state for the roadmap UI

### Cross-referencing

A data integrity test (`test_frontend_data_integrity.py`) validates that:

- Every `grammar_slug` referenced in curriculum units exists in the target language's backend grammar data
- Every `vocabulary_set_id` referenced in each language's curriculum exists in that language's backend vocabulary data, including Japanese, Korean, and Mainland Chinese
- Every `related` slug in grammar topics points to an existing topic

### Curriculum data flow

Curriculum state is exposed to both backend and frontend:

- `frontend/src/data/curriculum.ts` and curriculum API consumers — roadmap UI rendering
- `backend/app/data/curriculum.py` and language packages — canonical curriculum data for plan generation and lesson constraints

This split is intentional: the frontend needs fast roadmap rendering, and the backend needs authoritative curriculum data for plan generation and LLM constraint validation. Cross-file references are validated by data integrity tests.

---

## Phase 1+ completion criteria (all met in v1.1.0)

- [x] `/grammar` renders all topics from backend grammar data
- [x] `/grammar/[slug]` renders full detail; unknown slugs return 404
- [x] `/vocabulary` lists all sets grouped by level with flashcard-progress badges (fetches via `/api/vocabulary`)
- [x] `/vocabulary/[setId]` shows words + "Add to flashcards" button that integrates with the flashcard API and on-demand native-language study help
- [x] `/phrasebook` lists situations with level and register filters
- [x] `/progress` shows per-unit competency checklist with scores
- [x] `/progress` shows vocabulary progress bars per set (fetches via `/api/vocabulary`)
- [x] Level test available only after all units in a level are completed
- [x] Level test generates 20 curriculum-constrained questions via LLM
- [x] Level test recommendation thresholds: advance >= 75% / extend 55-74% / repeat < 55%
- [x] RESOURCES nav group works on desktop and mobile
- [x] `/plan` visual roadmap linked from dashboard
- [x] Data integrity test validates cross-references between curriculum, grammar, and vocabulary files
- [x] No regressions in Phase 1 features
