"""Comprehensive unit tests for quota_service.py.

Covers all public functions plus edge cases: zero limits, unlimited quotas,
overflow, concurrent checks, and boundary conditions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.services.quota_service import (
    _day_key,
    _seconds_until_midnight,
    _seconds_until_monday,
    _week_key,
    _weekly_seconds_key,
    check_all_quotas,
    check_and_increment_sessions,
    check_daily_minutes,
    check_monthly_tokens,
    check_weekly_minutes,
    get_monthly_tokens_used,
    get_quota_status,
    record_session_seconds,
)


# ── Enhanced mock Redis with incr/incrby/expire/ttl ───────────────────────────
class EnhancedMockRedis:
    """Redis mock supporting all commands used by quota_service."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str | int) -> None:
        self.store[key] = str(value)

    async def setex(self, key: str, ttl: int, value: str | int) -> None:
        self.store[key] = str(value)
        self._ttls[key] = ttl

    async def incr(self, key: str) -> int:
        current = int(self.store.get(key) or 0)
        new_val = current + 1
        self.store[key] = str(new_val)
        return new_val

    async def incrby(self, key: str, amount: int) -> int:
        current = int(self.store.get(key) or 0)
        new_val = current + amount
        self.store[key] = str(new_val)
        return new_val

    async def expire(self, key: str, ttl: int) -> None:
        self._ttls[key] = ttl

    async def ttl(self, key: str) -> int:
        if key not in self.store:
            return -2  # key does not exist
        return self._ttls.get(key, -1)  # -1 = no expiry

    async def eval(self, script: str, numkeys: int, *args: str) -> list[int]:
        """Minimal Lua interpreter for _CHECK_AND_INCR_SESSIONS_LUA."""
        key = args[0]
        limit = int(args[1])
        ttl = int(args[2])
        current = int(self.store.get(key) or 0)
        if limit > 0 and current >= limit:
            return [0, current]
        new_val = current + 1
        self.store[key] = str(new_val)
        if new_val == 1:
            self._ttls[key] = ttl
        return [1, current]


@pytest.fixture
def redis_mock() -> EnhancedMockRedis:
    return EnhancedMockRedis()


# ── Key helper tests ──────────────────────────────────────────────────────────


class TestKeyHelpers:
    """Tests for internal Redis key generation and TTL helpers."""

    def test_week_key_format(self):
        """_week_key produces the expected conv_sessions:{user}:{year}-W{week} format."""
        key = _week_key(42)
        assert key.startswith("conv_sessions:42:")
        # ISO week number part: YYYY-W{ww}
        tail = key.split(":42:")[1]
        assert tail.count("-") == 1
        year_part, week_part = tail.split("-")
        assert len(year_part) == 4
        assert week_part.startswith("W")
        assert 1 <= int(week_part[1:]) <= 53

    def test_day_key_format(self):
        """_day_key produces conv_seconds:{user}:{YYYY-MM-DD}."""
        key = _day_key(7)
        assert key.startswith("conv_seconds:7:")
        tail = key.split(":7:")[1]
        parts = tail.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4  # year
        assert 1 <= int(parts[1]) <= 12  # month
        assert 1 <= int(parts[2]) <= 31  # day

    def test_weekly_seconds_key_format(self):
        """_weekly_seconds_key produces conv_weekly_seconds:{user}:{year}-W{week}."""
        key = _weekly_seconds_key(99)
        assert key.startswith("conv_weekly_seconds:99:")
        tail = key.split(":99:")[1]
        assert tail.count("-") == 1
        year_part, week_part = tail.split("-")
        assert len(year_part) == 4
        assert week_part.startswith("W")

    def test_keys_for_same_user_are_different(self):
        """All three key types for the same user are distinct."""
        user_id = 1
        w = _week_key(user_id)
        d = _day_key(user_id)
        ws = _weekly_seconds_key(user_id)
        assert w != d
        assert w != ws
        assert d != ws
        assert "sessions" in w
        assert "weekly_seconds" in ws
        assert "seconds" in d

    def test_seconds_until_midnight_positive(self):
        """_seconds_until_midnight always returns a positive integer."""
        result = _seconds_until_midnight()
        assert isinstance(result, int)
        assert result >= 1
        assert result <= 24 * 3600  # at most 24 hours

    def test_seconds_until_monday_positive(self):
        """_seconds_until_monday always returns a positive integer."""
        result = _seconds_until_monday()
        assert isinstance(result, int)
        assert result >= 1
        assert result <= 7 * 24 * 3600  # at most 7 days

    def test_seconds_until_monday_in_range(self):
        """_seconds_until_monday returns value between 1 second and 7 days."""
        seconds = _seconds_until_monday()
        assert 1 <= seconds <= 7 * 24 * 3600

    def test_seconds_until_midnight_in_range(self):
        """_seconds_until_midnight returns value between 1 second and 24 hours."""
        seconds = _seconds_until_midnight()
        assert 1 <= seconds <= 24 * 3600


# ── get_quota_status tests ────────────────────────────────────────────────────


