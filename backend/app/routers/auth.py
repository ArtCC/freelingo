import base64
import json
import os
import uuid
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.app_logger import get_logger
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, get_redis
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    dummy_verify,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.models.user_language import UserLanguage
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.services import email_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
@limiter.limit("5/minute")
async def register(
    request: Request,
    data: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    if not settings.ALLOW_REGISTRATION:
        if data.invite_token:
            valid = await redis.get(f"invite:{data.invite_token}")
            if not valid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid or expired invite",
                )
            await redis.delete(f"invite:{data.invite_token}")
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Registration is closed"
            )
    else:
        pass

    if settings.BLOCKED_EMAIL_DOMAINS:
        email_domain = data.email.split("@")[-1].lower()
        if email_domain in [d.lower() for d in settings.BLOCKED_EMAIL_DOMAINS]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Email domain not allowed",
            )

    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    email_check = await db.execute(select(User).where(User.email == data.email))
    if email_check.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already taken")

    user_count = await db.scalar(select(func.count(User.id)))
    role = "admin" if (user_count == 0 and settings.FIRST_USER_IS_ADMIN) else "user"

    user = User(
        username=data.username,
        email=data.email,
        display_name=data.display_name or data.username,
        hashed_password=hash_password(data.password),
        native_language=data.native_language,
        target_language=data.target_language,
        role=role,
        is_active=True,
        is_verified=not settings.EMAIL_ENABLED,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Start freemium trial for new users when STRIPE_ENABLED and FREEMIUM_TRIAL_ENABLED
    if settings.STRIPE_ENABLED and settings.FREEMIUM_TRIAL_ENABLED:
        from datetime import timedelta

        user.freemium_trial_ends_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
            days=settings.FREEMIUM_TRIAL_DAYS
        )
        user.freemium_trial_used = True
        await db.commit()

    # UserLanguage is created during onboarding when the user picks a language.

    # Auto-login: issue tokens so the frontend can redirect to /onboarding
    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token()

    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis.setex(f"refresh:{refresh_token}", ttl, str(user.id))

    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=ttl,
    )

    # Send verification email asynchronously (fire-and-forget style — errors are logged, not raised)
    if user.email and settings.EMAIL_ENABLED:
        verify_token = str(uuid.uuid4())
        await redis.setex(f"verify_email:{verify_token}", 86400, str(user.id))  # 24h
        await email_service.send_verification_email(
            user.email, user.display_name, verify_token, locale=user.native_language
        )
        await email_service.send_welcome_email(
            user.email, user.display_name, locale=user.native_language
        )

    return RegisterResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        access_token=access_token,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    # Always run bcrypt to prevent timing-based user enumeration
    if user:
        password_ok = verify_password(data.password, user.hashed_password)
    else:
        dummy_verify()
        password_ok = False

    if not password_ok or not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user.last_login = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token()

    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis.setex(f"refresh:{refresh_token}", ttl, str(user.id))

    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=ttl,
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("60/minute")
async def refresh(
    request: Request,
    response: Response,
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token"
        )

    user_id = await redis.get(f"refresh:{token}")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    await redis.delete(f"refresh:{token}")

    new_refresh = create_refresh_token()
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis.setex(f"refresh:{new_refresh}", ttl, user_id)

    response.set_cookie(
        "refresh_token",
        new_refresh,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=ttl,
    )

    user = await db.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return {
        "access_token": create_access_token(user.id, user.role),
        "token_type": "bearer",
    }


@router.post("/logout")
@limiter.limit("60/minute")
async def logout(
    request: Request,
    response: Response,
    redis: Redis = Depends(get_redis),
):
    token = request.cookies.get("refresh_token")
    if token:
        await redis.delete(f"refresh:{token}")
    response.delete_cookie("refresh_token")
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserResponse)
@limiter.limit("60/minute")
async def get_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Auto-activate freemium trial for eligible existing users who registered
    # before the freemium launch. One-time, best-effort — if DB write fails,
    # the user still gets in (the trial is re-evaluated on the next request).
    try:
        if (
            settings.STRIPE_ENABLED
            and settings.FREEMIUM_TRIAL_ENABLED
            and current_user.freemium_trial_ends_at is None
            and not current_user.freemium_trial_used
            and current_user.subscription_status not in ("active", "trialing")
        ):
            from datetime import UTC, datetime, timedelta

            current_user.freemium_trial_ends_at = datetime.now(UTC).replace(
                tzinfo=None
            ) + timedelta(days=settings.FREEMIUM_TRIAL_DAYS)
            current_user.freemium_trial_used = True
            await db.commit()
    except Exception:
        pass  # best-effort, user still gets in

    return current_user


