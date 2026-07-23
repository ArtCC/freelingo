from __future__ import annotations

import asyncio
import logging
import os

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import FileResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import (
    get_active_study_plan,
    get_redis,
    require_not_maintenance,
    require_subscription_or_freemium,
    require_subscription_or_freemium_readonly,
)
from app.core.limiter import limiter
from app.models.listening import ListeningExercise
from app.models.study_plan import StudyPlan
from app.models.user import User
from app.schemas.listening import (
    CorrectAnswerOut,
    ListeningAttemptOut,
    ListeningExerciseOut,
    ListeningGeneratingResponse,
    ListeningHistoryResponse,
    ListeningNextResponse,
    ListeningSubmitRequest,
    ListeningSubmitResponse,
    QuestionOut,
)
from app.services.listening_service import (
    generate_and_save_exercise,
    get_available_exercise,
    get_user_history,
    submit_attempt,
)
from app.utils.db import db_session
from app.utils.redis import redis_client as _redis_client

router = APIRouter(prefix="/api/listening", tags=["listening"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_exercise_out(exercise: ListeningExercise) -> ListeningExerciseOut:
    """Convert ORM model to safe schema — no text, no correct answers."""
    return ListeningExerciseOut(
        id=exercise.id,
        level=exercise.level,
        target_language=exercise.target_language,
        exercise_type=exercise.exercise_type,
        topic=exercise.topic,
        duration_seconds=exercise.duration_seconds,
        questions=[
            QuestionOut(
                index=q["index"],
                question=q["question"],
                options=q["options"],
            )
            for q in exercise.questions
        ],
    )


# ---------------------------------------------------------------------------
# Background task for exercise generation
# ---------------------------------------------------------------------------


async def _background_generate(
    level: str,
    target_language: str,
    tts_service: object,
    storage_path: str,
    lock_key: str,
    voice: str = "",
) -> None:
    """
    Runs after the HTTP response is sent.
    Creates its own DB session and Redis client (request resources are already closed).
    Releases the Redis lock in all cases (success or failure).
    """
    async with _redis_client() as redis_conn:
        try:
            async with db_session() as db:
                await generate_and_save_exercise(
                    level, target_language, db, tts_service, storage_path, voice
                )
        except Exception:
            logger.exception(
                "listening: generation failed level=%s lang=%s", level, target_language
            )
        finally:
            await redis_conn.delete(lock_key)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/next", response_model=ListeningNextResponse)
@limiter.limit("10/minute")
async def get_next_exercise(
    request: Request,
    _maintenance: None = Depends(require_not_maintenance),
    wait: bool = False,
    plan: StudyPlan = Depends(get_active_study_plan),
    current_user: User = Depends(require_subscription_or_freemium_readonly("listening")),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ListeningNextResponse:
    """
    Return the next uncompleted exercise for the user's CEFR level and language.

    When ``wait=true`` the endpoint blocks (async) until an exercise becomes
    available or the generation lock disappears (max 90 s). This eliminates the
    need for client-side polling.
    """
    level, target_language = plan.cefr_level, plan.target_language
    exercise = await get_available_exercise(level, target_language, current_user.id, db)
    if exercise is not None:
        return ListeningNextResponse(available=True, exercise=_build_exercise_out(exercise))

    if not wait:
        return ListeningNextResponse(available=False)

    # Long-poll: wait up to 90 s for the background generation to finish.
    lock_key = f"listening:generating:{level}:{target_language}"
    for _ in range(90):
        await asyncio.sleep(1)
        exercise = await get_available_exercise(level, target_language, current_user.id, db)
        if exercise is not None:
            return ListeningNextResponse(available=True, exercise=_build_exercise_out(exercise))
        # If the lock is already gone and there is still no exercise, stop waiting.
        if not await redis.exists(lock_key):
            break

    # Final check: the background task may have saved the exercise and deleted
    # the lock between the two checks above (race condition).
    exercise = await get_available_exercise(level, target_language, current_user.id, db)
    if exercise is not None:
        return ListeningNextResponse(available=True, exercise=_build_exercise_out(exercise))

    return ListeningNextResponse(available=False)


@router.post(
    "/generate",
    response_model=ListeningGeneratingResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("5/minute")
async def generate_exercise(
    request: Request,
    background_tasks: BackgroundTasks,
    _maintenance: None = Depends(require_not_maintenance),
    voice: str = Query(default=""),
    plan: StudyPlan = Depends(get_active_study_plan),
    current_user: User = Depends(require_subscription_or_freemium("listening")),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ListeningGeneratingResponse:
    """
    Trigger on-demand exercise generation.

    - Acquires a Redis lock scoped to (level, target_language) with 60 s TTL.
    - If the lock is already held (another generation in progress), returns 202 immediately.
    - Otherwise, starts generation as a FastAPI BackgroundTask and returns 202.
    - Frontend calls GET /next?wait=true once and awaits the response (long poll).
    """
    level, target_language = plan.cefr_level, plan.target_language
    lock_key = f"listening:generating:{level}:{target_language}"

    acquired = await redis.set(lock_key, "1", nx=True, ex=60)
    if not acquired:
        # Another generation is already running
        return ListeningGeneratingResponse(status="generating")

    tts_service = request.app.state.tts_service
    background_tasks.add_task(
        _background_generate,
        level,
        target_language,
        tts_service,
        settings.AUDIO_STORAGE_PATH,
        lock_key,
        voice,
    )
    return ListeningGeneratingResponse(status="generating")


@router.get("/audio/{exercise_id}")
@limiter.limit("60/minute")
async def get_audio(
    request: Request,
    exercise_id: int,
    _maintenance: None = Depends(require_not_maintenance),
    plan: StudyPlan = Depends(get_active_study_plan),
    current_user: User = Depends(require_subscription_or_freemium_readonly("listening")),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """
    Stream the MP3 audio file for the exercise.

    The path is always constructed from exercise_id (integer) — never from
    a DB-stored string — to prevent path traversal.
    """
    exercise = await db.get(ListeningExercise, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="exercise_not_found")
    if exercise.target_language != plan.target_language:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="exercise_not_found")

    audio_path = os.path.join(settings.AUDIO_STORAGE_PATH, "listening", f"{exercise_id}.mp3")
    if not os.path.isfile(audio_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="audio_not_found")

    return FileResponse(
        path=audio_path,
        media_type="audio/mpeg",
        headers={"Accept-Ranges": "bytes"},
    )


@router.post("/attempt", response_model=ListeningSubmitResponse)
@limiter.limit("20/minute")
async def submit_listening_attempt(
    request: Request,
    body: ListeningSubmitRequest,
    _maintenance: None = Depends(require_not_maintenance),
    plan: StudyPlan = Depends(get_active_study_plan),
    current_user: User = Depends(require_subscription_or_freemium("listening")),
    db: AsyncSession = Depends(get_db),
) -> ListeningSubmitResponse:
    """Submit answers and receive score, XP, correct answers, and transcript."""
    try:
        attempt, exercise = await submit_attempt(
            body.exercise_id,
            current_user.id,
            body.answers,
            db,
            is_replay=body.replay,
            study_plan_id=plan.id,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "exercise_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="exercise_not_found"
            ) from exc
        if detail == "already_attempted":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="already_attempted"
            ) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc

    correct_answers = [
        CorrectAnswerOut(index=q["index"], correct=q["correct"]) for q in exercise.questions
    ]

    # Record freemium listening usage (best-effort)
    from app.services.freemium_service import maybe_record_freemium_usage

    await maybe_record_freemium_usage(current_user, "listening")

    return ListeningSubmitResponse(
        score=attempt.score,
        xp_earned=attempt.xp_earned,
        correct_answers=correct_answers,
        text=exercise.text,
    )


@router.get("/history", response_model=ListeningHistoryResponse)
@limiter.limit("60/minute")
async def get_listening_history(
    request: Request,
    _maintenance: None = Depends(require_not_maintenance),
    skip: int = 0,
    limit: int = 10,
    plan: StudyPlan = Depends(get_active_study_plan),
    current_user: User = Depends(require_subscription_or_freemium_readonly("listening")),
    db: AsyncSession = Depends(get_db),
) -> ListeningHistoryResponse:
    """Return paginated list of the user's past listening attempts."""
    limit = min(limit, 50)  # hard cap

    rows, total = await get_user_history(
        current_user.id,
        db,
        skip=skip,
        limit=limit,
        target_language=plan.target_language,
    )
    items = [
        ListeningAttemptOut(
            id=attempt.id,
            score=attempt.score,
            xp_earned=attempt.xp_earned,
            completed_at=attempt.completed_at,
            exercise=_build_exercise_out(exercise),
            text=exercise.text,
            answers=attempt.answers,
        )
        for attempt, exercise in rows
    ]
    return ListeningHistoryResponse(items=items, total=total, skip=skip, limit=limit)