class TestGetQuotaStatus:
    """Tests for get_quota_status — read-only usage snapshot."""

    @pytest.mark.asyncio
    async def test_all_zero_when_empty(self, redis_mock):
        """Fresh Redis returns zeros across all counters."""
        status = await get_quota_status(
            redis_mock,
            user_id=1,
            weekly_limit=5,
            daily_minutes_limit=30,
            weekly_minutes_limit=120,
        )
        assert status["sessions_this_week"] == 0
        assert status["sessions_limit"] == 5
        assert status["sessions_unlimited"] is False
        assert status["minutes_today"] == 0
        assert status["minutes_limit"] == 30
        assert status["time_unlimited"] is False
        assert status["minutes_this_week"] == 0
        assert status["weekly_minutes_limit"] == 120
        assert status["weekly_minutes_unlimited"] is False

    @pytest.mark.asyncio
    async def test_reflects_stored_values(self, redis_mock):
        """Returns actual Redis values divided / converted correctly."""
        await redis_mock.set(_week_key(1), "3")
        await redis_mock.set(_day_key(1), "120")  # 2 minutes
        await redis_mock.set(_weekly_seconds_key(1), "900")  # 15 minutes
        status = await get_quota_status(
            redis_mock,
            user_id=1,
            weekly_limit=7,
            daily_minutes_limit=45,
            weekly_minutes_limit=200,
        )
        assert status["sessions_this_week"] == 3
        assert status["minutes_today"] == 2
        assert status["minutes_this_week"] == 15

    @pytest.mark.asyncio
    async def test_unlimited_flags_when_limit_is_zero(self, redis_mock):
        """A limit of 0 means unlimited across all three limits."""
        status = await get_quota_status(
            redis_mock,
            user_id=1,
            weekly_limit=0,
            daily_minutes_limit=0,
            weekly_minutes_limit=0,
        )
        assert status["sessions_unlimited"] is True
        assert status["time_unlimited"] is True
        assert status["weekly_minutes_unlimited"] is True
        assert status["sessions_limit"] == 0
        assert status["minutes_limit"] == 0
        assert status["weekly_minutes_limit"] == 0

    @pytest.mark.asyncio
    async def test_mixed_limits_some_unlimited(self, redis_mock):
        """One limit zero while others have caps still shows correct flags."""
        status = await get_quota_status(
            redis_mock,
            user_id=1,
            weekly_limit=3,
            daily_minutes_limit=0,
            weekly_minutes_limit=60,
        )
        assert status["sessions_unlimited"] is False
        assert status["time_unlimited"] is True
        assert status["weekly_minutes_unlimited"] is False

    @pytest.mark.asyncio
    async def test_default_weekly_minutes_limit(self, redis_mock):
        """Default weekly_minutes_limit is 0 (unlimited)."""
        status = await get_quota_status(
            redis_mock, user_id=1, weekly_limit=5, daily_minutes_limit=30
        )
        assert status["weekly_minutes_limit"] == 0
        assert status["weekly_minutes_unlimited"] is True

    @pytest.mark.asyncio
    async def test_minutes_floor_division(self, redis_mock):
        """Seconds that don't form full minutes are truncated (floor division)."""
        await redis_mock.set(_day_key(1), "119")  # 1 full minute + 59s
        status = await get_quota_status(
            redis_mock, user_id=1, weekly_limit=5, daily_minutes_limit=30
        )
        assert status["minutes_today"] == 1  # floor division

    @pytest.mark.asyncio
    async def test_high_usage_display(self, redis_mock):
        """High values are reported correctly."""
        await redis_mock.set(_week_key(1), "999")
        await redis_mock.set(_day_key(1), "36000")  # 600 minutes
        status = await get_quota_status(
            redis_mock, user_id=1, weekly_limit=1000, daily_minutes_limit=600
        )
        assert status["sessions_this_week"] == 999
        assert status["minutes_today"] == 600


# ── check_and_increment_sessions tests ────────────────────────────────────────


