---
description: "Phase 10.1 spec — Multi-language: database migrations and new models."
applyTo: "backend/**"
---

# Phase 10.1 — Database: migrations and new models

## Goal

Lay the database foundation for multi-language support without breaking the running application or existing users. All existing users are on English (en-US or en-GB) — this migration seeds their data into the new structures automatically.

**This phase contains zero application logic changes.** No service, router, or frontend file is touched. The app continues to work exactly as before once the migration runs.

---

## 10.1.1 New table: `user_languages`

Relates users to the languages they are learning. Each row represents "user X is learning language Y".

- id — Type: integer; Notes: PK, autoincrement
- user_id — Type: integer; Notes: FK → users (CASCADE), NOT NULL
- target_language — Type: string(10); Notes: BCP-47, NOT NULL
- is_active — Type: boolean; Notes: `true` = current active language. Only one `true` per user. Default `true`.
- created_at — Type: datetime; Notes: Auto-set

**Constraints:**

- `UNIQUE(user_id, target_language)` — a user cannot have the same language duplicated.
- Composite index on `(user_id, is_active)` for fast active language lookups.
- When inserting a new `user_language` with `is_active=true`, any other active language for that user must be deactivated (`is_active=false`) — logic in the service (Phase 10.2).

---

## 10.1.2 Changes to existing models

### Table `study_plans`

**Already has** `target_language` (added in Phase 4). No structural changes.

**New constraint:** partial `UNIQUE(user_id, target_language)` where `is_active = true` — only one active plan per user per language:

```sql
CREATE UNIQUE INDEX uq_active_plan_per_lang
ON study_plans (user_id, target_language)
WHERE is_active = true;
```

This replaces "one active plan per user" with "one active plan per user per language".

### Table `progress`

- Add `study_plan_id` — integer, FK → study_plans (CASCADE), **nullable**, with index
- Backfill — Assign `study_plan_id` from each user's active plan (`is_active=true`)
- Fallback — Create a minimal study plan for orphan rows (user has progress but no active plan), then re-backfill
- NOT NULL — **Applied in Phase 10.3** (`0031_not_null_study_plan_id.py`) once services reliably populate this column

### Table `flashcards`

- Add `study_plan_id` — integer, FK → study_plans (CASCADE), **nullable**, with index
- Backfill — Assign `study_plan_id` from each user's active plan
- Fallback — Create a minimal study plan for orphan rows, then re-backfill
- NOT NULL — **Applied in Phase 10.3** (`0031_not_null_study_plan_id.py`) once services reliably populate this column

### Table `user_competencies`

- Add `study_plan_id` — integer, FK → study_plans (CASCADE), **nullable**, with index
- Backfill — Assign `study_plan_id` from each user's active plan
- Fallback — Create a minimal study plan for orphan rows, then re-backfill
- NOT NULL — **Applied in Phase 10.3** (`0031_not_null_study_plan_id.py`) once services reliably populate this column

### Table `conversations`

- Add `study_plan_id` — integer, FK → study_plans (SET NULL), nullable permanently
- No backfill — Existing conversations remain with `study_plan_id=NULL`

### Table `chat_history`

- Add `study_plan_id` — integer, FK → study_plans (SET NULL), nullable permanently
- No backfill — Existing rows remain with `study_plan_id=NULL`

### Table `memories`

- Add `study_plan_id` — integer, FK → study_plans (SET NULL), nullable permanently
- No backfill — Existing memories remain without an assigned plan
- Current semantics: provenance only. Memory ownership and retrieval remain global by `user_id`, and deleting the plan preserves the memory with `study_plan_id=NULL`.

### Table `llm_usage`

- Add `study_plan_id` — integer, FK → study_plans (SET NULL), nullable permanently
- No backfill — Existing usage records remain without an assigned plan

---

## 10.1.3 `target_language` column in `User`

The `target_language` column in `users` is **kept** as the preferred/default language. Its purpose changes:

- During registration/onboarding: set to the first language chosen.
- When switching the active language: automatically updated to the new active plan's language (Phase 10.2).
- It is NOT the source of truth for the active language — `user_languages.is_active=true` is. It exists for backward compatibility and as a fallback.

---

## 10.1.4 SQLAlchemy model: `UserLanguage`

**File:** `backend/app/models/user_language.py`

