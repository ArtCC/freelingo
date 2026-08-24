from __future__ import annotations

import asyncio
import struct

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from jwt.exceptions import PyJWTError
from pydantic import BaseModel
from sqlalchemy import select

from app.core.app_logger import get_logger
from app.core.config import settings
from app.core.deps import (
    MAINTENANCE_KEY,
    get_current_user,
    get_redis,
    require_not_maintenance,
)
from app.core.limiter import limiter
from app.core.security import decode_access_token
from app.models.conversation import Conversation as ConversationModel
from app.models.study_plan import StudyPlan
from app.models.user import User
from app.models.user_language import UserLanguage
from app.services.assessment_voice_trial import (
    AssessmentVoiceTrial,
    consume_assessment_voice_trial_token,
    validate_assessment_voice_trial_token,
)
from app.services.conversation_pipeline import ConversationPipeline
from app.services.freemium_service import (
    check_voice_quota,
    is_freemium_trial_active,
)
from app.services.language_helpers import voice_session_title
from app.services.llm_adapter import llm_adapter
from app.services.memory_service import get_user_memories
from app.services.quota_service import check_all_quotas
from app.services.subscription_service import is_subscribed
from app.utils.db import db_session
from app.utils.redis import redis_client as _redis_client

logger = get_logger(__name__)

router = APIRouter(tags=["conversation"])


# ── Shared voice access check ──────────────────────────────────────────────────


async def _check_voice_access(
    user: User,
    redis_client,
    voice_trial_token: str | None = None,
) -> tuple[bool, bool, AssessmentVoiceTrial | None, int]:
    """Check whether a user can access voice conversation.

    Returns (allowed, freemium_ok, voice_trial, freemium_remaining_seconds).
    - allowed: overall access granted
    - freemium_ok: access via freemium voice quota (for usage recording)
    - voice_trial: access via one-time assessment demo (None if not used)
    - freemium_remaining_seconds: remaining seconds when access is via voice quota

    Check order: subscribed → freemium trial → freemium voice quota → assessment trial.
    """
    if is_subscribed(user, settings.STRIPE_ENABLED):
        return True, False, None, 0

    if is_freemium_trial_active(user.freemium_trial_ends_at):
        return True, False, None, 0

    try:
        vq = await check_voice_quota(redis_client, user.id)
        if vq.allowed:
            return True, True, None, vq.remaining
    except Exception:
        logger.exception("[voice_access] Redis unavailable during freemium quota check")

    try:
        trial = await validate_assessment_voice_trial_token(
            redis_client,
            user=user,
            token=voice_trial_token,
            stripe_enabled=settings.STRIPE_ENABLED,
        )
        if trial:
            return True, False, trial, 0
    except Exception:
        logger.exception("[voice_access] Redis unavailable during assessment trial validation")

    return False, False, None, 0


class ConversationWarmupRequest(BaseModel):
    trial_token: str | None = None


def _make_silence_wav(duration_ms: int = 100, sample_rate: int = 16000) -> bytes:
    """Return a minimal valid PCM WAV with silence (for STT warmup)."""
    num_samples = sample_rate * duration_ms // 1000
    data = b"\x00" * (num_samples * 2)  # 16-bit mono
    byte_rate = sample_rate * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(data),
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        byte_rate,
        2,
        16,
        b"data",
        len(data),
    )
    return header + data


@router.post("/api/conversation/warmup")
@limiter.limit("20/minute")
async def conversation_warmup(
    request: Request,
    data: ConversationWarmupRequest | None = None,
    _maintenance: None = Depends(require_not_maintenance),
    current_user: User = Depends(get_current_user),
    redis=Depends(get_redis),
) -> JSONResponse:
    """Pre-heat TTS and STT services before a conversation session starts.

    Awaits model loading synchronously so the caller knows the models are
    ready before opening the WebSocket. The frontend must await this call
    and only then connect the WebSocket.
    """
    allowed, _, _, _ = await _check_voice_access(
        current_user,
        redis,
        voice_trial_token=data.trial_token if data else None,
    )
    if not allowed:
        return JSONResponse({"detail": "subscription_required"}, status_code=402)

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
        # OpenAI TTS warmup is just a lightweight model check; calling health
        # avoids a full synthesis request during session start.
        if hasattr(tts_service, "model"):
            await tts_service.health()  # type: ignore[union-attr]
        else:
            # Local Kokoro benefits from a real synthesis once to warm model
            # caches on first use.
            await tts_service.synthesize("ready")  # type: ignore[union-attr]
        logger.info("[warmup] TTS ready")
    except Exception as exc:
        logger.warning("[warmup] TTS warmup error: %s", exc)