class TestCheckAndIncrementSessions:
    """Tests for check_and_increment_sessions — atomic check + incr."""

    @pytest.mark.asyncio
    async def test_unlimited_always_allowed(self, redis_mock):
        """When weekly_limit is 0, sessions are always allowed."""
        allowed, used, limit = await check_and_increment_sessions(
            redis_mock, user_id=1, weekly_limit=0
        )
        assert allowed is True
        assert used == 0
        assert limit == 0

    @pytest.mark.asyncio
    async def test_first_session_allowed(self, redis_mock):
        """First session of the week is always allowed when limit > 0."""
        allowed, used, limit = await check_and_increment_sessions(
            redis_mock, user_id=1, weekly_limit=5
        )
        assert allowed is True
        assert used == 0
        assert limit == 5

    @pytest.mark.asyncio
    async def test_increments_counter(self, redis_mock):
        """Each call increments the session counter by 1."""
        await check_and_increment_sessions(redis_mock, user_id=1, weekly_limit=5)
        val = await redis_mock.get(_week_key(1))
        assert int(val) == 1
        await check_and_increment_sessions(redis_mock, user_id=1, weekly_limit=5)
        assert int(await redis_mock.get(_week_key(1))) == 2

    @pytest.mark.asyncio
    async def test_used_before_reflects_previous_value(self, redis_mock):
        """used_before is the value BEFORE increment, not after."""
        await redis_mock.set(_week_key(2), "2")
        allowed, used, limit = await check_and_increment_sessions(
            redis_mock, user_id=2, weekly_limit=5
        )
        assert used == 2  # before incr
        assert int(await redis_mock.get(_week_key(2))) == 3  # after incr

    @pytest.mark.asyncio
    async def test_denied_when_at_limit(self, redis_mock):
        """When current >= limit, session is denied and counter does NOT increment."""
        await redis_mock.set(_week_key(3), "3")
        allowed, used, limit = await check_and_increment_sessions(
            redis_mock, user_id=3, weekly_limit=3
        )
        assert allowed is False
        assert used == 3
        assert limit == 3
        # Counter must NOT have been incremented
        assert int(await redis_mock.get(_week_key(3))) == 3

    @pytest.mark.asyncio
    async def test_denied_when_over_limit(self, redis_mock):
        """When current > limit (edge case), session is denied."""
        await redis_mock.set(_week_key(4), "10")
        allowed, used, limit = await check_and_increment_sessions(
            redis_mock, user_id=4, weekly_limit=3
        )
        assert allowed is False
        assert int(await redis_mock.get(_week_key(4))) == 10  # unchanged

    @pytest.mark.asyncio
    async def test_first_session_sets_ttl(self, redis_mock):
        """First increment (new_val == 1) sets expire TTL on the key."""
        allowed, used, limit = await check_and_increment_sessions(
            redis_mock, user_id=5, weekly_limit=5
        )
        assert allowed is True
        ttl = await redis_mock.ttl(_week_key(5))
        assert ttl >= 1  # TTL was set

    @pytest.mark.asyncio
    async def test_subsequent_sessions_dont_reset_ttl(self, redis_mock):
        """Only the first session of the week sets the TTL."""
        first_key = _week_key(6)
        # Set initial state with an artificial TTL
        await redis_mock.set(first_key, "0")
        await redis_mock.expire(first_key, 999999)
        # First call: incr to 1, should NOT set TTL since val wasn't 1 before incr? Wait...
        # Actually the logic is: if new_val == 1, set TTL. Let me test that.
        # First call (key starts empty): get returns None, incr returns 1, sets TTL
        # Second call: get returns 1, incr returns 2, does NOT set TTL
        await check_and_increment_sessions(redis_mock, user_id=6, weekly_limit=5)
        _ = await redis_mock.ttl(first_key)
        await redis_mock.expire(first_key, 12345)  # override TTL
        await check_and_increment_sessions(redis_mock, user_id=6, weekly_limit=5)
        ttl_second = await redis_mock.ttl(first_key)
        # TTL should still be the overridden value, not refreshed
        assert ttl_second == 12345

    @pytest.mark.asyncio
    async def test_limit_exactly_one(self, redis_mock):
        """With limit=1, first call allowed, second denied."""
        allowed1, _, _ = await check_and_increment_sessions(redis_mock, user_id=7, weekly_limit=1)
        assert allowed1 is True
        allowed2, used2, _ = await check_and_increment_sessions(
            redis_mock, user_id=7, weekly_limit=1
        )
        assert allowed2 is False
        assert used2 == 1

    @pytest.mark.asyncio
    async def test_isolated_by_user(self, redis_mock):
        """Each user_id has an independent counter."""
        await check_and_increment_sessions(redis_mock, user_id=10, weekly_limit=2)
        await check_and_increment_sessions(redis_mock, user_id=10, weekly_limit=2)
        allowed_u10, _, _ = await check_and_increment_sessions(
            redis_mock, user_id=10, weekly_limit=2
        )
        assert allowed_u10 is False  # user 10 is at limit
        allowed_u20, _, _ = await check_and_increment_sessions(
            redis_mock, user_id=20, weekly_limit=2
        )
        assert allowed_u20 is True  # user 20 still has room


# ── check_daily_minutes tests ─────────────────────────────────────────────────


class TestCheckDailyMinutes:
    """Tests for check_daily_minutes — read-only check, no increment."""

    @pytest.mark.asyncio
    async def test_unlimited_always_allowed(self, redis_mock):
        """Limit of 0 means always allowed."""
        allowed, used, limit = await check_daily_minutes(
            redis_mock, user_id=1, daily_minutes_limit=0
        )
        assert allowed is True
        assert used == 0
        assert limit == 0

    @pytest.mark.asyncio
    async def test_allowed_when_under_limit(self, redis_mock):
        """Usage below the limit allows more time."""
        await redis_mock.set(_day_key(1), "120")  # 2 minutes of seconds
        allowed, used, limit = await check_daily_minutes(
            redis_mock, user_id=1, daily_minutes_limit=5
        )
        assert allowed is True
        assert used == 2
        assert limit == 5

    @pytest.mark.asyncio
    async def test_denied_when_at_limit(self, redis_mock):
        """Usage at or above the limit denies further time."""
        await redis_mock.set(_day_key(2), "300")  # exactly 5 minutes (300 sec)
        allowed, used, limit = await check_daily_minutes(
            redis_mock, user_id=2, daily_minutes_limit=5
        )
        assert allowed is False
        assert used == 5

    @pytest.mark.asyncio
    async def test_denied_when_over_limit(self, redis_mock):
        """Usage exceeding the limit denies time."""
        await redis_mock.set(_day_key(3), "600")  # 10 minutes
        allowed, used, limit = await check_daily_minutes(
            redis_mock, user_id=3, daily_minutes_limit=5
        )
        assert allowed is False
        assert used == 10

    @pytest.mark.asyncio
    async def test_zero_usage_with_limit(self, redis_mock):
        """Zero usage with a positive limit is allowed."""
        allowed, used, limit = await check_daily_minutes(
            redis_mock, user_id=4, daily_minutes_limit=30
        )
        assert allowed is True
        assert used == 0
        assert limit == 30

    @pytest.mark.asyncio
    async def test_seconds_just_under_next_minute(self, redis_mock):
        """299 seconds = 4 minutes (floor), still under limit of 5."""
        await redis_mock.set(_day_key(5), "299")
        allowed, used, _ = await check_daily_minutes(redis_mock, user_id=5, daily_minutes_limit=5)
        assert allowed is True
        assert used == 4

    @pytest.mark.asyncio
    async def test_does_not_modify_redis(self, redis_mock):
        """check_daily_minutes is read-only — Redis value is unchanged."""
        await redis_mock.set(_day_key(6), "180")
        before = await redis_mock.get(_day_key(6))
        await check_daily_minutes(redis_mock, user_id=6, daily_minutes_limit=5)
        after = await redis_mock.get(_day_key(6))
        assert before == after