The model must declare the `UNIQUE(user_id, target_language)` constraint and the composite index via `__table_args__` so that SQLAlchemy knows about them (required for autogenerate and ORM-level enforcement):

```python
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserLanguage(Base):
    __tablename__ = "user_languages"

    __table_args__ = (
        UniqueConstraint("user_id", "target_language", name="uq_user_language"),
        Index("ix_user_language_user_active", "user_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_language: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
```

---

## 10.1.5 Changes to existing SQLAlchemy models

### `StudyPlan` — add `__table_args__` with the partial unique index

**File:** `backend/app/models/study_plan.py`

The partial unique index `uq_active_plan_per_lang` must be declared in the model via `__table_args__`. This is the only way to make Alembic autogenerate detect and emit a PostgreSQL partial index automatically — if it is not in the model, autogenerate ignores it and the constraint never gets created.

```python
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StudyPlan(Base):
    __tablename__ = "study_plans"

    __table_args__ = (
        Index(
            "uq_active_plan_per_lang",
            "user_id",
            "target_language",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    # ... existing columns unchanged ...
```

### Remaining models — add `study_plan_id` column

**Tables with CASCADE** (`progress`, `flashcards`, `user_competencies`) — declared as **NOT NULL** with `ondelete="CASCADE"`. The database migration makes them nullable initially, then enforces NOT NULL in 0031. By the time the app code runs (after all migrations), the column is NOT NULL in both the ORM and the database:

```python
# Progress, Flashcard, UserCompetency — add:
study_plan_id: Mapped[int] = mapped_column(
    Integer, ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False, index=True
)
```

**Tables with SET NULL** (`conversations`, `chat_history`, `memories`, `llm_usage`) — nullable permanently:

```python
# Conversation, ChatHistory, Memory, LLMUsage — add:
study_plan_id: Mapped[int | None] = mapped_column(
    Integer, ForeignKey("study_plans.id", ondelete="SET NULL"), nullable=True, index=True
)
```

---

## 10.1.6 Register the new model in Alembic and the models package

These two changes **must be made before generating the migration**, so that Alembic's autogenerate detects all tables and columns automatically.

### `backend/app/models/__init__.py`

Replace the entire file with the complete, correct list of all models. The current file was missing `ReadingExercise` — this pre-existing omission meant Alembic never detected changes to the `reading` table. Fix it now alongside adding `UserLanguage`:

```python
from app.models.chat_history import ChatHistory
from app.models.competency import UserCompetency
from app.models.conversation import Conversation
from app.models.feedback import FeedbackComment, FeedbackEntry, FeedbackVote
from app.models.flashcard import Flashcard
from app.models.lesson import Exercise, Lesson
from app.models.listening import ListeningAttempt, ListeningExercise
from app.models.llm_usage import LLMUsage
from app.models.memory import Memory
from app.models.progress import Progress
from app.models.reading import ReadingExercise  # was missing — add
from app.models.study_plan import StudyPlan
from app.models.user import User
from app.models.user_language import UserLanguage  # new in Phase 10.1

__all__ = [
    "ChatHistory",
    "UserCompetency",
    "Conversation",
    "FeedbackComment",
    "FeedbackEntry",
    "FeedbackVote",
    "Flashcard",
    "Exercise",
    "Lesson",
    "ListeningAttempt",
    "ListeningExercise",
    "LLMUsage",
    "Memory",
    "Progress",
    "ReadingExercise",
    "StudyPlan",
    "User",
    "UserLanguage",
]
```

> **Note:** verify the exact class names exported from `reading.py` before applying — adjust if the file exports additional classes (e.g. `ReadingAttempt`).

### `backend/alembic/env.py`

Replace all individual model imports with a single import of the models package. The `__init__.py` already exports every model, so one import is sufficient — `env.py` never needs to be touched again when new models are added:

```python
# REMOVE all individual imports:
# import app.models.chat_history  # noqa: F401
# import app.models.flashcard     # noqa: F401
# import app.models.lesson        # noqa: F401
# import app.models.progress      # noqa: F401
# import app.models.study_plan    # noqa: F401
# import app.models.user          # noqa: F401

# REPLACE WITH a single line:
import app.models  # noqa: F401  — registers all models in Base.metadata via __init__.py
```

