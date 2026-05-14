from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.models.user import User
from app.schemas.tts_stt import TTSRequest

router = APIRouter(prefix="/api", tags=["tts"])


@router.post("/tts")
@limiter.limit("20/minute")
async def text_to_speech(
    request: Request,
    body: TTSRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Proxy TTS request to the configured service. Streams back audio/mpeg.

    Using StreamingResponse means the first bytes reach the browser as soon as
    the TTS service starts sending them (beneficial for OpenAI TTS which streams
    progressively; also populates the LRU cache so subsequent requests are instant).
    """
    tts_service = getattr(request.app.state, "tts_service", None)
    if tts_service is None:
        raise HTTPException(status_code=503, detail="TTS service is not enabled")
    return StreamingResponse(
        tts_service.synthesize_stream(body.text, body.voice),
        media_type="audio/mpeg",
    )