async def _warmup_stt(stt_service: object) -> None:
    try:
        wav = _make_silence_wav()
        await stt_service.transcribe(  # type: ignore[union-attr]
            wav,
            "warmup.wav",
            "audio/wav",
            language="en",
        )
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
        voice_pref: str = auth_msg.get("voice", "") or ""
        voice_trial_token: str | None = auth_msg.get("voice_trial_token")
        target_language_from_client: str | None = auth_msg.get("target_language")
        client_conversation_id_raw = auth_msg.get(
            "conversation_id"
        )  # optional: reserved for future API use
        if settings.TTS_PROVIDER == "openai":
            _VALID_VOICES = frozenset(
                {
                    "alloy",
                    "ash",
                    "coral",
                    "echo",
                    "fable",
                    "nova",
                    "onyx",
                    "sage",
                    "shimmer",
                }
            )
            if voice_pref not in _VALID_VOICES:
                voice_pref = ""
        else:
            voice_pref = ""  # local TTS ignores voice param
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except TimeoutError, PyJWTError, KeyError, ValueError, Exception:  # noqa: BLE001
        logger.warning("[conversation] Auth failed — closing WS 1008")
        await websocket.send_json(
            {"type": "error", "code": "auth_failed", "message": "Authentication failed"}
        )
        await websocket.close(code=1008)
        return

    async with db_session() as db:
        user = await db.get(User, user_id)
        if not user or not user.is_active:
            logger.warning(
                "[conversation] User %s not found or inactive — closing WS 1008",
                user_id,
            )
            await websocket.close(code=1008)
            return

        # Check maintenance mode
        try:
            async with _redis_client() as redis_check:
                maintenance = await redis_check.get(MAINTENANCE_KEY)
            if maintenance == "1" and user.role != "admin":
                logger.info(
                    "[conversation] Maintenance mode active — closing WS for user %s",
                    user_id,
                )
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "maintenance_mode",
                        "message": "Service temporarily unavailable — maintenance mode is active.",
                    }
                )
                await websocket.close(code=1013)
                return
        except Exception:
            pass  # Redis failure → allow through

        # Check subscription, freemium trial, freemium voice quota, or assessment voice trial.
        allowed = False
        voice_trial = None
        freemium_ok = False
        freemium_remaining_seconds = 0
        try:
            async with _redis_client() as redis_access:
                allowed, freemium_ok, voice_trial, freemium_remaining_seconds = (
                    await _check_voice_access(
                        user, redis_access, voice_trial_token=voice_trial_token
                    )
                )
        except Exception:
            logger.exception(
                "[conversation] Redis unavailable during voice access check — blocking"
            )
        if not allowed:
            logger.info(
                "[conversation] User %s has no active subscription — closing WS 1008",
                user_id,
            )
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "subscription_required",
                    "message": "Voice conversation is not available on your current plan.",
                }
            )
            await websocket.close(code=1008)
            return

        # --- Guard: TTS and STT must be enabled ---
        tts_service = getattr(websocket.app.state, "tts_service", None)
        stt_service = getattr(websocket.app.state, "stt_service", None)
        if tts_service is None or stt_service is None:
            logger.warning("[conversation] TTS or STT disabled — rejecting WS for user %s", user_id)
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "services_disabled",
                    "message": "TTS and STT must be enabled for conversation mode.",
                }
            )
            await websocket.close(code=1011)
            return

        # --- CEFR level and target language from active StudyPlan ---
        from app.services.user_language_service import get_active_language

        plan: StudyPlan | None = None
        if target_language_from_client:
            ul_result = await db.execute(
                select(UserLanguage).where(
                    UserLanguage.user_id == user_id,
                    UserLanguage.target_language == target_language_from_client,
                )
            )
            ul = ul_result.scalar_one_or_none()
            if ul:
                plan_result = await db.execute(
                    select(StudyPlan)
                    .where(
                        StudyPlan.user_language_id == ul.id,
                        StudyPlan.is_active == True,  # noqa: E712
                    )
                    .limit(1)
                )
                plan = plan_result.scalar_one_or_none()
        if not plan:
            active_lang = await get_active_language(db, user_id)
            if active_lang:
                result = await db.execute(
                    select(StudyPlan)
                    .where(
                        StudyPlan.user_language_id == active_lang.id,
                        StudyPlan.is_active == True,  # noqa: E712
                    )
                    .limit(1)
                )
                plan = result.scalar_one_or_none()
        if not plan:
            # No plan for the selected language — use A2 + the selected language
            cefr_level = "A2"
            study_plan_id_for_conv = None
            if target_language_from_client:
                target_language = target_language_from_client
            elif active_lang:
                target_language = active_lang.target_language
            else:
                target_language = "en-GB"
        else:
            cefr_level = plan.cefr_level
            if target_language_from_client:
                target_language = target_language_from_client
            else:
                ul_row = await db.execute(
                    select(UserLanguage).where(UserLanguage.id == plan.user_language_id)
                )
                ul = ul_row.scalar_one_or_none()
                target_language = ul.target_language if ul else plan.target_language
            study_plan_id_for_conv = plan.id

        # Read user settings before session closes to avoid DetachedInstanceError
        max_duration = (
            voice_trial.duration_seconds if voice_trial else user.conversation_max_duration
        )
        if freemium_ok and freemium_remaining_seconds > 0:
            max_duration = min(max_duration, freemium_remaining_seconds)
        inactivity_timeout = user.conversation_inactivity_timeout
        native_language = user.native_language
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

    logger.info(
        "[conversation] Session started — user=%s cefr=%s max_duration=%ss inactivity=%ss context_turns=%s",
        user_id,
        cefr_level,
        max_duration,
        inactivity_timeout,
        len(valid_context) if valid_context else 0,
    )
    # (already accepted at the top)

    # --- Quota checks ---
    async with _redis_client() as redis:
        try:
            max_duration, err_code, err_msg, close_code = await check_all_quotas(
                redis,
                user_id,
                monthly_tokens_limit,
                daily_minutes_limit,
                weekly_minutes_limit,
                weekly_sessions_limit,
                max_duration,
            )
            if err_code is not None:
                logger.info(
                    "[conversation] Quota exceeded — user=%s code=%s msg=%s",
                    user_id,
                    err_code,
                    err_msg,
                )
                await websocket.send_json({"type": "error", "code": err_code, "message": err_msg})
                await websocket.close(code=close_code)  # type: ignore[arg-type]
                return
        except Exception as exc:
            logger.error("[conversation] Quota check failed: %s", exc)
            raise

        if voice_trial:
            try:
                async with db_session() as db_trial:
                    trial_user = await db_trial.get(User, user_id)
                    if trial_user:
                        await consume_assessment_voice_trial_token(
                            redis,
                            user=trial_user,
                            token=voice_trial.token,
                        )
                        await db_trial.commit()
            except Exception as exc:
                logger.error("[conversation] Failed to consume voice trial: %s", exc)
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "internal_error",
                        "message": "Failed to initialise trial conversation.",
                    }
                )
                await websocket.close(code=1011)
                return

        # Create or reuse a Conversation record so the full transcript is persisted
        # to the same chat_history table used by text chats — this makes voice
        # sessions visible & reviewable in the tutor chat sidebar.
        # The frontend currently never sends conversation_id, so a new record is
        # always created. The reuse path is kept for future API flexibility.
        conversation_id: int | None = None
        try:
            async with db_session() as db_conv:
                # Reuse path: if a caller explicitly passes a valid conversation_id
                # that belongs to this user, append to that conversation.
                if (
                    isinstance(client_conversation_id_raw, (int, float))
                    and int(client_conversation_id_raw) > 0
                ):
                    existing = await db_conv.get(ConversationModel, int(client_conversation_id_raw))
                    if (
                        existing
                        and existing.user_id == user_id
                        and (
                            not existing.target_language
                            or existing.target_language == target_language
                        )
                    ):
                        conversation_id = existing.id
                if conversation_id is None:
                    conv = ConversationModel(
                        user_id=user_id,
                        title=voice_session_title(native_language),
                        source="voice",
                        study_plan_id=study_plan_id_for_conv,
                        target_language=target_language,
                    )
                    db_conv.add(conv)
                    await db_conv.commit()
                    await db_conv.refresh(conv)
                    conversation_id = conv.id
        except Exception as exc:
            logger.error("[conversation] Failed to create conversation record: %s", exc)
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "internal_error",
                    "message": "Failed to initialise conversation session.",
                }
            )
            await websocket.close(code=1011)
            return

        # Fetch user memories filtered by study plan
        memories = []
        try:
            async with db_session() as db_mem:
                memories = await get_user_memories(db_mem, user_id)
        except Exception:
            pass

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
            conversation_id=conversation_id,
            bio=user_bio,
            learning_goals=user_learning_goals,
            memories=memories,
            voice=voice_pref,
            study_plan_id=study_plan_id_for_conv,
        )
        pipeline._redis = redis
        pipeline._freemium_voice = freemium_ok

        try:
            await pipeline.run(websocket)
        except WebSocketDisconnect:
            logger.info("[conversation] WebSocketDisconnect — user=%s", user_id)
        except asyncio.CancelledError:
            logger.info("[conversation] CancelledError — user=%s", user_id)
        finally:
            await pipeline.cleanup()
            logger.info("[conversation] Session ended — user=%s", user_id)
