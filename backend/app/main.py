import asyncio
import logging
import os
from contextlib import asynccontextmanager

from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from alembic import command
from app.core.config import settings
from app.core.limiter import limiter

logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_AVATARS_DIR = "/app/avatars"
_TTS_PREVIEWS_DIR = "/app/tts_previews"
from app.routers import (
    admin,
    assessment,
    auth,
    chat,
    contact,
    conversation,
    curriculum,
    feedback,
    flashcards,
    freemium,
    grammar,
    languages,
    lessons,
    listening,
    memories,
    phrasebook,
    progress,
    reading,
    reviews,
    stt,
    study_plan,
    tts,
    vocabulary,
)
from app.routers import config as config_router
from app.routers import health as health_router
from app.services.stt_service import OpenAISTTService, WhisperSTTService
from app.services.tts_service import KokoroTTSService, OpenAITTSService


def _run_migrations() -> None:
    alembic_cfg = Config("/app/alembic.ini")
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    if (
        not settings.SECRET_KEY
        or "CHANGE_ME" in settings.SECRET_KEY
        or len(settings.SECRET_KEY) < 32
    ):
        raise RuntimeError(
            "SECRET_KEY is insecure or unconfigured. "
            "Set a random value of at least 32 characters in your .env file."
        )

    await asyncio.to_thread(_run_migrations)

    # Ensure the avatars directory exists on startup (persisted via Docker volume)
    os.makedirs(_AVATARS_DIR, exist_ok=True)
    # Ensure the TTS preview cache directory exists on startup
    os.makedirs(_TTS_PREVIEWS_DIR, exist_ok=True)

    if settings.TTS_PROVIDER == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("TTS_PROVIDER=openai requires OPENAI_API_KEY to be set")
        app.state.tts_service = OpenAITTSService(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_TTS_MODEL,
            voice=settings.OPENAI_TTS_VOICE,
            speed=settings.OPENAI_TTS_SPEED,
        )
    else:
        app.state.tts_service = KokoroTTSService(settings.TTS_BASE_URL, settings.TTS_VOICE)

    if settings.STT_PROVIDER == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("STT_PROVIDER=openai requires OPENAI_API_KEY to be set")
        app.state.stt_service = OpenAISTTService(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_STT_MODEL,
        )
    else:
        app.state.stt_service = WhisperSTTService(settings.STT_BASE_URL)

    yield


app = FastAPI(title="FreeLingo API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "0"  # Modern browsers ignore it; CSP is the right tool
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; object-src 'none'; base-uri 'self'"  # API-only responses (JSON/binary)
    )
    return response


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(assessment.router)
app.include_router(study_plan.router)
app.include_router(lessons.router)
app.include_router(flashcards.router)
app.include_router(grammar.router)
app.include_router(chat.router)
app.include_router(progress.router)
app.include_router(listening.router)
app.include_router(reading.router)
app.include_router(reviews.router)
app.include_router(tts.router)
app.include_router(stt.router)
app.include_router(conversation.router)
app.include_router(config_router.router)
app.include_router(contact.router)
app.include_router(curriculum.router)
app.include_router(feedback.router)
app.include_router(freemium.router)
app.include_router(memories.router)
app.include_router(phrasebook.router)
app.include_router(languages.router)
app.include_router(health_router.router)
app.include_router(vocabulary.router)

if settings.STRIPE_ENABLED:
    import stripe as _stripe

    from app.routers import billing as billing_router

    _stripe.api_key = settings.STRIPE_SECRET_KEY
    app.include_router(billing_router.router)
