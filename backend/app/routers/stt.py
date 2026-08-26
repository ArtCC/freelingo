from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.app_logger import get_logger
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.models.study_plan import StudyPlan
from app.models.user import User
from app.schemas.tts_stt import STTResponse
from app.services.language_helpers import get_iso639

router = APIRouter(prefix="/api", tags=["stt"])
logger = get_logger(__name__)


@router.post("/stt", response_model=STTResponse)
@limiter.limit("20/minute")
async def speech_to_text(
    request: Request,
    audio: UploadFile = File(...),
    study_plan_id: int = Form(..., gt=0, le=2_147_483_647),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> STTResponse:
    """Transcribe audio using the language of a user-owned study plan."""
    stt_service = getattr(request.app.state, "stt_service", None)
    if stt_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STT service is not enabled",
        )

    plan = await db.scalar(
        select(StudyPlan).where(
            StudyPlan.id == study_plan_id,
            StudyPlan.user_id == current_user.id,
        )
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study plan not found",
        )

    language = get_iso639(plan.target_language)
    audio_bytes = await audio.read()
    if len(audio_bytes) > 50 * 1024 * 1024:  # 50 MB
        raise HTTPException(status_code=413, detail="Audio file too large (max 50 MB)")

    logger.info(
        "stt_request",
        user_id=current_user.id,
        study_plan_id=plan.id,
        target_language=plan.target_language,
        language=language,
        provider=type(stt_service).__name__,
        model=getattr(stt_service, "model", None),
        audio_bytes=len(audio_bytes),
    )
    text = await stt_service.transcribe(
        audio_bytes,
        audio.filename or "audio.webm",
        mime_type=audio.content_type or "audio/webm",
        language=language,
    )
    return STTResponse(text=text)