**Why this matters:** the current `env.py` only imports 6 of the 14 existing models. Running `--autogenerate` with the old imports would silently skip the `study_plan_id` column additions to `conversations`, `user_competencies`, `memories`, and `llm_usage` — those tables would remain unmigrated with no error or warning.

### Generate the migration

Once both files are updated:

```bash
docker compose exec backend alembic revision --autogenerate -m "multi_language"
```

Rename the generated file to `0029_multi_language.py`. Then add the manual data steps described in 10.1.7 — autogenerate produces the DDL but cannot produce data operations (backfills, purges).

---

## 10.1.7 Alembic migration

**File:** `backend/alembic/versions/0029_multi_language.py`  
**Revision ID:** `0029_multi_language`  
**Down revision:** `0028_trial_used`

Autogenerate will produce the DDL (create table, add columns, create indexes including the partial one). The following data operations must be **added manually** inside `upgrade()` after the autogenerated DDL, in this exact order:

### Step 1 — Backfill `user_languages` from existing `users`

Every existing user already has `target_language` in the `users` table. This seeds one active row per user immediately so the app works for everyone right after the migration runs. **Without this step every existing user has no active language and the entire app breaks.**

```python
op.execute(
    """
    INSERT INTO user_languages (user_id, target_language, is_active, created_at)
    SELECT id, target_language, true, NOW()
    FROM users
    """
)
```

### Step 2 — Backfill `study_plan_id` for the 3 non-nullable tables

```python
op.execute(
    """
    UPDATE progress p
    SET study_plan_id = (
        SELECT id FROM study_plans sp
        WHERE sp.user_id = p.user_id AND sp.is_active = true
        LIMIT 1
    )
    """
)
op.execute(
    """
    UPDATE flashcards f
    SET study_plan_id = (
        SELECT id FROM study_plans sp
        WHERE sp.user_id = f.user_id AND sp.is_active = true
        LIMIT 1
    )
    """
)
op.execute(
    """
    UPDATE user_competencies uc
    SET study_plan_id = (
        SELECT id FROM study_plans sp
        WHERE sp.user_id = uc.user_id AND sp.is_active = true
        LIMIT 1
    )
    """
)
```

### Step 3 — Create fallback study plans for orphan rows

Rows where the user has progress/flashcards/competencies but no active study plan (e.g. the user never completed onboarding, or their plan was manually deleted). Instead of deleting this data, a minimal fallback study plan is created so the data is preserved. A re-backfill then populates `study_plan_id` from the newly created plans.

> **Implementation note:** This is a data-preserving alternative to purging orphans. The fallback plan is created with sensible defaults: `cefr_level='A1'`, `duration_weeks=12`, `days_per_week=4`, `target_language` from the user's `users.target_language` (current default `en-GB`), `completion_test_taken=false`. The `NOT EXISTS` guard prevents duplicate fallback plans when multiple orphan tables belong to the same user.

```python
# Create fallback plans for each orphan table (with dedup via NOT EXISTS)
op.execute("""
    INSERT INTO study_plans (user_id, cefr_level, target_language, goals,
        duration_weeks, days_per_week, current_unit, progress_day,
        generated_plan, is_active, completion_test_taken, created_at)
    SELECT DISTINCT ON (p.user_id)
        p.user_id, 'A1', COALESCE(u.target_language, 'en-US'), '[]'::json,
        12, 4, '', 0, '{}'::json, true, false, NOW()
    FROM progress p
    JOIN users u ON u.id = p.user_id
    WHERE p.study_plan_id IS NULL
      AND NOT EXISTS (
        SELECT 1 FROM study_plans sp
        WHERE sp.user_id = p.user_id AND sp.is_active = true
      )
    """)
# (repeat for flashcards and user_competencies)

# Re-run backfill now that fallback plans exist for previously-orphaned rows
op.execute("""
    UPDATE progress p
    SET study_plan_id = (
        SELECT id FROM study_plans sp
        WHERE sp.user_id = p.user_id AND sp.is_active = true
        LIMIT 1
    )
    WHERE p.study_plan_id IS NULL
    """)
# (repeat for flashcards and user_competencies)
```

