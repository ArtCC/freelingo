---
description: "Phase 7 specification for FreeLingo: Reading section — AI-generated reading comprehension exercises with multiple-choice questions, per-user attempt tracking, XP rewards, and history replay."
applyTo: "backend/**, frontend/**, messages/**"
---

# Phase 7 — Reading

## Objective

Add a dedicated Reading section where users practice reading comprehension in their active target language.
The backend generates a text via LLM and stores it in the database so subsequent users
at the same level receive the cached version at zero extra cost. Unlike Listening, no
TTS synthesis is performed — the text is shown directly to the user. The user reads
the passage, answers 5 multiple-choice comprehension questions graded to their CEFR
level, and receives immediate feedback with correct-answer reveal. Progress is saved
as an attempt with a score and XP reward. Completed exercises are not shown again as
"new", but remain accessible in a personal history tab.

---

## Milestones

- 1 — Milestone: DB models & migration; What is built: `reading_exercises` + `reading_attempts` tables
- 2 — Milestone: Backend service & router; What is built: LLM generation, answer evaluation, history
- 3 — Milestone: Frontend page & components; What is built: Exercise card, text display, question form, results panel, history
- 4 — Milestone: Navigation & i18n; What is built: Sidebar entry, translations in all 10 locale files

---

## Exercise types

- `notice` — Description: A short public notice, sign, or instruction; CEFR range: A1–A2
- `email` — Description: A short informal or formal email message; CEFR range: A1–B1
- `article` — Description: A short informational or educational article; CEFR range: B1–B2
- `news` — Description: A news report on a current or recent event; CEFR range: B1–C1
- `blog_post` — Description: An informal blog-style opinion or personal piece; CEFR range: B2–C1
- `review` — Description: A review of a book, film, restaurant, or product; CEFR range: B2–C2
- `essay` — Description: A formal argumentative or discursive essay; CEFR range: C1–C2

Types available per level (`_TYPES_BY_LEVEL` in `reading_service.py`):

- A1 — `notice`, `email`
- A2 — `notice`, `email`
- B1 — `email`, `article`, `news`
- B2 — `article`, `news`, `blog_post`, `review`
- C1 — `news`, `blog_post`, `review`, `essay`
- C2 — `review`, `essay`

One type is selected at random from the level-appropriate subset.

---

## Topics per level

Topics available per level (`_TOPICS_BY_LEVEL` in `reading_service.py`):

- A1 — `daily_routine`, `family`, `shopping`, `home`, `animals`
- A2 — `travel`, `food`, `weather`, `hobbies`, `school`
- B1 — `health`, `work`, `environment`, `sports`, `friendship`
- B2 — `technology`, `culture`, `education`, `media`, `money`
- C1 — `politics`, `science`, `literature`, `psychology`, `urban_life`
- C2 — `philosophy`, `history`, `global_affairs`, `ethics`, `economics`

One topic is selected at random from the level-appropriate subset at generation time.
The selected topic is passed to the LLM prompt as `{topic}` and stored in `ReadingExercise.topic`.
The service also injects language-aware cultural topic guidance. Japanese, Korean, and Mainland Chinese have dedicated cultural topic pools so generated readings avoid falling back to British cultural contexts.

---

## Text length by CEFR level

- A1 — ~80 words
- A2 — ~120 words
- B1 — ~200 words
- B2 — ~280 words
- C1 — ~380 words
- C2 — ~480 words

Slightly longer than listening equivalents since reading is faster to process than audio. Japanese and Mainland Chinese convert these base word counts into character ranges through `get_comprehension_length_guidance()`; word-spaced languages such as Korean keep word-count guidance.

---

## Milestone 1 — Database

### 1.1 `app/models/reading.py`

Two new SQLAlchemy 2.0 models.

**`ReadingExercise`** — one row per generated exercise, shared across users:

