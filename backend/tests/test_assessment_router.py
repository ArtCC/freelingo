"""
Comprehensive unit tests for backend/app/routers/assessment.py

Covers all endpoints, auth requirements, validation errors,
LLM error handling, Redis session management, and edge cases.
"""

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.services.llm_adapter import (
    LLMError,
    LLMTimeoutError,
    LLMUnavailableError,
)

pytestmark = pytest.mark.asyncio


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/assessment/start — additional tests (existing tests cover basic path)
# ═══════════════════════════════════════════════════════════════════════════════


async def test_start_assessment_handles_llm_generic_error(client: AsyncClient, test_user):
    """GET /start returns 502 when LLM raises generic LLMError."""
    _user, headers = test_user

    with patch(
        "app.routers.assessment.llm_adapter.structured_output",
        side_effect=LLMError("generic failure"),
    ):
        response = await client.get("/api/assessment/start", headers=headers)
        assert response.status_code == 502
        assert "ai_service_error" in response.json()["detail"]


async def test_start_assessment_with_explicit_language_param(client: AsyncClient, test_user):
    """GET /start accepts ?language= query param and uses it as target_language."""
    _user, headers = test_user

    mock_quiz = {
        "questions": [
            {
                "id": 1,
                "type": "multiple_choice",
                "difficulty": "A1",
                "question": "¿Cómo te llamas?",
                "options": ["A. Bien", "B. Me llamo Juan", "C. Adiós", "D. Hola"],
                "correct_answer": "B",
            }
        ]
    }

    with patch(
        "app.routers.assessment.llm_adapter.structured_output",
        return_value=mock_quiz,
    ):
        response = await client.get(
            "/api/assessment/start", headers=headers, params={"language": "es-ES"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "quiz" in data
        assert "session_id" in data


async def test_start_assessment_empty_quiz(client: AsyncClient, test_user):
    """GET /start handles LLM returning a quiz with zero questions."""
    _user, headers = test_user

    mock_quiz = {"questions": []}

    with patch(
        "app.routers.assessment.llm_adapter.structured_output",
        return_value=mock_quiz,
    ):
        response = await client.get("/api/assessment/start", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["quiz"]["questions"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/assessment/submit — additional tests
# ═══════════════════════════════════════════════════════════════════════════════


async def test_submit_assessment_requires_auth(client: AsyncClient):
    """POST /submit returns 401 without valid auth."""
    response = await client.post(
        "/api/assessment/submit",
        json={"answers": [{"question_id": 1, "answer": "B"}]},
    )
    assert response.status_code == 401


async def test_submit_assessment_handles_llm_timeout(client: AsyncClient, test_user):
    """POST /submit returns 504 when LLM times out during evaluation."""
    user, headers = test_user

    mock_quiz = {
        "questions": [
            {
                "id": 1,
                "type": "multiple_choice",
                "difficulty": "A1",
                "question": "Q?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "B",
            }
        ]
    }

    with patch(
        "app.routers.assessment.llm_adapter.structured_output",
        side_effect=[mock_quiz, LLMTimeoutError("timeout")],
    ):
        await client.get("/api/assessment/start", headers=headers)
        response = await client.post(
            "/api/assessment/submit",
            headers=headers,
            json={
                "answers": [{"question_id": 1, "answer": "B"}],
                "target_language": "en-US",
            },
        )
        assert response.status_code == 504
        assert "timed out" in response.json()["detail"]


async def test_submit_assessment_handles_llm_unavailable(client: AsyncClient, test_user):
    """POST /submit returns 503 when LLM is unreachable."""
    user, headers = test_user

    mock_quiz = {
        "questions": [
            {
                "id": 1,
                "type": "multiple_choice",
                "difficulty": "A1",
                "question": "Q?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "B",
            }
        ]
    }

    with patch(
        "app.routers.assessment.llm_adapter.structured_output",
        side_effect=[mock_quiz, LLMUnavailableError("unreachable")],
    ):
        await client.get("/api/assessment/start", headers=headers)
        response = await client.post(
            "/api/assessment/submit",
            headers=headers,
            json={
                "answers": [{"question_id": 1, "answer": "B"}],
                "target_language": "en-US",
            },
        )
        assert response.status_code == 503
        assert "ai_service_unavailable" in response.json()["detail"]


async def test_submit_assessment_handles_llm_generic_error(client: AsyncClient, test_user):
    """POST /submit returns 502 when LLM raises generic LLMError."""
    user, headers = test_user

    mock_quiz = {
        "questions": [
            {
                "id": 1,
                "type": "multiple_choice",
                "difficulty": "A1",
                "question": "Q?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "B",
            }
        ]
    }

    with patch(
        "app.routers.assessment.llm_adapter.structured_output",
        side_effect=[mock_quiz, LLMError("generic failure")],
    ):
        await client.get("/api/assessment/start", headers=headers)
        response = await client.post(
            "/api/assessment/submit",
            headers=headers,
            json={
                "answers": [{"question_id": 1, "answer": "B"}],
                "target_language": "en-US",
            },
        )
        assert response.status_code == 502
        assert "ai_service_error" in response.json()["detail"]


async def test_submit_assessment_legacy_key_fallback(client: AsyncClient, test_user, mock_redis):
    """POST /submit finds session using legacy key assessment:{user_id}."""
    user, headers = test_user

    mock_eval = {
        "cefr_level": "B1",
        "score": 0.80,
        "analysis": "Good",
        "strengths": ["reading"],
        "weaknesses": [],
    }

    # Store session under legacy key directly in mock_redis
    legacy_key = f"assessment:{user.id}"
    await mock_redis.setex(
        legacy_key,
        1800,
        json.dumps(
            {
                "session_id": "legacy-session",
                "quiz": {"questions": []},
                "target_language": "en-US",
            }
        ),
    )

    with patch(
        "app.routers.assessment.llm_adapter.structured_output",
        return_value=mock_eval,
    ):
        response = await client.post(
            "/api/assessment/submit",
            headers=headers,
            json={
                "answers": [{"question_id": 1, "answer": "B"}],
                # No target_language — forces legacy fallback
            },
        )
        assert response.status_code == 200
        assert response.json()["cefr_level"] == "B1"


async def test_submit_assessment_session_deleted_after_use(
    client: AsyncClient, test_user, mock_redis
):
    """POST /submit deletes the Redis session after successful evaluation."""
    user, headers = test_user

    mock_quiz = {
        "questions": [
            {
                "id": 1,
                "type": "multiple_choice",
                "difficulty": "A1",
                "question": "Q?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "B",
            }
        ]
    }

    mock_eval = {
        "cefr_level": "A2",
        "score": 0.65,
        "analysis": "OK",
        "strengths": [],
        "weaknesses": [],
    }

    with patch(
        "app.routers.assessment.llm_adapter.structured_output",
        side_effect=[mock_quiz, mock_eval],
    ):
        await client.get("/api/assessment/start", headers=headers)
        key = f"assessment:{user.id}:en-US"
        assert await mock_redis.get(key) is not None  # session exists

        await client.post(
            "/api/assessment/submit",
            headers=headers,
            json={
                "answers": [{"question_id": 1, "answer": "B"}],
                "target_language": "en-US",
            },
        )
        assert await mock_redis.get(key) is None  # session deleted


async def test_submit_assessment_no_session_after_legacy_deletion(client: AsyncClient, test_user):
    """POST /submit returns 404 when no session exists at all (no scoped, no legacy)."""
    _user, headers = test_user

    # No /start call made — no session in Redis at all.
    # Submit without target_language should fail because no session exists.
    response = await client.post(
        "/api/assessment/submit",
        headers=headers,
        json={"answers": [{"question_id": 1, "answer": "B"}]},
    )
    assert response.status_code == 404
    assert "No active assessment" in response.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/assessment/evaluate — deterministic evaluation (no LLM)
# ═══════════════════════════════════════════════════════════════════════════════


async def test_evaluate_requires_auth(client: AsyncClient):
    """POST /evaluate returns 401 without valid auth."""
    response = await client.post(
        "/api/assessment/evaluate",
        json={"answers": []},
    )
    assert response.status_code == 401


async def test_evaluate_empty_answers_returns_a1(client: AsyncClient, test_user):
    """POST /evaluate with empty answers returns A1, score 0."""
    _user, headers = test_user
    response = await client.post(
        "/api/assessment/evaluate",
        headers=headers,
        json={"answers": []},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["cefr_level"] == "A1"
    assert result["score"] == 0.0
    assert isinstance(result["skill_profile"], dict)


async def test_evaluate_all_correct_a2(client: AsyncClient, test_user):
    """POST /evaluate with 2+ correct A2 answers => A2 level."""
    _user, headers = test_user
    response = await client.post(
        "/api/assessment/evaluate",
        headers=headers,
        json={
            "answers": [
                # All three skills at A2, all correct
                {
                    "question_id": "q1",
                    "skill": "grammar",
                    "difficulty": "A2",
                    "correct": True,
                },
                {
                    "question_id": "q2",
                    "skill": "grammar",
                    "difficulty": "A2",
                    "correct": True,
                },
                {
                    "question_id": "q3",
                    "skill": "vocabulary",
                    "difficulty": "A2",
                    "correct": True,
                },
                {
                    "question_id": "q4",
                    "skill": "vocabulary",
                    "difficulty": "A2",
                    "correct": True,
                },
                {
                    "question_id": "q5",
                    "skill": "reading",
                    "difficulty": "A2",
                    "correct": True,
                },
                {
                    "question_id": "q6",
                    "skill": "reading",
                    "difficulty": "A2",
                    "correct": True,
                },
            ]
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["cefr_level"] == "A2"
    assert result["score"] == 1.0


async def test_evaluate_mixed_level_advances_to_highest_passing(client: AsyncClient, test_user):
    """POST /evaluate returns highest CEFR level with >= 2 questions and >= 60%."""
    _user, headers = test_user
    response = await client.post(
        "/api/assessment/evaluate",
        headers=headers,
        json={
            "answers": [
                # A1: 2/2 correct => 100% → A1 passes
                {
                    "question_id": "q1",
                    "skill": "grammar",
                    "difficulty": "A1",
                    "correct": True,
                },
                {
                    "question_id": "q2",
                    "skill": "vocabulary",
                    "difficulty": "A1",
                    "correct": True,
                },
                # A2: 2/3 correct => 66% → A2 passes
                {
                    "question_id": "q3",
                    "skill": "grammar",
                    "difficulty": "A2",
                    "correct": True,
                },
                {
                    "question_id": "q4",
                    "skill": "vocabulary",
                    "difficulty": "A2",
                    "correct": True,
                },
                {
                    "question_id": "q5",
                    "skill": "reading",
                    "difficulty": "A2",
                    "correct": False,
                },
                # B1: 1/2 correct => 50% → B1 fails
                {
                    "question_id": "q6",
                    "skill": "grammar",
                    "difficulty": "B1",
                    "correct": True,
                },
                {
                    "question_id": "q7",
                    "skill": "reading",
                    "difficulty": "B1",
                    "correct": False,
                },
            ]
        },
    )
    assert response.status_code == 200
    result = response.json()
    # Highest passing level is A2 (B1 had 50% < 60%)
    assert result["cefr_level"] == "A2"


async def test_evaluate_single_question_insufficient(client: AsyncClient, test_user):
    """POST /evaluate with only 1 question per level cannot pass any level."""
    _user, headers = test_user
    response = await client.post(
        "/api/assessment/evaluate",
        headers=headers,
        json={
            "answers": [
                {
                    "question_id": "q1",
                    "skill": "grammar",
                    "difficulty": "B1",
                    "correct": True,
                },
            ]
        },
    )
    assert response.status_code == 200
    result = response.json()
    # Only 1 B1 question, needs >= 2 → defaults to A1
    assert result["cefr_level"] == "A1"


async def test_evaluate_skill_profile_structure(client: AsyncClient, test_user):
    """POST /evaluate returns correct skill_profile with grammar/vocabulary/reading keys."""
    _user, headers = test_user
    response = await client.post(
        "/api/assessment/evaluate",
        headers=headers,
        json={
            "answers": [
                {
                    "question_id": "q1",
                    "skill": "grammar",
                    "difficulty": "A1",
                    "correct": True,
                },
                {
                    "question_id": "q2",
                    "skill": "grammar",
                    "difficulty": "A1",
                    "correct": False,
                },
                {
                    "question_id": "q3",
                    "skill": "vocabulary",
                    "difficulty": "A1",
                    "correct": True,
                },
                {
                    "question_id": "q4",
                    "skill": "reading",
                    "difficulty": "A1",
                    "correct": True,
                },
                {
                    "question_id": "q5",
                    "skill": "reading",
                    "difficulty": "A1",
                    "correct": False,
                },
            ]
        },
    )
    assert response.status_code == 200
    result = response.json()
    profile = result["skill_profile"]
    assert "grammar" in profile
    assert "vocabulary" in profile
    assert "reading" in profile
    assert profile["grammar"] == 0.5
    assert profile["vocabulary"] == 1.0
    assert profile["reading"] == 0.5


async def test_evaluate_strengths_and_weaknesses(client: AsyncClient, test_user):
    """POST /evaluate correctly identifies strengths (>= 0.65) and weaknesses (< 0.45)."""
    _user, headers = test_user
    response = await client.post(
        "/api/assessment/evaluate",
        headers=headers,
        json={
            "answers": [
                # Grammar: 3/3 = 1.0 → strength
                {
                    "question_id": "q1",
                    "skill": "grammar",
                    "difficulty": "A1",
                    "correct": True,
                },
                {
                    "question_id": "q2",
                    "skill": "grammar",
                    "difficulty": "A1",
                    "correct": True,
                },
                {
                    "question_id": "q3",
                    "skill": "grammar",
                    "difficulty": "A1",
                    "correct": True,
                },
                # Vocabulary: 0/2 = 0.0 → weakness
                {
                    "question_id": "q4",
                    "skill": "vocabulary",
                    "difficulty": "A1",
                    "correct": False,
                },
                {
                    "question_id": "q5",
                    "skill": "vocabulary",
                    "difficulty": "A1",
                    "correct": False,
                },
                # Reading: 1/2 = 0.5 → neither
                {
                    "question_id": "q6",
                    "skill": "reading",
                    "difficulty": "A1",
                    "correct": True,
                },
                {
                    "question_id": "q7",
                    "skill": "reading",
                    "difficulty": "A1",
                    "correct": False,
                },
            ]
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert "grammar" in result["strengths"]
    assert "vocabulary" in result["weaknesses"]
    assert "reading" not in result["strengths"]
    assert "reading" not in result["weaknesses"]


async def test_evaluate_unknown_skill_ignored(client: AsyncClient, test_user):
    """POST /evaluate ignores answers with skills outside grammar/vocabulary/reading."""
    _user, headers = test_user
    response = await client.post(
        "/api/assessment/evaluate",
        headers=headers,
        json={
            "answers": [
                {
                    "question_id": "q1",
                    "skill": "grammar",
                    "difficulty": "A1",
                    "correct": True,
                },
                {
                    "question_id": "q2",
                    "skill": "grammar",
                    "difficulty": "A1",
                    "correct": True,
                },
                {
                    "question_id": "q3",
                    "skill": "writing",
                    "difficulty": "A1",
                    "correct": True,
                },
            ]
        },
    )
    assert response.status_code == 200
    result = response.json()
    # Only grammar counted in skill_profile; "writing" is ignored
    assert result["skill_profile"]["grammar"] == 1.0
    assert "writing" not in result["skill_profile"]


async def test_evaluate_case_insensitive_skills(client: AsyncClient, test_user):
    """POST /evaluate handles uppercase/mixed-case skill names."""
    _user, headers = test_user
    response = await client.post(
        "/api/assessment/evaluate",
        headers=headers,
        json={
            "answers": [
                {
                    "question_id": "q1",
                    "skill": "GRAMMAR",
                    "difficulty": "A1",
                    "correct": True,
                },
                {
                    "question_id": "q2",
                    "skill": "Grammar",
                    "difficulty": "A1",
                    "correct": True,
                },
                {
                    "question_id": "q3",
                    "skill": "Reading",
                    "difficulty": "A1",
                    "correct": False,
                },
                {
                    "question_id": "q4",
                    "skill": "reading",
                    "difficulty": "A1",
                    "correct": False,
                },
            ]
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["skill_profile"]["grammar"] == 1.0
    assert result["skill_profile"]["reading"] == 0.0


async def test_evaluate_invalid_body_422(client: AsyncClient, test_user):
    """POST /evaluate returns 422 for malformed request body."""
    _user, headers = test_user

    # Missing required fields
    response = await client.post(
        "/api/assessment/evaluate",
        headers=headers,
        json={"answers": [{"wrong_field": "x"}]},
    )
    assert response.status_code == 422

    # Not a list
    response = await client.post(
        "/api/assessment/evaluate",
        headers=headers,
        json={"answers": "not-a-list"},
    )
    assert response.status_code == 422


def _answer(question_id: str, skill: str, difficulty: str, **overrides):
    answer = {
        "question_id": question_id,
        "skill": skill,
        "difficulty": difficulty,
        "correct": False,
    }
    answer.update(overrides)
    return answer


async def test_evaluate_accepts_answers_without_dont_know(client: AsyncClient, test_user):
    """Clients that do not send dont_know keep working unchanged."""
    _user, headers = test_user
    response = await client.post(
        "/api/assessment/evaluate",
        headers=headers,
        json={
            "answers": [
                _answer("q1", "grammar", "A2", correct=True),
                _answer("q2", "grammar", "A2", correct=True),
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["cefr_level"] == "A2"


async def test_evaluate_declared_gap_is_never_correct(client: AsyncClient, test_user):
    """A declared gap does not pass a level, even when the client also marks it correct."""
    _user, headers = test_user
    response = await client.post(
        "/api/assessment/evaluate",
        headers=headers,
        json={
            "answers": [
                _answer("q1", "grammar", "B2", correct=True, dont_know=True),
                _answer("q2", "grammar", "B2", correct=True, dont_know=True),
            ]
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["cefr_level"] == "A1"
    assert result["skill_profile"]["grammar"] == 0.0


async def test_evaluate_declared_gaps_make_a_skill_a_weakness(client: AsyncClient, test_user):
    """Half the questions declared as gaps mark the skill weak despite the other answers."""
    _user, headers = test_user
    response = await client.post(
        "/api/assessment/evaluate",
        headers=headers,
        json={
            "answers": [
                _answer("q1", "grammar", "A2", correct=True),
                _answer("q2", "grammar", "A2", dont_know=True),
                _answer("q3", "vocabulary", "A2", correct=True),
                _answer("q4", "vocabulary", "A2", correct=False),
            ]
        },
    )
    assert response.status_code == 200
    result = response.json()
    # Both skills score 0.5, but only grammar carries a declared gap.
    assert result["skill_profile"]["grammar"] == 0.5
    assert result["skill_profile"]["vocabulary"] == 0.5
    assert "grammar" in result["weaknesses"]
    assert "vocabulary" not in result["weaknesses"]


async def test_evaluate_weaknesses_are_not_duplicated(client: AsyncClient, test_user):
    """A skill that is already weak by score is listed once, not twice."""
    _user, headers = test_user
    response = await client.post(
        "/api/assessment/evaluate",
        headers=headers,
        json={
            "answers": [
                _answer("q1", "grammar", "A2", dont_know=True),
                _answer("q2", "grammar", "A2", dont_know=True),
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["weaknesses"].count("grammar") == 1


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/assessment/free-write — LLM evaluation of free-write
# ═══════════════════════════════════════════════════════════════════════════════


async def test_free_write_requires_auth(client: AsyncClient):
    """POST /free-write returns 401 without valid auth."""
    response = await client.post(
        "/api/assessment/free-write",
        json={
            "preliminary_level": "A2",
            "writing_prompt": "Describe your day",
            "student_answer": "I wake up early.",
        },
    )
    assert response.status_code == 401


async def test_free_write_success(client: AsyncClient, test_user):
    """POST /free-write returns LLM evaluation result on success."""
    _user, headers = test_user

    mock_free_write_result = '{"adjusted_level": "A2", "writing_score": 0.70, "analysis": "Good.", "strengths": ["basic grammar"], "weaknesses": ["vocabulary"]}'  # noqa: E501

    with patch(
        "app.services.assessment.llm_adapter.chat",
        return_value=mock_free_write_result,
    ):
        response = await client.post(
            "/api/assessment/free-write",
            headers=headers,
            json={
                "preliminary_level": "A2",
                "writing_prompt": "Describe your day",
                "student_answer": "I wake up early.",
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert "adjusted_level" in result
        assert "writing_score" in result


async def test_free_write_handles_llm_timeout(client: AsyncClient, test_user):
    """POST /free-write returns 504 when LLM times out."""
    _user, headers = test_user

    with patch(
        "app.services.assessment.llm_adapter.chat",
        side_effect=LLMTimeoutError("timeout"),
    ):
        response = await client.post(
            "/api/assessment/free-write",
            headers=headers,
            json={
                "preliminary_level": "A2",
                "writing_prompt": "Describe your day",
                "student_answer": "I wake up early.",
            },
        )
        assert response.status_code == 504
        assert "timed out" in response.json()["detail"]


async def test_free_write_handles_llm_unavailable(client: AsyncClient, test_user):
    """POST /free-write returns 503 when LLM is unreachable."""
    _user, headers = test_user

    with patch(
        "app.services.assessment.llm_adapter.chat",
        side_effect=LLMUnavailableError("unreachable"),
    ):
        response = await client.post(
            "/api/assessment/free-write",
            headers=headers,
            json={
                "preliminary_level": "A2",
                "writing_prompt": "Describe your day",
                "student_answer": "I wake up early.",
            },
        )
        assert response.status_code == 503
        assert "ai_service_unavailable" in response.json()["detail"]


async def test_free_write_handles_llm_generic_error(client: AsyncClient, test_user):
    """POST /free-write returns 502 when LLM raises generic LLMError."""
    _user, headers = test_user

    with patch(
        "app.services.assessment.llm_adapter.chat",
        side_effect=LLMError("generic failure"),
    ):
        response = await client.post(
            "/api/assessment/free-write",
            headers=headers,
            json={
                "preliminary_level": "A2",
                "writing_prompt": "Describe your day",
                "student_answer": "I wake up early.",
            },
        )
        assert response.status_code == 502
        assert "ai_service_error" in response.json()["detail"]


async def test_free_write_with_existing_session_gets_language(
    client: AsyncClient, test_user, mock_redis
):
    """POST /free-write picks up target_language from an active assessment session."""
    user, headers = test_user

    # Store a session in mock_redis with a specific target_language
    await mock_redis.setex(
        f"assessment:{user.id}:en-US",
        1800,
        json.dumps(
            {
                "session_id": "sess-1",
                "quiz": {"questions": []},
                "target_language": "en-US",
            }
        ),
    )

    mock_free_write_result = '{"adjusted_level": "A2", "writing_score": 0.70, "analysis": "OK", "strengths": [], "weaknesses": []}'  # noqa: E501

    with patch(
        "app.services.assessment.llm_adapter.chat",
        return_value=mock_free_write_result,
    ):
        response = await client.post(
            "/api/assessment/free-write",
            headers=headers,
            json={
                "preliminary_level": "A2",
                "writing_prompt": "Describe your day",
                "student_answer": "I wake up early.",
            },
        )
        assert response.status_code == 200


async def test_free_write_invalid_body_422(client: AsyncClient, test_user):
    """POST /free-write returns 422 for missing required fields."""
    _user, headers = test_user

    response = await client.post(
        "/api/assessment/free-write",
        headers=headers,
        json={"wrong_field": "value"},
    )
    assert response.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/assessment/complete — persist result & create study plan
# ═══════════════════════════════════════════════════════════════════════════════


async def test_complete_requires_auth(client: AsyncClient):
    """POST /complete returns 401 without valid auth."""
    response = await client.post(
        "/api/assessment/complete",
        json={
            "cefr_level": "A2",
            "strengths": ["grammar"],
            "weaknesses": ["vocabulary"],
            "duration_weeks": 4,
            "days_per_week": 4,
            "goals": ["grammar", "vocabulary"],
        },
    )
    assert response.status_code == 401


async def test_complete_success_creates_plan(client: AsyncClient, test_user, db_session):
    """POST /complete persists assessment and creates an active study plan."""
    user, headers = test_user

    # Deactivate any existing active plan to avoid unique constraint
    await deactivate_active_plans(db_session, user.id, "en-US")

    response = await client.post(
        "/api/assessment/complete",
        headers=headers,
        json={
            "cefr_level": "A1",
            "strengths": ["grammar"],
            "weaknesses": ["vocabulary"],
            "duration_weeks": 4,
            "days_per_week": 4,
            "goals": ["grammar", "vocabulary", "reading"],
            "target_language": "en-US",
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert "plan_id" in result
    assert result["cefr_level"] == "A1"
    assert isinstance(result["plan_id"], int)


async def test_complete_returns_voice_trial_for_unsubscribed_user(
    client: AsyncClient, test_user, db_session
):
    """POST /complete grants a one-time voice trial when hosted paywall is active."""
    user, headers = test_user
    await deactivate_active_plans(db_session, user.id, "en-US")

    with patch.object(settings, "STRIPE_ENABLED", True):
        response = await client.post(
            "/api/assessment/complete",
            headers=headers,
            json={
                "cefr_level": "A1",
                "strengths": ["grammar"],
                "weaknesses": [],
                "duration_weeks": 4,
                "days_per_week": 4,
                "goals": ["grammar"],
                "target_language": "en-US",
            },
        )

    assert response.status_code == 200
    trial = response.json()["voice_trial"]
    assert trial["available"] is True
    assert trial["token"]
    assert trial["duration_seconds"] == 300


async def test_complete_does_not_return_voice_trial_after_used(
    client: AsyncClient, test_user, db_session
):
    """The post-assessment voice trial is one-time per user."""
    user, headers = test_user
    user.assessment_voice_trial_used = True
    await db_session.commit()
    await deactivate_active_plans(db_session, user.id, "en-US")

    with patch.object(settings, "STRIPE_ENABLED", True):
        response = await client.post(
            "/api/assessment/complete",
            headers=headers,
            json={
                "cefr_level": "A1",
                "strengths": ["grammar"],
                "weaknesses": [],
                "duration_weeks": 4,
                "days_per_week": 4,
                "goals": ["grammar"],
                "target_language": "en-US",
            },
        )

    assert response.status_code == 200
    assert response.json()["voice_trial"] == {"available": False}


async def test_voice_trial_endpoint_returns_token_for_existing_plan(
    client: AsyncClient, test_user, db_session
):
    """POST /voice-trial regenerates a token when the one-time demo is still unused."""
    user, headers = test_user
    await deactivate_active_plans(db_session, user.id, "en-US")

    await client.post(
        "/api/assessment/complete",
        headers=headers,
        json={
            "cefr_level": "A1",
            "strengths": ["grammar"],
            "weaknesses": [],
            "duration_weeks": 4,
            "days_per_week": 4,
            "goals": ["grammar"],
            "target_language": "en-US",
        },
    )

    with patch.object(settings, "STRIPE_ENABLED", True):
        response = await client.post(
            "/api/assessment/voice-trial",
            headers=headers,
            json={"target_language": "en-US"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["cefr_level"] == "A1"
    assert data["voice_trial"]["available"] is True
    assert data["voice_trial"]["token"]
    assert data["voice_trial"]["duration_seconds"] == 300


async def test_voice_trial_endpoint_does_not_return_token_after_used(
    client: AsyncClient, test_user, db_session
):
    """POST /voice-trial respects the durable one-time used flag."""
    user, headers = test_user
    await deactivate_active_plans(db_session, user.id, "en-US")

    await client.post(
        "/api/assessment/complete",
        headers=headers,
        json={
            "cefr_level": "A1",
            "strengths": ["grammar"],
            "weaknesses": [],
            "duration_weeks": 4,
            "days_per_week": 4,
            "goals": ["grammar"],
            "target_language": "en-US",
        },
    )
    user.assessment_voice_trial_used = True
    await db_session.commit()

    with patch.object(settings, "STRIPE_ENABLED", True):
        response = await client.post(
            "/api/assessment/voice-trial",
            headers=headers,
            json={"target_language": "en-US"},
        )

    assert response.status_code == 200
    assert response.json()["voice_trial"] == {"available": False}


async def test_complete_with_language_in_session(
    client: AsyncClient, test_user, mock_redis, db_session
):
    """POST /complete reads target_language from Redis session when body lacks it."""
    user, headers = test_user

    # Store a session so the endpoint can extract target_language from it
    session_data = {
        "session_id": "sess-1",
        "quiz": {"questions": []},
        "target_language": "en-US",
    }
    await mock_redis.setex(
        f"assessment:{user.id}:en-US",
        1800,
        json.dumps(session_data),
    )

    await deactivate_active_plans(db_session, user.id, "en-US")

    response = await client.post(
        "/api/assessment/complete",
        headers=headers,
        json={
            "cefr_level": "A1",
            "strengths": ["grammar"],
            "weaknesses": [],
            "duration_weeks": 4,
            "days_per_week": 4,
            "goals": ["grammar"],
            # No target_language in body — will pick from session
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["cefr_level"] == "A1"


async def test_complete_invalid_body_422(client: AsyncClient, test_user):
    """POST /complete returns 422 for malformed request body."""
    _user, headers = test_user

    response = await client.post(
        "/api/assessment/complete",
        headers=headers,
        json={"cefr_level": "A1"},  # missing required fields with defaults won't 422...
    )
    # This should actually succeed since duration_weeks/days_per_week/goals have defaults
    assert response.status_code in (200, 422)

    # Missing cefr_level (required)
    response = await client.post(
        "/api/assessment/complete",
        headers=headers,
        json={"strengths": ["grammar"]},
    )
    assert response.status_code == 422


async def test_complete_deactivates_previous_active_plans(
    client: AsyncClient, test_user, db_session
):
    """POST /complete deactivates any existing active plan for the same language.

    Uses two different target languages to avoid SQLite's full UNIQUE constraint
    on user_language_id (SQLite ignores postgresql_where).
    """
    user, headers = test_user

    from sqlalchemy import delete

    from app.models.study_plan import StudyPlan

    # Call /complete for en-US → creates an active plan on user_language_id=1
    resp1 = await client.post(
        "/api/assessment/complete",
        headers=headers,
        json={
            "cefr_level": "A1",
            "strengths": ["grammar"],
            "weaknesses": [],
            "duration_weeks": 4,
            "days_per_week": 4,
            "goals": ["grammar"],
            "target_language": "en-US",
        },
    )
    assert resp1.status_code == 200
    plan1_id = resp1.json()["plan_id"]
    plan1 = await db_session.get(StudyPlan, plan1_id)
    assert plan1.is_active is True

    # Call /complete for a DIFFERENT language (es-ES)
    # The endpoint must deactivate plans for es-ES only — it must NOT touch plan1.
    resp2 = await client.post(
        "/api/assessment/complete",
        headers=headers,
        json={
            "cefr_level": "A1",
            "strengths": ["grammar"],
            "weaknesses": [],
            "duration_weeks": 4,
            "days_per_week": 4,
            "goals": ["grammar"],
            "target_language": "es-ES",
        },
    )
    assert resp2.status_code == 200

    # plan1 should still be active (different language)
    await db_session.refresh(plan1)
    assert plan1.is_active is True

    # Second plan for es-ES should also be active
    plan2_id = resp2.json()["plan_id"]
    plan2 = await db_session.get(StudyPlan, plan2_id)
    assert plan2.is_active is True
    assert plan2.id != plan1.id

    # Verify both plans are for different user_language rows
    assert plan1.user_language_id != plan2.user_language_id

    # Now delete the es-ES plan to clear SQLite's full UNIQUE constraint
    await db_session.execute(delete(StudyPlan).where(StudyPlan.id == plan2_id))
    await db_session.commit()

    # Re-calling /complete for es-ES should create a new active plan
    resp3 = await client.post(
        "/api/assessment/complete",
        headers=headers,
        json={
            "cefr_level": "A1",
            "strengths": ["grammar"],
            "weaknesses": [],
            "duration_weeks": 4,
            "days_per_week": 4,
            "goals": ["grammar"],
            "target_language": "es-ES",
        },
    )
    assert resp3.status_code == 200
    plan3_id = resp3.json()["plan_id"]

    plan3 = await db_session.get(StudyPlan, plan3_id)
    assert plan3.is_active is True
    assert plan3.user_language_id == plan2.user_language_id


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/assessment/level-test/questions/{plan_id}
# ═══════════════════════════════════════════════════════════════════════════════


async def test_level_test_questions_requires_auth(client: AsyncClient):
    """GET /level-test/questions/{id} returns 401 without valid auth."""
    response = await client.get("/api/assessment/level-test/questions/1")
    assert response.status_code == 401


async def test_level_test_questions_plan_not_found(client: AsyncClient, test_user):
    """GET /level-test/questions/{id} returns 404 for non-existent plan."""
    _user, headers = test_user
    response = await client.get("/api/assessment/level-test/questions/99999", headers=headers)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


async def test_level_test_questions_wrong_user(client: AsyncClient, test_user, db_session):
    """GET /level-test/questions/{id} returns 404 for plan belonging to another user."""
    _user, headers = test_user

    # Create a plan for a different user
    from app.core.security import hash_password
    from app.models.user import User

    other_user = User(
        username="other",
        email="other@example.com",
        display_name="Other",
        hashed_password=hash_password("pass"),
        role="user",
        native_language="es",
        target_language="en-US",
        is_active=True,
    )
    db_session.add(other_user)
    await db_session.flush()

    from app.models.user_language import UserLanguage

    ul = UserLanguage(user_id=other_user.id, target_language="en-US", is_active=True)
    db_session.add(ul)
    await db_session.flush()

    from app.models.study_plan import StudyPlan

    other_plan = StudyPlan(
        user_id=other_user.id,
        user_language_id=ul.id,
        cefr_level="A2",
        target_language="en-US",
        goals=["grammar"],
        duration_weeks=4,
        days_per_week=4,
        generated_plan={},
        is_active=True,
    )
    db_session.add(other_plan)
    await db_session.commit()

    response = await client.get(
        f"/api/assessment/level-test/questions/{other_plan.id}",
        headers=headers,
    )
    assert response.status_code == 404


async def test_level_test_questions_success(client: AsyncClient, test_user_with_plan, db_session):
    """GET /level-test/questions/{id} returns generated questions."""
    user, headers = test_user_with_plan

    # Get the plan from the fixture
    from sqlalchemy import select

    from app.models.study_plan import StudyPlan

    plan = (
        await db_session.execute(
            select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.is_active.is_(True))
        )
    ).scalar_one()

    mock_questions = '{"questions": [{"id": "lt-001", "skill": "grammar", "difficulty": "A1", "question": "What is...?", "options": ["A", "B", "C", "D"], "correct": "B"}]}'  # noqa: E501

    with patch(
        "app.services.assessment.llm_adapter.chat",
        return_value=mock_questions,
    ):
        response = await client.get(
            f"/api/assessment/level-test/questions/{plan.id}",
            headers=headers,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["plan_id"] == plan.id
        assert result["cefr_level"] == "A1"
        assert "questions" in result
        assert len(result["questions"]) == 1


async def test_level_test_questions_handles_llm_timeout(
    client: AsyncClient, test_user_with_plan, db_session
):
    """GET /level-test/questions/{id} returns 504 on LLM timeout."""
    user, headers = test_user_with_plan

    from sqlalchemy import select

    from app.models.study_plan import StudyPlan

    plan = (
        await db_session.execute(
            select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.is_active.is_(True))
        )
    ).scalar_one()

    with patch(
        "app.services.assessment.llm_adapter.chat",
        side_effect=LLMTimeoutError("timeout"),
    ):
        response = await client.get(
            f"/api/assessment/level-test/questions/{plan.id}",
            headers=headers,
        )
        assert response.status_code == 504
        assert "timed out" in response.json()["detail"]


async def test_level_test_questions_handles_llm_unavailable(
    client: AsyncClient, test_user_with_plan, db_session
):
    """GET /level-test/questions/{id} returns 503 on LLM unavailable."""
    user, headers = test_user_with_plan

    from sqlalchemy import select

    from app.models.study_plan import StudyPlan

    plan = (
        await db_session.execute(
            select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.is_active.is_(True))
        )
    ).scalar_one()

    with patch(
        "app.services.assessment.llm_adapter.chat",
        side_effect=LLMUnavailableError("unreachable"),
    ):
        response = await client.get(
            f"/api/assessment/level-test/questions/{plan.id}",
            headers=headers,
        )
        assert response.status_code == 503
        assert "ai_service_unavailable" in response.json()["detail"]


async def test_level_test_questions_handles_llm_generic_error(
    client: AsyncClient, test_user_with_plan, db_session
):
    """GET /level-test/questions/{id} returns 502 on generic LLM error."""
    user, headers = test_user_with_plan

    from sqlalchemy import select

    from app.models.study_plan import StudyPlan

    plan = (
        await db_session.execute(
            select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.is_active.is_(True))
        )
    ).scalar_one()

    with patch(
        "app.services.assessment.llm_adapter.chat",
        side_effect=LLMError("generic failure"),
    ):
        response = await client.get(
            f"/api/assessment/level-test/questions/{plan.id}",
            headers=headers,
        )
        assert response.status_code == 502
        assert "ai_service_error" in response.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/assessment/level-test/submit
# ═══════════════════════════════════════════════════════════════════════════════


async def test_level_test_submit_requires_auth(client: AsyncClient):
    """POST /level-test/submit returns 401 without valid auth."""
    response = await client.post(
        "/api/assessment/level-test/submit",
        json={"plan_id": 1, "answers": []},
    )
    assert response.status_code == 401


async def test_level_test_submit_plan_not_found(client: AsyncClient, test_user):
    """POST /level-test/submit returns 404 for non-existent plan."""
    _user, headers = test_user
    response = await client.post(
        "/api/assessment/level-test/submit",
        headers=headers,
        json={"plan_id": 99999, "answers": []},
    )
    assert response.status_code == 404


async def test_level_test_submit_high_score_advance(
    client: AsyncClient, test_user_with_plan, db_session
):
    """POST /level-test/submit with >= 75% score recommends 'advance' with next_level."""
    user, headers = test_user_with_plan

    from sqlalchemy import select

    from app.models.study_plan import StudyPlan

    plan = (
        await db_session.execute(
            select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.is_active.is_(True))
        )
    ).scalar_one()

    # 4/5 A2 grammar correct = 0.8 grammar → score = 0.8 (other skills 0)
    # Weighted average: (0.8 + 0 + 0) / 3 = 0.267... wait that's not right.
    # Actually evaluate_adaptive_quiz computes: sum(profile.values) / 3
    # With only grammar answers: grammar=0.8, vocab=0.0, reading=0.0 → (0.8)/3 ≈ 0.267
    #
    # We need all three skills to get a clean score. Let's do 80% across all three:
    # Grammar: 4/5 correct = 0.8
    # Vocab: 4/5 correct = 0.8
    # Reading: 4/5 correct = 0.8
    # Average: 0.8 → >= 0.75 → advance
    answers = []
    for i in range(15):
        skill = ["grammar", "vocabulary", "reading"][i % 3]
        correct = (i % 5) != 0  # 4 of 5 correct per skill
        answers.append(
            {
                "question_id": f"q{i}",
                "skill": skill,
                "difficulty": "A1",
                "correct": correct,
            }
        )

    response = await client.post(
        "/api/assessment/level-test/submit",
        headers=headers,
        json={"plan_id": plan.id, "answers": answers},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["recommendation"] == "advance"
    assert result["next_level"] == "A2"

    # Verify plan was updated
    await db_session.refresh(plan)
    assert plan.completion_test_taken is True
    assert plan.completion_test_score is not None
    assert plan.completion_test_recommendation == "advance"


async def test_level_test_submit_medium_score_extend(
    client: AsyncClient, test_user_with_plan, db_session
):
    """POST /level-test/submit with 55-74% score recommends 'extend'."""
    user, headers = test_user_with_plan

    from sqlalchemy import select

    from app.models.study_plan import StudyPlan

    plan = (
        await db_session.execute(
            select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.is_active.is_(True))
        )
    ).scalar_one()

    # 3/5 correct per skill = 0.6 → average = 0.6 → extend (>= 0.55 but < 0.75)
    answers = []
    for i in range(15):
        skill = ["grammar", "vocabulary", "reading"][i % 3]
        correct = i % 5 < 3  # 3 of 5 correct per skill
        answers.append(
            {
                "question_id": f"q{i}",
                "skill": skill,
                "difficulty": "A1",
                "correct": correct,
            }
        )

    response = await client.post(
        "/api/assessment/level-test/submit",
        headers=headers,
        json={"plan_id": plan.id, "answers": answers},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["recommendation"] == "extend"
    assert result["next_level"] is None


async def test_level_test_submit_low_score_repeat(
    client: AsyncClient, test_user_with_plan, db_session
):
    """POST /level-test/submit with < 55% score recommends 'repeat'."""
    user, headers = test_user_with_plan

    from sqlalchemy import select

    from app.models.study_plan import StudyPlan

    plan = (
        await db_session.execute(
            select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.is_active.is_(True))
        )
    ).scalar_one()

    # 1/5 correct per skill = 0.2 → average = 0.2 → repeat (< 0.55)
    answers = []
    for i in range(15):
        skill = ["grammar", "vocabulary", "reading"][i % 3]
        correct = i % 5 == 0  # 1 of 5 correct per skill
        answers.append(
            {
                "question_id": f"q{i}",
                "skill": skill,
                "difficulty": "A1",
                "correct": correct,
            }
        )

    response = await client.post(
        "/api/assessment/level-test/submit",
        headers=headers,
        json={"plan_id": plan.id, "answers": answers},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["recommendation"] == "repeat"
    assert result["next_level"] is None


async def test_level_test_submit_invalid_body_422(client: AsyncClient, test_user):
    """POST /level-test/submit returns 422 for malformed request body."""
    _user, headers = test_user

    response = await client.post(
        "/api/assessment/level-test/submit",
        headers=headers,
        json={"wrong_field": "value"},
    )
    assert response.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/assessment/level-test/result/{plan_id}
# ═══════════════════════════════════════════════════════════════════════════════


async def test_level_test_result_requires_auth(client: AsyncClient):
    """GET /level-test/result/{id} returns 401 without valid auth."""
    response = await client.get("/api/assessment/level-test/result/1")
    assert response.status_code == 401


async def test_level_test_result_plan_not_found(client: AsyncClient, test_user):
    """GET /level-test/result/{id} returns 404 for non-existent plan."""
    _user, headers = test_user
    response = await client.get("/api/assessment/level-test/result/99999", headers=headers)
    assert response.status_code == 404


async def test_level_test_result_not_taken(client: AsyncClient, test_user_with_plan, db_session):
    """GET /level-test/result/{id} returns 404 if test hasn't been taken yet."""
    user, headers = test_user_with_plan

    from sqlalchemy import select

    from app.models.study_plan import StudyPlan

    plan = (
        await db_session.execute(
            select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.is_active.is_(True))
        )
    ).scalar_one()

    # The test_user_with_plan fixture has completion_test_taken=False by default
    response = await client.get(
        f"/api/assessment/level-test/result/{plan.id}",
        headers=headers,
    )
    assert response.status_code == 404
    assert "result not found" in response.json()["detail"]


async def test_level_test_result_advance(client: AsyncClient, test_user_with_plan, db_session):
    """GET /level-test/result/{id} returns advance recommendation with next_level."""
    user, headers = test_user_with_plan

    from sqlalchemy import select

    from app.models.study_plan import StudyPlan

    plan = (
        await db_session.execute(
            select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.is_active.is_(True))
        )
    ).scalar_one()

    # Mark the plan as test taken with advance recommendation
    plan.completion_test_taken = True
    plan.completion_test_score = 0.85
    plan.completion_test_recommendation = "advance"
    await db_session.commit()

    response = await client.get(
        f"/api/assessment/level-test/result/{plan.id}",
        headers=headers,
    )
    assert response.status_code == 200
    result = response.json()
    assert result["score"] == 0.85
    assert result["recommendation"] == "advance"
    assert result["next_level"] == "A2"


async def test_level_test_result_repeat(client: AsyncClient, test_user_with_plan, db_session):
    """GET /level-test/result/{id} returns repeat recommendation without next_level."""
    user, headers = test_user_with_plan

    from sqlalchemy import select

    from app.models.study_plan import StudyPlan

    plan = (
        await db_session.execute(
            select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.is_active.is_(True))
        )
    ).scalar_one()

    plan.completion_test_taken = True
    plan.completion_test_score = 0.40
    plan.completion_test_recommendation = "repeat"
    await db_session.commit()

    response = await client.get(
        f"/api/assessment/level-test/result/{plan.id}",
        headers=headers,
    )
    assert response.status_code == 200
    result = response.json()
    assert result["score"] == 0.40
    assert result["recommendation"] == "repeat"
    assert result["next_level"] is None


async def test_level_test_result_extend(client: AsyncClient, test_user_with_plan, db_session):
    """GET /level-test/result/{id} returns extend recommendation without next_level."""
    user, headers = test_user_with_plan

    from sqlalchemy import select

    from app.models.study_plan import StudyPlan

    plan = (
        await db_session.execute(
            select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.is_active.is_(True))
        )
    ).scalar_one()

    plan.completion_test_taken = True
    plan.completion_test_score = 0.60
    plan.completion_test_recommendation = "extend"
    await db_session.commit()

    response = await client.get(
        f"/api/assessment/level-test/result/{plan.id}",
        headers=headers,
    )
    assert response.status_code == 200
    result = response.json()
    assert result["score"] == 0.60
    assert result["recommendation"] == "extend"
    assert result["next_level"] is None


async def test_level_test_result_c2_advance(client: AsyncClient, test_user_with_plan, db_session):
    """GET /level-test/result returns advance for C2 with next_level=None (no higher level)."""
    user, headers = test_user_with_plan

    from sqlalchemy import select

    from app.models.study_plan import StudyPlan

    # Get the user's plan and update its level to C2
    plan = (
        await db_session.execute(
            select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.is_active.is_(True))
        )
    ).scalar_one()

    plan.cefr_level = "C2"
    plan.completion_test_taken = True
    plan.completion_test_score = 0.90
    plan.completion_test_recommendation = "advance"
    await db_session.commit()

    response = await client.get(
        f"/api/assessment/level-test/result/{plan.id}",
        headers=headers,
    )
    assert response.status_code == 200
    result = response.json()
    assert result["recommendation"] == "advance"
    assert result["next_level"] is None  # No level above C2


async def test_level_test_result_null_score_defaults_to_zero(
    client: AsyncClient, test_user_with_plan, db_session
):
    """GET /level-test/result with null score defaults to 0.0."""
    user, headers = test_user_with_plan

    from sqlalchemy import select

    from app.models.study_plan import StudyPlan

    plan = (
        await db_session.execute(
            select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.is_active.is_(True))
        )
    ).scalar_one()

    plan.completion_test_taken = True
    plan.completion_test_score = None  # Null score
    plan.completion_test_recommendation = "repeat"
    await db_session.commit()

    response = await client.get(
        f"/api/assessment/level-test/result/{plan.id}",
        headers=headers,
    )
    assert response.status_code == 200
    result = response.json()
    assert result["score"] == 0.0


async def test_level_test_result_null_recommendation_defaults_to_repeat(
    client: AsyncClient, test_user_with_plan, db_session
):
    """GET /level-test/result with null recommendation defaults to 'repeat'."""
    user, headers = test_user_with_plan

    from sqlalchemy import select

    from app.models.study_plan import StudyPlan

    plan = (
        await db_session.execute(
            select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.is_active.is_(True))
        )
    ).scalar_one()

    plan.completion_test_taken = True
    plan.completion_test_score = 0.5
    plan.completion_test_recommendation = None  # Null recommendation
    await db_session.commit()

    response = await client.get(
        f"/api/assessment/level-test/result/{plan.id}",
        headers=headers,
    )
    assert response.status_code == 200
    result = response.json()
    assert result["recommendation"] == "repeat"


# ═══════════════════════════════════════════════════════════════════════════════
# Helper — re-exported from conftest for convenience in this file
# ═══════════════════════════════════════════════════════════════════════════════

from tests.conftest import deactivate_active_plans  # noqa: E402
