from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.app_logger import get_logger
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.models.chat_history import ChatHistory
from app.models.conversation import Conversation
from app.models.llm_usage import LLMUsage
from app.models.progress import Progress
from app.models.study_plan import StudyPlan
from app.models.user import User
from app.models.user_language import UserLanguage
from app.schemas.language import (
    LanguageAddRequest,
    LanguagePlanInfo,
    LanguageProgressInfo,
    LanguageSwitchRequest,
    UserLanguageListResponse,
    UserLanguageOut,
)
from app.services.user_language_service import (
    add_language,
    get_active_language,
    get_user_languages,
    switch_language,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/languages", tags=["languages"])


async def _build_plan_info(
    db: AsyncSession, user_id: int, target_language: str
) -> LanguagePlanInfo | None:
    ul_result = await db.execute(
        select(UserLanguage.id).where(
            UserLanguage.user_id == user_id,
            UserLanguage.target_language == target_language,
        )
    )
    ul_id = ul_result.scalar_one_or_none()
    if ul_id is None:
        return None
    result = await db.execute(
        select(StudyPlan)
        .where(
            StudyPlan.user_language_id == ul_id,
            StudyPlan.is_active.is_(True),
        )
        .order_by(StudyPlan.created_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        return None

    total_days = plan.duration_weeks * plan.days_per_week
    completion_pct = round((plan.progress_day / total_days) * 100, 1) if total_days > 0 else 0.0

    return LanguagePlanInfo(
        id=plan.id,
        cefr_level=plan.cefr_level,
        progress_day=plan.progress_day,
        total_days=total_days,
        completion_pct=completion_pct,
    )


async def _build_progress_info(
    db: AsyncSession, user_id: int, target_language: str
) -> LanguageProgressInfo | None:
    # Find the active plan for this language via UserLanguage
    plan_res = await db.execute(
        select(StudyPlan.id)
        .select_from(StudyPlan)
        .join(UserLanguage, StudyPlan.user_language_id == UserLanguage.id)
        .where(
            UserLanguage.user_id == user_id,
            UserLanguage.target_language == target_language,
            StudyPlan.is_active.is_(True),
        )
    )
    plan_row = plan_res.first()
    if not plan_row:
        return None

    plan_id = plan_row[0]

    entries_res = await db.execute(
        select(Progress).where(Progress.study_plan_id == plan_id).order_by(Progress.date.desc())
    )
    entries = entries_res.scalars().all()

    total_xp = sum(e.xp_earned for e in entries)
    current_streak = entries[0].streak_day if entries else 0
    lessons_completed = sum(e.lessons_completed for e in entries)

    return LanguageProgressInfo(
        total_xp=total_xp,
        current_streak=current_streak,
        lessons_completed=lessons_completed,
    )


@router.get("", response_model=UserLanguageListResponse)
@limiter.limit("60/minute")
async def list_languages(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.auth import get_available_languages

    rows = await get_user_languages(db, current_user.id)

    languages: list[UserLanguageOut] = []
    for lang in rows:
        plan = await _build_plan_info(db, current_user.id, lang.target_language)
        progress = (
            await _build_progress_info(db, current_user.id, lang.target_language) if plan else None
        )
        languages.append(
            UserLanguageOut(
                target_language=lang.target_language,
                is_active=lang.is_active,
                plan=plan,
                progress=progress,
            )
        )

    return UserLanguageListResponse(
        languages=languages,
        all_supported_languages=get_available_languages(),
    )


@router.get("/active")
@limiter.limit("60/minute")
async def get_active(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    active = await get_active_language(db, current_user.id)
    if not active:
        raise HTTPException(status_code=404, detail="No active language set")
    return {"target_language": active.target_language, "is_active": active.is_active}


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def add_new_language(
    request: Request,
    data: LanguageAddRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await add_language(db, current_user.id, data.target_language)
    return {"target_language": entry.target_language, "is_active": entry.is_active}


@router.put("/active")
@limiter.limit("60/minute")
async def switch_active_language(
    request: Request,
    data: LanguageSwitchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await switch_language(db, current_user.id, data.target_language)
    # Also update the user's target_language field for backward compatibility
    current_user.target_language = data.target_language
    await db.commit()
    return {"target_language": entry.target_language, "is_active": entry.is_active}


@router.delete("/{target_language}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def delete_language(
    request: Request,
    target_language: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # ── Find the UserLanguage row ────────────────────────────────────────
    ul_result = await db.execute(
        select(UserLanguage).where(
            UserLanguage.user_id == current_user.id,
            UserLanguage.target_language == target_language,
        )
    )
    ul = ul_result.scalar_one_or_none()
    if not ul:
        raise HTTPException(status_code=404, detail="Language not found")

    # ── Validation (same rules as remove_language) ───────────────────────
    count_result = await db.execute(
        select(func.count())
        .select_from(UserLanguage)
        .where(UserLanguage.user_id == current_user.id)
    )
    if count_result.scalar() <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the only language",
        )
    if ul.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the active language",
        )

    # ── Clean up SET NULL tables before cascading delete ─────────────────
    plan_result = await db.execute(select(StudyPlan.id).where(StudyPlan.user_language_id == ul.id))
    plan_ids = [row[0] for row in plan_result.fetchall()]
    if plan_ids:
        await db.execute(delete(ChatHistory).where(ChatHistory.study_plan_id.in_(plan_ids)))
        await db.execute(delete(Conversation).where(Conversation.study_plan_id.in_(plan_ids)))
        await db.execute(delete(LLMUsage).where(LLMUsage.study_plan_id.in_(plan_ids)))

    # ── Delete UserLanguage → CASCADE deletes StudyPlan →
    #     CASCADE deletes progress, flashcards, user_competencies,
    #     listening_attempts, reading_attempts ─────────────────────────────
    await db.delete(ul)
    await db.commit()