```python
class ReadingExercise(Base):
    __tablename__ = "reading_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    level: Mapped[str] = mapped_column(String(2), nullable=False, index=True)          # A1–C2
    target_language: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # BCP-47
    exercise_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # notice | email | article | news | blog_post | review | essay
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)  # sent to client immediately (unlike listening)
    questions: Mapped[dict] = mapped_column(JSON, nullable=False)
    # [{"index": 0, "question": "...", "options": {"A":...,"B":...,"C":...,"D":...}, "correct": "B"}, ...]
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
```

**`ReadingAttempt`** — one row per user completion:

```python
class ReadingAttempt(Base):
    __tablename__ = "reading_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reading_exercises.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    answers: Mapped[dict] = mapped_column(JSON, nullable=False)
    # {"0": "B", "1": "A", "2": "C", "3": "D", "4": "A"}
    score: Mapped[int] = mapped_column(Integer, nullable=False)   # 0–5
    xp_earned: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
```

No ORM relationships are defined — queries use explicit JOINs.

### Questions JSON schema

Stored in `reading_exercises.questions` (identical structure to listening):

```json
[
  {
    "index": 0,
    "question": "What is the main topic of the article?",
    "options": {
      "A": "Climate change",
      "B": "Urban transport",
      "C": "Food production",
      "D": "Digital privacy"
    },
    "correct": "B"
  }
]
```

5 questions ordered by cognitive demand:

- Q0–Q1: literal comprehension (explicitly stated information)
- Q2–Q3: inference (implied meaning, tone, purpose)
- Q4: vocabulary or register (word meaning in context or formality level)

### 1.2 Alembic migration `0019_reading.py`

```
revision = "0019_reading"
down_revision = "0018_listening"
```

Creates tables `reading_exercises` and `reading_attempts` with all columns and
a composite index on `(level, target_language)` for the pool lookup query.

---

## Milestone 2 — Backend

### 2.1 `_parse_llm_json` utility

Move the `_parse_llm_json` function from `app/services/listening_service.py` to
`app/services/llm_adapter.py` as a module-level utility and update the import in
`listening_service.py`. Both `listening_service.py` and `reading_service.py` import it
from `llm_adapter`.

````python
# app/services/llm_adapter.py

