from __future__ import annotations

import asyncio
import logging
import struct

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

logger = logging.getLogger(__name__)
from jwt.exceptions import PyJWTError
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.deps import get_current_user, require_subscription
from app.services.subscription_service import is_subscribed
from app.core.security import decode_access_token
from app.models.study_plan import StudyPlan
from app.models.user import User
from app.services.conversation_pipeline import ConversationPipeline
from app.services.llm_adapter import llm_adapter
from app.services.quota_service import check_and_increment_sessions, check_daily_minutes, check_monthly_tokens, check_weekly_minutes

router = APIRouter(tags=["conversation"])


def _make_silence_wav(duration_ms: int = 100, sample_rate: int = 16000) -> bytes:
    """Return a minimal valid PCM WAV with silence (for STT warmup)."""
    num_samples = sample_rate * duration_ms // 1000
    data = b"\x00" * (num_samples * 2)  # 16-bit mono
    byte_rate = sample_rate * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(data), b"WAVE",
        b"fmt ", 16, 1, 1, sample_rate, byte_rate, 2, 16,
        b"data", len(data),
    )
    return header + data


@router.post("/api/conversation/warmup")
async def conversation_warmup(
    request: Request,
    _current_user: User = Depends(require_subscription),
) -> JSONResponse:
    """Pre-heat TTS and STT services before a conversation session starts.

    Awaits model loading synchronously so the caller knows the models are
    ready before opening the WebSocket. The frontend must await this call
    and only then connect the WebSocket.
    """
    tts_service = getattr(request.app.state, "tts_service", None)
    stt_service = getattr(request.app.state, "stt_service", None)

    tasks = []
    if tts_service:
        tasks.append(_warmup_tts(tts_service))
    if stt_service:
        tasks.append(_warmup_stt(stt_service))
    if tasks:
        await asyncio.gather(*tasks)

    return JSONResponse({"status": "ready"})


async def _warmup_tts(tts_service: object) -> None:
    try:
        # Use a realistic sentence to warm up TTS model weights properly.
        # Caching it also speeds up the very first greeting in sessions.
        await tts_service.synthesize("Hello! Let's practice your English together.")  # type: ignore[union-attr]
        logger.info("[warmup] TTS ready")
    except Exception as exc:
        logger.warning("[warmup] TTS warmup error: %s", exc)


async def _warmup_stt(stt_service: object) -> None:
    try:
        wav = _make_silence_wav()
        await stt_service.transcribe(wav, "warmup.wav", "audio/wav")  # type: ignore[union-attr]
        logger.info("[warmup] STT ready")
    except Exception as exc:
        logger.warning("[warmup] STT warmup error: %s", exc)


