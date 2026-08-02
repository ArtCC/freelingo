from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "email": "new@test.com",
            "password": "Test1234!@",
            "display_name": "New User",
            "native_language": "es",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"
    assert data["role"] == "admin"
    assert "access_token" in data
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    await client.post(
        "/api/auth/register",
        json={
            "username": "dup",
            "email": "dup@test.com",
            "password": "Test1234!@",
            "display_name": "Dup",
            "native_language": "es",
        },
    )
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "dup",
            "email": "dup2@test.com",
            "password": "Test5678!@",
            "display_name": "Dup2",
            "native_language": "fr",
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_when_closed_without_invite(client):
    from app.core.config import settings

    original = settings.ALLOW_REGISTRATION
    settings.ALLOW_REGISTRATION = False
    try:
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "locked",
                "email": "locked@test.com",
                "password": "Test1234!@",
                "display_name": "Locked",
                "native_language": "es",
            },
        )
        assert response.status_code == 403
    finally:
        settings.ALLOW_REGISTRATION = original


@pytest.mark.asyncio
async def test_first_user_is_admin(client):
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "first",
            "email": "first@test.com",
            "password": "Test1234!@",
            "display_name": "First",
            "native_language": "en",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_second_user_is_not_admin(client):
    await client.post(
        "/api/auth/register",
        json={
            "username": "admin_first",
            "email": "adminfirst@test.com",
            "password": "Test1234!@",
            "display_name": "Admin",
            "native_language": "en",
        },
    )
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "regular",
            "email": "regular@test.com",
            "password": "Test1234!@",
            "display_name": "Regular",
            "native_language": "es",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "user"


