"""Freemium status endpoint — returns quota and trial state for the current user."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis

from app.core.deps import get_current_user, get_redis
from app.core.limiter import limiter
from app.models.user import User
from app.services.freemium_service import get_freemium_status

router = APIRouter(prefix="/api/freemium", tags=["freemium"])


@router.get("/status")
@limiter.limit("60/minute")
async def freemium_status(
    request: Request,
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> dict:
    status = await get_freemium_status(
        redis,
        current_user.id,
        current_user.freemium_trial_ends_at,
    )
    return {
        "trial_active": status.trial_active,
        "trial_ends_at": status.trial_ends_at,
        "chat_remaining": status.chat_remaining,
        "chat_limit": status.chat_limit,
        "lessons_remaining": status.lessons_remaining,
        "lessons_limit": status.lessons_limit,
        "listening_remaining": status.listening_remaining,
        "listening_limit": status.listening_limit,
        "reading_remaining": status.reading_remaining,
        "reading_limit": status.reading_limit,
        "voice_remaining_seconds": status.voice_remaining_seconds,
        "voice_limit_seconds": status.voice_limit_seconds,
    }
