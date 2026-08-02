---
description: "Phase 10.3 spec — Multi-language: new API endpoints and refactor of existing ones."
applyTo: "backend/**"
---

# Phase 10.3 — API: new endpoints and refactor of existing ones

## Goal

Expose the multi-language functionality via REST endpoints and wire the existing endpoints to the active language plan. After this phase the full backend API is multi-language aware.

**Prerequisite:** Phase 10.2 must be merged before starting this phase.

---

## 10.3.0 Migration: apply NOT NULL to `study_plan_id`

**File:** `backend/alembic/versions/0031_not_null_study_plan_id.py`  
**Revision ID:** `0031_not_null_study_plan_id`  
**Down revision:** `0030_not_null_study_plan_id`

Now that Phase 10.3 wires `get_active_study_plan` into all callers (`routers/lessons.py`, `routers/flashcards.py`, `routers/listening.py`, `routers/reading.py`), every INSERT into `progress`, `flashcards`, and `user_competencies` always provides a `study_plan_id`. The constraint is therefore safe to enforce.

> **Deploy order for 10.3:** code changes first (all callers updated), then `alembic upgrade head`. Do NOT run the migration before the code.

```python
def upgrade() -> None:
    op.alter_column("progress", "study_plan_id", nullable=False)
    op.alter_column("flashcards", "study_plan_id", nullable=False)
    op.alter_column("user_competencies", "study_plan_id", nullable=False)


def downgrade() -> None:
    op.alter_column("user_competencies", "study_plan_id", nullable=True)
    op.alter_column("flashcards", "study_plan_id", nullable=True)
    op.alter_column("progress", "study_plan_id", nullable=True)
```

---

## 10.3.1 Language validation

**File:** `backend/app/core/config.py`

Add one new setting:

```python
AVAILABLE_TARGET_LANGUAGES: list[str] = ["en-US", "en-GB", "es-ES", "it-IT", "pt-PT"]
```

`pydantic-settings` parses a comma-separated string automatically (e.g. `AVAILABLE_TARGET_LANGUAGES=en-US,es-ES`). On startup the backend silently filters out any value not present in `SUPPORTED_TARGET_LANGUAGES`, so misconfigured entries are ignored without raising an error.

---

**File:** `backend/app/schemas/auth.py`

Expand `SUPPORTED_TARGET_LANGUAGES` (the master set of all languages the system has curriculum data for):

```python
SUPPORTED_TARGET_LANGUAGES: set[str] = {
    "en-US", "en-GB",
    "es-ES",
    "it-IT",
    "pt-PT",
}


def get_available_languages() -> list[str]:
    """Returns the operator-configured subset, filtered to known languages."""
    from app.core.config import settings  # local import to avoid circular

    return [
        lang
        for lang in settings.AVAILABLE_TARGET_LANGUAGES
        if lang in SUPPORTED_TARGET_LANGUAGES
    ]
```

`SUPPORTED_TARGET_LANGUAGES` is a code constant — it only grows when new curriculum data is added. `AVAILABLE_TARGET_LANGUAGES` is an ops concern: it controls what the end-user can choose at runtime.

---

## 10.3.2 New Pydantic schemas

**File:** `backend/app/schemas/language.py` (new)

```python
from pydantic import BaseModel, field_validator

from app.schemas.auth import get_available_languages


class LanguageAddRequest(BaseModel):
    target_language: str

    @field_validator("target_language")
    @classmethod
    def validate_target_language(cls, v: str) -> str:
        available = get_available_languages()
        if v not in available:
            raise ValueError(f"Language not available. Choose from: {available}")
        return v


class LanguageSwitchRequest(BaseModel):
    target_language: str

    @field_validator("target_language")
    @classmethod
    def validate_target_language(cls, v: str) -> str:
        available = get_available_languages()
        if v not in available:
            raise ValueError(f"Language not available. Choose from: {available}")
        return v


class LanguagePlanInfo(BaseModel):
    id: int
    cefr_level: str | None
    progress_day: int
    total_days: int
    completion_pct: float


class LanguageProgressInfo(BaseModel):
    total_xp: int        # SUM(Progress.xp_earned) WHERE study_plan_id = plan.id
    current_streak: int  # latest Progress.streak_day for the plan
    lessons_completed: int  # SUM(Progress.lessons_completed) WHERE study_plan_id = plan.id


class UserLanguageOut(BaseModel):
    target_language: str
    is_active: bool
    plan: LanguagePlanInfo | None
    progress: LanguageProgressInfo | None


class UserLanguageListResponse(BaseModel):
    languages: list[UserLanguageOut]
    all_supported_languages: list[str]
```

### Update `GenerateStudyPlanRequest`