@router.patch("/me", response_model=UserResponse)
@limiter.limit("60/minute")
async def update_me(
    request: Request,
    data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.display_name is not None:
        current_user.display_name = data.display_name
    if data.email is not None and data.email != current_user.email:
        dup = await db.execute(select(User).where(User.email == data.email))
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already taken")
        current_user.email = data.email
    if data.password is not None:
        current_user.hashed_password = hash_password(data.password)
    if data.native_language is not None:
        current_user.native_language = data.native_language
    if data.target_language is not None:
        current_user.target_language = data.target_language
        # Sync with user_languages: if the user already has this language, activate it.
        from app.services.user_language_service import (
            get_user_languages,
        )  # noqa: PLC0415

        user_langs = await get_user_languages(db, current_user.id)
        existing = next(
            (ul for ul in user_langs if ul.target_language == data.target_language),
            None,
        )
        if existing:
            from app.services.user_language_service import (
                switch_language,
            )  # noqa: PLC0415

            await switch_language(db, current_user.id, data.target_language)
        else:
            # If switching variant of the same language (e.g. en-US → en-GB),
            # update the existing row instead of creating a duplicate.
            new_prefix = data.target_language.split("-")[0]
            same_base = next(
                (ul for ul in user_langs if ul.target_language.split("-")[0] == new_prefix),
                None,
            )
            if same_base:
                # Deactivate all currently active languages
                await db.execute(
                    update(UserLanguage)
                    .where(
                        UserLanguage.user_id == current_user.id,
                        UserLanguage.is_active.is_(True),
                    )
                    .values(is_active=False)
                )
                same_base.target_language = data.target_language
                same_base.is_active = True
            else:
                from app.services.user_language_service import (
                    add_language,
                )  # noqa: PLC0415

                await add_language(db, current_user.id, data.target_language)
    if data.ui_locale is not None:
        current_user.ui_locale = data.ui_locale if data.ui_locale.strip() else None
    if data.conversation_max_duration is not None:
        current_user.conversation_max_duration = data.conversation_max_duration
    if data.conversation_inactivity_timeout is not None:
        current_user.conversation_inactivity_timeout = data.conversation_inactivity_timeout
    if data.bio is not None:
        current_user.bio = data.bio if data.bio.strip() else None
    if data.learning_goals is not None:
        current_user.learning_goals = json.dumps(data.learning_goals)

    await db.commit()
    await db.refresh(current_user)
    return current_user


_MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2 MB
_ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png"}
_AVATARS_DIR = "/app/avatars"


def _avatar_path_from_reference(avatar: str | None) -> str | None:
    if not avatar or not avatar.startswith("/api/avatars/"):
        return None
    filename = avatar.split("?")[0].split("/")[-1]
    if filename != os.path.basename(filename):
        return None
    return os.path.join(_AVATARS_DIR, filename)


def _validate_avatar_bytes(content_type: str | None, data: bytes) -> str:
    if content_type not in _ALLOWED_AVATAR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG and PNG images are allowed",
        )
    if content_type == "image/jpeg" and data.startswith(b"\xff\xd8\xff"):
        if len(data) < 4 or not data.endswith(b"\xff\xd9"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image file"
            )
        return "jpg"
    if content_type == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n"):
        if len(data) < 24 or data[12:16] != b"IHDR":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image file"
            )
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        if width <= 0 or height <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image file"
            )
        return "png"
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image file")


