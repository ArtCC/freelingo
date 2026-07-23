"""Freemium quota and trial helpers backed by Redis.

When STRIPE_ENABLED=true and a user is not subscribed:
- Quota counters in Redis with TTL-based auto-reset:
  - freemium:chat:{user_id}:{YYYY-MM-DD}       → daily chat messages (midnight reset)
  - freemium:lessons:{user_id}:{YYYY-MM-DD}     → daily lessons (midnight reset)
  - freemium:listening:{user_id}:{YYYY-Www}     → weekly listening exercises (Monday reset)
  - freemium:reading:{user_id}:{YYYY-Www}       → weekly reading exercises (Monday reset)
  - freemium:voice:{user_id}:{YYYY-Www}         → weekly voice seconds (Monday reset)
- A counter value of 0 means the user hasn't used any quota yet.
- When a counter exceeds the configured limit the feature is blocked.

A user with an active freemium trial (freemium_trial_ends_at in the future)
gets unlimited access — no quota checks apply.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis

from app.core.config import settings


def _day_key(user_id: int) -> str:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"freemium:chat:{user_id}:{today}"


def _lessons_day_key(user_id: int) -> str:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"freemium:lessons:{user_id}:{today}"


def _listening_week_key(user_id: int) -> str:
    now = datetime.now(UTC)
    year, week, _ = now.isocalendar()
    return f"freemium:listening:{user_id}:{year}-W{week:02d}"


def _reading_week_key(user_id: int) -> str:
    now = datetime.now(UTC)
    year, week, _ = now.isocalendar()
    return f"freemium:reading:{user_id}:{year}-W{week:02d}"


def _voice_week_key(user_id: int) -> str:
    now = datetime.now(UTC)
    year, week, _ = now.isocalendar()
    return f"freemium:voice:{user_id}:{year}-W{week:02d}"


def _seconds_until_midnight() -> int:
    now = datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(int((tomorrow - now).total_seconds()), 1)


def _seconds_until_monday() -> int:
    now = datetime.now(UTC)
    days_ahead = 7 - now.weekday()
    next_monday = (now + timedelta(days=days_ahead)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(int((next_monday - now).total_seconds()), 1)


@dataclass(frozen=True)
class QuotaResult:
    allowed: bool
    remaining: int
    limit: int


# ── Trial helpers ──────────────────────────────────────────────────────────────


def is_freemium_trial_active(freemium_trial_ends_at: datetime | None) -> bool:
    """Check whether the user currently has an active freemium trial.

    freemium_trial_ends_at is stored as a naive UTC datetime in the database
    (set via datetime.now(UTC).replace(tzinfo=None) on registration). The comparison
    strips tzinfo from datetime.now(UTC) to keep both operands timezone-naive,
    which produces the correct result as long as both sides represent UTC.
    """
    if not settings.STRIPE_ENABLED:
        return False
    if not settings.FREEMIUM_TRIAL_ENABLED:
        return False
    if freemium_trial_ends_at is None:
        return False
    return freemium_trial_ends_at > datetime.now(UTC).replace(tzinfo=None)


# ── Quota-check helpers ────────────────────────────────────────────────────────


async def _check_daily_quota(
    redis: Redis,
    key_fn,
    user_id: int,
    limit: int,
) -> QuotaResult:
    """Generic daily quota check. Increments the counter only in record_* functions."""
    used = int((await redis.get(key_fn(user_id))) or 0)
    remaining = max(limit - used, 0)
    return QuotaResult(
        allowed=remaining > 0,
        remaining=remaining,
        limit=limit,
    )


async def _check_weekly_quota(
    redis: Redis,
    key_fn,
    user_id: int,
    limit: int,
) -> QuotaResult:
    used = int((await redis.get(key_fn(user_id))) or 0)
    remaining = max(limit - used, 0)
    return QuotaResult(
        allowed=remaining > 0,
        remaining=remaining,
        limit=limit,
    )


async def check_chat_quota(redis: Redis, user_id: int) -> QuotaResult:
    return await _check_daily_quota(redis, _day_key, user_id, settings.FREEMIUM_CHAT_DAILY_MESSAGES)


async def check_lesson_quota(redis: Redis, user_id: int) -> QuotaResult:
    return await _check_daily_quota(
        redis, _lessons_day_key, user_id, settings.FREEMIUM_LESSONS_DAILY
    )


async def check_listening_quota(redis: Redis, user_id: int) -> QuotaResult:
    return await _check_weekly_quota(
        redis, _listening_week_key, user_id, settings.FREEMIUM_LISTENING_WEEKLY
    )


async def check_reading_quota(redis: Redis, user_id: int) -> QuotaResult:
    return await _check_weekly_quota(
        redis, _reading_week_key, user_id, settings.FREEMIUM_READING_WEEKLY
    )


async def check_voice_quota(redis: Redis, user_id: int) -> QuotaResult:
    return await _check_weekly_quota(
        redis, _voice_week_key, user_id, settings.FREEMIUM_VOICE_WEEKLY_MINUTES * 60
    )


# ── Record usage ───────────────────────────────────────────────────────────────


_INCR_WITH_TTL_LUA = """
local val = redis.call('INCRBY', KEYS[1], ARGV[1])
redis.call('EXPIRE', KEYS[1], ARGV[2])
return val
"""


async def _incr_with_ttl(redis: Redis, key: str, amount: int, ttl_seconds: int) -> int:
    """Atomically increment a counter and set its TTL using a Lua script."""
    return int(
        await redis.eval(
            _INCR_WITH_TTL_LUA,
            1,
            key,
            str(amount),
            str(ttl_seconds),
        )
    )


async def record_chat_usage(redis: Redis, user_id: int) -> int:
    return await _incr_with_ttl(redis, _day_key(user_id), 1, _seconds_until_midnight())


async def record_lesson_usage(redis: Redis, user_id: int) -> int:
    return await _incr_with_ttl(redis, _lessons_day_key(user_id), 1, _seconds_until_midnight())


async def record_listening_usage(redis: Redis, user_id: int) -> int:
    return await _incr_with_ttl(redis, _listening_week_key(user_id), 1, _seconds_until_monday())


async def record_reading_usage(redis: Redis, user_id: int) -> int:
    return await _incr_with_ttl(redis, _reading_week_key(user_id), 1, _seconds_until_monday())


async def record_voice_usage(redis: Redis, user_id: int, seconds: int) -> int:
    return await _incr_with_ttl(redis, _voice_week_key(user_id), seconds, _seconds_until_monday())


# ── Quota status for frontend ──────────────────────────────────────────────────


@dataclass(frozen=True)
class FreemiumStatus:
    trial_active: bool
    trial_ends_at: str | None
    chat_remaining: int
    chat_limit: int
    lessons_remaining: int
    lessons_limit: int
    listening_remaining: int
    listening_limit: int
    reading_remaining: int
    reading_limit: int
    voice_remaining_seconds: int
    voice_limit_seconds: int


async def get_freemium_status(
    redis: Redis,
    user_id: int,
    freemium_trial_ends_at: datetime | None,
) -> FreemiumStatus:
    trial_active = is_freemium_trial_active(freemium_trial_ends_at)

    chat = await check_chat_quota(redis, user_id)
    lessons = await check_lesson_quota(redis, user_id)
    listening = await check_listening_quota(redis, user_id)
    reading = await check_reading_quota(redis, user_id)
    voice = await check_voice_quota(redis, user_id)

    trial_ends_str = None
    if freemium_trial_ends_at:
        trial_ends_str = freemium_trial_ends_at.isoformat()

    return FreemiumStatus(
        trial_active=trial_active,
        trial_ends_at=trial_ends_str,
        chat_remaining=chat.remaining,
        chat_limit=chat.limit,
        lessons_remaining=lessons.remaining,
        lessons_limit=lessons.limit,
        listening_remaining=listening.remaining,
        listening_limit=listening.limit,
        reading_remaining=reading.remaining,
        reading_limit=reading.limit,
        voice_remaining_seconds=voice.remaining,
        voice_limit_seconds=voice.limit,
    )
