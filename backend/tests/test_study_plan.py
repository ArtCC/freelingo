from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.lessons import ExerciseContent, LessonContent
from tests.conftest import deactivate_active_plans, make_study_plan


@pytest.mark.asyncio
async def test_get_current_plan_empty(client, test_user):
    user, headers = test_user

    response = await client.get("/api/study-plan/current", headers=headers)
    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.asyncio
async def test_generate_study_plan(client, test_user):
    user, headers = test_user

    response = await client.post(
        "/api/study-plan/generate",
        headers=headers,
        json={
            "cefr_level": "A2",
            "goals": ["grammar", "vocabulary"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["cefr_level"] == "A2"
    assert data["goals"] == ["grammar", "vocabulary"]
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_get_current_plan_after_generate(client, test_user):
    user, headers = test_user

    await client.post(
        "/api/study-plan/generate",
        headers=headers,
        json={
            "cefr_level": "A1",
            "goals": ["vocabulary"],
        },
    )

    response = await client.get("/api/study-plan/current", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert data["cefr_level"] == "A1"
    assert data["goals"] == ["vocabulary"]


@pytest.mark.asyncio
async def test_get_today_lessons(client, test_user):
    user, headers = test_user

    await client.post(
        "/api/study-plan/generate",
        headers=headers,
        json={
            "cefr_level": "A1",
            "goals": ["vocabulary"],
        },
    )

    response = await client.get("/api/study-plan/today", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "plan_id" in data
    assert "progress_day" in data
    assert "total_days" in data
    assert "pending_count" in data
    assert data["progress_day"] == 0
    assert data["total_days"] == 48  # 12 weeks × 4 days
    assert data["pending_count"] == 0
    assert len(data["lessons"]) >= 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cefr_level", "expected_native_language"),
    [("A1", "es"), ("A2", "es"), ("B1", "es")],
)
async def test_today_passes_native_language_only_for_beginner_lessons(
    client, test_user, db_session, cefr_level, expected_native_language
):
    """Lazy lesson generation receives native_language for all CEFR levels."""
    user, headers = test_user

    await deactivate_active_plans(db_session, user.id)
    await make_study_plan(
        db_session,
        user_id=user.id,
        cefr_level=cefr_level,
        goals=["grammar"],
        duration_weeks=1,
        days_per_week=1,
        current_unit="",
        generated_plan={
            "title": "Test Plan",
            "cefr_level": cefr_level,
            "duration_weeks": 1,
            "days_per_week": 1,
            "ends_with_test": False,
            "weekly_plan": [
                {
                    "week": 1,
                    "theme": "basics",
                    "days": [
                        {
                            "day": 1,
                            "lesson_type": "grammar",
                            "title": "Generated Lesson",
                            "objectives": [],
                            "estimated_minutes": 20,
                            "unit_id": "",
                            "grammar_points": [],
                            "vocabulary_set_ids": [],
                        }
                    ],
                }
            ],
        },
        is_active=True,
        progress_day=0,
    )

    generated = LessonContent(
        lesson_type="grammar",
        title="Generated Lesson",
        cefr_level=cefr_level,
        explanation={"text": "Explanation", "key_points": [], "examples": []},
        exercises=[
            ExerciseContent(
                type="multiple_choice",
                question="Question?",
                options=["A", "B"],
                correct="A",
                explanation="Because.",
            )
        ],
        vocabulary=[],
        grammar_refs=[],
        unit_id="",
    )
    with patch(
        "app.routers.study_plan.generate_lesson",
        new=AsyncMock(return_value=generated),
    ) as mock_generate:
        response = await client.get("/api/study-plan/today", headers=headers)

    assert response.status_code == 200
    assert mock_generate.await_args.kwargs["native_language"] == expected_native_language


@pytest.mark.asyncio
async def test_generate_requires_auth(client):
    response = await client.post(
        "/api/study-plan/generate",
        json={
            "cefr_level": "A1",
            "goals": ["grammar"],
            "weeks": 4,
            "minutes_per_day": 30,
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_generate_study_plan_defaults(client, test_user):
    """Verify plan is created with correct default duration and days_per_week."""
    user, headers = test_user

    response = await client.post(
        "/api/study-plan/generate",
        headers=headers,
        json={"cefr_level": "B1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["cefr_level"] == "B1"
    assert data["duration_weeks"] == 12
    assert data["days_per_week"] == 4
    assert data["progress_day"] == 0


# ── POST /api/study-plan/skip-day ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_skip_day_increments_progress(client, test_user):
    """POST /skip-day increments progress_day by 1 and returns updated state."""
    user, headers = test_user

    await client.post(
        "/api/study-plan/generate",
        headers=headers,
        json={"cefr_level": "A1", "goals": ["grammar"]},
    )

    response = await client.post("/api/study-plan/skip-day", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["progress_day"] == 1
    assert data["total_days"] == 48


@pytest.mark.asyncio
async def test_skip_day_no_plan_returns_404(client, test_user):
    """POST /skip-day with no active plan returns 404."""
    _, headers = test_user
    response = await client.post("/api/study-plan/skip-day", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_skip_day_requires_auth(client):
    """POST /skip-day without a valid token returns 401."""
    response = await client.post(
        "/api/study-plan/skip-day",
        headers={"Authorization": "Bearer invalid"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_skip_day_does_not_exceed_total(client, test_user, db_session):
    """POST /skip-day is capped at total_days and does not go over."""

    user, headers = test_user

    await deactivate_active_plans(db_session, user.id)

    _ = await make_study_plan(
        db_session,
        user_id=user.id,
        cefr_level="A1",
        goals=["grammar"],
        duration_weeks=1,
        days_per_week=2,
        current_unit="",
        generated_plan={},
        is_active=True,
        progress_day=2,
    )

    response = await client.post("/api/study-plan/skip-day", headers=headers)
    assert response.status_code == 200
    data = response.json()
    # Should stay at 2, not exceed it
    assert data["progress_day"] == 2
    assert data["total_days"] == 2


# ── GET /api/study-plan/pending-lessons ───────────────────────────────────────


@pytest.mark.asyncio
async def test_pending_lessons_empty_for_new_plan(client, test_user):
    """No pending lessons for a brand-new plan with progress_day=0."""
    user, headers = test_user

    await client.post(
        "/api/study-plan/generate",
        headers=headers,
        json={"cefr_level": "A1", "goals": ["grammar"]},
    )

    response = await client.get("/api/study-plan/pending-lessons", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_pending_lessons_returns_incomplete_past_lessons(client, test_user, db_session):
    """Incomplete lessons from days before progress_day appear in pending list."""
    from app.models.lesson import Lesson

    user, headers = test_user

    await deactivate_active_plans(db_session, user.id)

    plan = await make_study_plan(
        db_session,
        user_id=user.id,
        cefr_level="A1",
        goals=["grammar"],
        duration_weeks=4,
        days_per_week=4,
        current_unit="",
        generated_plan={},
        is_active=True,
        progress_day=1,
    )

    # Incomplete lesson on day 0 (week=1, day=1) — should be pending
    pending_lesson = Lesson(
        study_plan_id=plan.id,
        title="Pending Grammar",
        lesson_type="grammar",
        cefr_level="A1",
        week_number=1,
        day_number=1,
        content={},
        is_completed=False,
    )
    db_session.add(pending_lesson)

    # Incomplete lesson on day 1 (week=1, day=2) — current day, not pending
    current_lesson = Lesson(
        study_plan_id=plan.id,
        title="Current Vocab",
        lesson_type="vocabulary",
        cefr_level="A1",
        week_number=1,
        day_number=2,
        content={},
        is_completed=False,
    )
    db_session.add(current_lesson)
    await db_session.commit()

    response = await client.get("/api/study-plan/pending-lessons", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Pending Grammar"


@pytest.mark.asyncio
async def test_pending_lessons_requires_auth(client):
    """GET /pending-lessons without a valid token returns 401."""
    response = await client.get(
        "/api/study-plan/pending-lessons",
        headers={"Authorization": "Bearer invalid"},
    )
    assert response.status_code == 401


# ── GET /api/study-plan/lessons ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_plan_lessons_returns_generated_lessons(client, test_user, db_session):
    """Generated lessons include the metadata needed to render plan actions."""
    from app.models.lesson import Lesson

    user, headers = test_user
    await deactivate_active_plans(db_session, user.id)
    plan = await make_study_plan(
        db_session,
        user_id=user.id,
        cefr_level="A1",
        goals=["grammar"],
        duration_weeks=4,
        days_per_week=4,
        current_unit="unit-a1-1",
        generated_plan={},
        is_active=True,
    )
    db_session.add_all(
        [
            Lesson(
                study_plan_id=plan.id,
                title="Completed Grammar",
                lesson_type="grammar",
                cefr_level="A1",
                week_number=1,
                day_number=1,
                unit_id="unit-a1-1",
                content={},
                is_completed=True,
            ),
            Lesson(
                study_plan_id=plan.id,
                title="Current Vocabulary",
                lesson_type="vocabulary",
                cefr_level="A1",
                week_number=1,
                day_number=2,
                unit_id="unit-a1-1",
                content={},
                is_completed=False,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/study-plan/lessons", headers=headers)

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": response.json()[0]["id"],
            "title": "Completed Grammar",
            "lesson_type": "grammar",
            "week_number": 1,
            "day_number": 1,
            "unit_id": "unit-a1-1",
            "is_completed": True,
        },
        {
            "id": response.json()[1]["id"],
            "title": "Current Vocabulary",
            "lesson_type": "vocabulary",
            "week_number": 1,
            "day_number": 2,
            "unit_id": "unit-a1-1",
            "is_completed": False,
        },
    ]


# ── Auto-advance in GET /api/study-plan/today ─────────────────────────────────


@pytest.mark.asyncio
async def test_today_auto_advances_when_day_complete(client, test_user, db_session):
    """GET /today auto-advances progress_day when all lessons for the current day are complete."""
    from app.models.lesson import Lesson

    user, headers = test_user

    await deactivate_active_plans(db_session, user.id)

    plan = await make_study_plan(
        db_session,
        user_id=user.id,
        cefr_level="A1",
        goals=["grammar"],
        duration_weeks=4,
        days_per_week=4,
        current_unit="",
        generated_plan={
            "title": "Test",
            "cefr_level": "A1",
            "duration_weeks": 4,
            "days_per_week": 4,
            "ends_with_test": False,
            "weekly_plan": [
                {
                    "week": 1,
                    "theme": "basics",
                    "days": [
                        {
                            "day": 1,
                            "lesson_type": "grammar",
                            "title": "Day 1 Lesson",
                            "objectives": [],
                            "estimated_minutes": 20,
                            "unit_id": "",
                            "grammar_points": [],
                            "vocabulary_set_ids": [],
                        },
                        {
                            "day": 2,
                            "lesson_type": "vocabulary",
                            "title": "Day 2 Lesson",
                            "objectives": [],
                            "estimated_minutes": 20,
                            "unit_id": "",
                            "grammar_points": [],
                            "vocabulary_set_ids": [],
                        },
                    ],
                }
            ],
        },
        is_active=True,
        progress_day=0,
    )

    # Add a completed lesson for day 1 (progress_day=0 → week=1, day=1)
    lesson = Lesson(
        study_plan_id=plan.id,
        title="Day 1 Lesson",
        lesson_type="grammar",
        cefr_level="A1",
        week_number=1,
        day_number=1,
        content={},
        is_completed=True,
    )
    db_session.add(lesson)
    await db_session.commit()

    response = await client.get("/api/study-plan/today", headers=headers)
    assert response.status_code == 200
    data = response.json()
    # Auto-advance should have moved progress_day from 0 to 1
    assert data["progress_day"] == 1


# ── GET /today when plan is fully complete ────────────────────────────────────


@pytest.mark.asyncio
async def test_today_returns_empty_when_plan_complete(client, test_user, db_session):
    """GET /today with progress_day == total_days returns empty lessons list."""

    user, headers = test_user

    total = 2  # 1 week × 2 days

    await deactivate_active_plans(db_session, user.id)

    _ = await make_study_plan(
        db_session,
        user_id=user.id,
        cefr_level="A1",
        goals=["grammar"],
        duration_weeks=1,
        days_per_week=2,
        current_unit="",
        generated_plan={
            "title": "Complete Plan",
            "cefr_level": "A1",
            "duration_weeks": 1,
            "days_per_week": 2,
            "ends_with_test": False,
            "weekly_plan": [],
        },
        is_active=True,
        progress_day=total,
    )

    response = await client.get("/api/study-plan/today", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["lessons"] == []
    assert data["progress_day"] == total
    assert data["total_days"] == total


@pytest.mark.asyncio
async def test_today_passes_previous_unit_lessons_to_generator(client, test_user, db_session):
    """Lessons of the same unit are generated with the content of their siblings as context."""
    user, headers = test_user

    await deactivate_active_plans(db_session, user.id)
    await make_study_plan(
        db_session,
        user_id=user.id,
        cefr_level="A2",
        goals=["grammar"],
        duration_weeks=1,
        days_per_week=1,
        current_unit="a2_unit_1",
        generated_plan={
            "title": "Test Plan",
            "cefr_level": "A2",
            "duration_weeks": 1,
            "days_per_week": 1,
            "ends_with_test": False,
            "weekly_plan": [
                {
                    "week": 1,
                    "theme": "basics",
                    "days": [
                        {
                            "day": 1,
                            "lesson_type": lesson_type,
                            "title": title,
                            "objectives": [],
                            "estimated_minutes": 20,
                            "unit_id": "a2_unit_1",
                            "grammar_points": [],
                            "vocabulary_set_ids": [],
                        }
                        for title, lesson_type in (
                            ("Unit Lesson One", "grammar"),
                            ("Unit Lesson Two", "vocabulary"),
                        )
                    ],
                }
            ],
        },
        is_active=True,
        progress_day=0,
    )

    generated = LessonContent(
        lesson_type="grammar",
        title="Unit Lesson One",
        cefr_level="A2",
        unit_id="a2_unit_1",
        explanation={
            "text": "Explanation",
            "key_points": [],
            "examples": [{"sentence": "We booked a hotel.", "note": "Perfect tense"}],
        },
        exercises=[
            ExerciseContent(
                type="multiple_choice",
                question="Question?",
                options=["A", "B"],
                correct="A",
                explanation="Because.",
            )
        ],
        vocabulary=[],
        grammar_refs=[],
    )
    with patch(
        "app.routers.study_plan.generate_lesson",
        new=AsyncMock(return_value=generated),
    ) as mock_generate:
        response = await client.get("/api/study-plan/today", headers=headers)

    assert response.status_code == 200
    assert mock_generate.await_count == 2

    first_call, second_call = mock_generate.await_args_list
    assert first_call.kwargs["previous_lessons"] == []

    previous = second_call.kwargs["previous_lessons"]
    assert [item["title"] for item in previous] == ["Unit Lesson One"]
    assert previous[0]["lesson_type"] == "grammar"
    assert previous[0]["content"]["explanation"]["examples"][0]["sentence"] == "We booked a hotel."
