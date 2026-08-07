from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.models.dashboard_banner import DashboardBanner
from app.models.user import User
from app.schemas.dashboard_banner import DashboardBannerDismissRequest

router = APIRouter(prefix="/api/dashboard-banner", tags=["dashboard-banner"])


@router.put("/dismiss", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def dismiss_dashboard_banner(
    request: Request,
    data: DashboardBannerDismissRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    banner = await db.scalar(
        select(DashboardBanner)
        .where(DashboardBanner.id == 1, DashboardBanner.is_active.is_(True))
        .with_for_update()
    )
    if banner is None or banner.revision != data.revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dashboard banner revision is stale or invalid",
        )

    if current_user.dismissed_dashboard_banner_revision != data.revision:
        current_user.dismissed_dashboard_banner_revision = data.revision
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