@pytest.mark.asyncio
async def test_login_success_and_sets_cookie(client):
    await client.post(
        "/api/auth/register",
        json={
            "username": "loginuser",
            "email": "loginuser@test.com",
            "password": "Test1234!@",
            "display_name": "Login",
            "native_language": "es",
        },
    )
    response = await client.post(
        "/api/auth/login",
        json={"email": "loginuser@test.com", "password": "Test1234!@"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_login_invalid_credentials(client):
    response = await client.post(
        "/api/auth/login",
        json={"email": "nobody@test.com", "password": "wrong"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client, db_session):
    from app.core.security import hash_password
    from app.models.user import User

    user = User(
        username="inactive",
        email="inactive@test.com",
        display_name="Inactive",
        hashed_password=hash_password("testpass"),
        role="user",
        native_language="es",
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/auth/login",
        json={"email": "inactive@test.com", "password": "testpass"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotates_token(client):
    await client.post(
        "/api/auth/register",
        json={
            "username": "refreshuser",
            "email": "refreshuser@test.com",
            "password": "Test1234!@",
            "display_name": "Refresh",
            "native_language": "en",
        },
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "refreshuser@test.com", "password": "Test1234!@"},
    )
    refresh_cookie = login_resp.cookies.get("refresh_token")

    client.cookies.set("refresh_token", refresh_cookie)
    response = await client.post("/api/auth/refresh")
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_refresh_missing_cookie(client):
    response = await client.post("/api/auth/refresh")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_replayed_token(client):
    await client.post(
        "/api/auth/register",
        json={
            "username": "replayuser",
            "email": "replayuser@test.com",
            "password": "Test1234!@",
            "display_name": "Replay",
            "native_language": "en",
        },
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "replayuser@test.com", "password": "Test1234!@"},
    )
    refresh_cookie = login_resp.cookies.get("refresh_token")

    client.cookies.set("refresh_token", refresh_cookie)
    await client.post("/api/auth/refresh")

    client.cookies.set("refresh_token", refresh_cookie)
    response = await client.post("/api/auth/refresh")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(client):
    await client.post(
        "/api/auth/register",
        json={
            "username": "logoutuser",
            "email": "logoutuser@test.com",
            "password": "Test1234!@",
            "display_name": "Logout",
            "native_language": "en",
        },
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "logoutuser@test.com", "password": "Test1234!@"},
    )
    refresh_cookie = login_resp.cookies.get("refresh_token")

    client.cookies.set("refresh_token", refresh_cookie)
    response = await client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json()["detail"] == "Logged out"


@pytest.mark.asyncio
async def test_get_me_authenticated(client, test_user):
    user, headers = test_user

    response = await client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["role"] == "user"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_patch_me(client, test_user):
    user, headers = test_user

    response = await client.patch(
        "/api/auth/me",
        headers=headers,
        json={"display_name": "Updated Name"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_patch_me_duplicate_email(client, db_session):
    """M-03: PATCH /me should reject an email already used by another user."""
    from app.core.security import create_access_token, hash_password
    from app.models.user import User

    user_a = User(
        username="user_a",
        email="user_a@test.com",
        display_name="A",
        hashed_password=hash_password("pass1234"),
        role="user",
        native_language="es",
        is_active=True,
    )
    user_b = User(
        username="user_b",
        email="user_b@test.com",
        display_name="B",
        hashed_password=hash_password("pass1234"),
        role="user",
        native_language="en",
        is_active=True,
    )
    db_session.add(user_a)
    db_session.add(user_b)
    await db_session.commit()
    await db_session.refresh(user_b)

    token = create_access_token(user_b.id, user_b.role)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.patch(
        "/api/auth/me",
        headers=headers,
        json={"email": "user_a@test.com"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_patch_me_same_email_allowed(client, test_user):
    """M-03: PATCH /me with the user's own current email should succeed."""
    user, headers = test_user

    response = await client.patch(
        "/api/auth/me",
        headers=headers,
        json={"email": "test@example.com"},
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_email_valid_token(client, db_session, mock_redis):
    """Valid verify-email token marks user as verified."""
    import uuid

    from app.core.security import hash_password
    from app.models.user import User

    user = User(
        username="verifyme",
        email="verifyme@test.com",
        display_name="Verify Me",
        hashed_password=hash_password("pass1234"),
        role="user",
        native_language="es",
        is_active=True,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = str(uuid.uuid4())
    await mock_redis.setex(f"verify_email:{token}", 86400, str(user.id))

    response = await client.get(f"/api/auth/verify-email?token={token}")
    assert response.status_code == 200

    await db_session.refresh(user)
    assert user.is_verified is True


@pytest.mark.asyncio
async def test_verify_email_invalid_token(client):
    response = await client.get("/api/auth/verify-email?token=invalid-token")
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forgot_password_always_200(client):
    """forgot-password always returns 200 regardless of whether the email exists."""
    response = await client.post(
        "/api/auth/forgot-password",
        json={"email": "nobody@test.com"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_valid_token(client, db_session, mock_redis):
    import uuid

    from app.core.security import hash_password, verify_password
    from app.models.user import User

    user = User(
        username="resetme",
        email="resetme@test.com",
        display_name="Reset Me",
        hashed_password=hash_password("oldpass1"),
        role="user",
        native_language="es",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = str(uuid.uuid4())
    await mock_redis.setex(f"reset_password:{token}", 3600, str(user.id))

    response = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "NewPass1!@"},
    )
    assert response.status_code == 200

    await db_session.refresh(user)
    assert verify_password("NewPass1!@", user.hashed_password)


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client):
    response = await client.post(
        "/api/auth/reset-password",
        json={"token": "bad-token", "new_password": "NewPass1!@"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_resend_verification_already_verified(client, db_session):
    from app.core.security import create_access_token, hash_password
    from app.models.user import User

    user = User(
        username="alreadyverified",
        email="alreadyverified@test.com",
        display_name="Verified",
        hashed_password=hash_password("pass1234"),
        role="user",
        native_language="es",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(user.id, user.role)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/api/auth/resend-verification", headers=headers)
    assert response.status_code == 200
    assert response.json()["detail"] == "Already verified"


@pytest.mark.asyncio
async def test_resend_verification_no_email(client, db_session):
    """resend-verification returns 400 when user has no email address."""
    from app.core.security import create_access_token, hash_password
    from app.models.user import User

    user = User(
        username="noemailuser",
        email=None,
        display_name="No Email",
        hashed_password=hash_password("pass1234"),
        role="user",
        native_language="es",
        is_active=True,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(user.id, user.role)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/api/auth/resend-verification", headers=headers)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_resend_verification_email_disabled(client, db_session):
    """resend-verification returns 503 when EMAIL_ENABLED=false."""
    from app.core.config import settings
    from app.core.security import create_access_token, hash_password
    from app.models.user import User

    user = User(
        username="emaildisabled",
        email="emaildisabled@test.com",
        display_name="Email Disabled",
        hashed_password=hash_password("pass1234"),
        role="user",
        native_language="es",
        is_active=True,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(user.id, user.role)
    headers = {"Authorization": f"Bearer {token}"}

    original = settings.EMAIL_ENABLED
    settings.EMAIL_ENABLED = False
    try:
        response = await client.post("/api/auth/resend-verification", headers=headers)
        assert response.status_code == 503
    finally:
        settings.EMAIL_ENABLED = original


@pytest.mark.asyncio
async def test_verify_email_token_consumed_after_use(client, db_session, mock_redis):
    """verify-email token cannot be reused after successful verification."""
    import uuid

    from app.core.security import hash_password
    from app.models.user import User

    user = User(
        username="oncetoken",
        email="oncetoken@test.com",
        display_name="Once Token",
        hashed_password=hash_password("pass1234"),
        role="user",
        native_language="en",
        is_active=True,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = str(uuid.uuid4())
    await mock_redis.setex(f"verify_email:{token}", 86400, str(user.id))

    # First call: success
    r1 = await client.get(f"/api/auth/verify-email?token={token}")
    assert r1.status_code == 200

    # Second call: token already consumed
    r2 = await client.get(f"/api/auth/verify-email?token={token}")
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_token_consumed_after_use(client, db_session, mock_redis):
    """reset-password token cannot be reused after successful reset."""
    import uuid

    from app.core.security import hash_password
    from app.models.user import User

    user = User(
        username="oncereset",
        email="oncereset@test.com",
        display_name="Once Reset",
        hashed_password=hash_password("oldpass1"),
        role="user",
        native_language="en",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = str(uuid.uuid4())
    await mock_redis.setex(f"reset_password:{token}", 3600, str(user.id))

    # First call: success
    r1 = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "NewPass1!@"},
    )
    assert r1.status_code == 200

    # Second call: token already consumed
    r2 = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "AnotherP1!"},
    )
    assert r2.status_code == 400


# ---------------------------------------------------------------------------
# UI locale
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_me_ui_locale_valid(client, test_user):
    """Setting a supported ui_locale persists and is returned in the response."""
    _, headers = test_user

    response = await client.patch(
        "/api/auth/me",
        headers=headers,
        json={"ui_locale": "fr"},
    )
    assert response.status_code == 200
    assert response.json()["ui_locale"] == "fr"


@pytest.mark.asyncio
async def test_patch_me_rejects_unsupported_languages(client, test_user):
    """Unsupported UI and native language codes must be rejected with 422."""
    _, headers = test_user

    response = await client.patch(
        "/api/auth/me",
        headers=headers,
        json={"ui_locale": "zh"},
    )
    assert response.status_code == 422
    response = await client.patch(
        "/api/auth/me",
        headers=headers,
        json={"native_language": "xx"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_me_ui_locale_empty_string_clears(client, test_user):
    """Sending an empty string for ui_locale stores NULL (auto-detect)."""
    _, headers = test_user

    response = await client.patch(
        "/api/auth/me",
        headers=headers,
        json={"ui_locale": ""},
    )
    assert response.status_code == 200
    assert response.json()["ui_locale"] is None


@pytest.mark.asyncio
async def test_register_unsupported_native_language(client):
    """Registration must reject native_language codes outside SUPPORTED_LANGUAGES."""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "testuser_zh",
            "email": "testuser_zh@example.com",
            "password": "ValidPass1!",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_sets_freemium_trial(client):
    """New user gets freemium trial persisted in DB when STRIPE_ENABLED=true."""
    from app.core.config import settings

    with (
        patch.object(settings, "STRIPE_ENABLED", True),
        patch.object(settings, "FREEMIUM_TRIAL_ENABLED", True),
        patch.object(settings, "FREEMIUM_TRIAL_DAYS", 7),
    ):
        res = await client.post(
            "/api/auth/register",
            json={
                "username": "freemiumtrial",
                "email": "freemium@test.com",
                "password": "Test1234!@",
                "display_name": "Trial User",
                "native_language": "es",
            },
        )
    assert res.status_code == 200
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = await client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    body = me.json()
    assert body["freemium_trial_used"] is True
    assert body["freemium_trial_ends_at"] is not None
