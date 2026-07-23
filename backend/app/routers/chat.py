import json
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.app_logger import get_logger
from app.core.database import get_db
from app.core.deps import (
    get_active_study_plan_optional,
    require_not_maintenance,
    require_subscription_or_freemium,
    require_subscription_or_freemium_readonly,
)
from app.core.limiter import limiter
from app.models.chat_history import ChatHistory
from app.models.conversation import Conversation
from app.models.llm_usage import LLMUsage
from app.models.progress import Progress
from app.models.user import User
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatRequest,
    ConversationCreate,
    ConversationResponse,
)
from app.services.language_helpers import get_language_name, get_native_language_name
from app.services.llm_adapter import (
    LLMError,
    LLMStream,
    LLMTimeoutError,
    LLMUnavailableError,
    llm_adapter,
)
from app.services.memory_service import (
    build_memory_context,
    get_user_memories,
    parse_memory_marker,
    save_memories,
    strip_memory_marker,
)
from app.services.prompts.common import get_language_prompt_overlay
from app.services.prompts.tutor import build_tutor_system_prompt

router = APIRouter(prefix="/api/chat", tags=["chat"])

logger = get_logger(__name__)


def _build_tutor_system_prompt(
    *,
    student_name: str,
    cefr_level: str,
    native_language: str,
    target_language_name: str,
    total_xp: int,
    streak: int,
    lessons_today: int,
    skills: str,
    user_context: str,
    memory_context: str,
    language_prompt_overlay: str = "",
) -> str:
    return build_tutor_system_prompt(
        student_name=student_name,
        cefr_level=cefr_level,
        native_language=native_language,
        target_language_name=target_language_name,
        total_xp=total_xp,
        streak=streak,
        lessons_today=lessons_today,
        skills=skills,
        user_context=user_context,
        memory_context=memory_context,
        language_prompt_overlay=language_prompt_overlay,
    )


MAX_HISTORY = 30
DEFAULT_CEFR = "A2"
DEFAULT_TARGET_LANG = "en-GB"


async def _resolve_chat_context(
    db: AsyncSession,
    user: User,
) -> tuple[str, str, int | None]:
    """Resolve CEFR level, target language, and study_plan_id for chat.

    Only uses the active language's plan. If none exists, defaults to A2
    and the active language's code. Never falls back to another language's
    plan — that would make the tutor speak the wrong language.
    """
    from app.services.user_language_service import get_active_language

    # Try active study plan for the active language
    plan = await get_active_study_plan_optional(user, db)
    if plan:
        return plan.cefr_level, plan.target_language, plan.id

    # No plan — use active language's code or default
    active_lang = await get_active_language(db, user.id)
    target_language = active_lang.target_language if active_lang else DEFAULT_TARGET_LANG
    return DEFAULT_CEFR, target_language, None


# ── Conversations ────────────────────────────────────────────────────────────


@router.get("/conversations", response_model=list[ConversationResponse])
@limiter.limit("60/minute")
async def list_conversations(
    request: Request,
    _maintenance: None = Depends(require_not_maintenance),
    current_user: User = Depends(require_subscription_or_freemium_readonly("chat")),
    db: AsyncSession = Depends(get_db),
):
    # Filter conversations by the active language (not study plan)
    from app.services.user_language_service import get_active_language

    active_lang = await get_active_language(db, current_user.id)
    if not active_lang:
        return []
    where_clause = (Conversation.user_id == current_user.id) & (
        Conversation.target_language == active_lang.target_language
    )

    result = await db.execute(
        select(Conversation).where(where_clause).order_by(Conversation.updated_at.desc())
    )
    return result.scalars().all()


