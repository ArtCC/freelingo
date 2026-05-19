from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.app_logger import get_logger
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.lesson import Exercise, Lesson
from app.models.study_plan import StudyPlan
from app.models.user import User
from app.schemas.study_plan import (
    GeneratedPlan,
    GenerateStudyPlanRequest,
    StudyPlanResponse,
    TodayLesson,
    TodayResponse,
)
from app.services.lesson_generator import generate_lesson
from app.services.llm_adapter import LLMError, LLMTimeoutError, LLMUnavailableError  # noqa: F401
from app.services.study_plan_generator import generate_study_plan

logger = get_logger(__name__)

router = APIRouter(prefix="/api/study-plan", tags=["study-plan"])


@router.get("/current", response_model=Optional[StudyPlanResponse])
async def get_current_plan(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StudyPlan)
        .where(StudyPlan.user_id == current_user.id, StudyPlan.is_active.is_(True))
        .order_by(StudyPlan.created_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        return None
    return plan


@router.post("/generate", response_model=StudyPlanResponse)
async def create_study_plan(
    data: GenerateStudyPlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Deactivate old plans
    old_plans = await db.execute(
        select(StudyPlan).where(
            StudyPlan.user_id == current_user.id, StudyPlan.is_active.is_(True)
        )
    )
    for old in old_plans.scalars().all():
        old.is_active = False

    generated = await generate_study_plan(data)

    from app.data.curriculum import get_curriculum_units  # noqa: PLC0415
    units = get_curriculum_units(data.cefr_level)
    first_unit_id = units[0].id if units else ""

    plan_dict = generated.model_dump() if hasattr(generated, "model_dump") else generated
    plan = StudyPlan(
        user_id=current_user.id,
        cefr_level=data.cefr_level,
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
async def get_today_lessons(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StudyPlan)
        .where(StudyPlan.user_id == current_user.id, StudyPlan.is_active.is_(True))
        .order_by(StudyPlan.created_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="No active study plan found")

    from datetime import date

    start_date = plan.created_at.date() if hasattr(plan.created_at, "date") else plan.created_at
    days_elapsed = (date.today() - start_date).days
    current_week = min((days_elapsed // plan.days_per_week) + 1, plan.duration_weeks)
    current_day = (days_elapsed % plan.days_per_week) + 1

    weekly_plan = (
        plan.generated_plan.get("weekly_plan")
        if isinstance(plan.generated_plan, dict)
        else getattr(plan.generated_plan, "weekly_plan", None)
    )
    if not weekly_plan:
        raise HTTPException(status_code=500, detail="Study plan data is malformed")

    week = None
    for w in weekly_plan:
        w_week = w["week"] if isinstance(w, dict) else w.week
        if w_week == current_week:
            week = w
            break

    if not week:
        week = weekly_plan[0]

    days = week["days"] if isinstance(week, dict) else week.days

    # Resolve lesson IDs from the DB (matched by week + day + title)
    lesson_rows_result = await db.execute(
        select(Lesson).where(
            Lesson.study_plan_id == plan.id,
            Lesson.week_number == current_week,
            Lesson.day_number == current_day,
        )
    )
    lesson_by_title: dict[str, int] = {
        row.title: row.id for row in lesson_rows_result.scalars().all()
    }

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

        lesson_id = lesson_by_title.get(d_title)

        # Resolve curriculum grammar/vocabulary context for this unit
        grammar_points: list[str] = []
        vocabulary_set_ids: list[str] = []
        if d_unit_id:
            from app.data.curriculum import get_curriculum_units  # noqa: PLC0415
            for cu in get_curriculum_units(plan.cefr_level):
                if cu.id == d_unit_id:
                    grammar_points = cu.grammar_points
                    vocabulary_set_ids = cu.vocabulary_set_ids
                    break

        # Auto-generate the lesson if it doesn't exist yet
        if lesson_id is None:
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
                    target_language=current_user.target_language,
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

                for ex in (content_dict.get("exercises") or []):
                    exercise = Exercise(
                        lesson_id=lesson.id,
                        exercise_type=ex.get("type", "multiple_choice"),
                        question=ex.get("question", ""),
                        options=ex.get("options"),
                        correct_answer=ex.get("correct", ""),
                    )
                    db.add(exercise)

                await db.commit()
                await db.refresh(lesson)
                lesson_id = lesson.id
            except Exception:
                logger.exception("Failed to generate or persist lesson for plan %s", plan.id)

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
            )
        )

    return TodayResponse(plan_id=plan.id, cefr_level=plan.cefr_level, lessons=today_lessons)
