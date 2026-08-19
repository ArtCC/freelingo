from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.app_logger import get_logger
from app.core.database import get_db
from app.core.deps import get_active_study_plan, get_current_user
from app.core.limiter import limiter
from app.models.lesson import Exercise, Lesson
from app.models.study_plan import StudyPlan
from app.models.user import User
from app.models.user_language import UserLanguage
from app.schemas.study_plan import (
    GenerateStudyPlanRequest,
    PendingLessonResponse,
    PlanLessonResponse,
    StudyPlanResponse,
    TodayLesson,
    TodayResponse,
)
from app.services.lesson_generator import generate_lesson
from app.services.study_plan_generator import generate_study_plan
from app.services.user_language_service import ensure_user_language, get_active_language

logger = get_logger(__name__)

router = APIRouter(prefix="/api/study-plan", tags=["study-plan"])


@router.get("/current", response_model=Optional[StudyPlanResponse])
@limiter.limit("60/minute")
async def get_current_plan(
    request: Request,
    language: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if language:
        ul_result = await db.execute(
            select(UserLanguage).where(
                UserLanguage.user_id == current_user.id,
                UserLanguage.target_language == language,
            )
        )
        ul = ul_result.scalar_one_or_none()
        if ul is None:
            return None
        result = await db.execute(
            select(StudyPlan)
            .where(
                StudyPlan.user_language_id == ul.id,
                StudyPlan.is_active.is_(True),
            )
            .order_by(StudyPlan.created_at.desc())
            .limit(1)
        )
        plan = result.scalar_one_or_none()
    else:
        try:
            plan = await get_active_study_plan(current_user, db)
        except HTTPException:
            return None
    if not plan:
        return None
    return plan


@router.post("/generate", response_model=StudyPlanResponse)
@limiter.limit("10/minute")
async def create_study_plan(
    request: Request,
    data: GenerateStudyPlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resolved_language = data.target_language
    if not resolved_language:
        # Fall back to active language
        active_lang = await get_active_language(db, current_user.id)
        resolved_language = (
            active_lang.target_language if active_lang else current_user.target_language
        )

    # Ensure a UserLanguage row exists for this language (creates one inactive if missing)
    user_lang = await ensure_user_language(db, current_user.id, resolved_language)

    # Deactivate old plans — scoped to this language only
    old_plans = await db.execute(
        select(StudyPlan).where(
            StudyPlan.user_language_id == user_lang.id,
            StudyPlan.is_active.is_(True),
        )
    )
    for old in old_plans.scalars().all():
        old.is_active = False

    generated = await generate_study_plan(data, target_language=resolved_language)

    from app.data.curriculum import get_curriculum_units  # noqa: PLC0415

    units = get_curriculum_units(data.cefr_level, resolved_language)
    first_unit_id = units[0].id if units else ""

    plan_dict = generated.model_dump() if hasattr(generated, "model_dump") else generated
    plan = StudyPlan(
        user_id=current_user.id,
        user_language_id=user_lang.id,
        cefr_level=data.cefr_level,
        target_language=resolved_language,
        goals=data.goals,
        duration_weeks=data.duration_weeks,
        days_per_week=data.days_per_week,
        current_unit=first_unit_id,
        generated_plan=plan_dict,
        is_active=True,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


@router.get("/today", response_model=TodayResponse)
@limiter.limit("20/minute")
async def get_today_lessons(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    active_lang = await get_active_language(db, current_user.id)
    if not active_lang:
        raise HTTPException(status_code=404, detail="No active language set")
    plan_result = await db.execute(
        select(StudyPlan).where(
            StudyPlan.user_language_id == active_lang.id,
            StudyPlan.is_active.is_(True),
        )
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="No active study plan found")
    total_days = plan.duration_weeks * plan.days_per_week

    # Load all existing lessons for this plan at once
    all_lessons_result = await db.execute(select(Lesson).where(Lesson.study_plan_id == plan.id))
    all_lessons = all_lessons_result.scalars().all()

    # Index by (week_number, day_number) for fast lookups
    lessons_by_wday: dict[tuple[int, int], list] = defaultdict(list)
    for lsn in all_lessons:
        lessons_by_wday[(lsn.week_number, lsn.day_number)].append(lsn)

    # Auto-advance: move past days where every lesson is already complete
    original_progress = plan.progress_day
    while plan.progress_day < total_days:
        _w = (plan.progress_day // plan.days_per_week) + 1
        _d = (plan.progress_day % plan.days_per_week) + 1
        day_ls = lessons_by_wday.get((_w, _d), [])
        if day_ls and all(lsn.is_completed for lsn in day_ls):
            plan.progress_day += 1
        else:
            break

    if plan.progress_day != original_progress:
        await db.commit()

    # Count incomplete lessons from days the plan has already passed
    pending_count = sum(
        1
        for lsn in all_lessons
        if not lsn.is_completed
        and (lsn.week_number - 1) * plan.days_per_week + (lsn.day_number - 1) < plan.progress_day
    )

    if plan.progress_day >= total_days:
        return TodayResponse(
            plan_id=plan.id,
            cefr_level=plan.cefr_level,
            lessons=[],
            progress_day=plan.progress_day,
            total_days=total_days,
            pending_count=pending_count,
        )

    current_week = (plan.progress_day // plan.days_per_week) + 1
    current_day = (plan.progress_day % plan.days_per_week) + 1

    weekly_plan = (
        plan.generated_plan.get("weekly_plan")
        if isinstance(plan.generated_plan, dict)
        else getattr(plan.generated_plan, "weekly_plan", None)
    )
    if not weekly_plan:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Study plan data is malformed",
        )

    week = None
    for w in weekly_plan:
        w_week = w["week"] if isinstance(w, dict) else w.week
        if w_week == current_week:
            week = w
            break

    if not week:
        return TodayResponse(
            plan_id=plan.id,
            cefr_level=plan.cefr_level,
            lessons=[],
            progress_day=plan.progress_day,
            total_days=total_days,
            pending_count=pending_count,
        )

    days = week["days"] if isinstance(week, dict) else week.days

    # Build title→(id, is_completed) lookup from already-loaded lessons
    lesson_by_title: dict[str, tuple[int, bool]] = {
        row.title: (row.id, row.is_completed)
        for row in lessons_by_wday.get((current_week, current_day), [])
    }

    # Sibling lessons already generated for each unit, ordered as the student worked through them.
    # Passed to the generator so a new lesson does not repeat what the unit already covered.
    lessons_by_unit: dict[str, list] = defaultdict(list)
    for lsn in sorted(all_lessons, key=lambda item: (item.week_number, item.day_number, item.id)):
        if lsn.unit_id:
            lessons_by_unit[lsn.unit_id].append(lsn)

    today_lessons = []
    for d in days:
        d_day = d["day"] if isinstance(d, dict) else d.day
        if d_day != current_day:
            continue
        d_title = d["title"] if isinstance(d, dict) else d.title
        d_type = d["lesson_type"] if isinstance(d, dict) else d.lesson_type
        d_obj = d["objectives"] if isinstance(d, dict) else d.objectives
        d_min = d["estimated_minutes"] if isinstance(d, dict) else d.estimated_minutes
        d_unit_id = d.get("unit_id", "") if isinstance(d, dict) else getattr(d, "unit_id", "")

        _existing = lesson_by_title.get(d_title)
        lesson_id: int | None = _existing[0] if _existing else None
        lesson_completed: bool = _existing[1] if _existing else False

        # Resolve curriculum context for lesson generation
        grammar_points: list[str] = []
        vocabulary_set_ids: list[str] = []
        if d_unit_id:
            from app.data.curriculum import get_curriculum_units  # noqa: PLC0415

            for cu in get_curriculum_units(plan.cefr_level, plan.target_language):
                if cu.id == d_unit_id:
                    grammar_points = cu.grammar_points
                    vocabulary_set_ids = cu.vocabulary_set_ids
                    break

        # Auto-generate the lesson if it doesn't exist yet
        plan_id = plan.id  # cache before any rollback that would expire the ORM object
        if lesson_id is None:
            previous_lessons = [
                {
                    "title": sibling.title,
                    "lesson_type": sibling.lesson_type,
                    "content": sibling.content,
                }
                for sibling in lessons_by_unit.get(d_unit_id, [])
                if sibling.title != d_title
            ]
            try:
                content = await generate_lesson(
                    cefr_level=plan.cefr_level,
                    lesson_type=d_type,
                    topic=d_title,
                    week=current_week,
                    day=current_day,
                    unit_id=d_unit_id,
                    grammar_points=grammar_points,
                    vocabulary_set_ids=vocabulary_set_ids,
                    target_language=plan.target_language,
                    native_language=current_user.native_language,
                    previous_lessons=previous_lessons,
                )
                content_dict = content.model_dump() if hasattr(content, "model_dump") else content

                lesson = Lesson(
                    study_plan_id=plan.id,
                    title=d_title,
                    lesson_type=d_type,
                    cefr_level=plan.cefr_level,
                    week_number=current_week,
                    day_number=current_day,
                    unit_id=d_unit_id,
                    content=content_dict,
                )
                db.add(lesson)
                await db.flush()

                exercises_data = content_dict.get("exercises") or []
                for ex in exercises_data:
                    exercise = Exercise(
                        lesson_id=lesson.id,
                        exercise_type=ex.get("type", "multiple_choice"),
                        question=ex.get("question", ""),
                        options=ex.get("options"),
                        correct_answer=ex.get("correct", ""),
                        explanation=ex.get("explanation"),
                    )
                    db.add(exercise)

                if not exercises_data:
                    await db.rollback()
                    raise ValueError("Lesson generated with no exercises")

                await db.commit()
                await db.refresh(lesson)
                lesson_id = lesson.id
                if d_unit_id:
                    lessons_by_unit[d_unit_id].append(lesson)
            except IntegrityError:
                await db.rollback()
                dup = await db.execute(
                    select(Lesson).where(
                        Lesson.study_plan_id == plan_id,
                        Lesson.week_number == current_week,
                        Lesson.day_number == current_day,
                        Lesson.title == d_title,
                    )
                )
                existing = dup.scalar_one_or_none()
                if existing:
                    lesson_id = existing.id
                    lesson_completed = existing.is_completed
            except Exception:
                logger.exception("Failed to generate or persist lesson for plan %s", plan_id)

        if lesson_id is not None:
            today_lessons.append(
                TodayLesson(
                    id=lesson_id,
                    title=d_title,
                    lesson_type=d_type,
                    week=current_week,
                    day=current_day,
                    objectives=d_obj,
                    estimated_minutes=d_min,
                    unit_id=d_unit_id,
                    is_completed=lesson_completed,
                )
            )

    return TodayResponse(
        plan_id=plan.id,
        cefr_level=plan.cefr_level,
        lessons=today_lessons,
        progress_day=plan.progress_day,
        total_days=total_days,
        pending_count=pending_count,
    )


@router.post("/skip-day")
@limiter.limit("60/minute")
async def skip_today(
    request: Request,
    plan: StudyPlan = Depends(get_active_study_plan),
    db: AsyncSession = Depends(get_db),
):
    total_days = plan.duration_weeks * plan.days_per_week
    plan.progress_day = min(plan.progress_day + 1, total_days)
    await db.commit()
    return {"progress_day": plan.progress_day, "total_days": total_days}


@router.get("/pending-lessons", response_model=list[PendingLessonResponse])
@limiter.limit("60/minute")
async def get_pending_lessons(
    request: Request,
    plan: StudyPlan = Depends(get_active_study_plan),
    db: AsyncSession = Depends(get_db),
):
    incomplete_result = await db.execute(
        select(Lesson).where(
            Lesson.study_plan_id == plan.id,
            Lesson.is_completed.is_(False),
        )
    )
    pending = [
        lsn
        for lsn in incomplete_result.scalars().all()
        if (lsn.week_number - 1) * plan.days_per_week + (lsn.day_number - 1) < plan.progress_day
    ]
    return pending


@router.get("/lessons", response_model=list[PlanLessonResponse])
@limiter.limit("60/minute")
async def get_plan_lessons(
    request: Request,
    plan: StudyPlan = Depends(get_active_study_plan),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Lesson)
        .where(Lesson.study_plan_id == plan.id)
        .order_by(Lesson.week_number, Lesson.day_number, Lesson.id)
    )
    return result.scalars().all()