**File:** `backend/app/schemas/study_plan.py`

```python
class GenerateStudyPlanRequest(BaseModel):
    cefr_level: str
    goals: list[str]
    duration_weeks: int
    days_per_week: int
    target_language: str | None = None  # NEW: if not provided, uses the active language
```

---

## 10.3.3 New router: `languages.py`

**File:** `backend/app/routers/languages.py`  
**Prefix:** `/api/languages`  
**Tag:** `languages`  
**Auth:** all endpoints require `require_subscription`.

- GET — Route: `/api/languages`; Description: Lists the languages the user is learning, with summarised progress
- GET — Route: `/api/languages/active`; Description: Returns the user's current active language
- POST — Route: `/api/languages`; Description: Adds a new language (`{ target_language: "it-IT" }`)
- PUT — Route: `/api/languages/active`; Description: Switches the active language (`{ target_language: "it-IT" }`)
- DELETE — Route: `/api/languages/{target_language}`; Description: Removes a language, its `UserLanguage` row, and all its associated `StudyPlan` rows

**`GET /api/languages` response:**

```json
{
  "languages": [
    {
      "target_language": "en-US",
      "is_active": true,
      "plan": {
        "id": 1,
        "cefr_level": "B1",
        "progress_day": 42,
        "total_days": 48,
        "completion_pct": 87.5
      },
      "progress": {
        "total_xp": 12500,
        "current_streak": 23,
        "lessons_completed": 38
      }
    },
    {
      "target_language": "it-IT",
      "is_active": false,
      "plan": null
    }
  ],
  "all_supported_languages": ["en-US", "es-ES"]
}
```

`all_supported_languages` returns `get_available_languages()` — the operator-configured subset, not the hardcoded 5. The frontend uses this list to build the "Add new language" modal and filters out the languages the user is already learning.

**`DELETE /api/languages/{target_language}` implementation note:**

`user_language_service.remove_language` (Phase 10.2) only deletes the `UserLanguage` row. The router must also delete all `StudyPlan` rows for that `(user_id, target_language)` combination **before** deleting the `UserLanguage` row, to avoid orphaned plans:

```python
# Delete all study plans for this language (staged — not yet committed)
await db.execute(
    delete(StudyPlan).where(
        StudyPlan.user_id == current_user.id,
        StudyPlan.target_language == target_language,
    )
)
await db.flush()  # stage within the current transaction; do NOT commit yet
await user_language_service.remove_language(db, current_user.id, target_language)
# remove_language calls db.commit() — this single commit covers both the plan
# deletes and the UserLanguage delete, keeping the operation atomic.
```

The `StudyPlan` CASCADE will handle `progress`, `flashcards`, and `user_competencies` rows automatically.

Register the new router in `backend/app/main.py`.

---

## 10.3.4 Refactor of existing endpoints

### `GET /api/study-plan/current`

- Accept optional query param `?language=it-IT` to retrieve a specific language's plan (used by the frontend to preview before switching).
- **Without `?language`**: inject `plan: StudyPlan = Depends(get_active_study_plan)` and return it directly.
- **With `?language`**: bypass the dependency — query `StudyPlan` directly for `(user_id, target_language, is_active=True)`. Return 404 if not found. Do NOT raise an error if that language is not the active one.

### `POST /api/study-plan/generate`

- Accept `target_language` in the body (from `GenerateStudyPlanRequest`). If not provided, use the active language.
- **Bug fix — `StudyPlan` constructor missing `target_language`:** the current code creates `StudyPlan(user_id=..., cefr_level=..., ...)` without setting `target_language`. Resolve the language and set it explicitly:

  ```python
  resolved_language = data.target_language or active_plan.target_language
  plan = StudyPlan(
      ...
      target_language=resolved_language,
      ...
  )
  # Also pass it to the generator:
  generated = await generate_study_plan(data, target_language=resolved_language)
  ```

- **Multi-language fix:** scope plan deactivation to the specific language (see critical fix below).

### `GET /api/study-plan/today`

- Use `get_active_study_plan` instead of reading `current_user.target_language`.

### `GET /api/flashcards/*` and `POST /api/flashcards/generate`

- Filter by `study_plan_id` of the active plan instead of just `user_id`.
- `POST /api/flashcards/generate`: assign the active plan's `study_plan_id` to generated flashcards.

### `GET /api/progress/*` and `GET /api/progress/competencies`

- Filter by `study_plan_id` of the active plan.

### `GET/POST /api/chat` and `/ws/conversation`

Use the active plan's `study_plan_id` to:

- Determine `target_language` for the system prompt.
- Store `study_plan_id` in `conversations` and `chat_history` rows.
- Load memories globally by `user_id`; pass the active `study_plan_id` only as optional provenance when Lingu saves a new memory.