@router.post("/me/avatar", response_model=UserResponse)
@limiter.limit("60/minute")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read(_MAX_AVATAR_BYTES + 1)
    if len(data) > _MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Image too large (max 2 MB)"
        )
    ext = _validate_avatar_bytes(file.content_type, data)

    # Delete the existing file if it was previously stored on disk
    old_path = _avatar_path_from_reference(current_user.avatar)
    if old_path and os.path.exists(old_path):
        os.remove(old_path)

    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(_AVATARS_DIR, filename)
    os.makedirs(_AVATARS_DIR, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(data)

    # Append a timestamp to bust the browser cache on re-upload
    ts = int(datetime.now(UTC).timestamp() * 1000)
    current_user.avatar = f"/api/avatars/{filename}?v={ts}"
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/me/avatar-file", response_model=None)
@limiter.limit("60/minute")
async def get_avatar_file(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Response:
    if not current_user.avatar:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found")

    if current_user.avatar.startswith("data:image/"):
        header, _, payload = current_user.avatar.partition(",")
        media_type = header.removeprefix("data:").split(";")[0]
        try:
            return Response(
                content=base64.b64decode(payload),
                media_type=media_type,
                headers={"Cache-Control": "private, no-store"},
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found"
            ) from exc

    if not current_user.avatar.startswith("/api/avatars/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found")

    path = _avatar_path_from_reference(current_user.avatar)
    if not path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found")
    if not os.path.exists(path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found")

    filename = os.path.basename(path)
    media_type = "image/jpeg" if filename.lower().endswith(".jpg") else "image/png"
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "private, no-store"})


@router.delete("/me/avatar", response_model=UserResponse)
@limiter.limit("60/minute")
async def delete_avatar(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    old_path = _avatar_path_from_reference(current_user.avatar)
    if old_path and os.path.exists(old_path):
        os.remove(old_path)
    current_user.avatar = None
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def delete_me(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    if current_user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts cannot be self-deleted",
        )
    token = request.cookies.get("refresh_token")
    if token:
        await redis.delete(f"refresh:{token}")
    response.delete_cookie("refresh_token")
    # Clean up avatar file from disk before deleting the user record
    old_path = _avatar_path_from_reference(current_user.avatar)
    if old_path and os.path.exists(old_path):
        os.remove(old_path)
    user_email = current_user.email
    user_display_name = current_user.display_name
    user_locale = current_user.native_language
    await db.delete(current_user)
    await db.commit()
    try:
        await email_service.send_account_deleted_email(user_email, user_display_name, user_locale)
    except Exception:
        logger.warning("Failed to send account-deleted email to %s", user_email)


@router.get("/quota")
@limiter.limit("60/minute")
async def get_my_quota(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Return conversation quota status for the current user."""
    from app.services.quota_service import (  # noqa: PLC0415
        get_monthly_tokens_used,
        get_quota_status,
    )

    quota = await get_quota_status(
        redis,
        current_user.id,
        current_user.conversation_weekly_sessions,
        current_user.conversation_daily_minutes,
        current_user.conversation_weekly_minutes,
    )
    tokens_used = await get_monthly_tokens_used(db, current_user.id)
    quota["tokens_this_month"] = tokens_used
    quota["tokens_monthly_limit"] = current_user.monthly_tokens_limit
    quota["tokens_unlimited"] = current_user.monthly_tokens_limit == 0
    return quota


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


@router.get("/verify-email")
@limiter.limit("60/minute")
async def verify_email(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    user_id_str = await redis.get(f"verify_email:{token}")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )
    user = await db.get(User, int(user_id_str))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_verified = True
    await db.commit()
    await redis.delete(f"verify_email:{token}")
    return {"detail": "Email verified successfully"}


@router.post("/resend-verification")
@limiter.limit("3/minute")
async def resend_verification(
    request: Request,
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    if current_user.is_verified:
        return {"detail": "Already verified"}
    if not current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No email address on file"
        )
    if not settings.EMAIL_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email not configured",
        )
    verify_token = str(uuid.uuid4())
    await redis.setex(f"verify_email:{verify_token}", 86400, str(current_user.id))
    await email_service.send_verification_email(
        current_user.email,
        current_user.display_name,
        verify_token,
        locale=current_user.native_language,
    )
    return {"detail": "Verification email sent"}


# ---------------------------------------------------------------------------
# Password reset (public — no auth required)
# ---------------------------------------------------------------------------


@router.post("/forgot-password")
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    # Always return 200 to avoid user enumeration
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if user and settings.EMAIL_ENABLED:
        reset_token = str(uuid.uuid4())
        await redis.setex(f"reset_password:{reset_token}", 3600, str(user.id))  # 1h
        await email_service.send_reset_password_email(
            user.email, user.display_name, reset_token, locale=user.native_language
        )
    return {"detail": "If that email is registered you will receive a reset link shortly"}


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    user_id_str = await redis.get(f"reset_password:{data.token}")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    user = await db.get(User, int(user_id_str))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.hashed_password = hash_password(data.new_password)
    await db.commit()
    await redis.delete(f"reset_password:{data.token}")
    return {"detail": "Password updated successfully"}
