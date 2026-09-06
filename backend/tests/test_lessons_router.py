"""Comprehensive unit tests for backend/app/routers/lessons.py

Covers all 4 endpoints with auth, validation, edge cases, LLM mocking,
cross-user isolation, and full lesson lifecycle.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.schemas.lessons import (
    FillBlankEvaluation,
    FreeWriteCorrection,
    FreeWriteEvaluation,
    NativeExerciseHintResponse,
    NativeExplanationResponse,
    PronunciationEvaluation,
)
from app.services.llm_adapter import LLMError, LLMTimeoutError, LLMUnavailableError

# ── helpers ──────────────────────────────────────────────────────────────────


async def _create_lesson_with_plan(db_session, user_id, **kwargs):
    """Create a StudyPlan + Lesson owned by user_id."""
    from app.models.lesson import Lesson
    from tests.conftest import make_study_plan

    plan = await make_study_plan(
        db_session,
        user_id=user_id,
        cefr_level="A2",
        goals=["grammar"],
        duration_weeks=4,
        days_per_week=4,
        current_unit="",
        generated_plan={},
        is_active=True,
    )
    defaults = dict(
        study_plan_id=plan.id,
        title="Test Lesson",
        lesson_type="grammar",
        cefr_level="A2",
        week_number=1,
        day_number=1,
        content={},
    )
    defaults.update(kwargs)
    lesson = Lesson(**defaults)
    db_session.add(lesson)
    await db_session.commit()
    await db_session.refresh(lesson)
    return lesson


async def _create_lesson_with_exercise(
    db_session, user_id, *, exercise_type="multiple_choice", **ex_kwargs
):
    """Create StudyPlan + Lesson + Exercise. Returns (lesson, exercise)."""
    from app.models.lesson import Exercise, Lesson
    from tests.conftest import make_study_plan

    plan = await make_study_plan(
        db_session,
        user_id=user_id,
        cefr_level="A2",
        goals=["grammar"],
        duration_weeks=4,
        days_per_week=4,
        current_unit="",
        generated_plan={},
        is_active=True,
    )
    lesson = Lesson(
        study_plan_id=plan.id,
        title="Test Lesson",
        lesson_type="grammar",
        cefr_level="A2",
        week_number=1,
        day_number=1,
        content={},
    )
    db_session.add(lesson)
    await db_session.flush()

    defaults = dict(
        lesson_id=lesson.id,
        exercise_type=exercise_type,
        question="Test question?",
        options=["A", "B", "C", "D"],
        correct_answer="B",
    )
    defaults.update(ex_kwargs)
    exercise = Exercise(**defaults)
    db_session.add(exercise)
    await db_session.commit()
    await db_session.refresh(lesson)
    await db_session.refresh(exercise)
    return lesson, exercise


# ── GET /api/lessons/{lesson_id} ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_lesson_requires_auth(client):
    """GET /lessons/{id} without token returns 401."""
    response = await client.get("/api/lessons/1")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_lesson_other_user_forbidden(client, test_user, db_session):
    """User cannot GET a lesson that belongs to another user's plan."""
    from app.core.security import hash_password
    from app.models.user import User

    owner = User(
        username="lessonowner2",
        email="lessonowner2@example.com",
        display_name="Lesson Owner",
        hashed_password=hash_password("ownerpass"),
        role="user",
        native_language="es",
        is_active=True,
    )
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)

    lesson = await _create_lesson_with_plan(db_session, owner.id)

    _, headers_other = test_user
    response = await client.get(f"/api/lessons/{lesson.id}", headers=headers_other)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_lesson_fill_blank_sanitization(client, test_user, db_session):
    """Fill-blank exercises with ___ in explanation but not question are swapped."""
    from app.models.lesson import Exercise

    user, headers = test_user
    lesson = await _create_lesson_with_plan(db_session, user.id)

    ex = Exercise(
        lesson_id=lesson.id,
        exercise_type="fill_blank",
        question="Complete the sentence with the correct word.",
        options=None,
        correct_answer="Her",
        explanation="___ name is Maria. (she)",
    )
    db_session.add(ex)
    await db_session.commit()

    response = await client.get(f"/api/lessons/{lesson.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["exercises"]) == 1
    exercise_data = data["exercises"][0]
    # Sanitized: question should now contain the gapped sentence
    assert "___" in exercise_data["question"]
    assert "name is Maria" in exercise_data["question"]
    # Original explanation should be swapped into explanation field
    assert exercise_data["explanation"] == "Complete the sentence with the correct word."


@pytest.mark.asyncio
async def test_get_lesson_fill_blank_already_correct(client, test_user, db_session):
    """Fill-blank exercises that already have ___ in question are NOT swapped."""
    from app.models.lesson import Exercise

    user, headers = test_user
    lesson = await _create_lesson_with_plan(db_session, user.id)

    ex = Exercise(
        lesson_id=lesson.id,
        exercise_type="fill_blank",
        question="___ name is Maria. (she)",
        options=None,
        correct_answer="Her",
        explanation="Use possessive adjective.",
    )
    db_session.add(ex)
    await db_session.commit()

    response = await client.get(f"/api/lessons/{lesson.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    exercise_data = data["exercises"][0]
    # Already correct: question should keep the gapped sentence
    assert "___ name is Maria" in exercise_data["question"]
    assert exercise_data["explanation"] == "Use possessive adjective."


@pytest.mark.asyncio
async def test_get_lesson_no_exercises(client, test_user, db_session):
    """GET lesson with zero exercises returns empty exercises list."""
    user, headers = test_user
    lesson = await _create_lesson_with_plan(db_session, user.id)

    response = await client.get(f"/api/lessons/{lesson.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["lesson"]["title"] == "Test Lesson"
    assert data["exercises"] == []


@pytest.mark.asyncio
async def test_generate_native_explanation_persists_content(client, test_user, db_session):
    """POST /native-explanation translates a lesson explanation and stores it."""
    user, headers = test_user
    lesson = await _create_lesson_with_plan(
        db_session,
        user.id,
        content={
            "explanation": {
                "text": "German nouns have gender.",
                "key_points": ["Use der, die, das."],
                "examples": [{"sentence": "Das ist ein Haus.", "note": "Neuter noun."}],
            }
        },
    )

    translated = NativeExplanationResponse(
        text="Los sustantivos alemanes tienen genero.",
        key_points=["Usa der, die, das."],
        examples=[{"sentence": "Das ist ein Haus.", "note": "Sustantivo neutro."}],
    )
    with patch(
        "app.routers.lessons.llm_adapter.structured_output",
        new=AsyncMock(return_value=translated),
    ) as mock_structured:
        response = await client.post(
            f"/api/lessons/{lesson.id}/native-explanation", headers=headers
        )

    assert response.status_code == 200
    assert response.json()["native_explanation"]["text"] == translated.text
    prompt = mock_structured.await_args.args[0][0]["content"]
    assert "<<<EXPLANATION_JSON" in prompt
    assert "German nouns have gender." in prompt

    await db_session.refresh(lesson)
    assert lesson.content["native_explanation"]["text"] == translated.text


@pytest.mark.asyncio
async def test_generate_native_explanation_returns_existing(client, test_user, db_session):
    """POST /native-explanation is idempotent when the translation already exists."""
    user, headers = test_user
    existing = {
        "text": "Ya traducido.",
        "key_points": ["Punto clave."],
        "examples": [],
    }
    lesson = await _create_lesson_with_plan(
        db_session,
        user.id,
        content={"explanation": {"text": "Source"}, "native_explanation": existing},
    )

    with patch(
        "app.routers.lessons.llm_adapter.structured_output",
        new=AsyncMock(),
    ) as mock_structured:
        response = await client.post(
            f"/api/lessons/{lesson.id}/native-explanation", headers=headers
        )

    assert response.status_code == 200
    assert response.json()["native_explanation"] == existing
    mock_structured.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_native_explanation_accepts_b1_plus(client, test_user, db_session):
    """Native explanations are generated for all levels, including B1+."""
    user, headers = test_user
    lesson = await _create_lesson_with_plan(
        db_session,
        user.id,
        cefr_level="B1",
        content={"explanation": {"text": "Source"}},
    )

    translated = NativeExplanationResponse(
        text="Traducción de B1.",
        key_points=["Punto clave."],
        examples=[],
    )
    with patch(
        "app.routers.lessons.llm_adapter.structured_output",
        new=AsyncMock(return_value=translated),
    ):
        response = await client.post(
            f"/api/lessons/{lesson.id}/native-explanation", headers=headers
        )

    assert response.status_code == 200
    assert response.json()["native_explanation"]["text"] == translated.text


@pytest.mark.asyncio
async def test_get_lesson_includes_user_answers(client, test_user, db_session):
    """GET lesson returns exercises with user_answer, score, feedback when answered."""
    from app.models.lesson import Exercise

    user, headers = test_user
    lesson = await _create_lesson_with_plan(db_session, user.id)

    ex = Exercise(
        lesson_id=lesson.id,
        exercise_type="multiple_choice",
        question="Q?",
        options=["A", "B"],
        correct_answer="B",
        user_answer="B",
        score=1.0,
        feedback="Correct!",
    )
    db_session.add(ex)
    await db_session.commit()

    response = await client.get(f"/api/lessons/{lesson.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["exercises"][0]["user_answer"] == "B"
    assert data["exercises"][0]["score"] == 1.0
    assert data["exercises"][0]["feedback"] == "Correct!"


@pytest.mark.asyncio
async def test_get_lesson_includes_native_hint_from_content(client, test_user, db_session):
    """GET lesson returns exercise native_hint from generated lesson JSON."""
    from app.models.lesson import Exercise

    user, headers = test_user
    lesson = await _create_lesson_with_plan(
        db_session,
        user.id,
        content={"exercises": [{"native_hint": "Fíjate en el sujeto."}]},
    )

    ex = Exercise(
        lesson_id=lesson.id,
        exercise_type="fill_blank",
        question="Ich ___ müde.",
        options=None,
        correct_answer="bin",
        explanation="Use the first-person form.",
    )
    db_session.add(ex)
    await db_session.commit()

    response = await client.get(f"/api/lessons/{lesson.id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["exercises"][0]["native_hint"] == "Fíjate en el sujeto."


@pytest.mark.asyncio
async def test_generate_native_hint_returns_existing(client, test_user, db_session):
    """POST /native-hint returns cached exercise hint without calling the LLM."""
    from app.models.lesson import Exercise

    user, headers = test_user
    lesson = await _create_lesson_with_plan(
        db_session,
        user.id,
        content={"exercises": [{"native_hint": "Ya existe."}]},
    )
    ex = Exercise(
        lesson_id=lesson.id,
        exercise_type="multiple_choice",
        question="Q?",
        options=["A", "B"],
        correct_answer="B",
        explanation="Choose B.",
    )
    db_session.add(ex)
    await db_session.commit()
    await db_session.refresh(ex)

    with patch(
        "app.routers.lessons.llm_adapter.structured_output",
        new=AsyncMock(),
    ) as mock_structured:
        response = await client.post(f"/api/lessons/exercises/{ex.id}/native-hint", headers=headers)

    assert response.status_code == 200
    assert response.json()["native_hint"] == "Ya existe."
    mock_structured.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_native_hint_persists_content(client, test_user, db_session):
    """POST /native-hint generates and stores a missing exercise hint."""
    from app.models.lesson import Exercise

    user, headers = test_user
    lesson = await _create_lesson_with_plan(
        db_session,
        user.id,
        content={"exercises": [{}]},
    )
    ex = Exercise(
        lesson_id=lesson.id,
        exercise_type="fill_blank",
        question="Ich ___ müde.",
        options=None,
        correct_answer="bin",
        explanation="Use the first-person form of sein.",
    )
    db_session.add(ex)
    await db_session.commit()
    await db_session.refresh(ex)

    generated = NativeExerciseHintResponse(native_hint="Fíjate en el sujeto y el verbo.")
    with patch(
        "app.routers.lessons.llm_adapter.structured_output",
        new=AsyncMock(return_value=generated),
    ) as mock_structured:
        response = await client.post(f"/api/lessons/exercises/{ex.id}/native-hint", headers=headers)

    assert response.status_code == 200
    assert response.json()["native_hint"] == generated.native_hint
    prompt = mock_structured.await_args.args[0][0]["content"]
    assert "Do not reveal the answer" in prompt
    assert "Ich ___ müde." in prompt

    await db_session.refresh(lesson)
    assert lesson.content["exercises"][0]["native_hint"] == generated.native_hint


@pytest.mark.asyncio
async def test_generate_native_hint_rejects_answer_revealing_hint(client, test_user, db_session):
    """POST /native-hint rejects generated hints that contain the answer literally."""
    from app.models.lesson import Exercise

    user, headers = test_user
    lesson = await _create_lesson_with_plan(
        db_session,
        user.id,
        content={"exercises": [{}]},
    )
    ex = Exercise(
        lesson_id=lesson.id,
        exercise_type="fill_blank",
        question="Ich ___ müde.",
        options=None,
        correct_answer="bin",
        explanation="Use the first-person form of sein.",
    )
    db_session.add(ex)
    await db_session.commit()
    await db_session.refresh(ex)

    generated = NativeExerciseHintResponse(native_hint="Piensa en la forma bin.")
    with patch(
        "app.routers.lessons.llm_adapter.structured_output",
        new=AsyncMock(return_value=generated),
    ):
        response = await client.post(f"/api/lessons/exercises/{ex.id}/native-hint", headers=headers)

    assert response.status_code == 503

    await db_session.refresh(lesson)
    assert "native_hint" not in lesson.content["exercises"][0]


# ── POST /api/lessons/{lesson_id}/complete ───────────────────────────────────


@pytest.mark.asyncio
async def test_complete_lesson_requires_auth(client):
    """POST /complete without token returns 401."""
    response = await client.post("/api/lessons/1/complete")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_complete_lesson_other_user_forbidden(client, test_user, db_session):
    """User cannot complete a lesson belonging to another user."""
    from app.core.security import hash_password
    from app.models.user import User

    owner = User(
        username="otherlessonowner",
        email="otherlessonowner@example.com",
        display_name="Other Owner",
        hashed_password=hash_password("ownerpass"),
        role="user",
        native_language="es",
        is_active=True,
    )
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)

    lesson = await _create_lesson_with_plan(db_session, owner.id)

    _, headers_other = test_user
    response = await client.post(f"/api/lessons/{lesson.id}/complete", headers=headers_other)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_complete_lesson_already_completed(client, test_user, db_session):
    """Completing an already-completed lesson succeeds (idempotent)."""
    user, headers = test_user
    lesson = await _create_lesson_with_plan(db_session, user.id)

    with patch("app.routers.lessons.update_daily_progress", new_callable=AsyncMock) as progress:
        r1 = await client.post(f"/api/lessons/{lesson.id}/complete", headers=headers)
        r2 = await client.post(f"/api/lessons/{lesson.id}/complete", headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["is_completed"] is True
    assert r2.json()["completed_at"] == r1.json()["completed_at"]
    progress.assert_awaited_once()


@pytest.mark.asyncio
async def test_complete_lesson_rolls_back_when_progress_update_fails(client, test_user, db_session):
    """Completion and progress updates commit atomically."""
    user, headers = test_user
    lesson = await _create_lesson_with_plan(db_session, user.id)

    with (
        patch(
            "app.routers.lessons.update_daily_progress",
            new_callable=AsyncMock,
            side_effect=RuntimeError("progress failed"),
        ),
        pytest.raises(RuntimeError, match="progress failed"),
    ):
        await client.post(f"/api/lessons/{lesson.id}/complete", headers=headers)

    await db_session.rollback()
    await db_session.refresh(lesson)
    assert lesson.is_completed is False
    assert lesson.completed_at is None


@pytest.mark.asyncio
async def test_complete_lesson_retry_bypasses_quota_check(client, test_user, db_session):
    """An already-completed lesson remains readable when no quota remains."""
    user, headers = test_user
    lesson = await _create_lesson_with_plan(db_session, user.id)
    lesson.is_completed = True
    await db_session.commit()

    with patch(
        "app.routers.lessons.check_subscription_or_freemium_access",
        new_callable=AsyncMock,
    ) as access_check:
        response = await client.post(f"/api/lessons/{lesson.id}/complete", headers=headers)

    assert response.status_code == 200
    assert response.json()["is_completed"] is True
    access_check.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_lesson_sets_completed_at(client, test_user, db_session):
    """Complete sets completed_at to a non-null datetime."""
    user, headers = test_user
    lesson = await _create_lesson_with_plan(db_session, user.id)

    response = await client.post(f"/api/lessons/{lesson.id}/complete", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["is_completed"] is True
    assert data["completed_at"] is not None


@pytest.mark.asyncio
async def test_complete_lesson_with_unit_id(client, test_user, db_session):
    """Complete a lesson that has a unit_id — exercises competency scoring path."""
    user, headers = test_user
    lesson = await _create_lesson_with_plan(db_session, user.id, unit_id="a2-unit-1")

    response = await client.post(f"/api/lessons/{lesson.id}/complete", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_completed"] is True


@pytest.mark.asyncio
async def test_complete_lesson_with_scored_exercises(client, test_user, db_session):
    """Complete lesson with previously scored exercises — computes lesson_score."""
    from app.models.lesson import Exercise

    user, headers = test_user
    lesson = await _create_lesson_with_plan(db_session, user.id, unit_id="a2-unit-1")

    e1 = Exercise(
        lesson_id=lesson.id,
        exercise_type="multiple_choice",
        question="Q1",
        options=["A", "B"],
        correct_answer="B",
        score=0.8,
    )
    e2 = Exercise(
        lesson_id=lesson.id,
        exercise_type="multiple_choice",
        question="Q2",
        options=["A", "B"],
        correct_answer="A",
        score=1.0,
    )
    db_session.add_all([e1, e2])
    await db_session.commit()

    response = await client.post(f"/api/lessons/{lesson.id}/complete", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_completed"] is True


# ── POST /api/lessons/exercises/{exercise_id}/answer ─────────────────────────


@pytest.mark.asyncio
async def test_answer_exercise_requires_auth(client):
    """Answer endpoint without token returns 401."""
    response = await client.post("/api/lessons/exercises/1/answer", json={"answer": "B"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_answer_exercise_not_found(client, test_user):
    """Answering a non-existent exercise returns 404."""
    _, headers = test_user
    response = await client.post(
        "/api/lessons/exercises/99999/answer",
        headers=headers,
        json={"answer": "B"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_answer_exercise_already_answered(client, test_user, db_session):
    """Answering an already-answered exercise returns 409."""
    from datetime import UTC, datetime

    from app.models.lesson import Exercise

    user, headers = test_user
    lesson = await _create_lesson_with_plan(db_session, user.id)

    ex = Exercise(
        lesson_id=lesson.id,
        exercise_type="multiple_choice",
        question="Q?",
        options=["A", "B"],
        correct_answer="B",
        user_answer="B",
        score=1.0,
        feedback="Already done!",
        answered_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(ex)
    await db_session.commit()

    response = await client.post(
        f"/api/lessons/exercises/{ex.id}/answer",
        headers=headers,
        json={"answer": "B"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_answer_exercise_cross_user_forbidden(client, test_user, db_session):
    """User cannot answer an exercise on another user's lesson."""
    from app.core.security import hash_password
    from app.models.user import User

    owner = User(
        username="exowner",
        email="exowner@example.com",
        display_name="Ex Owner",
        hashed_password=hash_password("ownerpass"),
        role="user",
        native_language="es",
        is_active=True,
    )
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)

    lesson, exercise = await _create_lesson_with_exercise(db_session, owner.id)

    _, headers_other = test_user
    response = await client.post(
        f"/api/lessons/exercises/{exercise.id}/answer",
        headers=headers_other,
        json={"answer": "B"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_answer_exercise_missing_body(client, test_user):
    """Answer without body returns 422."""
    _, headers = test_user
    response = await client.post(
        "/api/lessons/exercises/1/answer",
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_answer_exercise_empty_answer_field(client, test_user, db_session):
    """Answer with empty string is valid, returns 200 with score 0."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(db_session, user.id)

    response = await client.post(
        f"/api/lessons/exercises/{exercise.id}/answer",
        headers=headers,
        json={"answer": ""},
    )
    assert response.status_code == 200
    data = response.json()
    # Empty string doesn't match "B", score = 0.0
    assert data["score"] == 0.0


# ── multiple_choice exercises ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_answer_mc_old_format_prefix_answer(client, test_user, db_session):
    """Compatibility: answer 'a. works' when correct_answer is 'works'."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="multiple_choice",
        question="She ___ (work).",
        options=["works", "is working", "worked"],
        correct_answer="works",
    )

    response = await client.post(
        f"/api/lessons/exercises/{exercise.id}/answer",
        headers=headers,
        json={"answer": "a. works"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 1.0


@pytest.mark.asyncio
async def test_answer_mc_old_format_prefix_correct_answer(client, test_user, db_session):
    """Compatibility: correct_answer has prefix 'b. is working' but user sends plain answer."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="multiple_choice",
        question="She ___ (work).",
        options=["works", "is working", "worked"],
        correct_answer="b. is working",
    )

    response = await client.post(
        f"/api/lessons/exercises/{exercise.id}/answer",
        headers=headers,
        json={"answer": "is working"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 1.0


@pytest.mark.asyncio
async def test_answer_mc_both_have_prefixes(client, test_user, db_session):
    """Compatibility: both answer and correct_answer have letter prefixes."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="multiple_choice",
        question="She ___ (work).",
        options=["works", "is working", "worked"],
        correct_answer="b. is working",
    )

    response = await client.post(
        f"/api/lessons/exercises/{exercise.id}/answer",
        headers=headers,
        json={"answer": "b. is working"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 1.0


@pytest.mark.asyncio
async def test_answer_mc_case_insensitive(client, test_user, db_session):
    """MC evaluation is case-insensitive."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="multiple_choice",
        question="Q?",
        options=["A", "B"],
        correct_answer="B",
    )

    response = await client.post(
        f"/api/lessons/exercises/{exercise.id}/answer",
        headers=headers,
        json={"answer": "b"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 1.0


# ── fill_blank exercises (LLM mocked) ────────────────────────────────────────


@pytest.mark.asyncio
async def test_answer_fill_blank_correct(client, test_user, db_session):
    """Fill-blank with LLM returning correct result."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="fill_blank",
        question="___ name is Maria.",
        options=None,
        correct_answer="Her",
    )

    mock_eval = AsyncMock(
        return_value=FillBlankEvaluation(is_correct=True, score=1.0, feedback="Perfect!")
    )

    with patch("app.routers.lessons.evaluate_fill_blank", mock_eval):
        response = await client.post(
            f"/api/lessons/exercises/{exercise.id}/answer",
            headers=headers,
            json={"answer": "Her"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 1.0
    assert data["feedback"] == "Perfect!"
    assert data["correct_answer"] == "Her"
    assert mock_eval.await_args.kwargs["native_language"] == "es"


@pytest.mark.asyncio
async def test_answer_fill_blank_wrong(client, test_user, db_session):
    """Fill-blank with LLM returning wrong result."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="fill_blank",
        question="___ name is Maria.",
        options=None,
        correct_answer="Her",
    )

    mock_eval = AsyncMock(
        return_value=FillBlankEvaluation(
            is_correct=False, score=0.0, feedback="The correct answer is 'Her'."
        )
    )

    with patch("app.routers.lessons.evaluate_fill_blank", mock_eval):
        response = await client.post(
            f"/api/lessons/exercises/{exercise.id}/answer",
            headers=headers,
            json={"answer": "His"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 0.0
    assert "Her" in data["feedback"]
    assert mock_eval.await_args.kwargs["native_language"] == "es"


@pytest.mark.asyncio
async def test_answer_fill_blank_llm_fallback_correct(client, test_user, db_session):
    """When LLM fails, fallback string comparison marks correct answer."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="fill_blank",
        question="___ name is Maria.",
        options=None,
        correct_answer="Her",
    )

    with patch(
        "app.routers.lessons.evaluate_fill_blank",
        side_effect=LLMTimeoutError("timeout"),
    ):
        response = await client.post(
            f"/api/lessons/exercises/{exercise.id}/answer",
            headers=headers,
            json={"answer": "Her"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 1.0
    assert data["feedback"] == "Correcto!"


@pytest.mark.asyncio
async def test_answer_fill_blank_llm_fallback_wrong(client, test_user, db_session):
    """When LLM fails, fallback string comparison marks wrong answer."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="fill_blank",
        question="___ name is Maria.",
        options=None,
        correct_answer="Her",
    )

    with patch(
        "app.routers.lessons.evaluate_fill_blank",
        side_effect=LLMUnavailableError("unavailable"),
    ):
        response = await client.post(
            f"/api/lessons/exercises/{exercise.id}/answer",
            headers=headers,
            json={"answer": "His"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 0.0
    assert "Her" in data["feedback"]
    assert "La respuesta correcta" in data["feedback"]


@pytest.mark.asyncio
async def test_answer_fill_blank_llm_fallback_slash_alternatives(client, test_user, db_session):
    """LLM fallback accepts answers matching any slash-separated alternative."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="fill_blank",
        question="___ name is Maria.",
        options=None,
        correct_answer="Her/his",
    )

    with patch(
        "app.routers.lessons.evaluate_fill_blank",
        side_effect=LLMError("error"),
    ):
        response = await client.post(
            f"/api/lessons/exercises/{exercise.id}/answer",
            headers=headers,
            json={"answer": "his"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 1.0


# ── free_write exercises (LLM mocked) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_answer_free_write_with_llm(client, test_user, db_session):
    """Free-write exercise evaluated by LLM."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="free_write",
        question="Describe your morning routine.",
        options=["grammar", "spelling"],
        correct_answer="Sample answer.",
    )

    mock_eval = AsyncMock(
        return_value=FreeWriteEvaluation(score=0.8, feedback="Good grammar.", corrections=[])
    )

    with patch("app.routers.lessons.evaluate_free_write", mock_eval):
        response = await client.post(
            f"/api/lessons/exercises/{exercise.id}/answer",
            headers=headers,
            json={"answer": "I wake up at 7am and eat breakfast."},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 0.8
    assert data["feedback"] == "Good grammar."
    assert data["corrections"] is None
    assert mock_eval.await_args.kwargs["native_language"] == "es"


@pytest.mark.asyncio
async def test_answer_free_write_returns_and_persists_corrections(client, test_user, db_session):
    """Free-write corrections are returned in the answer and lesson detail responses."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="free_write",
        question="Describe your last trip.",
        options=["grammar"],
        correct_answer="Sample answer.",
    )

    mock_eval = AsyncMock(
        return_value=FreeWriteEvaluation(
            score=0.8,
            feedback="Good.",
            corrections=[
                FreeWriteCorrection(
                    original="mit auto",
                    corrected="mit dem Auto",
                    explanation="Dative article after 'mit'.",
                )
            ],
        )
    )

    with patch("app.routers.lessons.evaluate_free_write", mock_eval):
        response = await client.post(
            f"/api/lessons/exercises/{exercise.id}/answer",
            headers=headers,
            json={"answer": "Ich bin mit auto gefahren."},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["corrections"] == [
        {
            "original": "mit auto",
            "corrected": "mit dem Auto",
            "explanation": "Dative article after 'mit'.",
        }
    ]

    detail = await client.get(f"/api/lessons/{lesson.id}", headers=headers)
    assert detail.status_code == 200
    detail_exercise = detail.json()["exercises"][0]
    assert detail_exercise["corrections"] == data["corrections"]


def test_free_write_evaluation_drops_unusable_corrections():
    """Malformed correction objects from the LLM are discarded, not persisted."""
    evaluation = FreeWriteEvaluation.model_validate(
        {
            "score": 0.7,
            "feedback": "Almost.",
            "corrections": [
                {},
                {"original": "foo"},
                {"original": "   ", "corrected": "bar"},
                {"original": "foo", "corrected": None},
                "not an object",
                {"original": "mit auto", "corrected": "mit dem Auto"},
            ],
        }
    )

    assert [c.model_dump() for c in evaluation.corrections] == [
        {"original": "mit auto", "corrected": "mit dem Auto", "explanation": ""}
    ]


def test_free_write_correction_requires_original_and_corrected():
    """A correction cannot be built without both text fields."""
    with pytest.raises(ValidationError):
        FreeWriteCorrection(original="foo")
    with pytest.raises(ValidationError):
        FreeWriteCorrection(corrected="bar")


@pytest.mark.asyncio
async def test_answer_free_write_persists_only_usable_corrections(client, test_user, db_session):
    """Incomplete correction objects never reach the response or the database."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="free_write",
        question="Describe your last trip.",
        options=["grammar"],
        correct_answer="Sample answer.",
    )

    mock_eval = AsyncMock(
        return_value=FreeWriteEvaluation(
            score=0.8,
            feedback="Good.",
            corrections=[
                {"original": "abenteuer"},
                {"original": "", "corrected": "Abenteuer"},
                {"original": "mit auto", "corrected": "mit dem Auto"},
            ],
        )
    )

    with patch("app.routers.lessons.evaluate_free_write", mock_eval):
        response = await client.post(
            f"/api/lessons/exercises/{exercise.id}/answer",
            headers=headers,
            json={"answer": "Ich bin mit auto gefahren."},
        )

    assert response.status_code == 200
    assert response.json()["corrections"] == [
        {"original": "mit auto", "corrected": "mit dem Auto", "explanation": ""}
    ]

    detail = await client.get(f"/api/lessons/{lesson.id}", headers=headers)
    assert detail.json()["exercises"][0]["corrections"] == response.json()["corrections"]


@pytest.mark.asyncio
async def test_answer_free_write_no_criteria_in_options(client, test_user, db_session):
    """Free-write without useful options uses default criteria."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="free_write",
        question="Describe your morning.",
        options=None,
        correct_answer="Sample.",
    )

    mock_eval = AsyncMock(
        return_value=FreeWriteEvaluation(score=0.7, feedback="Decent.", corrections=[])
    )

    with patch("app.routers.lessons.evaluate_free_write", mock_eval):
        response = await client.post(
            f"/api/lessons/exercises/{exercise.id}/answer",
            headers=headers,
            json={"answer": "I wake up."},
        )

    assert response.status_code == 200
    # Verify default criteria were used (grammar, spelling, coherence)
    call_args = mock_eval.call_args
    assert call_args is not None


@pytest.mark.asyncio
async def test_answer_free_write_llm_fallback(client, test_user, db_session):
    """When LLM fails, free-write fallback returns score 0.5 with placeholder feedback."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="free_write",
        question="Describe your morning.",
        options=["grammar"],
        correct_answer="Sample.",
    )

    with patch(
        "app.routers.lessons.evaluate_free_write",
        side_effect=LLMTimeoutError("timeout"),
    ):
        response = await client.post(
            f"/api/lessons/exercises/{exercise.id}/answer",
            headers=headers,
            json={"answer": "My morning routine is simple."},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 0.5
    assert "No se pudo evaluar" in data["feedback"]
    assert data["corrections"] is None


# ── pronunciation exercises (LLM mocked) ────────────────────────────────────


@pytest.mark.asyncio
async def test_answer_pronunciation_with_llm(client, test_user, db_session):
    """Pronunciation exercise evaluated by LLM."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="pronunciation",
        question="Listen and repeat:",
        options=["Focus on -ing endings"],
        correct_answer="I am working today.",
    )

    mock_eval = AsyncMock(
        return_value=PronunciationEvaluation(
            score=0.85, feedback="Good pronunciation.", is_correct=True
        )
    )

    with patch("app.routers.lessons.evaluate_pronunciation", mock_eval):
        response = await client.post(
            f"/api/lessons/exercises/{exercise.id}/answer",
            headers=headers,
            json={"answer": "I am working today"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 0.85
    assert data["feedback"] == "Good pronunciation."
    assert mock_eval.await_args.kwargs["native_language"] == "es"


@pytest.mark.asyncio
async def test_answer_pronunciation_llm_fallback_exact_match(client, test_user, db_session):
    """Pronunciation LLM fallback: exact match (ignoring punctuation) returns 1.0."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="pronunciation",
        question="Listen and repeat:",
        options=None,
        correct_answer="Hello, world!",
    )

    with patch(
        "app.routers.lessons.evaluate_pronunciation",
        side_effect=LLMUnavailableError("unavailable"),
    ):
        response = await client.post(
            f"/api/lessons/exercises/{exercise.id}/answer",
            headers=headers,
            json={"answer": "Hello, world"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 1.0
    assert data["feedback"] == "Buena pronunciacion!"


@pytest.mark.asyncio
async def test_answer_pronunciation_llm_fallback_contains_target(client, test_user, db_session):
    """Pronunciation LLM fallback: transcription contains target phrase returns 1.0."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="pronunciation",
        question="Listen and repeat:",
        options=None,
        correct_answer="working",
    )

    with patch(
        "app.routers.lessons.evaluate_pronunciation",
        side_effect=LLMError("error"),
    ):
        response = await client.post(
            f"/api/lessons/exercises/{exercise.id}/answer",
            headers=headers,
            json={"answer": "I am working today"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 1.0


@pytest.mark.asyncio
async def test_answer_pronunciation_llm_fallback_mismatch(client, test_user, db_session):
    """Pronunciation LLM fallback: completely different answer returns 0.0."""
    user, headers = test_user
    lesson, exercise = await _create_lesson_with_exercise(
        db_session,
        user.id,
        exercise_type="pronunciation",
        question="Listen and repeat:",
        options=None,
        correct_answer="Good morning",
    )

    with patch(
        "app.routers.lessons.evaluate_pronunciation",
        side_effect=LLMTimeoutError("timeout"),
    ):
        response = await client.post(
            f"/api/lessons/exercises/{exercise.id}/answer",
            headers=headers,
            json={"answer": "Something completely different"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 0.0
    assert "Good morning" in data["feedback"]
    assert "La frase objetivo" in data["feedback"]


# ── lifecycle: start → answer → complete ─────────────────────────────────────


@pytest.mark.asyncio
async def test_full_lesson_lifecycle(client, test_user, db_session):
    """End-to-end: start lesson, answer all exercises, complete lesson."""
    from app.models.lesson import Exercise

    user, headers = test_user
    lesson = await _create_lesson_with_plan(db_session, user.id)

    # Create 2 exercises
    e1 = Exercise(
        lesson_id=lesson.id,
        exercise_type="multiple_choice",
        question="Q1?",
        options=["A", "B"],
        correct_answer="B",
    )
    e2 = Exercise(
        lesson_id=lesson.id,
        exercise_type="multiple_choice",
        question="Q2?",
        options=["A", "B"],
        correct_answer="A",
    )
    db_session.add_all([e1, e2])
    await db_session.commit()
    await db_session.refresh(e1)
    await db_session.refresh(e2)

    # Step 1: Start lesson
    r_start = await client.post(f"/api/lessons/{lesson.id}/start", headers=headers)
    assert r_start.status_code == 200
    assert r_start.json()["id"] == lesson.id

    # Step 2: Get lesson with exercises
    r_get = await client.get(f"/api/lessons/{lesson.id}", headers=headers)
    assert r_get.status_code == 200
    assert len(r_get.json()["exercises"]) == 2

    # Step 3: Answer both exercises
    r_a1 = await client.post(
        f"/api/lessons/exercises/{e1.id}/answer",
        headers=headers,
        json={"answer": "B"},
    )
    assert r_a1.status_code == 200
    assert r_a1.json()["score"] == 1.0

    r_a2 = await client.post(
        f"/api/lessons/exercises/{e2.id}/answer",
        headers=headers,
        json={"answer": "B"},  # wrong answer
    )
    assert r_a2.status_code == 200
    assert r_a2.json()["score"] == 0.0

    # Step 4: Answering same exercise again fails
    r_dup = await client.post(
        f"/api/lessons/exercises/{e1.id}/answer",
        headers=headers,
        json={"answer": "B"},
    )
    assert r_dup.status_code == 409

    # Step 5: Complete lesson
    r_complete = await client.post(f"/api/lessons/{lesson.id}/complete", headers=headers)
    assert r_complete.status_code == 200
    assert r_complete.json()["is_completed"] is True


@pytest.mark.asyncio
async def test_lifecycle_lesson_with_unit(client, test_user, db_session):
    """Lifecycle for a lesson with unit_id — exercises competency scoring."""
    from app.models.lesson import Exercise

    user, headers = test_user
    lesson = await _create_lesson_with_plan(db_session, user.id, unit_id="a2-unit-1")

    e1 = Exercise(
        lesson_id=lesson.id,
        exercise_type="multiple_choice",
        question="Q1?",
        options=["A", "B"],
        correct_answer="B",
    )
    db_session.add(e1)
    await db_session.commit()
    await db_session.refresh(e1)

    # Answer exercise
    await client.post(
        f"/api/lessons/exercises/{e1.id}/answer",
        headers=headers,
        json={"answer": "B"},
    )

    # Complete with unit — triggers competency path
    r_complete = await client.post(f"/api/lessons/{lesson.id}/complete", headers=headers)
    assert r_complete.status_code == 200
    assert r_complete.json()["is_completed"] is True