### `POST /api/lessons/{id}/complete` and `POST /api/lessons/exercises/{id}/answer`

`routers/lessons.py` calls `update_daily_progress` and `upsert_unit_competency` without `study_plan_id`. The `lesson` object already has `lesson.study_plan_id` via the FK — pass it through:

```python
await update_daily_progress(
    db,
    current_user.id,
    lesson_completed=True,
    skill=lesson.lesson_type,
    study_plan_id=lesson.study_plan_id,  # ADD THIS
)

await upsert_unit_competency(
    db,
    current_user.id,
    unit_id=lesson.unit_id,
    competency_texts=u.competency_checklist,
    lesson_score=lesson_score,
    study_plan_id=lesson.study_plan_id,  # ADD THIS
)
```

Apply to both the lesson completion endpoint and the exercise answer endpoint.

### `GET /api/listening/*` and `GET /api/reading/*`

Both routers have an identical private `_get_user_level(user_id, db)` helper that queries the first active plan with `.order_by(created_at.desc()).limit(1)` — this could pick the wrong plan in multi-language. Replace it with `get_active_study_plan` dependency injection in the endpoint functions.

**Implementation pattern** (apply to both `routers/listening.py` and `routers/reading.py`):

1. Remove `_get_user_level`.
2. Add `plan: StudyPlan = Depends(get_active_study_plan)` to each endpoint function.
3. Replace `level, target_language = await _get_user_level(current_user.id, db)` with `level, target_language = plan.cefr_level, plan.target_language`.
4. Pass `study_plan_id=plan.id` to `update_daily_progress` (Phase 10.3 wires this, Phase 10.2 added the parameter).

### `PATCH /api/auth/me`

When updating `target_language`:

- If the user already has that language in `user_languages`, activate it (without creating a new plan).
- If not, add a row to `user_languages` but **do not create a `StudyPlan`** — the user must go through the assessment flow.

### `POST /api/assessment/complete` and `POST /api/study-plan/generate` — critical multi-language fix

Both endpoints currently deactivate **all** active plans for the user before creating a new one. This destroys the English plan when creating a Spanish plan. **Must be scoped to the specific language.**

**`POST /api/assessment/complete`** — read `target_language` from the Redis session (stored there by `start` in this phase), scope the deactivation, and use it in the `StudyPlan` constructor:

```python
session = json.loads(session_raw)
target_language = session.get("target_language", current_user.target_language)

# Scope deactivation to this language only
old_result = await db.execute(
    select(StudyPlan).where(
        StudyPlan.user_id == current_user.id,
        StudyPlan.is_active.is_(True),
        StudyPlan.target_language == target_language,
    )
)
for old in old_result.scalars().all():
    old.is_active = False

generated = await generate_study_plan(plan_request, target_language=target_language)
plan = StudyPlan(
    ...
    target_language=target_language,  # NOT current_user.target_language
    ...
)
```

**`POST /api/study-plan/generate`** — same scoping pattern:

```python
# CURRENT CODE — BREAKS MULTI-LANGUAGE
old_result = await db.execute(
    select(StudyPlan).where(
        StudyPlan.user_id == current_user.id,
        StudyPlan.is_active.is_(True),
    )
)

# CORRECT — scope to target_language
old_result = await db.execute(
    select(StudyPlan).where(
        StudyPlan.user_id == current_user.id,
        StudyPlan.is_active.is_(True),
        StudyPlan.target_language == resolved_language,
    )
)
```

### `GET /api/assessment/start` and `POST /api/assessment/submit`

- `GET /api/assessment/start` must accept `?language=es-ES` query param. **Default: the user's currently active language** (resolved via `get_active_study_plan` or `get_active_language`). Do NOT hardcode `en-US` as default — that would start an English quiz for a Spanish learner.
- LLM prompt: `"Generate an adaptive CEFR quiz with 20 questions for {target_language_name} language proficiency."`.
- **Redis key stays as `assessment:{user_id}`** — do NOT include the language in the key. Instead, store `target_language` inside the session JSON itself:

  ```python
  await redis.setex(
      f"assessment:{current_user.id}",
      _ASSESSMENT_TTL,
      json.dumps({"session_id": session_id, "quiz": quiz, "target_language": target_language}),
  )
  ```

  This way `submit` and `complete` can read `target_language` from the session without any schema or key changes.

- `POST /api/assessment/submit` requires no changes to its signature or logic.

> **Do NOT change the Redis key format** to `assessment:{user_id}:{target_language}`. That would require threading `target_language` through `submit` (which currently has no such field) and break any in-flight sessions on deploy.

### `GET /api/assessment/level-test/questions/{plan_id}`

