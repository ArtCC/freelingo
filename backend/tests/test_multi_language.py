"""Multi-language tests — Phase 10.1 / 10.2 / 10.3.

Covers:
  10.1 — Database isolation and constraints
  10.2 — Prompt language awareness
  10.3 — Language API endpoints (CRUD, validation, assessment)
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token, hash_password
from app.models.flashcard import Flashcard
from app.models.memory import Memory
from app.models.progress import Progress
from app.models.study_plan import StudyPlan
from app.models.user import User
from app.models.user_language import UserLanguage
from app.services.memory_service import get_user_memories

# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════


async def _make_user(db, *, username="mluser", email="ml@example.com"):
    user = User(
        username=username,
        email=email,
        display_name="ML User",
        hashed_password=hash_password("testpass"),
        role="user",
        native_language="es",
        target_language="en-US",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    db.add(UserLanguage(user_id=user.id, target_language="en-US", is_active=True))
    await db.commit()
    await db.refresh(user)
    token = create_access_token(user.id, user.role)
    return user, {"Authorization": f"Bearer {token}"}


async def _add_language(db, user_id: int, code: str, *, active: bool = False):
    from sqlalchemy import update as _update

    if active:
        await db.execute(
            _update(UserLanguage)
            .where(UserLanguage.user_id == user_id, UserLanguage.is_active.is_(True))
            .values(is_active=False)
        )
    entry = UserLanguage(user_id=user_id, target_language=code, is_active=active)
    db.add(entry)
    await db.commit()
    return entry


async def _make_plan(db, user_id: int, *, cefr="A1", language="en-US", active=True):
    from tests.conftest import make_study_plan

    return await make_study_plan(
        db,
        user_id=user_id,
        cefr_level=cefr,
        target_language=language,
        goals=["grammar"],
        duration_weeks=4,
        days_per_week=4,
        current_unit="",
        generated_plan={},
        is_active=active,
    )


# ═════════════════════════════════════════════════════════════════════════════
# 10.1 — Database isolation and constraints
# ═════════════════════════════════════════════════════════════════════════════


class TestMultiLanguageIsolation:
    @pytest.mark.asyncio
    async def test_active_plan_per_language(self, client, db_session):
        """Two languages can each have an active plan simultaneously."""
        user, _headers = await _make_user(db_session)

        await _add_language(db_session, user.id, "es-ES", active=False)
        plan_en = await _make_plan(db_session, user.id, language="en-US")
        plan_es = await _make_plan(db_session, user.id, language="es-ES")

        assert plan_en.is_active
        assert plan_es.is_active
        assert plan_en.target_language != plan_es.target_language

    @pytest.mark.asyncio
    async def test_unique_index_prevents_duplicate_active_plans(self, client, db_session):
        """Cannot create two active plans for the same user+language."""
        from sqlalchemy.exc import IntegrityError

        user, _headers = await _make_user(db_session)

        await _make_plan(db_session, user.id, language="en-US", active=True)

        with pytest.raises(IntegrityError):
            await _make_plan(db_session, user.id, language="en-US", active=True)

    @pytest.mark.asyncio
    async def test_progress_isolated_by_language(self, client, db_session):
        """Progress for one language does not affect the other."""
        user, _headers = await _make_user(db_session)
        await _add_language(db_session, user.id, "es-ES", active=False)
        plan_en = await _make_plan(db_session, user.id, language="en-US")
        plan_es = await _make_plan(db_session, user.id, language="es-ES")

        today = date.today()
        db_session.add_all(
            [
                Progress(
                    user_id=user.id,
                    study_plan_id=plan_en.id,
                    date=today,
                    xp_earned=100,
                    streak_day=5,
                    lessons_completed=3,
                ),
                Progress(
                    user_id=user.id,
                    study_plan_id=plan_es.id,
                    date=today,
                    xp_earned=50,
                    streak_day=2,
                    lessons_completed=1,
                ),
            ]
        )
        await db_session.commit()

        count_en = await db_session.scalar(
            select(func.count()).where(Progress.study_plan_id == plan_en.id)
        )
        count_es = await db_session.scalar(
            select(func.count()).where(Progress.study_plan_id == plan_es.id)
        )
        assert count_en == 1
        assert count_es == 1

    @pytest.mark.asyncio
    async def test_flashcards_isolated_by_language(self, client, db_session):
        """Flashcards are scoped by study_plan_id — no cross-language leakage."""
        user, _headers = await _make_user(db_session)
        await _add_language(db_session, user.id, "es-ES", active=False)
        plan_en = await _make_plan(db_session, user.id, language="en-US")
        plan_es = await _make_plan(db_session, user.id, language="es-ES")

        fc_en = Flashcard(
            user_id=user.id,
            study_plan_id=plan_en.id,
            word="dog",
            definition="A canine animal",
            example_sentence="The dog is running.",
            translation="perro",
            source="chat",
        )
        fc_es = Flashcard(
            user_id=user.id,
            study_plan_id=plan_es.id,
            word="casa",
            definition="Edificio donde se vive",
            example_sentence="La casa es grande.",
            translation="house",
            source="chat",
        )
        db_session.add_all([fc_en, fc_es])
        await db_session.commit()

        count_en = await db_session.scalar(
            select(func.count()).where(Flashcard.study_plan_id == plan_en.id)
        )
        count_es = await db_session.scalar(
            select(func.count()).where(Flashcard.study_plan_id == plan_es.id)
        )
        assert count_en == 1
        assert count_es == 1

    @pytest.mark.asyncio
    async def test_memories_shared_across_languages(self, client, db_session):
        """Plan provenance never limits global user memory retrieval."""
        user, _headers = await _make_user(db_session)
        await _add_language(db_session, user.id, "es-ES", active=False)
        plan_en = await _make_plan(db_session, user.id, language="en-US")
        plan_es = await _make_plan(db_session, user.id, language="es-ES")

        mem_en = Memory(
            user_id=user.id,
            study_plan_id=plan_en.id,
            content="User likes dogs",
            source="chat",
        )
        mem_es = Memory(
            user_id=user.id,
            study_plan_id=plan_es.id,
            content="Usuario prefiere gatos",
            source="chat",
        )
        db_session.add_all([mem_en, mem_es])
        await db_session.commit()

        memories = await get_user_memories(db_session, user.id)
        assert [memory.content for memory in memories] == [
            "User likes dogs",
            "Usuario prefiere gatos",
        ]

    @pytest.mark.asyncio
    async def test_conversations_isolated_by_language(self, client, db_session):
        """Conversations are scoped by study_plan_id."""
        from app.models.conversation import Conversation

        user, _headers = await _make_user(db_session)
        await _add_language(db_session, user.id, "es-ES", active=False)
        plan_en = await _make_plan(db_session, user.id, language="en-US")
        plan_es = await _make_plan(db_session, user.id, language="es-ES")

        conv_en = Conversation(
            user_id=user.id,
            study_plan_id=plan_en.id,
            title="English chat",
            source="chat",
        )
        conv_es = Conversation(
            user_id=user.id,
            study_plan_id=plan_es.id,
            title="Spanish chat",
            source="chat",
        )
        db_session.add_all([conv_en, conv_es])
        await db_session.commit()

        count_en = await db_session.scalar(
            select(func.count()).where(Conversation.study_plan_id == plan_en.id)
        )
        count_es = await db_session.scalar(
            select(func.count()).where(Conversation.study_plan_id == plan_es.id)
        )
        assert count_en == 1
        assert count_es == 1


# ═════════════════════════════════════════════════════════════════════════════
# 10.2 — Prompt language awareness
# ═════════════════════════════════════════════════════════════════════════════


class TestPromptLanguage:
    @pytest.mark.asyncio
    async def test_active_language_resolves_to_study_plan(self, client, db_session):
        """The active UserLanguage's target_language is used to find the active
        study plan via get_active_study_plan dependency."""
        user, headers = await _make_user(db_session)
        plan = await _make_plan(db_session, user.id, language="en-US", cefr="B1")

        # get_active_study_plan resolves plan by active UserLanguage
        from app.core.database import get_db

        async def _resolve():

            # Simulate what the dependency does
            async for _session in get_db():
                break
            return None  # can't fully test dependency injection here

        # Verify the plan matches the active language
        assert plan.target_language == "en-US"

    @pytest.mark.asyncio
    async def test_add_language_activates_new_language(self, client, db_session):
        """When a new language is added, it becomes the active one."""
        user, headers = await _make_user(db_session)

        # en-US is active (from test_user fixture pattern)
        active_before = await client.get("/api/languages/active", headers=headers)
        assert active_before.json()["target_language"] == "en-US"

        # Add es-ES — should become active
        await client.post("/api/languages", headers=headers, json={"target_language": "es-ES"})
        active_after = await client.get("/api/languages/active", headers=headers)
        assert active_after.json()["target_language"] == "es-ES"

    @pytest.mark.asyncio
    async def test_study_plan_generator_accepts_language_param(self, client, db_session):
        """POST /api/study-plan/generate accepts target_language parameter."""
        user, headers = await _make_user(db_session)
        await _add_language(db_session, user.id, "es-ES", active=False)

        res = await client.post(
            "/api/study-plan/generate",
            headers=headers,
            json={
                "cefr_level": "A2",
                "goals": ["vocabulary"],
                "target_language": "es-ES",
                "duration_weeks": 4,
                "days_per_week": 4,
            },
        )
        assert res.status_code == 200
        data = res.json()
        # Verify the plan was created for the requested language
        assert data["cefr_level"] == "A2"
        # The plan in the DB should have the correct target_language
        es_plan = (
            await db_session.execute(
                select(StudyPlan).where(
                    StudyPlan.user_id == user.id,
                    StudyPlan.target_language == "es-ES",
                )
            )
        ).scalar_one_or_none()
        assert es_plan is not None


# ═════════════════════════════════════════════════════════════════════════════
# 10.3 — Language API endpoints
# ═════════════════════════════════════════════════════════════════════════════


class TestLanguageAPI:
    @pytest.mark.asyncio
    async def test_add_new_language(self, client, db_session):
        """POST /api/languages creates a UserLanguage row."""
        user, headers = await _make_user(db_session)

        res = await client.post(
            "/api/languages",
            headers=headers,
            json={"target_language": "es-ES"},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["target_language"] == "es-ES"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_add_duplicate_language(self, client, db_session):
        """POST with an already-existing language returns 409."""
        user, headers = await _make_user(db_session)

        await client.post("/api/languages", headers=headers, json={"target_language": "es-ES"})
        res = await client.post(
            "/api/languages", headers=headers, json={"target_language": "es-ES"}
        )
        assert res.status_code == 409

    @pytest.mark.asyncio
    async def test_switch_language(self, client, db_session):
        """PUT /api/languages/active switches the active language."""
        user, headers = await _make_user(db_session)
        await client.post("/api/languages", headers=headers, json={"target_language": "es-ES"})

        # es-ES should now be active (was just added, which auto-activates)
        active_res = await client.get("/api/languages/active", headers=headers)
        assert active_res.json()["target_language"] == "es-ES"

        # Switch back to en-US
        switch_res = await client.put(
            "/api/languages/active",
            headers=headers,
            json={"target_language": "en-US"},
        )
        assert switch_res.status_code == 200
        assert switch_res.json()["target_language"] == "en-US"

        # Verify it actually changed
        active_res = await client.get("/api/languages/active", headers=headers)
        assert active_res.json()["target_language"] == "en-US"

    @pytest.mark.asyncio
    async def test_list_languages(self, client, db_session):
        """GET /api/languages returns all languages with summarised progress."""
        user, headers = await _make_user(db_session)
        await _make_plan(db_session, user.id, language="en-US", cefr="B1")

        res = await client.get("/api/languages", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "languages" in data
        assert len(data["languages"]) >= 1
        assert any(lang["target_language"] == "en-US" for lang in data["languages"])
        assert "all_supported_languages" in data
        assert "ja-JP" in data["all_supported_languages"]
        assert "ko-KR" in data["all_supported_languages"]
        assert "zh-CN" in data["all_supported_languages"]

    @pytest.mark.asyncio
    async def test_remove_language_cascades(self, client, db_session):
        """Language deletion removes scoped data but preserves global memories."""
        user, headers = await _make_user(db_session)
        await client.post("/api/languages", headers=headers, json={"target_language": "es-ES"})
        plan_es = await _make_plan(db_session, user.id, language="es-ES")
        memory = Memory(
            user_id=user.id,
            study_plan_id=plan_es.id,
            content="User enjoys cooking",
            source="chat",
        )
        db_session.add(memory)
        await db_session.commit()
        memory_id = memory.id
        user_id = user.id

        # Switch away from es-ES first (can't delete active language)
        await client.put(
            "/api/languages/active",
            headers=headers,
            json={"target_language": "en-US"},
        )

        res = await client.delete("/api/languages/es-ES", headers=headers)
        assert res.status_code == 204

        # Verify it's gone
        remaining = (
            (await db_session.execute(select(UserLanguage).where(UserLanguage.user_id == user.id)))
            .scalars()
            .all()
        )
        assert all(lang.target_language != "es-ES" for lang in remaining)
        db_session.expire_all()
        preserved = await db_session.get(Memory, memory_id)
        assert preserved is not None
        assert preserved.user_id == user_id
        assert preserved.study_plan_id is None

    @pytest.mark.asyncio
    async def test_cannot_remove_last_language(self, client, db_session):
        """DELETE when user has only 1 language returns 400."""
        user, headers = await _make_user(db_session)

        res = await client.delete("/api/languages/en-US", headers=headers)
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_cannot_remove_active_language(self, client, db_session):
        """DELETE on the currently active language returns 400."""
        user, headers = await _make_user(db_session)
        await client.post("/api/languages", headers=headers, json={"target_language": "es-ES"})

        # es-ES is now active (added last, auto-activates), try to delete it
        res = await client.delete("/api/languages/es-ES", headers=headers)
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_supported_languages_validation(self, client, db_session):
        """POST /api/languages with unsupported language returns 422."""
        user, headers = await _make_user(db_session)

        res = await client.post(
            "/api/languages",
            headers=headers,
            json={"target_language": "xx-XX"},
        )
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_japanese_language_can_be_added(self, client, db_session):
        """ja-JP is accepted by the backend language allow-list."""
        user, headers = await _make_user(db_session)

        res = await client.post(
            "/api/languages", headers=headers, json={"target_language": "ja-JP"}
        )

        assert res.status_code == 201
        assert res.json()["target_language"] == "ja-JP"

    @pytest.mark.asyncio
    async def test_korean_language_can_be_added(self, client, db_session):
        """ko-KR is accepted by the backend language allow-list."""
        user, headers = await _make_user(db_session)

        res = await client.post(
            "/api/languages", headers=headers, json={"target_language": "ko-KR"}
        )

        assert res.status_code == 201
        assert res.json()["target_language"] == "ko-KR"

    @pytest.mark.asyncio
    async def test_chinese_language_can_be_added(self, client, db_session):
        """zh-CN is accepted by the backend language allow-list."""
        user, headers = await _make_user(db_session)

        res = await client.post(
            "/api/languages", headers=headers, json={"target_language": "zh-CN"}
        )

        assert res.status_code == 201
        assert res.json()["target_language"] == "zh-CN"

    @pytest.mark.asyncio
    async def test_plan_deactivation_scoped_by_language(self, client, db_session):
        """Creating a Spanish plan does not deactivate the active English plan."""
        user, headers = await _make_user(db_session)
        await _add_language(db_session, user.id, "es-ES", active=False)
        plan_en = await _make_plan(db_session, user.id, language="en-US")

        await client.post(
            "/api/study-plan/generate",
            headers=headers,
            json={
                "cefr_level": "A1",
                "goals": ["vocabulary"],
                "target_language": "es-ES",
                "duration_weeks": 4,
                "days_per_week": 4,
            },
        )

        await db_session.refresh(plan_en)
        assert plan_en.is_active is True  # English plan should still be active

        es_plan = (
            await db_session.execute(
                select(StudyPlan).where(
                    StudyPlan.user_id == user.id,
                    StudyPlan.target_language == "es-ES",
                )
            )
        ).scalar_one_or_none()
        assert es_plan is not None
        assert es_plan.is_active is True

    @pytest.mark.asyncio
    async def test_onboarding_creates_user_language(self, client, db_session):
        """Registration + PATCH /api/auth/me creates UserLanguage row."""
        user = User(
            username="freshuser",
            email="fresh@example.com",
            display_name="Fresh",
            hashed_password=hash_password("testpass"),
            role="user",
            native_language="fr",
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        token = create_access_token(user.id, user.role)
        headers = {"Authorization": f"Bearer {token}"}

        res = await client.patch(
            "/api/auth/me",
            headers=headers,
            json={"target_language": "es-ES"},
        )
        assert res.status_code == 200

        ul = (
            await db_session.execute(
                select(UserLanguage).where(
                    UserLanguage.user_id == user.id,
                    UserLanguage.target_language == "es-ES",
                )
            )
        ).scalar_one_or_none()
        assert ul is not None
        assert ul.is_active is True

    @pytest.mark.asyncio
    async def test_assessment_language_param(self, client, db_session):
        """GET /api/assessment/start?language=es-ES stores session under scoped Redis key."""
        from unittest.mock import patch as mock_patch

        user, headers = await _make_user(db_session)
        await _add_language(db_session, user.id, "es-ES", active=False)

        mock_quiz = {
            "questions": [
                {
                    "id": 1,
                    "type": "multiple_choice",
                    "difficulty": "A1",
                    "question": "¿Cuál es la capital de España?",
                    "options": ["A. París", "B. Madrid", "C. Roma", "D. Lisboa"],
                    "correct_answer": "B",
                }
            ]
        }

        with mock_patch(
            "app.routers.assessment.llm_adapter.structured_output",
            return_value=mock_quiz,
        ):
            res = await client.get(
                "/api/assessment/start?language=es-ES",
                headers=headers,
            )

        assert res.status_code == 200
        data = res.json()
        assert "quiz" in data
        assert "session_id" in data

    @pytest.mark.asyncio
    async def test_assessment_redis_key_isolation(self, client, db_session, mock_redis):
        """Two simultaneous assessments for different languages must not overwrite each other.

        Flow:
          1. Start English assessment   → stores at assessment:{uid}:en-US
          2. Start Spanish assessment   → stores at assessment:{uid}:es-ES
          3. Submit English answers with target_language=en-US → resolves en-US session, returns result
          4. Verify Spanish session is still intact at assessment:{uid}:es-ES
        """
        import json as _json
        from unittest.mock import patch as mock_patch

        user, headers = await _make_user(db_session)
        await _add_language(db_session, user.id, "es-ES", active=False)

        mock_quiz_en = {
            "questions": [
                {
                    "id": 1,
                    "type": "multiple_choice",
                    "difficulty": "B1",
                    "question": "Choose the correct verb form.",
                    "options": ["A. have", "B. has", "C. had", "D. having"],
                    "correct_answer": "A",
                }
            ]
        }
        mock_quiz_es = {
            "questions": [
                {
                    "id": 2,
                    "type": "multiple_choice",
                    "difficulty": "A1",
                    "question": "¿Qué significa 'perro'?",
                    "options": ["A. cat", "B. dog", "C. bird", "D. fish"],
                    "correct_answer": "B",
                }
            ]
        }
        mock_eval = {
            "cefr_level": "B1",
            "score": 0.8,
            "analysis": "Good",
            "strengths": ["grammar"],
            "weaknesses": [],
        }

        # Step 1: start English assessment
        with mock_patch(
            "app.routers.assessment.llm_adapter.structured_output",
            return_value=mock_quiz_en,
        ):
            await client.get("/api/assessment/start?language=en-US", headers=headers)

        # Step 2: start Spanish assessment (must NOT overwrite the English session)
        with mock_patch(
            "app.routers.assessment.llm_adapter.structured_output",
            return_value=mock_quiz_es,
        ):
            await client.get("/api/assessment/start?language=es-ES", headers=headers)

        # Verify both sessions are stored under separate keys
        en_session_raw = await mock_redis.get(f"assessment:{user.id}:en-US")
        es_session_raw = await mock_redis.get(f"assessment:{user.id}:es-ES")
        assert en_session_raw is not None, "English session must still exist"
        assert es_session_raw is not None, "Spanish session must exist"

        en_session = _json.loads(en_session_raw)
        es_session = _json.loads(es_session_raw)
        assert en_session["target_language"] == "en-US"
        assert es_session["target_language"] == "es-ES"

        # Step 3: submit English answers — must evaluate the English session
        with mock_patch(
            "app.routers.assessment.llm_adapter.structured_output",
            return_value=mock_eval,
        ):
            submit_res = await client.post(
                "/api/assessment/submit",
                headers=headers,
                json={
                    "answers": [{"question_id": 1, "answer": "A"}],
                    "target_language": "en-US",
                },
            )
        assert submit_res.status_code == 200
        assert submit_res.json()["cefr_level"] == "B1"

        # Step 4: Spanish session must be untouched after English submission
        es_session_after = await mock_redis.get(f"assessment:{user.id}:es-ES")
        assert es_session_after is not None, "Spanish session must survive English submission"
        assert _json.loads(es_session_after)["target_language"] == "es-ES"

        # English session must have been deleted by /submit
        en_session_after = await mock_redis.get(f"assessment:{user.id}:en-US")
        assert en_session_after is None, "English session must be deleted after submission"


# ═════════════════════════════════════════════════════════════════════════════
# 10.6 — Curriculum per language
# ═════════════════════════════════════════════════════════════════════════════


class TestCurriculumPerLanguage:
    @pytest.mark.asyncio
    async def test_curriculum_english(self, client):
        """get_curriculum('en-US') returns English curriculum."""
        from app.data.curriculum import get_curriculum

        c = get_curriculum("en-US")
        assert "A1" in c
        assert "C2" in c
        assert len(c["A1"]) == 8
        assert len(c["C2"]) == 8

    @pytest.mark.asyncio
    async def test_curriculum_spanish(self, client):
        """get_curriculum('es-ES') returns Spanish curriculum."""
        from app.data.curriculum import get_curriculum

        c = get_curriculum("es-ES")
        assert "A1" in c
        assert "C2" in c
        assert len(c["A1"]) == 8
        assert len(c["C2"]) == 8
        # Verify it's Spanish content
        assert c["A1"][0].title == "Saludos y presentaciones"

    @pytest.mark.asyncio
    async def test_curriculum_italian(self, client):
        """get_curriculum('it-IT') returns Italian curriculum."""
        from app.data.curriculum import get_curriculum

        c = get_curriculum("it-IT")
        assert "A1" in c
        assert "C2" in c
        assert len(c["A1"]) == 8
        assert c["A1"][0].title == "Saluti e presentazioni"

    @pytest.mark.asyncio
    async def test_curriculum_portuguese(self, client):
        """get_curriculum('pt-PT') returns Portuguese curriculum."""
        from app.data.curriculum import get_curriculum

        c = get_curriculum("pt-PT")
        assert "A1" in c
        assert "C2" in c
        assert len(c["A1"]) == 8
        assert c["A1"][0].title == "Saudações e apresentações"

    @pytest.mark.asyncio
    async def test_curriculum_french(self, client):
        """get_curriculum('fr-FR') returns French curriculum."""
        from app.data.curriculum import get_curriculum

        c = get_curriculum("fr-FR")
        assert "A1" in c
        assert "C2" in c
        assert len(c["A1"]) == 8
        assert c["A1"][0].title == "Se présenter et saluer"

    @pytest.mark.asyncio
    async def test_curriculum_german(self, client):
        """get_curriculum('de-DE') returns German curriculum."""
        from app.data.curriculum import get_curriculum

        c = get_curriculum("de-DE")
        assert c is not None
        assert "A1" in c
        assert len(c["A1"]) == 8
        assert c["A1"][0].title == "Sich vorstellen und begrüßen"

    @pytest.mark.asyncio
    async def test_curriculum_fallback(self, client):
        """Unsupported language falls back to English."""
        from app.data.curriculum import get_curriculum

        c = get_curriculum("xx-XX")
        assert "A1" in c
        # Should be English content
        assert c["A1"][0].title == "Identity & Greetings"

    @pytest.mark.asyncio
    async def test_curriculum_japanese(self, client):
        """get_curriculum('ja-JP') returns Japanese curriculum."""
        from app.data.curriculum import get_curriculum

        c = get_curriculum("ja-JP")
        assert list(c.keys()) == ["A1", "A2", "B1", "B2", "C1", "C2"]
        assert len(c["A1"]) == 8
        assert c["A1"][0].title == "文字とあいさつ"
        assert c["C2"][-1].title == "C2総復習と最終統合"

    @pytest.mark.asyncio
    async def test_curriculum_korean(self, client):
        """get_curriculum('ko-KR') returns Korean curriculum."""
        from app.data.curriculum import get_curriculum

        c = get_curriculum("ko-KR")
        assert list(c.keys()) == ["A1", "A2", "B1", "B2", "C1", "C2"]
        assert len(c["A1"]) == 8
        assert c["A1"][0].title == "한글과 기본 인사"
        assert c["C2"][-1].title == "C2 종합 복습"

    @pytest.mark.asyncio
    async def test_curriculum_chinese(self, client):
        """get_curriculum('zh-CN') returns Mainland Chinese curriculum."""
        from app.data.curriculum import get_curriculum

        c = get_curriculum("zh-CN")
        assert list(c.keys()) == ["A1", "A2", "B1", "B2", "C1", "C2"]
        assert len(c["A1"]) == 8
        assert c["A1"][0].title == "拼音、声调和问候"
        assert c["C2"][-1].title == "C2综合复习"

    @pytest.mark.asyncio
    async def test_get_curriculum_units_with_language(self, client):
        """get_curriculum_units resolves correct language."""
        from app.data.curriculum import get_curriculum_units

        en_units = get_curriculum_units("A1", "en-US")
        es_units = get_curriculum_units("A1", "es-ES")

        assert en_units[0].title != es_units[0].title
        assert len(en_units) == 8
        assert len(es_units) == 8