> **Note — NOT NULL deferred to Phase 10.3:** The columns are left nullable after the backfill+fallback. The NOT NULL constraint is added in Phase 10.3's migration (`0031_not_null_study_plan_id.py`), once the services that INSERT into these tables have been updated to always populate `study_plan_id`. Applying NOT NULL here would cause every new INSERT by the still-unmodified services to fail until 10.3 is deployed. Migration `0030_not_null_study_plan_id.py` is a placeholder (no-op) that reserves the revision number between 0029 and 0031.

### `downgrade()`

Must reverse in exact inverse order:

```python
def downgrade() -> None:
    # 1. Drop partial unique index on study_plans
    op.drop_index("uq_active_plan_per_lang", table_name="study_plans")

    # 2. Drop study_plan_id columns from all 7 tables
    #    (columns are nullable — no NOT NULL reversal needed here; that is in 0030)
    op.drop_column("progress", "study_plan_id")
    op.drop_column("flashcards", "study_plan_id")
    op.drop_column("conversations", "study_plan_id")
    op.drop_column("chat_history", "study_plan_id")
    op.drop_column("user_competencies", "study_plan_id")
    op.drop_column("memories", "study_plan_id")
    op.drop_column("llm_usage", "study_plan_id")

    # 3. Drop user_languages table (CASCADE handles the unique constraint and indexes)
    op.drop_table("user_languages")
```

---

## 10.1.8 Fix affected tests before merging

The partial unique index `uq_active_plan_per_lang` (`UNIQUE(user_id, target_language) WHERE is_active = true`) enforces a constraint that did not exist before. Several existing tests violate it by creating multiple active plans for the same user and language:

**Affected test files:**

- `backend/tests/test_assessment.py` — `POST /api/assessment/complete` creates a new active plan; if a fixture already created one for the same language, the insert fails with a unique constraint violation.
- `backend/tests/test_study_plan.py` — `POST /api/study-plan/generate` has the same pattern.
- `backend/tests/conftest.py` — shared fixtures that create study plans may need to deactivate the previous plan before creating a new one.

**Fix:** before creating a new active plan in any test or fixture, deactivate any existing active plan for that user+language first, or use a unique language per test. This mirrors the logic that `POST /api/assessment/complete` must implement in Phase 10.3.

---

## Tests

### New tests (`backend/tests/test_multi_language.py`)

- `test_active_plan_per_language` — Two simultaneously active languages with fully independent plans
- `test_progress_isolated_by_language` — XP and streak are independent per language
- `test_flashcards_isolated_by_language` — Flashcards filtered by `study_plan_id` — no cross-language leakage
- `test_conversations_isolated_by_language` — Conversations filtered by active language
- `test_memories_shared_across_languages` — Memories from different plan provenances are retrieved together by `user_id`
- `test_unique_index_prevents_duplicate_active_plans` — Partial unique index enforces one active plan per user+language

### Existing test updates

- `backend/tests/conftest.py` — Add shared `user_language` fixture; scope `StudyPlan` fixtures to avoid duplicate active plans per language
- `backend/tests/test_study_plan.py` — Create `UserLanguage` rows; scope plan deactivation

## New files in this phase

- `backend/app/models/user_language.py` — New SQLAlchemy model
- `backend/alembic/versions/0029_multi_language.py` — Alembic migration

## Modified files in this phase

- `backend/app/models/study_plan.py` — Add `__table_args__` with partial unique index
- `backend/app/models/progress.py` — Add `study_plan_id` column
- `backend/app/models/flashcard.py` — Add `study_plan_id` column
- `backend/app/models/conversation.py` — Add `study_plan_id` column
- `backend/app/models/chat_history.py` — Add `study_plan_id` column
- `backend/app/models/competency.py` — Add `study_plan_id` column
- `backend/app/models/memory.py` — Add `study_plan_id` column
- `backend/app/models/llm_usage.py` — Add `study_plan_id` column
- `backend/app/models/__init__.py` — Add `UserLanguage`, fix missing `ReadingExercise`
- `backend/alembic/env.py` — Replace individual imports with `import app.models`
- `backend/tests/conftest.py` — Deactivate existing active plan before creating a new one (see 10.1.8)
- `backend/tests/test_assessment.py` — Deactivate existing active plan before creating a new one (see 10.1.8)
- `backend/tests/test_study_plan.py` — Deactivate existing active plan before creating a new one (see 10.1.8)
