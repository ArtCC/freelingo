from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import PyJWTError as JWTError
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.study_plan import StudyPlan
from app.models.user import User
from app.services.subscription_service import is_subscribed

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

MAINTENANCE_KEY = "maintenance_mode"


async def get_redis():
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except JWTError, KeyError, ValueError:
        raise HTTPException(status_code=401, detail="Invalid token") from None

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


async def check_maintenance_mode(redis: Redis = Depends(get_redis)) -> None:
    """Raise 503 if maintenance mode is active in Redis."""
    try:
        if await redis.get(MAINTENANCE_KEY) == "1":
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable — maintenance mode is active",
            )
    except HTTPException:
        raise
    except Exception:
        pass  # Redis failure → allow through


async def require_subscription(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency for endpoints gated by subscription.

    Returns the user unchanged when STRIPE_ENABLED=false (self-hosted mode).
    Raises HTTP 402 when STRIPE_ENABLED=true and user has no active subscription.
    """
    if not is_subscribed(current_user, settings.STRIPE_ENABLED):
        raise HTTPException(status_code=402, detail="subscription_required")
    return current_user


def require_subscription_or_freemium(feature: str):
    """Factory that returns a FastAPI dependency checking subscription OR freemium quota.

    When STRIPE_ENABLED=false the user always passes (self-hosted mode).
    When STRIPE_ENABLED=true the check follows this order:
      1. Subscribed (trialing/active) → allowed
      2. Freemium trial active → allowed
      3. Freemium quota available for *feature* → allowed
      4. Otherwise → 402 with freemium_exhausted detail

    *feature* must be one of: chat, lessons, listening, reading, voice.
    """

    async def _check(
        redis: Redis = Depends(get_redis),
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not settings.STRIPE_ENABLED:
            return current_user

        if is_subscribed(current_user, settings.STRIPE_ENABLED):
            return current_user

        from app.services.freemium_service import is_freemium_trial_active

        if is_freemium_trial_active(current_user.freemium_trial_ends_at):
            return current_user

        try:
            from app.services.freemium_service import (
                check_chat_quota,
                check_lesson_quota,
                check_listening_quota,
                check_reading_quota,
                check_voice_quota,
            )

            check_map = {
                "chat": check_chat_quota,
                "lessons": check_lesson_quota,
                "listening": check_listening_quota,
                "reading": check_reading_quota,
                "voice": check_voice_quota,
            }
            checker = check_map.get(feature)
            if checker is None:
                raise HTTPException(status_code=402, detail="subscription_required")

            result = await checker(redis, current_user.id)
            if not result.allowed:
                raise HTTPException(
                    status_code=402,
                    detail={
                        "reason": "freemium_exhausted",
                        "feature": feature,
                        "remaining": result.remaining,
                        "limit": result.limit,
                    },
                )
        except HTTPException:
            raise
        except Exception:
            # Redis unavailable or other error → block access safely
            raise HTTPException(status_code=402, detail="subscription_required") from None

        return current_user

    return _check


async def require_not_maintenance(
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> None:
    """Dependency for operational features disabled during maintenance mode."""
    if current_user.role != "admin":
        await check_maintenance_mode(redis)


async def get_active_study_plan(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyPlan:
    """Return the active study plan for the user's active language."""
    from app.services.user_language_service import get_active_language

    active_lang = await get_active_language(db, current_user.id)
    if not active_lang:
        raise HTTPException(status_code=404, detail="No active language set")

    result = await db.execute(
        select(StudyPlan).where(
            StudyPlan.user_language_id == active_lang.id,
            StudyPlan.is_active == True,  # noqa: E712
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="No active study plan found")
    return plan


async def get_active_study_plan_optional(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyPlan | None:
    """Return the active study plan, or None if no plan exists yet."""
    from app.services.user_language_service import get_active_language

    active_lang = await get_active_language(db, current_user.id)
    if not active_lang:
        return None

    result = await db.execute(
        select(StudyPlan).where(
            StudyPlan.user_language_id == active_lang.id,
            StudyPlan.is_active == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()