**No change required in Phase 10.3.** The function `get_curriculum(target_language)` does not exist yet — the language-aware curriculum dispatcher is created in Phase 10.6. Until then, `get_curriculum_units(plan.cefr_level)` is correct and safe because only the English curriculum exists.

---

## Tests

### New tests (`backend/tests/test_multi_language.py`)

- `test_add_new_language` — `POST /api/languages` creates `UserLanguage` row and marks it active
- `test_add_duplicate_language` — `POST` with an already-existing language → 409
- `test_switch_language` — `PUT /api/languages/active` switches the active language correctly
- `test_list_languages` — `GET /api/languages` returns all languages with summarised progress
- `test_remove_language_cascades` — `DELETE /api/languages/{code}` removes plan, lessons, flashcards, progress, etc. in cascade
- `test_cannot_remove_last_language` — `DELETE` when user has only 1 language → 400
- `test_cannot_remove_active_language` — `DELETE` on the currently active language → 400
- `test_onboarding_creates_user_language` — Registration + completing assessment automatically creates `UserLanguage` row
- `test_supported_languages_validation` — `POST /api/languages` with unsupported language → 422
- `test_assessment_language_param` — `GET /api/assessment/start?language=es-ES` generates questions in Spanish
- `test_assessment_redis_key_isolation` — Two simultaneous assessments in different languages do not overwrite each other in Redis
- `test_plan_deactivation_scoped_by_language` — Creating a Spanish plan does not deactivate the active English plan

### Existing test updates

- `backend/tests/test_auth.py` — Add `UserLanguage` creation to user setup
- `backend/tests/test_study_plan.py` — Scope plan deactivation by language
- `backend/tests/test_flashcards.py` — Set `study_plan_id` on created flashcards
- `backend/tests/test_lessons.py` — Set `study_plan_id` on progress/competency rows
- `backend/tests/test_chat.py` — Set `study_plan_id` on conversations/chat_history rows
- `backend/tests/test_conversation.py` — Set `study_plan_id` on conversation rows
- `backend/tests/test_listening.py` — Use `get_active_study_plan` (remove `_get_user_level`)
- `backend/tests/test_reading.py` — Use `get_active_study_plan` (remove `_get_user_level`)
- `backend/tests/test_progress.py` — Set `study_plan_id`; verify language isolation
- `backend/tests/test_memories.py` — Set `study_plan_id`; verify filtering
- `backend/tests/test_assessment.py` — Scope plan deactivation; add `UserLanguage` fixture; test Redis key isolation

## New files in this phase

- `backend/app/schemas/language.py` — New Pydantic schemas
- `backend/app/routers/languages.py` — New router (5 endpoints)
- `backend/alembic/versions/0031_not_null_study_plan_id.py` — Alembic migration (NOT NULL)

## Modified files in this phase

- **`backend/app/core/config.py`** — Add `AVAILABLE_TARGET_LANGUAGES` setting
- **`backend/app/schemas/auth.py`** — Expand `SUPPORTED_TARGET_LANGUAGES`; add `get_available_languages()`
- **`.env.example`** — Add `AVAILABLE_TARGET_LANGUAGES=en-US,en-GB,es-ES,it-IT,pt-PT` (with comment explaining it is the operator-visible subset)
- **`docker-compose.yml`** — Add `AVAILABLE_TARGET_LANGUAGES: ${AVAILABLE_TARGET_LANGUAGES:-en-US,en-GB,es-ES,it-IT,pt-PT}` to the `backend` service environment
- **`backend/app/schemas/study_plan.py`** — Add `target_language` to `GenerateStudyPlanRequest`
- **`backend/app/routers/study_plan.py`** — Use `get_active_study_plan`, scope deactivation, `target_language` param
- **`backend/app/routers/lessons.py`** — Pass `study_plan_id=lesson.study_plan_id` to `update_daily_progress` and `upsert_unit_competency`
- **`backend/app/routers/flashcards.py`** — Filter by `study_plan_id`
- **`backend/app/routers/progress.py`** — Filter by `study_plan_id`
- **`backend/app/routers/chat.py`** — Use active plan, store `study_plan_id`
- **`backend/app/routers/conversation.py`** — Use active plan, store `study_plan_id`
- **`backend/app/routers/listening.py`** — Use `get_active_study_plan`
- **`backend/app/routers/reading.py`** — Use `get_active_study_plan`
- **`backend/app/routers/auth.py`** — Update `PATCH /me` for `user_languages`
- **`backend/app/routers/assessment.py`** — `?language` param on `/start`, `target_language` stored in Redis session, scoped deactivation in `/complete`, `target_language` passed to `StudyPlan` constructor
- **`backend/app/main.py`** — Register `languages` router
