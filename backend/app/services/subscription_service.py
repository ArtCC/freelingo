"""Subscription helpers for Phase 5 Stripe integration.

These functions are the single source of truth for subscription access control.
When STRIPE_ENABLED=false every user is considered subscribed (self-hosted mode).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User


def is_subscribed(user: User, stripe_enabled: bool) -> bool:
    """Return True if the user has full access to AI features.

    - stripe_enabled=False  → always True (self-hosted / no paywall)
    - stripe_enabled=True   → only "trialing" or "active" subscriptions pass
    """
    if not stripe_enabled:
        return True
    return user.subscription_status in ("trialing", "active")


async def apply_subscription_quotas(user: User, db: AsyncSession) -> None:
    """Set default quotas when a subscription becomes active or trialing."""
    user.conversation_weekly_sessions = settings.DEFAULT_CONVERSATION_WEEKLY_SESSIONS
    user.conversation_weekly_minutes = settings.DEFAULT_CONVERSATION_WEEKLY_MINUTES
    user.conversation_daily_minutes = settings.DEFAULT_CONVERSATION_DAILY_MINUTES
    user.monthly_tokens_limit = settings.DEFAULT_MONTHLY_TOKENS_LIMIT
    user.conversation_max_duration = settings.DEFAULT_CONVERSATION_MAX_DURATION
    user.conversation_inactivity_timeout = settings.DEFAULT_CONVERSATION_INACTIVITY_TIMEOUT
    await db.commit()