@router.websocket("/ws/conversation")
async def conversation_ws(
    websocket: WebSocket,
) -> None:
    # --- Accept first, then authenticate via first JSON message ---
    await websocket.accept()

    initial_context_raw: list | None = None
    try:
        auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
        token = auth_msg.get("token", "")
        initial_context_raw = auth_msg.get("context")  # optional chat history
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (asyncio.TimeoutError, PyJWTError, KeyError, ValueError, Exception):
        logger.warning("[conversation] Auth failed — closing WS 1008")
        await websocket.send_json({"type": "error", "code": "auth_failed", "message": "Authentication failed"})
        await websocket.close(code=1008)
        return

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if not user or not user.is_active:
            logger.warning("[conversation] User %s not found or inactive — closing WS 1008", user_id)
            await websocket.close(code=1008)
            return

        # Check subscription
        if not is_subscribed(user, settings.STRIPE_ENABLED):
            logger.info("[conversation] User %s has no active subscription — closing WS 1008", user_id)
            await websocket.send_json({
                "type": "error",
                "code": "subscription_required",
                "message": "An active subscription is required to use voice conversation.",
            })
            await websocket.close(code=1008)
            return

        # --- Guard: TTS and STT must be enabled ---
        tts_service = getattr(websocket.app.state, "tts_service", None)
        stt_service = getattr(websocket.app.state, "stt_service", None)
        if tts_service is None or stt_service is None:
            logger.warning("[conversation] TTS or STT disabled — rejecting WS for user %s", user_id)
            await websocket.send_json({
                "type": "error",
                "code": "services_disabled",
                "message": "TTS and STT must be enabled for conversation mode.",
            })
            await websocket.close(code=1011)
            return

        # --- CEFR level from active StudyPlan, fallback B1 ---
        result = await db.execute(
            select(StudyPlan)
            .where(StudyPlan.user_id == user_id, StudyPlan.is_active == True)  # noqa: E712
            .order_by(StudyPlan.created_at.desc())
            .limit(1)
        )
        plan = result.scalar_one_or_none()
        cefr_level = plan.cefr_level if plan else "B1"

        # Read user settings before session closes to avoid DetachedInstanceError
        max_duration = user.conversation_max_duration
        inactivity_timeout = user.conversation_inactivity_timeout
        native_language = user.native_language
        target_language = user.target_language
        student_name = user.display_name
        user_bio = user.bio
        user_learning_goals = user.learning_goals
        weekly_sessions_limit = user.conversation_weekly_sessions
        daily_minutes_limit = user.conversation_daily_minutes
        weekly_minutes_limit = user.conversation_weekly_minutes
        monthly_tokens_limit = user.monthly_tokens_limit

    # Validate and sanitize optional chat context passed from the tutor chat
    valid_context: list[dict] | None = None
    if isinstance(initial_context_raw, list):
        sanitized = [
            {"role": m["role"], "content": m["content"]}
            for m in initial_context_raw[:20]
            if isinstance(m, dict)
            and m.get("role") in ("user", "assistant")
            and isinstance(m.get("content"), str)
            and m["content"].strip()
        ]
        if sanitized:
            valid_context = sanitized

    logger.info("[conversation] Session started — user=%s cefr=%s max_duration=%ss inactivity=%ss context_turns=%s",
                user_id, cefr_level, max_duration, inactivity_timeout, len(valid_context) if valid_context else 0)
    # (already accepted at the top)

    # --- Quota checks ---
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        # Check monthly token quota (DB-backed) — blocks both chat and voice
        if monthly_tokens_limit > 0:
            async with AsyncSessionLocal() as db_quota:
                tokens_ok, tokens_used, tokens_limit = await check_monthly_tokens(
                    db_quota, user_id, monthly_tokens_limit
                )
            if not tokens_ok:
                logger.info(
                    "[conversation] Monthly token quota exceeded — user=%s used=%s limit=%s",
                    user_id, tokens_used, tokens_limit,
                )
                await websocket.send_json({
                    "type": "error",
                    "code": "quota_exceeded_tokens",
                    "message": f"Monthly token limit reached ({tokens_used}/{tokens_limit} tokens). Voice is unavailable until next month.",
                })
                await websocket.close(code=1008)
                await redis.aclose()
                return

        # Check daily minutes first (read-only) so we never waste a weekly session slot
        daily_ok, minutes_used, minutes_limit = await check_daily_minutes(
            redis, user_id, daily_minutes_limit
        )
        if not daily_ok:
            logger.info(
                "[conversation] Daily minutes quota exceeded — user=%s used=%s limit=%s",
                user_id, minutes_used, minutes_limit,
            )
            await websocket.send_json({
                "type": "error",
                "code": "quota_exceeded_time",
                "message": f"Daily time limit reached ({minutes_used}/{minutes_limit} min).",
            })
            await websocket.close(code=1008)
            await redis.aclose()
            return

        # Check weekly minutes (read-only)
        weekly_min_ok, weekly_min_used, weekly_min_limit = await check_weekly_minutes(
            redis, user_id, weekly_minutes_limit
        )
        if not weekly_min_ok:
            logger.info(
                "[conversation] Weekly minutes quota exceeded — user=%s used=%s limit=%s",
                user_id, weekly_min_used, weekly_min_limit,
            )
            await websocket.send_json({
                "type": "error",
                "code": "quota_exceeded_weekly_minutes",
                "message": f"Weekly time limit reached ({weekly_min_used}/{weekly_min_limit} min).",
            })
            await websocket.close(code=1008)
            await redis.aclose()
            return

        # Then check + increment weekly sessions
        sessions_ok, sessions_used, sessions_limit = await check_and_increment_sessions(
            redis, user_id, weekly_sessions_limit
        )
        if not sessions_ok:
            logger.info(
                "[conversation] Weekly session quota exceeded — user=%s used=%s limit=%s",
                user_id, sessions_used, sessions_limit,
            )
            await websocket.send_json({
                "type": "error",
                "code": "quota_exceeded_sessions",
                "message": f"Weekly session limit reached ({sessions_used}/{sessions_limit}).",
            })
            await websocket.close(code=1008)
            await redis.aclose()
            return

        # Cap session max_duration to remaining daily minutes if limited
        if daily_minutes_limit > 0:
            remaining_seconds = (daily_minutes_limit - minutes_used) * 60
            max_duration = min(max_duration, remaining_seconds)
        # Cap session max_duration to remaining weekly minutes if limited
        if weekly_minutes_limit > 0:
            remaining_weekly_seconds = (weekly_minutes_limit - weekly_min_used) * 60
            max_duration = min(max_duration, remaining_weekly_seconds)
    except Exception as exc:
        logger.error("[conversation] Quota check failed: %s", exc)
        await redis.aclose()
        raise

    pipeline = ConversationPipeline(
        llm=llm_adapter,
        tts=tts_service,
        stt=stt_service,
        cefr_level=cefr_level,
        native_language=native_language,
        target_language=target_language,
        student_name=student_name,
        max_duration=max_duration,
        inactivity_timeout=inactivity_timeout,
        initial_context=valid_context,
        user_id=user_id,
        bio=user_bio,
        learning_goals=user_learning_goals,
    )
    pipeline._redis = redis

    try:
        await pipeline.run(websocket)
    except WebSocketDisconnect:
        logger.info("[conversation] WebSocketDisconnect — user=%s", user_id)
    except asyncio.CancelledError:
        logger.info("[conversation] CancelledError — user=%s", user_id)
    finally:
        await pipeline.cleanup()
        await redis.aclose()
        logger.info("[conversation] Session ended — user=%s", user_id)
