import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.models.flashcard import Flashcard
from app.models.study_plan import StudyPlan
from app.models.user import User
from app.schemas.flashcards import (
    FlashcardBulkCreate,
    FlashcardBulkResponse,
    FlashcardCreate,
    FlashcardFromWordRequest,
    FlashcardFromWordResponse,
    FlashcardGenerateRequest,
    FlashcardGenerateResponse,
    FlashcardListResponse,
    FlashcardResponse,
    FlashcardReview,
    VocabularyListResponse,
)
from app.services.flashcard_sm2 import generate_flashcards, lookup_word, sm2_update
from app.services.llm_adapter import (
    LLMError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.services.progress_service import update_daily_progress
from app.services.user_language_service import get_active_language

router = APIRouter(prefix="/api/flashcards", tags=["flashcards"])


def _normalize_flashcard_word(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


async def _find_existing_flashcard(
    db: AsyncSession, user_id: int, study_plan_id: int, word: str
) -> Flashcard | None:
    """Return the oldest card in the plan whose word matches `word` case-insensitively.

    Matching is done in SQL (`lower(trim(word))`) so a save never materializes the
    whole plan. Ordering by id makes the winner deterministic when duplicates already
    exist.
    """
    normalized = _normalize_flashcard_word(word)
    if not normalized:
        return None
    result = await db.execute(
        select(Flashcard)
        .where(
            Flashcard.user_id == user_id,
            Flashcard.study_plan_id == study_plan_id,
            func.lower(func.trim(Flashcard.word)) == normalized,
        )
        .order_by(Flashcard.id)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _respond_with_existing_flashcard(
    db: AsyncSession, card: Flashcard
) -> FlashcardFromWordResponse:
    """Build the from-word response for a card that already exists in the plan.

    `already_saved` means "already visible in My Vocabulary" (source == from_text).
    A generated or imported card is promoted to from_text instead of duplicated, so
    the word shows up in the vocabulary list and the UI reports a fresh save.
    """
    already_saved = card.source == "from_text"
    if not already_saved:
        card.source = "from_text"
        await db.commit()
        await db.refresh(card)
    resp = FlashcardFromWordResponse.model_validate(card)
    resp.already_saved = already_saved
    return resp


async def _get_active_plan_or_404(db: AsyncSession, user_id: int) -> StudyPlan:
    """Return the active study plan, raising 404 if none."""
    active_lang = await get_active_language(db, user_id)
    if not active_lang:
        raise HTTPException(status_code=404, detail="No active language set")
    result = await db.execute(
        select(StudyPlan).where(
            StudyPlan.user_language_id == active_lang.id,
            StudyPlan.is_active.is_(True),
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="No active study plan found")
    return plan


@router.get("/due", response_model=FlashcardListResponse)
@limiter.limit("60/minute")
async def get_due_flashcards(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await _get_active_plan_or_404(db, current_user.id)
    from datetime import date as date_type

    result = await db.execute(
        select(Flashcard)
        .where(
            Flashcard.user_id == current_user.id,
            Flashcard.study_plan_id == plan.id,
            Flashcard.next_review <= date_type.today(),
        )
        .order_by(Flashcard.next_review)
    )
    due = result.scalars().all()

    count_result = await db.execute(
        select(func.count(Flashcard.id)).where(
            Flashcard.user_id == current_user.id,
            Flashcard.study_plan_id == plan.id,
        )
    )
    total = count_result.scalar()

    return FlashcardListResponse(due=due, total=total)


@router.get("/all", response_model=list[FlashcardResponse])
@limiter.limit("60/minute")
async def get_all_flashcards(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await _get_active_plan_or_404(db, current_user.id)
    result = await db.execute(
        select(Flashcard)
        .where(
            Flashcard.user_id == current_user.id,
            Flashcard.study_plan_id == plan.id,
        )
        .order_by(Flashcard.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=FlashcardResponse)
@limiter.limit("60/minute")
async def create_flashcard(
    request: Request,
    data: FlashcardCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await _get_active_plan_or_404(db, current_user.id)
    card = Flashcard(
        user_id=current_user.id,
        study_plan_id=plan.id,
        word=data.word,
        definition=data.definition,
        example_sentence=data.example_sentence,
        translation=data.translation,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


@router.post("/bulk", response_model=FlashcardBulkResponse)
@limiter.limit("60/minute")
async def create_flashcards_bulk(
    request: Request,
    data: FlashcardBulkCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await _get_active_plan_or_404(db, current_user.id)
    existing = await db.execute(
        select(Flashcard.word).where(
            Flashcard.user_id == current_user.id,
            Flashcard.study_plan_id == plan.id,
        )
    )
    existing_words = {_normalize_flashcard_word(word) for word in existing.scalars().all()}
    created_words: set[str] = set()

    created = 0
    for item in data.flashcards:
        normalized_word = _normalize_flashcard_word(item.word)
        if (
            not normalized_word
            or normalized_word in existing_words
            or normalized_word in created_words
        ):
            continue

        card = Flashcard(
            user_id=current_user.id,
            study_plan_id=plan.id,
            word=item.word.strip(),
            definition=item.definition,
            example_sentence=item.example_sentence,
            translation=item.translation,
        )
        db.add(card)
        created_words.add(normalized_word)
        existing_words.add(normalized_word)
        created += 1

    await db.commit()
    return FlashcardBulkResponse(created=created)


@router.post("/{card_id}/review", response_model=FlashcardResponse)
@limiter.limit("60/minute")
async def review_flashcard(
    request: Request,
    card_id: int,
    data: FlashcardReview,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await db.get(Flashcard, card_id)
    if not card or card.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard not found")

    card = sm2_update(card, data.quality)
    await db.commit()
    await db.refresh(card)

    await update_daily_progress(
        db,
        current_user.id,
        flashcard_reviewed=True,
        skill="vocabulary",
        skill_score=min(data.quality / 5.0, 1.0),
        study_plan_id=card.study_plan_id,
    )
    return card


@router.post("/generate", response_model=FlashcardGenerateResponse)
@limiter.limit("20/minute")
async def generate_flashcards_endpoint(
    request: Request,
    data: FlashcardGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await _get_active_plan_or_404(db, current_user.id)
    try:
        existing = await db.execute(
            select(Flashcard.word).where(
                Flashcard.user_id == current_user.id,
                Flashcard.study_plan_id == plan.id,
            )
        )
        existing_words = {_normalize_flashcard_word(word) for word in existing.scalars().all()}
        seen_words: set[str] = set()

        result = await generate_flashcards(
            topic=data.topic,
            count=data.count,
            cefr_level=data.cefr_level,
            native_language=current_user.native_language,
            target_language=plan.target_language,
        )
        unique_flashcards = []
        for card_data in result.flashcards:
            normalized_word = _normalize_flashcard_word(card_data.word)
            if (
                not normalized_word
                or normalized_word in existing_words
                or normalized_word in seen_words
            ):
                continue

            seen_words.add(normalized_word)
            existing_words.add(normalized_word)
            unique_flashcards.append(card_data)

            card = Flashcard(
                user_id=current_user.id,
                study_plan_id=plan.id,
                word=card_data.word.strip(),
                definition=card_data.definition,
                example_sentence=card_data.example_sentence,
                translation=card_data.translation,
            )
            db.add(card)
        result.flashcards = unique_flashcards
        await db.commit()
        return result
    except LLMTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The AI model took too long.",
        )
    except LLMUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ai_service_unavailable",
        )
    except LLMError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ai_service_error",
        )


@router.post("/from-word", response_model=FlashcardFromWordResponse)
@limiter.limit("30/minute")
async def create_flashcard_from_word(
    request: Request,
    data: FlashcardFromWordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await _get_active_plan_or_404(db, current_user.id)
    existing = await _find_existing_flashcard(db, current_user.id, plan.id, data.word)
    if existing is not None:
        return await _respond_with_existing_flashcard(db, existing)

    try:
        card_data = await lookup_word(
            word=data.word.strip(),
            context=data.context,
            cefr_level=data.cefr_level,
            native_language=current_user.native_language,
            target_language=plan.target_language,
        )
    except LLMTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The AI model took too long.",
        )
    except LLMUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ai_service_unavailable",
        )
    except LLMError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ai_service_error",
        )

    # Re-check with the canonical form returned by the LLM (it may differ from the
    # selected surface form), which also narrows the race window opened by the LLM
    # call. Deduplication stays best-effort: two concurrent inserts can still both
    # pass this check.
    existing = await _find_existing_flashcard(db, current_user.id, plan.id, card_data.word)
    if existing is not None:
        return await _respond_with_existing_flashcard(db, existing)

    card = Flashcard(
        user_id=current_user.id,
        study_plan_id=plan.id,
        word=card_data.word,
        definition=card_data.definition,
        example_sentence=card_data.example_sentence,
        translation=card_data.translation,
        source="from_text",
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return FlashcardFromWordResponse.model_validate(card)


@router.get("/vocabulary", response_model=VocabularyListResponse)
@limiter.limit("60/minute")
async def get_vocabulary_flashcards(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: str = Query(""),
):
    plan = await _get_active_plan_or_404(db, current_user.id)
    filters = [
        Flashcard.user_id == current_user.id,
        Flashcard.study_plan_id == plan.id,
        Flashcard.source == "from_text",
    ]
    if search:
        filters.append(Flashcard.word.ilike(f"%{search}%"))

    total_res = await db.execute(select(func.count(Flashcard.id)).where(*filters))
    total = total_res.scalar() or 0

    items_res = await db.execute(
        select(Flashcard)
        .where(*filters)
        .order_by(func.lower(Flashcard.word))
        .offset((page - 1) * limit)
        .limit(limit)
    )
    items = items_res.scalars().all()

    pages = max(1, (total + limit - 1) // limit)
    return VocabularyListResponse(items=items, total=total, page=page, pages=pages)


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_flashcard(
    request: Request,
    card_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await db.get(Flashcard, card_id)
    if not card or card.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    await db.delete(card)
    await db.commit()