@router.post("/conversations", response_model=ConversationResponse)
@limiter.limit("60/minute")
async def create_conversation(
    request: Request,
    data: ConversationCreate,
    _maintenance: None = Depends(require_not_maintenance),
    current_user: User = Depends(require_subscription_or_freemium_readonly("chat")),
    db: AsyncSession = Depends(get_db),
):
    plan = await get_active_study_plan_optional(current_user, db)
    from app.services.user_language_service import get_active_language

    active_lang = await get_active_language(db, current_user.id)
    target_language = active_lang.target_language if active_lang else DEFAULT_TARGET_LANG
    conv = Conversation(
        user_id=current_user.id,
        title=data.title or "New conversation",
        study_plan_id=plan.id if plan else None,
        target_language=target_language,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_conversation(
    request: Request,
    conversation_id: int,
    _maintenance: None = Depends(require_not_maintenance),
    current_user: User = Depends(require_subscription_or_freemium_readonly("chat")),
    db: AsyncSession = Depends(get_db),
):
    conv = await db.get(Conversation, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    # Verify conversation belongs to the current active language
    from app.services.user_language_service import get_active_language

    active_lang = await get_active_language(db, current_user.id)
    if active_lang and conv.target_language and conv.target_language != active_lang.target_language:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    await db.delete(conv)
    await db.commit()


@router.get("/conversations/{conversation_id}/messages", response_model=ChatHistoryResponse)
@limiter.limit("60/minute")
async def get_conversation_messages(
    request: Request,
    conversation_id: int,
    _maintenance: None = Depends(require_not_maintenance),
    current_user: User = Depends(require_subscription_or_freemium_readonly("chat")),
    db: AsyncSession = Depends(get_db),
):
    conv = await db.get(Conversation, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    # Filter messages by active language (not study plan)
    from app.services.user_language_service import get_active_language

    active_lang = await get_active_language(db, current_user.id)
    if not active_lang:
        return ChatHistoryResponse(messages=[])
    where_clause = (
        (ChatHistory.conversation_id == conversation_id)
        & (ChatHistory.user_id == current_user.id)
        & (ChatHistory.target_language == active_lang.target_language)
    )
    result = await db.execute(
        select(ChatHistory)
        .where(where_clause)
        .order_by(ChatHistory.created_at.asc())
        .limit(MAX_HISTORY)
    )
    messages = [{"role": m.role, "content": m.content} for m in result.scalars().all()]
    return ChatHistoryResponse(messages=messages)


# ── Chat (streaming) ─────────────────────────────────────────────────────────


@router.post("")
@limiter.limit("30/minute")
async def chat(
    request: Request,
    request_data: ChatRequest,
    _maintenance: None = Depends(require_not_maintenance),
    current_user: User = Depends(require_subscription_or_freemium("chat")),
    db: AsyncSession = Depends(get_db),
):
    if current_user.monthly_tokens_limit > 0:
        from app.services.quota_service import check_monthly_tokens  # noqa: PLC0415

        allowed, tokens_used, token_limit = await check_monthly_tokens(
            db, current_user.id, current_user.monthly_tokens_limit
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Monthly token limit reached ({tokens_used}/{token_limit} tokens). Chat is unavailable until next month.",
            )

    cefr_level, target_language, study_plan_id = await _resolve_chat_context(db, current_user)

    # Resolve or create conversation
    if request_data.conversation_id:
        conv = await db.get(Conversation, request_data.conversation_id)
        if not conv or conv.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )
        if conv.target_language and conv.target_language != target_language:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )
    else:
        # Auto-create a conversation titled with the first 60 chars of the message
        title = request_data.message[:60].replace("\n", " ").replace("\r", "").strip()
        if len(request_data.message) > 60:
            title += "..."
        conv = Conversation(
            user_id=current_user.id,
            title=title,
            study_plan_id=study_plan_id,
            target_language=target_language,
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)

    conversation_id = conv.id

    if study_plan_id:
        prog_result = await db.execute(
            select(Progress).where(
                Progress.study_plan_id == study_plan_id,
                Progress.date == date.today(),
            )
        )
        prog = prog_result.scalar_one_or_none()
        total_xp_result = await db.execute(
            select(Progress).where(Progress.study_plan_id == study_plan_id)
        )
        total_xp = sum(p.xp_earned for p in total_xp_result.scalars().all())
        skills_str = (
            ", ".join(f"{k}: {round(v * 100)}%" for k, v in (prog.skills or {}).items())
            if prog and prog.skills
            else "none yet"
        )
        streak = prog.streak_day if prog else 0
        lessons_today = prog.lessons_completed if prog else 0
    else:
        total_xp = 0
        skills_str = "none yet"
        streak = 0
        lessons_today = 0
        prog = None

    # Build user context section from bio and learning goals
    _ctx_parts: list[str] = []
    if current_user.learning_goals:
        try:
            import json as _json  # noqa: PLC0415

            goals = _json.loads(current_user.learning_goals)
            if goals:
                _ctx_parts.append(f"Learning goals: {', '.join(goals)}")
        except ValueError, TypeError:
            pass
    if current_user.bio and current_user.bio.strip():
        _ctx_parts.append(f"About the student: {current_user.bio.strip()}")
    user_context = (
        ("\nStudent context:\n" + "\n".join(f"- {p}" for p in _ctx_parts) + "\n")
        if _ctx_parts
        else ""
    )

    memories = await get_user_memories(db, current_user.id, study_plan_id=study_plan_id)
    memory_context = build_memory_context(memories)

    target_language_name = get_language_name(target_language)
    language_prompt_overlay = get_language_prompt_overlay(target_language)

    system_prompt = _build_tutor_system_prompt(
        student_name=current_user.display_name,
        cefr_level=cefr_level,
        native_language=get_native_language_name(current_user.native_language),
        target_language_name=target_language_name,
        total_xp=total_xp,
        streak=streak,
        lessons_today=lessons_today,
        skills=skills_str,
        user_context=user_context,
        memory_context=memory_context,
        language_prompt_overlay=language_prompt_overlay,
    )

    db.add(
        ChatHistory(
            user_id=current_user.id,
            conversation_id=conversation_id,
            role="user",
            content=request_data.message,
            study_plan_id=study_plan_id,
            target_language=target_language,
        )
    )
    await db.commit()

    result = await db.execute(
        select(ChatHistory)
        .where(
            ChatHistory.user_id == current_user.id,
            ChatHistory.conversation_id == conversation_id,
        )
        .order_by(ChatHistory.created_at.desc())
        .limit(MAX_HISTORY)
    )
    db_messages = list(result.scalars().all())
    db_messages.reverse()

    messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m.role, "content": m.content} for m in db_messages
    ]

    async def event_stream():
        full_response = ""
        sent_len = 0
        memory_block_active = False
        try:
            yield f"data: {json.dumps({'conversation_id': conversation_id})}\n\n"
            stream = await llm_adapter.chat(messages, stream=True)
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response += token

                    if memory_block_active:
                        mem_end = full_response.find("<<ENDMEMORY>>", sent_len)
                        if mem_end != -1:
                            memory_block_active = False
                            sent_len = mem_end + len("<<ENDMEMORY>>")
                        else:
                            continue

                    marker_start = full_response.find("<<MEMORY>>", sent_len)
                    if marker_start != -1:
                        clean_up_to_marker = full_response[:marker_start]
                        if len(clean_up_to_marker) > sent_len:
                            unsent = clean_up_to_marker[sent_len:]
                            yield f"data: {json.dumps({'token': unsent})}\n\n"
                        sent_len = marker_start
                        memory_block_active = True
                        continue

                    # Withhold any trailing partial <<MEMORY>> prefix to avoid leaking
                    # it to the frontend before the complete marker is assembled
                    _marker = "<<MEMORY>>"
                    safe_len = len(full_response)
                    for _pi in range(len(_marker), 0, -1):
                        if full_response.endswith(_marker[:_pi]):
                            safe_len = len(full_response) - _pi
                            break
                    if safe_len > sent_len:
                        unsent = full_response[sent_len:safe_len]
                        yield f"data: {json.dumps({'token': unsent})}\n\n"
                        sent_len = safe_len

            # Strip memory marker before saving to DB
            clean_response = strip_memory_marker(full_response)
            # Ensure we sent all clean text to the frontend
            if len(clean_response) > sent_len:
                unsent = clean_response[sent_len:]
                yield f"data: {json.dumps({'token': unsent})}\n\n"

            db.add(
                ChatHistory(
                    user_id=current_user.id,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=clean_response,
                    study_plan_id=study_plan_id,
                    target_language=target_language,
                )
            )
            conv.updated_at = datetime.now(UTC).replace(tzinfo=None)
            await db.commit()

            memory_items = parse_memory_marker(full_response)
            memory_updated = False
            if memory_items:
                try:
                    saved = await save_memories(
                        db,
                        current_user.id,
                        memory_items,
                        "chat",
                        study_plan_id=study_plan_id,
                    )
                    if saved:
                        memory_updated = True
                except Exception:
                    await db.rollback()
                    logger.debug("Failed to save memories — ignored")

            if memory_updated:
                yield f"data: {json.dumps({'memory_updated': True})}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"

            # Record freemium chat usage (best-effort)
            from app.services.freemium_service import maybe_record_freemium_usage

            await maybe_record_freemium_usage(current_user, "chat")

            # Persist token usage best-effort in a separate transaction
            if isinstance(stream, LLMStream) and (
                stream.prompt_tokens is not None or stream.completion_tokens is not None
            ):
                try:
                    db.add(
                        LLMUsage(
                            user_id=current_user.id,
                            source="chat",
                            prompt_tokens=stream.prompt_tokens,
                            completion_tokens=stream.completion_tokens,
                            total_tokens=stream.total_tokens,
                            study_plan_id=study_plan_id,
                        )
                    )
                    await db.commit()
                except Exception:
                    await db.rollback()
                    logger.debug("Failed to save LLM usage — ignored")
        except LLMTimeoutError:
            logger.warning(
                "LLM timeout for user %s conversation %s",
                current_user.id,
                conversation_id,
            )
            yield f"data: {json.dumps({'error': 'The AI model took too long. Please try again.'})}\n\n"
        except LLMUnavailableError:
            logger.error("LLM unavailable for user %s", current_user.id)
            yield f"data: {json.dumps({'error': 'The AI service is currently unavailable.'})}\n\n"
        except LLMError:
            logger.exception(
                "LLM error for user %s conversation %s",
                current_user.id,
                conversation_id,
            )
            yield f"data: {json.dumps({'error': 'Something went wrong. Please try again.'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Legacy history endpoint (kept for backwards compat) ──────────────────────


@router.get("/history", response_model=ChatHistoryResponse)
@limiter.limit("60/minute")
async def get_history(
    request: Request,
    _maintenance: None = Depends(require_not_maintenance),
    current_user: User = Depends(require_subscription_or_freemium_readonly("chat")),
    db: AsyncSession = Depends(get_db),
):
    # Filter history by active language (not study plan)
    from app.services.user_language_service import get_active_language

    active_lang = await get_active_language(db, current_user.id)
    if not active_lang:
        return ChatHistoryResponse(messages=[])
    where_clause = (ChatHistory.user_id == current_user.id) & (
        ChatHistory.target_language == active_lang.target_language
    )
    result = await db.execute(
        select(ChatHistory)
        .where(where_clause)
        .order_by(ChatHistory.created_at.asc())
        .limit(MAX_HISTORY)
    )
    messages = [{"role": m.role, "content": m.content} for m in result.scalars().all()]
    return ChatHistoryResponse(messages=messages)
