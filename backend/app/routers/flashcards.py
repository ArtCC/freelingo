from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.flashcard import Flashcard
from app.models.user import User
from app.schemas.flashcards import (
    FlashcardCreate,
    FlashcardGenerateRequest,
    FlashcardGenerateResponse,
    FlashcardListResponse,
    FlashcardResponse,
    FlashcardReview,
)
from app.services.flashcard_sm2 import generate_flashcards, sm2_update
from app.services.llm_adapter import (
    LLMError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.services.progress_service import update_daily_progress

router = APIRouter(prefix="/api/flashcards", tags=["flashcards"])


@router.get("/due", response_model=FlashcardListResponse)
async def get_due_flashcards(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import date as date_type

    result = await db.execute(
        select(Flashcard)
        .where(
            Flashcard.user_id == current_user.id,
            Flashcard.next_review <= date_type.today(),
        )
        .order_by(Flashcard.next_review)
    )
    due = result.scalars().all()

    count_result = await db.execute(
        select(func.count(Flashcard.id)).where(
            Flashcard.user_id == current_user.id
        )
    )
    total = count_result.scalar()

    return FlashcardListResponse(due=due, total=total)


@router.get("/all", response_model=list[FlashcardResponse])
async def get_all_flashcards(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Flashcard)
        .where(Flashcard.user_id == current_user.id)
        .order_by(Flashcard.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=FlashcardResponse)
async def create_flashcard(
    data: FlashcardCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = Flashcard(
        user_id=current_user.id,
        word=data.word,
        definition=data.definition,
        example_sentence=data.example_sentence,
        translation=data.translation,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


@router.post("/{card_id}/review", response_model=FlashcardResponse)
async def review_flashcard(
    card_id: int,
    data: FlashcardReview,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await db.get(Flashcard, card_id)
    if not card or card.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Flashcard not found")

    card = sm2_update(card, data.quality)
    await db.commit()
    await db.refresh(card)

    await update_daily_progress(
        db, current_user.id,
        flashcard_reviewed=True,
        skill="vocabulary",
        skill_score=min(data.quality / 5.0, 1.0),
    )
    return card


@router.post("/generate", response_model=FlashcardGenerateResponse)
async def generate_flashcards_endpoint(
    data: FlashcardGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await generate_flashcards(
            topic=data.topic,
            count=data.count,
            cefr_level=data.cefr_level,
            native_language=data.native_language,
            target_language=current_user.target_language,
        )
        # Persist generated cards
        for card_data in result.flashcards:
            card = Flashcard(
                user_id=current_user.id,
                word=card_data.word,
                definition=card_data.definition,
                example_sentence=card_data.example_sentence,
                translation=card_data.translation,
            )
            db.add(card)
        await db.commit()
        return result
    except LLMTimeoutError:
        raise HTTPException(
            status_code=504, detail="The AI model took too long."
        )
    except LLMUnavailableError as e:
        raise HTTPException(
            status_code=503, detail=f"AI service unavailable: {str(e)}"
        )
    except LLMError as e:
        raise HTTPException(
            status_code=502, detail=f"Failed to generate flashcards: {str(e)}"
        )