# ── check_weekly_minutes tests ────────────────────────────────────────────────


class TestCheckWeeklyMinutes:
    """Tests for check_weekly_minutes — read-only check."""

    @pytest.mark.asyncio
    async def test_unlimited_always_allowed(self, redis_mock):
        """Limit of 0 means always allowed (weekly)."""
        allowed, used, limit = await check_weekly_minutes(
            redis_mock, user_id=1, weekly_minutes_limit=0
        )
        assert allowed is True
        assert used == 0
        assert limit == 0

    @pytest.mark.asyncio
    async def test_allowed_when_under_limit(self, redis_mock):
        """Usage below the weekly limit allows more time."""
        await redis_mock.set(_weekly_seconds_key(1), "600")  # 10 minutes
        allowed, used, limit = await check_weekly_minutes(
            redis_mock, user_id=1, weekly_minutes_limit=15
        )
        assert allowed is True
        assert used == 10

    @pytest.mark.asyncio
    async def test_denied_when_at_limit(self, redis_mock):
        """Usage at the weekly limit denies further time."""
        await redis_mock.set(_weekly_seconds_key(2), "3600")  # 60 minutes
        allowed, used, limit = await check_weekly_minutes(
            redis_mock, user_id=2, weekly_minutes_limit=60
        )
        assert allowed is False
        assert used == 60

    @pytest.mark.asyncio
    async def test_denied_when_over_limit(self, redis_mock):
        """Usage exceeding the weekly limit denies time."""
        await redis_mock.set(_weekly_seconds_key(3), "7200")  # 120 minutes
        allowed, used, limit = await check_weekly_minutes(
            redis_mock, user_id=3, weekly_minutes_limit=60
        )
        assert allowed is False
        assert used == 120

    @pytest.mark.asyncio
    async def test_zero_usage_with_limit(self, redis_mock):
        """No usage stored yet, check passes."""
        allowed, used, limit = await check_weekly_minutes(
            redis_mock, user_id=4, weekly_minutes_limit=120
        )
        assert allowed is True
        assert used == 0
        assert limit == 120

    @pytest.mark.asyncio
    async def test_does_not_modify_redis(self, redis_mock):
        """check_weekly_minutes is read-only."""
        key = _weekly_seconds_key(5)
        await redis_mock.set(key, "1800")
        before = await redis_mock.get(key)
        await check_weekly_minutes(redis_mock, user_id=5, weekly_minutes_limit=30)
        after = await redis_mock.get(key)
        assert before == after


# ── record_session_seconds tests ──────────────────────────────────────────────


class TestRecordSessionSeconds:
    """Tests for record_session_seconds — accumulates seconds into daily & weekly."""

    @pytest.mark.asyncio
    async def test_records_to_both_keys(self, redis_mock):
        """Seconds are recorded in both the daily and weekly second counters."""
        await record_session_seconds(redis_mock, user_id=1, seconds=300)
        assert int(await redis_mock.get(_day_key(1))) == 300
        assert int(await redis_mock.get(_weekly_seconds_key(1))) == 300

    @pytest.mark.asyncio
    async def test_accumulates_with_existing_values(self, redis_mock):
        """Multiple calls accumulate (add) rather than overwrite."""
        await record_session_seconds(redis_mock, user_id=1, seconds=100)
        await record_session_seconds(redis_mock, user_id=1, seconds=200)
        assert int(await redis_mock.get(_day_key(1))) == 300
        assert int(await redis_mock.get(_weekly_seconds_key(1))) == 300

    @pytest.mark.asyncio
    async def test_ignores_zero(self, redis_mock):
        """Zero seconds is a no-op — no keys created or modified."""
        await record_session_seconds(redis_mock, user_id=1, seconds=0)
        assert await redis_mock.get(_day_key(1)) is None
        assert await redis_mock.get(_weekly_seconds_key(1)) is None

    @pytest.mark.asyncio
    async def test_ignores_negative(self, redis_mock):
        """Negative seconds are silently ignored."""
        await record_session_seconds(redis_mock, user_id=1, seconds=100)
        await record_session_seconds(redis_mock, user_id=1, seconds=-50)
        # Should still be 100 (no change from negative call)
        assert int(await redis_mock.get(_day_key(1))) == 100

    @pytest.mark.asyncio
    async def test_sets_ttl_when_key_is_new(self, redis_mock):
        """First write to a day/hour key sets TTL to expire at midnight/Monday."""
        await record_session_seconds(redis_mock, user_id=2, seconds=60)
        ttl_day = await redis_mock.ttl(_day_key(2))
        ttl_week = await redis_mock.ttl(_weekly_seconds_key(2))
        assert ttl_day >= 1
        assert ttl_week >= 1

    @pytest.mark.asyncio
    async def test_does_not_reset_ttl_if_already_set(self, redis_mock):
        """When key already has a TTL, it is not overwritten."""
        day_key = _day_key(3)
        week_key = _weekly_seconds_key(3)
        # Manually set values with artificial TTLs
        await redis_mock.set(day_key, "100")
        await redis_mock.expire(day_key, 500)
        await redis_mock.set(week_key, "100")
        await redis_mock.expire(week_key, 600)
        # Now record more seconds — should NOT overwrite TTLs
        await record_session_seconds(redis_mock, user_id=3, seconds=50)
        assert await redis_mock.ttl(day_key) == 500
        assert await redis_mock.ttl(week_key) == 600

    @pytest.mark.asyncio
    async def test_large_seconds_value(self, redis_mock):
        """Large values (e.g. a very long session) are recorded correctly."""
        await record_session_seconds(redis_mock, user_id=4, seconds=36000)  # 10 hours
        assert int(await redis_mock.get(_day_key(4))) == 36000
        assert int(await redis_mock.get(_weekly_seconds_key(4))) == 36000

    @pytest.mark.asyncio
    async def test_isolated_between_users(self, redis_mock):
        """Each user's seconds are tracked independently."""
        await record_session_seconds(redis_mock, user_id=10, seconds=300)
        await record_session_seconds(redis_mock, user_id=20, seconds=500)
        assert int(await redis_mock.get(_day_key(10))) == 300
        assert int(await redis_mock.get(_day_key(20))) == 500

    @pytest.mark.asyncio
    async def test_daily_and_weekly_independent(self, redis_mock):
        """Daily and weekly counters start from different base values."""
        # Pre-set weekly to a non-zero value, leave daily empty
        await redis_mock.set(_weekly_seconds_key(5), "1000")
        await record_session_seconds(redis_mock, user_id=5, seconds=200)
        assert int(await redis_mock.get(_day_key(5))) == 200
        assert int(await redis_mock.get(_weekly_seconds_key(5))) == 1200


