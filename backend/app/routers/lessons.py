from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.lesson import Exercise, Lesson
from app.models.study_plan import StudyPlan
from app.models.user import User
from app.schemas.lessons import (
    ExerciseAnswerRequest,
    ExerciseAnswerResponse,
    LessonDetailResponse,
    LessonResponse,
)
from app.services.lesson_generator import evaluate_free_write, evaluate_pronunciation, generate_lesson
from app.services.llm_adapter import (
    LLMError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.services.progress_service import update_daily_progress, upsert_unit_competency

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


async def _get_lesson_for_user(lesson_id: int, user_id: int, db: AsyncSession) -> Lesson:
    """Fetch a lesson and verify it belongs to the requesting user via its study plan."""
    result = await db.execute(
        select(Lesson)
        .join(StudyPlan, Lesson.study_plan_id == StudyPlan.id)
        .where(Lesson.id == lesson_id, StudyPlan.user_id == user_id)
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson


@router.get("/{lesson_id}", response_model=LessonDetailResponse)
async def get_lesson(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lesson = await _get_lesson_for_user(lesson_id, current_user.id, db)

    result = await db.execute(
        select(Exercise).where(Exercise.lesson_id == lesson_id).order_by(Exercise.id)
    )
    exercises = result.scalars().all()

    return LessonDetailResponse(lesson=lesson, exercises=exercises)


@router.post("/{lesson_id}/start", response_model=LessonResponse)
async def start_lesson(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lesson = await _get_lesson_for_user(lesson_id, current_user.id, db)
    return lesson


@router.post("/{lesson_id}/complete", response_model=LessonResponse)
async def complete_lesson(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lesson = await _get_lesson_for_user(lesson_id, current_user.id, db)

    lesson.is_completed = True
    lesson.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    await db.refresh(lesson)

    await update_daily_progress(
        db, current_user.id,
        lesson_completed=True,
        skill=lesson.lesson_type,
    )

    # Update per-unit competency if lesson belongs to a curriculum unit
    if lesson.unit_id:
        from app.data.curriculum import get_curriculum_units  # noqa: PLC0415
        from app.models.study_plan import StudyPlan  # noqa: PLC0415

        plan = await db.get(StudyPlan, lesson.study_plan_id)
        if plan:
            for u in get_curriculum_units(plan.cefr_level):
                if u.id == lesson.unit_id:
                    # Score this lesson: average of answered exercises
                    result_ex = await db.execute(
                        select(Exercise).where(
                            Exercise.lesson_id == lesson.id,
                            Exercise.score.is_not(None),
                        )
                    )
                    exercises = result_ex.scalars().all()
                    lesson_score = (
                        sum(e.score for e in exercises if e.score is not None) / len(exercises)
                        if exercises
                        else 0.5
                    )
                    await upsert_unit_competency(
                        db,
                        current_user.id,
                        unit_id=lesson.unit_id,
                        competency_texts=u.competency_checklist,
                        lesson_score=lesson_score,
                    )
                    await db.commit()
                    break

    return lesson


@router.post("/exercises/{exercise_id}/answer", response_model=ExerciseAnswerResponse)
async def answer_exercise(
    exercise_id: int,
    data: ExerciseAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exercise = await db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    lesson = await _get_lesson_for_user(exercise.lesson_id, current_user.id, db)

    user_answer = data.answer.strip().lower() if data.answer else ""
    correct = exercise.correct_answer.strip().lower()

    if exercise.exercise_type == "free_write":
        prompt = exercise.question
        criteria = ["grammar", "spelling", "coherence"]
        try:
            eval_result = await evaluate_free_write(
                cefr_level=lesson.cefr_level,
                prompt=prompt,
                criteria=criteria,
                answer=data.answer,
            )
            sco = eval_result.score if hasattr(eval_result, "score") else eval_result["score"]
            fb = eval_result.feedback if hasattr(eval_result, "feedback") else eval_result["feedback"]
            exercise.score = sco
            exercise.feedback = fb
        except (LLMTimeoutError, LLMUnavailableError, LLMError):
            exercise.score = 0.5
            exercise.feedback = "Could not evaluate free-write answer at this time."
    elif exercise.exercise_type == "pronunciation":
        transcription = data.answer
        try:
            eval_result = await evaluate_pronunciation(
                cefr_level=lesson.cefr_level,
                target=exercise.correct_answer,
                transcription=transcription,
            )
            exercise.score = eval_result.score
            exercise.feedback = eval_result.feedback
        except (LLMTimeoutError, LLMUnavailableError, LLMError):
            # Fallback: simple normalised comparison
            norm_target = exercise.correct_answer.strip().lower()
            norm_answer = transcription.strip().lower()
            is_close = (
                norm_target == norm_answer
                or norm_target in norm_answer
                or norm_answer in norm_target
            )
            exercise.score = 1.0 if is_close else 0.3
            exercise.feedback = (
                "Good pronunciation!"
                if is_close
                else f"The target phrase was: {exercise.correct_answer}"
            )
    else:
        is_correct = user_answer == correct
        exercise.score = 1.0 if is_correct else 0.0
        exercise.feedback = "Correct!" if is_correct else f"The correct answer is: {exercise.correct_answer}"

    exercise.user_answer = data.answer
    exercise.answered_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    await db.refresh(exercise)

    await update_daily_progress(
        db, current_user.id,
        exercise_correct=exercise.score >= 0.5,
        skill=lesson.lesson_type,
        skill_score=exercise.score,
    )

    return ExerciseAnswerResponse(
        id=exercise.id,
        score=exercise.score,
        feedback=exercise.feedback,
        correct_answer=exercise.correct_answer,
    )
