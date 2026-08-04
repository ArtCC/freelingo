from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competency import UserCompetency
from app.models.progress import Progress

XP_LESSON_COMPLETE = 20
XP_EXERCISE_CORRECT = 5
XP_EXERCISE_WRONG = 1
XP_FLASHCARD_REVIEW = 2


async def update_daily_progress(
    db: AsyncSession,
    user_id: int,
    *,
    study_plan_id: int | None = None,
    lesson_completed: bool = False,
    exercise_correct: bool | None = None,
    flashcard_reviewed: bool = False,
    xp: int = 0,
    skill: str | None = None,
    skill_score: float | None = None,
    commit: bool = True,
) -> Progress:
    today = date.today()

    base_filter = [Progress.user_id == user_id]
    if study_plan_id is not None:
        base_filter.append(Progress.study_plan_id == study_plan_id)

    result = await db.execute(select(Progress).where(*base_filter, Progress.date == today))
    entry = result.scalar_one_or_none()

    if not entry:
        yesterday = today - timedelta(days=1)
        yest_result = await db.execute(
            select(Progress).where(*base_filter, Progress.date == yesterday)
        )
        yest = yest_result.scalar_one_or_none()
        streak = (yest.streak_day + 1) if yest else 1

        entry = Progress(
            user_id=user_id,
            date=today,
            xp_earned=0,
            lessons_completed=0,
            exercises_correct=0,
            exercises_total=0,
            streak_day=streak,
            skills={},
            study_plan_id=study_plan_id,
        )
        db.add(entry)
        await db.flush()

    if lesson_completed:
        entry.lessons_completed += 1
        entry.xp_earned += XP_LESSON_COMPLETE

    if exercise_correct is not None:
        entry.exercises_total += 1
        if exercise_correct:
            entry.exercises_correct += 1
            entry.xp_earned += XP_EXERCISE_CORRECT
        else:
            entry.xp_earned += XP_EXERCISE_WRONG

    if flashcard_reviewed:
        entry.xp_earned += XP_FLASHCARD_REVIEW

    if xp > 0:
        entry.xp_earned += xp

    if skill and skill_score is not None:
        skills = dict(entry.skills or {})
        old = skills.get(skill, skill_score)
        skills[skill] = round(old * 0.7 + skill_score * 0.3, 3)
        entry.skills = skills

    if commit:
        await db.commit()
        await db.refresh(entry)
    else:
        await db.flush()
    return entry


async def upsert_unit_competency(
    db: AsyncSession,
    user_id: int,
    unit_id: str,
    competency_texts: list[str],
    lesson_score: float,
    *,
    study_plan_id: int | None = None,
) -> None:
    """
    Update (or create) UserCompetency rows for all competencies in a unit.

    Uses an exponential moving average:  new = 0.7 * old + 0.3 * lesson_score
    Marks a competency as mastered when score >= 0.80.
    """
    if not unit_id or not competency_texts:
        return

    now = datetime.now(UTC).replace(tzinfo=None)

    for text in competency_texts:
        result = await db.execute(
            select(UserCompetency).where(
                UserCompetency.user_id == user_id,
                UserCompetency.unit_id == unit_id,
                UserCompetency.competency_text == text,
                UserCompetency.study_plan_id == study_plan_id,
            )
        )
        row: UserCompetency | None = result.scalar_one_or_none()

        if row is None:
            row = UserCompetency(
                user_id=user_id,
                unit_id=unit_id,
                competency_text=text,
                score=lesson_score,
                mastered=lesson_score >= 0.80,
                updated_at=now,
                study_plan_id=study_plan_id,
            )
            db.add(row)
        else:
            row.score = round(row.score * 0.7 + lesson_score * 0.3, 3)
            row.mastered = row.score >= 0.80
            row.updated_at = now

    await db.flush()


async def get_unit_competencies(
    db: AsyncSession,
    user_id: int,
    study_plan_id: int | None = None,
) -> list[dict]:
    """Return aggregated competency scores per unit for the given user."""
    conditions = [UserCompetency.user_id == user_id]
    if study_plan_id is not None:
        conditions.append(UserCompetency.study_plan_id == study_plan_id)
    result = await db.execute(select(UserCompetency).where(*conditions))
    rows = result.scalars().all()

    # Aggregate per unit: average score across all competency rows
    unit_scores: dict[str, list[float]] = {}
    for row in rows:
        unit_scores.setdefault(row.unit_id, []).append(row.score)

    return [
        {
            "unit_id": uid,
            "score": round(sum(scores) / len(scores), 3),
            "mastered_count": sum(1 for r in rows if r.unit_id == uid and r.mastered),
            "total_count": len(scores),
        }
        for uid, scores in unit_scores.items()
    ]
