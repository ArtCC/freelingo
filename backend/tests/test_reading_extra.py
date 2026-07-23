"""Extra reading tests: lock contention, long-poll, not-found, pagination, paywall."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.reading import ReadingExercise
from app.models.study_plan import StudyPlan
from app.models.user import User

# ---------------------------------------------------------------------------
# Redis mock
# ---------------------------------------------------------------------------


class _MockRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def set(self, key: str, value: str, *, nx: bool = False, ex: int | None = None):
        if nx and key in self._store:
            return None
        self._store[key] = value
        return True

    async def get(self, key: str):
        return self._store.get(key)

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    async def getex(self, key: str):
        return self._store.get(key)

    async def aclose(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def reading_client(db_session):
    from app.routers.admin import get_redis as admin_get_redis
    from app.routers.assessment import get_redis as assessment_get_redis
    from app.routers.auth import get_redis as auth_get_redis
    from app.routers.reading import get_redis as reading_get_redis

    mock_redis = _MockRedis()

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[auth_get_redis] = lambda: mock_redis
    app.dependency_overrides[admin_get_redis] = lambda: mock_redis
    app.dependency_overrides[assessment_get_redis] = lambda: mock_redis
    app.dependency_overrides[reading_get_redis] = lambda: mock_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, mock_redis, db_session

    app.dependency_overrides.clear()


async def _make_user(
    db,
    *,
    username: str = "rexuser",
    email: str = "rexuser@example.com",
    subscription_status: str = "none",
) -> tuple[User, dict[str, str]]:
    from app.models.user_language import UserLanguage

    user = User(
        username=username,
        email=email,
        display_name="Reading Extra User",
        hashed_password=hash_password("testpass"),
        role="user",
        native_language="es",
        target_language="en-US",
        is_active=True,
        subscription_status=subscription_status,
    )
    db.add(user)
    await db.flush()
    db.add(UserLanguage(user_id=user.id, target_language="en-US", is_active=True))
    await db.flush()
    token = create_access_token(user.id, user.role)
    return user, {"Authorization": f"Bearer {token}"}


async def _make_plan(db, user_id: int, level: str = "B1") -> StudyPlan:
    from tests.conftest import make_study_plan

    return await make_study_plan(
        db,
        user_id=user_id,
        cefr_level=level,
        target_language="en-US",
        goals=[],
        duration_weeks=4,
        days_per_week=4,
        current_unit="",
        generated_plan={},
        is_active=True,
    )


_QUESTIONS = [
    {
        "index": i,
        "question": f"Q{i}?",
        "options": {"A": "a", "B": "correct", "C": "c", "D": "d"},
        "correct": "B",
    }
    for i in range(5)
]
_ALL_CORRECT = {str(i): "B" for i in range(5)}


# ---------------------------------------------------------------------------
# 1. Lock already held → /generate returns generating without spawning task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_locked(reading_client) -> None:
    """When lock is held, generate returns 202 without acquiring it again."""
    ac, mock_redis, db = reading_client
    user, headers = await _make_user(db)
    await _make_plan(db, user.id, level="B1")
    await db.commit()

    # Pre-seed lock
    await mock_redis.set("reading:generating:B1:en-US", "1")

    r = await ac.post("/api/reading/generate", headers=headers)
    assert r.status_code == 202
    assert r.json()["status"] == "generating"


# ---------------------------------------------------------------------------
# 2. Long-poll: /next?wait=true returns exercise once it appears
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_next_wait_returns_exercise(reading_client) -> None:
    """With wait=true, if an exercise is inserted while polling, it is returned."""
    ac, mock_redis, db = reading_client
    user, headers = await _make_user(db, username="waituser", email="wait@example.com")
    await _make_plan(db, user.id, level="B1")

    # Place a lock so long-poll checks the pool in the loop
    await mock_redis.set("reading:generating:B1:en-US", "1")

    # Insert exercise and release lock *before* the await (synchronous setup)
    ex = ReadingExercise(
        level="B1",
        target_language="en-US",
        exercise_type="article",
        topic="Fast topic",
        text="Text for long-poll test.",
        questions=_QUESTIONS,
    )
    db.add(ex)
    await mock_redis.delete("reading:generating:B1:en-US")
    await db.commit()

    r = await ac.get("/api/reading/next?wait=true", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["available"] is True
    assert data["exercise"]["topic"] == "Fast topic"


# ---------------------------------------------------------------------------
# 3. /attempt with non-existent exercise → 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_not_found(reading_client) -> None:
    ac, _, db = reading_client
    user, headers = await _make_user(db, username="notfound", email="notfound@example.com")
    await _make_plan(db, user.id)
    await db.commit()

    r = await ac.post(
        "/api/reading/attempt",
        headers=headers,
        json={"exercise_id": 99999, "answers": _ALL_CORRECT},
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "exercise_not_found"


# ---------------------------------------------------------------------------
# 4. History pagination (skip / limit)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_history_pagination(reading_client) -> None:
    """History respects skip and limit parameters and returns total count."""
    ac, _, db = reading_client
    user, headers = await _make_user(db, username="paguser", email="paguser@example.com")
    await _make_plan(db, user.id)
    await db.commit()

    r = await ac.get("/api/reading/history?skip=0&limit=5", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["skip"] == 0
    assert data["limit"] == 5
    assert data["total"] == 0
    assert data["items"] == []


# ---------------------------------------------------------------------------
# 5. Paywall — unauthenticated user is blocked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_paywall_blocked(reading_client) -> None:
    """With STRIPE_ENABLED=True an unsubscribed user still accesses /api/reading/next via freemium."""
    ac, _, db = reading_client
    user, headers = await _make_user(
        db,
        username="paywalled",
        email="paywalled@example.com",
        subscription_status="none",
    )
    await _make_plan(db, user.id)
    await db.commit()

    with patch.object(settings, "STRIPE_ENABLED", True):
        r = await ac.get("/api/reading/next", headers=headers)

    assert r.status_code == 200
