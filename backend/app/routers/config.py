"""Public configuration endpoint.

Returns runtime flags the frontend needs to decide UI behaviour
(e.g. whether to show the pricing/billing section).
No sensitive information is exposed.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import MAINTENANCE_KEY, get_redis
from app.core.limiter import limiter
from app.models.dashboard_banner import DashboardBanner

router = APIRouter(tags=["config"])


@router.get("/api/config")
@limiter.limit("60/minute")
async def get_config(
    request: Request,  # noqa: ARG001
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return public runtime configuration flags."""
    maintenance_mode = False
    try:
        maintenance_mode = await redis.get(MAINTENANCE_KEY) == "1"
    except Exception:
        pass

    banner = await db.get(DashboardBanner, 1)
    public_banner = None
    if banner is not None and banner.is_active:
        public_banner = {
            "revision": banner.revision,
            "translations": banner.translations,
        }

    return {
        "stripe_enabled": settings.STRIPE_ENABLED,
        "stripe_trial_days": settings.STRIPE_TRIAL_DAYS,
        "freemium_trial_enabled": settings.FREEMIUM_TRIAL_ENABLED,
        "tts_provider": settings.TTS_PROVIDER,
        "openai_tts_voice": settings.OPENAI_TTS_VOICE,
        "maintenance_mode": maintenance_mode,
        "price_monthly": settings.PRICE_MONTHLY,
        "price_yearly": settings.PRICE_YEARLY,
        "total_price_monthly": settings.TOTAL_PRICE_MONTHLY,
        "total_price_yearly": settings.TOTAL_PRICE_YEARLY,
        "dashboard_banner": public_banner,
    }