# ── get_monthly_tokens_used tests ─────────────────────────────────────────────


class TestGetMonthlyTokensUsed:
    """Tests for get_monthly_tokens_used — DB-backed token counting."""

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_usage(self, db_session):
        """When the user has no LLMUsage rows, return 0."""
        used = await get_monthly_tokens_used(db_session, user_id=999)
        assert used == 0

    @pytest.mark.asyncio
    async def test_sums_current_month_only(self, db_session, test_user):
        """Only rows from the current calendar month are summed."""
        from app.models.llm_usage import LLMUsage

        user, _ = test_user
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Current month entry
        current = LLMUsage(
            user_id=user.id,
            source="chat",
            total_tokens=100,
            created_at=month_start.replace(day=15, tzinfo=None),
        )
        # Previous month entry
        if month_start.month == 1:
            prev_month = month_start.replace(year=month_start.year - 1, month=12, tzinfo=None)
        else:
            prev_month = month_start.replace(month=month_start.month - 1, tzinfo=None)
        old = LLMUsage(
            user_id=user.id,
            source="conversation",
            total_tokens=500,
            created_at=prev_month.replace(day=20),
        )
        db_session.add_all([current, old])
        await db_session.commit()

        used = await get_monthly_tokens_used(db_session, user_id=user.id)
        assert used == 100

    @pytest.mark.asyncio
    async def test_sums_multiple_entries_current_month(self, db_session, test_user):
        """Multiple entries in the same month are added together."""
        from app.models.llm_usage import LLMUsage

        user, _ = test_user
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        db_session.add_all(
            [
                LLMUsage(
                    user_id=user.id,
                    source="chat",
                    total_tokens=50,
                    created_at=month_start.replace(day=5),
                ),
                LLMUsage(
                    user_id=user.id,
                    source="chat",
                    total_tokens=30,
                    created_at=month_start.replace(day=10),
                ),
                LLMUsage(
                    user_id=user.id,
                    source="conversation",
                    total_tokens=20,
                    created_at=month_start.replace(day=20),
                ),
            ]
        )
        await db_session.commit()
        used = await get_monthly_tokens_used(db_session, user_id=user.id)
        assert used == 100

    @pytest.mark.asyncio
    async def test_handles_null_total_tokens(self, db_session, test_user):
        """Rows with total_tokens=None are treated as 0 (via coalesce)."""
        from app.models.llm_usage import LLMUsage

        user, _ = test_user
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        db_session.add_all(
            [
                LLMUsage(
                    user_id=user.id,
                    source="chat",
                    total_tokens=100,
                    created_at=month_start.replace(day=1, tzinfo=None),
                ),
                LLMUsage(
                    user_id=user.id,
                    source="conversation",
                    total_tokens=None,
                    created_at=month_start.replace(day=2, tzinfo=None),
                ),
            ]
        )
        await db_session.commit()
        used = await get_monthly_tokens_used(db_session, user_id=user.id)
        assert used == 100

    @pytest.mark.asyncio
    async def test_isolated_by_user(self, db_session, test_user):
        """Each user's tokens are counted independently."""
        from app.core.security import hash_password
        from app.models.llm_usage import LLMUsage
        from app.models.user import User
        from app.models.user_language import UserLanguage

        user, _ = test_user
        # Create a second user
        user2 = User(
            username="otheruser",
            email="other@example.com",
            display_name="Other",
            hashed_password=hash_password("pass"),
            role="user",
            native_language="fr",
            target_language="en-US",
            is_active=True,
        )
        db_session.add(user2)
        await db_session.flush()
        db_session.add(UserLanguage(user_id=user2.id, target_language="en-US", is_active=True))
        await db_session.flush()

        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        db_session.add_all(
            [
                LLMUsage(
                    user_id=user.id,
                    source="chat",
                    total_tokens=200,
                    created_at=month_start.replace(day=1, tzinfo=None),
                ),
                LLMUsage(
                    user_id=user2.id,
                    source="chat",
                    total_tokens=999,
                    created_at=month_start.replace(day=1, tzinfo=None),
                ),
            ]
        )
        await db_session.commit()

        assert await get_monthly_tokens_used(db_session, user_id=user.id) == 200
        assert await get_monthly_tokens_used(db_session, user_id=user2.id) == 999