def parse_llm_json(raw: str) -> dict:
    """Strip optional code fences and parse JSON from LLM output."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return json.loads(cleaned.strip())
````

### 2.2 LLM prompt (`app/services/reading_service.py`)

The generation prompt is built by `build_reading_generation_prompt()` and passed to
`llm_adapter.structured_output()` with `ReadingGenerationResponse`, so the LLM response is validated
as a Pydantic model before persistence.

```
You are an English language content creator. Generate a reading comprehension exercise
for a {level} learner. Target language variant: {target_language}.

Requirements:
- Exercise type: {exercise_type} ({exercise_type_desc})
- Topic area: {topic}
- Length: approximately {word_count} words
- Use {target_language} vocabulary and spelling conventions
- Write in the natural register appropriate for the exercise type
- Do not use headers, markdown, or lists — plain flowing prose only
  (exception: emails may include a greeting and sign-off)

Return ONLY valid JSON with no prose, no code fences, no extra text:
{{
  "topic": "<brief topic label, max 10 words>",
  "text": "<exercise text as flowing prose>",
  "questions": [
    {{
      "index": 0,
      "question": "<question text>",
      "options": {{ "A": "<option>", "B": "<option>", "C": "<option>", "D": "<option>" }},
      "correct": "<A|B|C|D>"
    }}
  ]
}}

Include exactly 5 questions ordered by cognitive demand:
- Q0-Q1: literal comprehension (directly stated information)
- Q2-Q3: inference (implied meaning, tone, or purpose)
- Q4: vocabulary or register (word meaning in context or formality level)
```

Error handling: malformed JSON/schema responses are handled by `structured_output()`'s JSON-only retry.
If validation still fails, the service raises `ValueError` for the generation task.

### 2.3 Service (`app/services/reading_service.py`)

```python
async def get_available_exercise(
    level: str,
    target_language: str,
    user_id: int,
    db: AsyncSession,
) -> ReadingExercise | None:
    """
    Returns an exercise for this level/language that the user has NOT yet completed.
    Returns None if the pool is empty.
    """

async def generate_and_save_exercise(
    level: str,
    target_language: str,
    db: AsyncSession,
) -> ReadingExercise:
    """
    Calls LLM via structured_output → generates validated text + 5 questions.
    No TTS — text is stored directly.
    Commits and returns the new ReadingExercise.
    """

def calculate_score(
    questions: list[dict], answers: dict[str, str]
) -> tuple[int, int]:
    """Return (score 0–5, xp_earned). Pure function — no DB access."""

async def submit_attempt(
    exercise_id: int,
    user_id: int,
    answers: dict[str, str],
    db: AsyncSession,
    is_replay: bool = False,
) -> tuple[ReadingAttempt, ReadingExercise]:
    """
    Score answers, persist attempt, increment view_count, award XP.
    Returns (attempt, exercise).
    Raises ValueError("exercise_not_found") if exercise_id is invalid.
    Raises ValueError("already_attempted") if user already submitted and is_replay=False.
    When is_replay=True the duplicate guard is skipped and xp_earned is forced to 0.
    """

async def get_user_history(
    user_id: int,
    db: AsyncSession,
    skip: int = 0,
    limit: int = 10,
) -> tuple[list[tuple[ReadingAttempt, ReadingExercise]], int]:
    """Returns past attempts ordered by completed_at DESC, joined with exercise data."""
```

A Redis lock key `reading:generating:{level}:{target_language}` (TTL 60 s) prevents
duplicate generation requests. If the lock is held, `POST /generate` returns HTTP 202
with `{ "status": "generating" }` and the frontend long-polls `GET /next?wait=true`
until the exercise is ready (max 90 s).

Generation runs as a FastAPI `BackgroundTask` (same pattern as listening) because LLM
calls can take 5–30 s depending on the provider and model. The background task creates
its own DB session and Redis client, and releases the lock in a `finally` block.

### 2.4 Router (`app/routers/reading.py`)

All endpoints require a valid access token. Reading is an AI-powered feature and
subject to the Stripe paywall when `STRIPE_ENABLED=true`.

- **GET `/api/reading/next`** — Rate limit: 10/min. Auth: require_subscription. Returns the next uncompleted exercise for the user's CEFR level and language. **Text and questions are included immediately** (unlike listening). Returns `{"available": false}` when the pool is empty. Supports `?wait=true` for long-polling (max 90 s).
- **POST `/api/reading/generate`** — Rate limit: 5/min. Auth: require_subscription. Acquires a per-(level, language) Redis lock (`nx=True, ex=60`) and enqueues a `BackgroundTask` that calls LLM and saves the exercise. Returns HTTP 202 with `{"status": "generating"}`. Returns 202 if a generation job is already running.
- **POST `/api/reading/attempt`** — Rate limit: 20/min. Auth: require_subscription. Submits answers (`{exercise_id, answers, replay}`). Returns score (0–5), XP earned (0–50), and correct answers. Returns 404 (exercise not found), 409 (already attempted), 400 (wrong number of answers).
- **GET `/api/reading/history`** — Rate limit: 60/min. Auth: require_subscription. Returns paginated list of the user's past attempts with scores, XP, exercise text, and correct answers. Query params: `skip` (default 0), `limit` (default 10, max 50).

> **Key difference from listening:** `GET /next` returns the exercise `text` immediately
> in the response body — there is no audio to serve and no "transcript reveal" on submit.
> The correct answers remain hidden until `POST /attempt` is called.

### 2.5 Schemas (`app/schemas/reading.py`)

**`ReadingExerciseOut`** — includes text (shown to user immediately), no correct answers:

```python
class QuestionOut(BaseModel):
    index: int
    question: str
    options: dict[str, str]   # { "A": ..., "B": ..., "C": ..., "D": ... }
    # correct is intentionally omitted

class ReadingExerciseOut(BaseModel):
    id: int
    level: str
    target_language: str
    exercise_type: str
    topic: str
    text: str               # ← included (unlike ListeningExerciseOut)
    questions: list[QuestionOut]
    model_config = {"from_attributes": True}
```

**`ReadingNextResponse`**:

```python
class ReadingNextResponse(BaseModel):
    available: bool
    exercise: ReadingExerciseOut | None = None

class ReadingGeneratingResponse(BaseModel):
    status: str  # "generating"
```

**`ReadingSubmitRequest`**:

```python
class ReadingSubmitRequest(BaseModel):
    exercise_id: int
    answers: dict[str, str]   # {"0": "A", "1": "C", ...} — keys "0"–"4"
    replay: bool = False
```

**`ReadingSubmitResponse`**:

```python
class CorrectAnswerOut(BaseModel):
    index: int
    correct: str

class ReadingSubmitResponse(BaseModel):
    score: int
    xp_earned: int
    correct_answers: list[CorrectAnswerOut]
```

**`ReadingAttemptOut`** — used in history:

```python
class ReadingAttemptOut(BaseModel):
    id: int
    score: int
    xp_earned: int
    completed_at: datetime
    exercise: ReadingExerciseOut   # includes text
    answers: dict[str, str]
    correct_answers: list[CorrectAnswerOut]

class ReadingHistoryResponse(BaseModel):
    items: list[ReadingAttemptOut]
    total: int
    skip: int
    limit: int
```

### 2.6 `app/main.py`

Register the router (prefix already declared inside the router module):

```python
from app.routers import reading
app.include_router(reading.router)  # prefix="/api/reading" set in router
```

---

## Milestone 3 — Frontend

### 3.1 Page — `frontend/src/app/(app)/reading/page.tsx`

Single file — all logic and UI inline, wrapped in `PaywallGate`.

Six UI states controlled by local `PageState` type:

- `loading` — Initial fetch of `GET /api/reading/next` in progress
- `generating` — `POST /api/reading/generate` sent; long-polls `GET /next?wait=true` until available
- `idle` — No exercise available and no generation in progress; shows "Generate exercise" button
- `exercise` — Passage text + question form shown simultaneously; selecting one word in either the passage or a question prompt opens the shared vocabulary-save tooltip, while answer options remain normal selection controls; "Submit" activates when all 5 answered
- `results` — Score, XP, per-question feedback (correct/incorrect highlight); "Next exercise" / "View history" buttons. After a successful new attempt, the page may open the reusable review prompt, subject to duplicate-review checks and local dismissal cooldown. Replay attempts from history do not trigger the prompt.
- `history` — Paginated list of past attempts, 10 per page, using the shared Previous/Next controls. Each card shows topic, score, a text preview, and a replay action. Page changes send `skip` and `limit` to the history endpoint; controls are hidden for a single page and disabled while loading.

**Key UX difference from Listening:** there is no audio player and no "I'm ready"
gate — the text passage and questions are displayed side by side (or stacked on mobile)
immediately. The user scrolls to re-read as needed. There is no transcript reveal on
submission (the text was already visible).

### 3.2 Layout

- **Desktop**: two-column layout inside the exercise card — passage on the left (~55%),
  questions on the right (~45%).
- **Mobile**: stacked — passage first, questions below (with a sticky "back to top" link
  for long passages).
- Passage is rendered in a scrollable `<div>` with a subtle border to visually separate
  it from the question form.

### 3.3 i18n keys

Add `"reading": "Reading"` under the `nav` key in **all 10 locale files**. The label
stays in English ("Reading") in every locale — same convention as "Listening".

Also add page-level strings under a new `reading` namespace:

```json
"reading": {
  "title": "Reading",
  "tabPractice": "Practice",
  "tabHistory": "History",
  "generateButton": "Generate exercise",
  "generatingMessage": "Generating your exercise...",
  "submitButton": "Submit answers",
  "nextButton": "Next exercise",
  "score": "{score} / 5",
  "xpEarned": "+{xp} XP",
  "noHistory": "No exercises completed yet.",
  "reviewButton": "Review",
  "typeNotice": "Notice",
  "typeEmail": "Email",
  "typeArticle": "Article",
  "typeNews": "News",
  "typeBlogPost": "Blog post",
  "typeReview": "Review",
  "typeEssay": "Essay",
  "emptyState": "No exercises available for your level yet.",
  "errorGenerate": "Could not generate exercise. Please try again.",
  "errorSubmit": "Could not submit answers. Please try again."
}
```

### 3.4 Sidebar — `frontend/src/app/(app)/layout.tsx`

Add to `mainNavItems` immediately after the Listening entry:

```typescript
{ href: '/reading', label: tNav('reading') },
```

---

## XP rewards

- 0/5 — 0 XP
- 1/5 — 10 XP
- 2/5 — 20 XP
- 3/5 — 30 XP
- 4/5 — 40 XP
- 5/5 — 50 XP

XP is added via the shared `update_daily_progress` service (same mechanism as lessons
and listening). Replaying an exercise from history awards **no additional XP**.

---

## Stripe paywall

Reading is an AI-powered feature. When `STRIPE_ENABLED=true`:

- `GET /api/reading/next` — ✅
- `POST /api/reading/generate` — ✅
- `POST /api/reading/attempt` — ✅
- `GET /api/reading/history` — ❌ (accessible without subscription)

The frontend wraps the whole page in `PaywallGate`. History tab bypasses the gate via
separate fetch (same pattern as listening history).

---

## Rate limiting summary

- `GET /api/reading/next` — 10/min
- `POST /api/reading/generate` — 5/min
- `POST /api/reading/attempt` — 20/min
- `GET /api/reading/history` — 60/min

---

## Differences from Listening at a glance

- TTS synthesis — Listening: ✅ LLM → TTS → MP3; Reading: ❌ LLM only
- Audio endpoint — Listening: `GET /audio/{id}`; Reading: —
- Text in exercise response — Listening: ❌ Hidden until submit; Reading: ✅ Included immediately
- Transcript reveal on submit — Listening: ✅; Reading: — (already visible)
- `audio_path` / `duration_seconds` — Listening: ✅; Reading: —
- `play_count` — Listening: ✅; Reading: `view_count`
- Frontend audio player — Listening: ✅ `ExerciseAudioPlayer`; Reading: —
- "I'm ready" gate — Listening: ✅ (must play before answering); Reading: —
- Generation pipeline — Listening: Background task (LLM + TTS); Reading: Background task (LLM only)

---

## Testing

Tests live in `backend/tests/test_reading.py` and `backend/tests/test_reading_extra.py`.

### Core tests (`test_reading.py`)

- `test_next_no_exercise` — returns `{"available": false}` when pool is empty
- `test_generate_and_next` — generate triggers background task, exercise appears on next poll
- `test_submit_correct_answers` — all-correct yields score=5, xp=50
- `test_submit_wrong_answers` — all-wrong yields score=0, xp=0
- `test_submit_duplicate` — second submit returns 409
- `test_replay_no_xp` — replay=true scores correctly but xp_earned=0
- `test_history_empty` — returns empty list before any attempts
- `test_history_after_attempt` — attempt appears in history with correct fields

### Edge-case tests (`test_reading_extra.py`)

- `test_generate_locked` — concurrent generate returns 202 without spawning a second job
- `test_next_wait_returns_exercise` — `wait=true` resolves once exercise is in DB
- `test_submit_exercise_not_found` — returns 404
- `test_history_pagination` — `skip` and `limit` params work correctly
- `test_paywall_blocked` — 403 when `STRIPE_ENABLED=true` and subscription is inactive
