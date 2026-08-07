from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.limiter import limiter
from app.models.dashboard_banner import DashboardBanner
from app.models.user import User
from app.schemas.dashboard_banner import (
    DashboardBannerAdminResponse,
    DashboardBannerTranslateRequest,
    DashboardBannerTranslationResponse,
    DashboardBannerUpdate,
)
from app.services.llm_adapter import LLMError, llm_adapter

router = APIRouter(prefix="/api/admin/dashboard-banner", tags=["admin"])

_TRANSLATION_PROMPT = """Translate this dashboard announcement faithfully into all ten requested locales.
Return en, es, fr, pt, de, it, ru, nl, pl, and ro. Preserve the original tone and meaning.
Do not add claims, details, formatting, Markdown, or HTML. Every field must contain plain text only.
For the source locale, copy each provided field exactly.

Source locale: {source_locale}
Title: {title}
Subtitle: {subtitle}
Description: {description}
"""


@router.get("", response_model=DashboardBannerAdminResponse | None)
@limiter.limit("60/minute")
async def get_dashboard_banner(
    request: Request,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await db.get(DashboardBanner, 1)


@router.post("/translate", response_model=DashboardBannerTranslationResponse)
@limiter.limit("10/minute")
async def translate_dashboard_banner(
    request: Request,
    data: DashboardBannerTranslateRequest,
    _admin: User = Depends(require_admin),
):
    prompt = _TRANSLATION_PROMPT.format(**data.model_dump())
    try:
        result = await llm_adapter.structured_output(
            [{"role": "user", "content": prompt}],
            DashboardBannerTranslationResponse,
        )
    except LLMError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not translate dashboard banner",
        ) from None

    translations = result.translations.model_dump()
    translations[data.source_locale] = {
        "title": data.title,
        "subtitle": data.subtitle,
        "description": data.description,
    }
    return DashboardBannerTranslationResponse(translations=translations)


@router.put("", response_model=DashboardBannerAdminResponse)
@limiter.limit("60/minute")
async def update_dashboard_banner(
    request: Request,
    data: DashboardBannerUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Serialize creation as well as updates; a missing singleton row cannot itself be row-locked.
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(500050)"))

    banner = await db.scalar(
        select(DashboardBanner).where(DashboardBanner.id == 1).with_for_update()
    )
    translations = data.translations.model_dump()
    if banner is None:
        banner = DashboardBanner(
            id=1,
            source_locale=data.source_locale,
            is_active=data.is_active,
            translations=translations,
            revision=1,
        )
        db.add(banner)
    else:
        content_changed = (
            banner.source_locale != data.source_locale or banner.translations != translations
        )
        banner.source_locale = data.source_locale
        banner.is_active = data.is_active
        banner.translations = translations
        if content_changed:
            banner.revision += 1

    await db.commit()
    await db.refresh(banner)
    return banner