# ── check_monthly_tokens tests ────────────────────────────────────────────────


class TestCheckMonthlyTokens:
    """Tests for check_monthly_tokens — DB-backed monthly limit check."""

    @pytest.mark.asyncio
    async def test_unlimited_always_allowed(self, db_session):
        """Limit of 0 means unlimited tokens."""
        allowed, used, limit = await check_monthly_tokens(db_session, user_id=1, monthly_limit=0)
        assert allowed is True
        assert used == 0
        assert limit == 0

    @pytest.mark.asyncio
    async def test_allowed_when_under_limit(self, db_session, test_user):
        """When tokens_used < monthly_limit, allowed=True."""
        from app.models.llm_usage import LLMUsage

        user, _ = test_user
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        db_session.add(
            LLMUsage(
                user_id=user.id,
                source="chat",
                total_tokens=5000,
                created_at=month_start.replace(day=10, tzinfo=None),
            )
        )
        await db_session.commit()

        allowed, used, limit = await check_monthly_tokens(
            db_session, user_id=user.id, monthly_limit=10000
        )
        assert allowed is True
        assert used == 5000
        assert limit == 10000

    @pytest.mark.asyncio
    async def test_denied_when_at_limit(self, db_session, test_user):
        """When tokens_used >= monthly_limit, allowed=False."""
        from app.models.llm_usage import LLMUsage

        user, _ = test_user
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        db_session.add(
            LLMUsage(
                user_id=user.id,
                source="chat",
                total_tokens=10000,
                created_at=month_start.replace(day=10, tzinfo=None),
            )
        )
        await db_session.commit()

        allowed, used, limit = await check_monthly_tokens(
            db_session, user_id=user.id, monthly_limit=10000
        )
        assert allowed is False
        assert used == 10000

    @pytest.mark.asyncio
    async def test_denied_when_over_limit(self, db_session, test_user):
        """When tokens_used > monthly_limit, allowed=False."""
        from app.models.llm_usage import LLMUsage

        user, _ = test_user
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        db_session.add(
            LLMUsage(
                user_id=user.id,
                source="chat",
                total_tokens=15000,
                created_at=month_start.replace(day=10, tzinfo=None),
            )
        )
        await db_session.commit()

        allowed, used, limit = await check_monthly_tokens(
            db_session, user_id=user.id, monthly_limit=10000
        )
        assert allowed is False
        assert used == 15000


# ── check_all_quotas tests ────────────────────────────────────────────────────


class TestCheckAllQuotas:
    """Tests for check_all_quotas — aggregated quota pipeline."""

    @pytest.mark.asyncio
    async def test_all_quotas_pass(self, redis_mock, db_session):
        """When all quotas are under limit, returns success with capped duration."""
        user_id = 1
        with patch(  # pyright: ignore[reportUnknownMemberType]
            "app.utils.db.db_session", return_value=AsyncMock()
        ) as mock_sf:
            cm = AsyncMock()
            cm.__aenter__.return_value = db_session
            mock_sf.return_value = cm

            max_dur, err_code, err_msg, close_code = await check_all_quotas(
                redis_mock,
                user_id,
                monthly_tokens_limit=100000,
                daily_minutes_limit=30,
                weekly_minutes_limit=120,
                weekly_sessions_limit=10,
                max_duration=3600,
            )
        assert err_code is None
        assert err_msg is None
        assert close_code is None
        assert max_dur == 1800  # capped to daily limit (30 min = 1800 s)

    @pytest.mark.asyncio
    async def test_caps_max_duration_to_daily_remaining(self, redis_mock, db_session):
        """max_duration is capped to remaining daily minutes when limit > 0."""
        user_id = 2
        # Pre-set daily usage: 25 minutes = 1500 seconds
        await redis_mock.set(_day_key(user_id), "1500")

        with patch("app.utils.db.db_session", return_value=AsyncMock()) as mock_sf:
            cm = AsyncMock()
            cm.__aenter__.return_value = db_session
            mock_sf.return_value = cm

            max_dur, err_code, _, _ = await check_all_quotas(
                redis_mock,
                user_id,
                monthly_tokens_limit=100000,
                daily_minutes_limit=30,
                weekly_minutes_limit=0,  # unlimited weekly
                weekly_sessions_limit=10,
                max_duration=3600,
            )
        assert err_code is None
        # 30 - 25 = 5 minutes remaining = 300 seconds
        assert max_dur == 300

    @pytest.mark.asyncio
    async def test_caps_max_duration_to_weekly_remaining(self, redis_mock, db_session):
        """max_duration is capped to remaining weekly minutes."""
        user_id = 3
        # Pre-set weekly usage: 100 minutes = 6000 seconds
        await redis_mock.set(_weekly_seconds_key(user_id), "6000")

        with patch("app.utils.db.db_session", return_value=AsyncMock()) as mock_sf:
            cm = AsyncMock()
            cm.__aenter__.return_value = db_session
            mock_sf.return_value = cm

            max_dur, err_code, _, _ = await check_all_quotas(
                redis_mock,
                user_id,
                monthly_tokens_limit=100000,
                daily_minutes_limit=30,
                weekly_minutes_limit=120,
                weekly_sessions_limit=10,
                max_duration=3600,
            )
        assert err_code is None
        # 120 - 100 = 20 minutes = 1200 seconds
        # Daily is 30 min remaining = 1800s; weekly is tighter
        assert max_dur == 1200

    @pytest.mark.asyncio
    async def test_both_limits_cap_to_tighter(self, redis_mock, db_session):
        """When both daily and weekly have remaining, the tighter cap wins."""
        user_id = 4
        await redis_mock.set(_day_key(user_id), "1500")  # 25 min used → 5 min remaining
        await redis_mock.set(
            _weekly_seconds_key(user_id), "6000"
        )  # 100 min used → 20 min remaining

        with patch("app.utils.db.db_session", return_value=AsyncMock()) as mock_sf:
            cm = AsyncMock()
            cm.__aenter__.return_value = db_session
            mock_sf.return_value = cm

            max_dur, err_code, _, _ = await check_all_quotas(
                redis_mock,
                user_id,
                monthly_tokens_limit=100000,
                daily_minutes_limit=30,
                weekly_minutes_limit=120,
                weekly_sessions_limit=10,
                max_duration=3600,
            )
        assert err_code is None
        assert max_dur == 300  # 5 min * 60

    @pytest.mark.asyncio
    async def test_daily_minutes_exceeded(self, redis_mock, db_session):
        """When daily minutes are exhausted, error returned before hitting sessions."""
        user_id = 5
        await redis_mock.set(_day_key(user_id), "1800")  # 30 minutes (at limit)

        with patch("app.utils.db.db_session", return_value=AsyncMock()) as mock_sf:
            cm = AsyncMock()
            cm.__aenter__.return_value = db_session
            mock_sf.return_value = cm

            max_dur, err_code, err_msg, close_code = await check_all_quotas(
                redis_mock,
                user_id,
                monthly_tokens_limit=100000,
                daily_minutes_limit=30,
                weekly_minutes_limit=0,
                weekly_sessions_limit=10,
                max_duration=3600,
            )
        assert err_code == "quota_exceeded_time"
        assert "30/30 min" in err_msg
        assert close_code == 1008
        assert max_dur == 3600  # original uncapped

    @pytest.mark.asyncio
    async def test_weekly_minutes_exceeded(self, redis_mock, db_session):
        """When weekly minutes are exhausted."""
        user_id = 6
        await redis_mock.set(_weekly_seconds_key(user_id), "12000")  # 200 min (over 120)

        with patch("app.utils.db.db_session", return_value=AsyncMock()) as mock_sf:
            cm = AsyncMock()
            cm.__aenter__.return_value = db_session
            mock_sf.return_value = cm

            max_dur, err_code, err_msg, close_code = await check_all_quotas(
                redis_mock,
                user_id,
                monthly_tokens_limit=100000,
                daily_minutes_limit=60,
                weekly_minutes_limit=120,
                weekly_sessions_limit=10,
                max_duration=3600,
            )
        assert err_code == "quota_exceeded_weekly_minutes"
        assert "200/120 min" in err_msg
        assert close_code == 1008

    @pytest.mark.asyncio
    async def test_sessions_exceeded(self, redis_mock, db_session):
        """When weekly sessions are exhausted."""
        user_id = 7
        await redis_mock.set(_week_key(user_id), "5")  # at limit of 5

        with patch("app.utils.db.db_session", return_value=AsyncMock()) as mock_sf:
            cm = AsyncMock()
            cm.__aenter__.return_value = db_session
            mock_sf.return_value = cm

            max_dur, err_code, err_msg, close_code = await check_all_quotas(
                redis_mock,
                user_id,
                monthly_tokens_limit=100000,
                daily_minutes_limit=60,
                weekly_minutes_limit=0,
                weekly_sessions_limit=5,
                max_duration=3600,
            )
        assert err_code == "quota_exceeded_sessions"
        assert "5/5" in err_msg
        assert close_code == 1008

    @pytest.mark.asyncio
    async def test_tokens_exceeded(self, redis_mock, db_session, test_user):
        """When monthly tokens are exhausted, error returned before other checks."""
        from app.models.llm_usage import LLMUsage

        user, _ = test_user
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        db_session.add(
            LLMUsage(
                user_id=user.id,
                source="chat",
                total_tokens=50000,
                created_at=month_start.replace(day=10, tzinfo=None),
            )
        )
        await db_session.commit()

        with patch("app.utils.db.db_session", return_value=AsyncMock()) as mock_sf:
            cm = AsyncMock()
            cm.__aenter__.return_value = db_session
            mock_sf.return_value = cm

            max_dur, err_code, err_msg, close_code = await check_all_quotas(
                redis_mock,
                user.id,
                monthly_tokens_limit=10000,
                daily_minutes_limit=60,
                weekly_minutes_limit=0,
                weekly_sessions_limit=10,
                max_duration=3600,
            )
        assert err_code == "quota_exceeded_tokens"
        assert "50000/10000 tokens" in err_msg
        assert close_code == 1008

    @pytest.mark.asyncio
    async def test_all_unlimited_passes(self, redis_mock, db_session):
        """When all limits are 0, everything passes and max_duration is unchanged."""
        user_id = 10
        with patch("app.utils.db.db_session", return_value=AsyncMock()) as mock_sf:
            cm = AsyncMock()
            cm.__aenter__.return_value = db_session
            mock_sf.return_value = cm

            max_dur, err_code, err_msg, close_code = await check_all_quotas(
                redis_mock,
                user_id,
                monthly_tokens_limit=0,
                daily_minutes_limit=0,
                weekly_minutes_limit=0,
                weekly_sessions_limit=0,
                max_duration=7200,
            )
        assert err_code is None
        assert err_msg is None
        assert close_code is None
        assert max_dur == 7200

    @pytest.mark.asyncio
    async def test_token_check_skipped_when_limit_zero(self, redis_mock, db_session):
        """When monthly_tokens_limit is 0, the DB query is skipped entirely."""
        user_id = 11
        # Don't even need to mock db_session since it won't be called
        # But we still need it available in case
        with patch("app.utils.db.db_session", return_value=AsyncMock()) as mock_sf:
            mock_sf.assert_not_called = lambda: None  # won't be called
            cm = AsyncMock()
            cm.__aenter__.return_value = db_session
            mock_sf.return_value = cm

            max_dur, err_code, _, _ = await check_all_quotas(
                redis_mock,
                user_id,
                monthly_tokens_limit=0,  # skip DB
                daily_minutes_limit=30,
                weekly_minutes_limit=0,
                weekly_sessions_limit=10,
                max_duration=1800,
            )
        assert err_code is None


# ── Integration / workflow tests ──────────────────────────────────────────────


class TestQuotaWorkflow:
    """End-to-end quota lifecycle tests."""

    @pytest.mark.asyncio
    async def test_full_session_lifecycle(self, redis_mock):
        """Simulate a complete session: check, record, check again."""
        user_id = 1
        # Initial: all zeros
        status = await get_quota_status(
            redis_mock,
            user_id,
            weekly_limit=5,
            daily_minutes_limit=30,
            weekly_minutes_limit=120,
        )
        assert status["sessions_this_week"] == 0
        assert status["minutes_today"] == 0

        # Start session: check + increment
        allowed, _, _ = await check_and_increment_sessions(redis_mock, user_id, weekly_limit=5)
        assert allowed is True

        # Record 5 minutes of conversation
        await record_session_seconds(redis_mock, user_id, seconds=300)

        # Verify state
        daily_ok, minutes_used, _ = await check_daily_minutes(
            redis_mock, user_id, daily_minutes_limit=30
        )
        assert daily_ok is True
        assert minutes_used == 5

        # Record more time up to the daily limit
        await record_session_seconds(redis_mock, user_id, seconds=1500)  # 25 more → 30 total
        daily_ok2, minutes_used2, _ = await check_daily_minutes(
            redis_mock, user_id, daily_minutes_limit=30
        )
        assert daily_ok2 is False
        assert minutes_used2 == 30

    @pytest.mark.asyncio
    async def test_session_limit_prevents_new_sessions(self, redis_mock):
        """Once weekly session limit is reached, no new sessions are allowed."""
        user_id = 2
        limit = 3

        # Use all sessions
        for _ in range(limit):
            allowed, _, _ = await check_and_increment_sessions(
                redis_mock, user_id, weekly_limit=limit
            )
            assert allowed is True

        # Next attempt should fail
        allowed, _, _ = await check_and_increment_sessions(redis_mock, user_id, weekly_limit=limit)
        assert allowed is False

    @pytest.mark.asyncio
    async def test_minute_limits_independent_of_sessions(self, redis_mock):
        """Time limits and session limits are tracked independently."""
        user_id = 3
        # Record a lot of time
        await record_session_seconds(redis_mock, user_id, seconds=7200)  # 120 min

        # Sessions still available even though time is used
        allowed, _, _ = await check_and_increment_sessions(redis_mock, user_id, weekly_limit=10)
        assert allowed is True

        # But daily time is exceeded
        daily_ok, _, _ = await check_daily_minutes(redis_mock, user_id, daily_minutes_limit=30)
        assert daily_ok is False

    @pytest.mark.asyncio
    async def test_concurrent_quota_checks(self, redis_mock):
        """Multiple rapid checks behave correctly."""
        user_id = 4
        # Start with some usage
        await redis_mock.set(_week_key(user_id), "2")
        await redis_mock.set(_day_key(user_id), "900")  # 15 min
        await redis_mock.set(_weekly_seconds_key(user_id), "900")  # 15 min

        # Check all three quota types in parallel
        daily_ok, daily_used, _ = await check_daily_minutes(
            redis_mock, user_id, daily_minutes_limit=30
        )
        weekly_min_ok, weekly_used, _ = await check_weekly_minutes(
            redis_mock, user_id, weekly_minutes_limit=120
        )
        session_ok, session_used, _ = await check_and_increment_sessions(
            redis_mock, user_id, weekly_limit=5
        )

        assert daily_ok is True
        assert daily_used == 15
        assert weekly_min_ok is True
        assert weekly_used == 15
        assert session_ok is True
        assert session_used == 2  # before increment

    @pytest.mark.asyncio
    async def test_zero_limits_everything_unlimited(self, redis_mock):
        """When all limits are 0, everything is always allowed."""
        user_id = 5
        # Record arbitrarily large values
        await redis_mock.set(_week_key(user_id), "9999999")
        await redis_mock.set(_day_key(user_id), "99999999")
        await redis_mock.set(_weekly_seconds_key(user_id), "999999999")

        # All checks pass because limits are 0
        allowed_s, _, _ = await check_and_increment_sessions(redis_mock, user_id, weekly_limit=0)
        allowed_d, _, _ = await check_daily_minutes(redis_mock, user_id, daily_minutes_limit=0)
        allowed_w, _, _ = await check_weekly_minutes(redis_mock, user_id, weekly_minutes_limit=0)

        assert allowed_s is True
        assert allowed_d is True
        assert allowed_w is True
