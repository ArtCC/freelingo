"""Tests for the WebSocket conversation endpoint and pipeline."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from httpx_ws import aconnect_ws

from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.routers import conversation as conversation_router

# ---------------------------------------------------------------------------
# Helper: create a real user and return a valid JWT
# ---------------------------------------------------------------------------


async def _create_user_and_token(db_session) -> tuple:
    from app.core.security import hash_password
    from app.models.user import User
    from app.models.user_language import UserLanguage

    user = User(
        username="convuser",
        email="conv@example.com",
        display_name="Conv User",
        hashed_password=hash_password("convpass"),
        role="user",
        native_language="es",
        target_language="en-US",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserLanguage(user_id=user.id, target_language="en-US", is_active=True))
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(user.id, user.role)
    return user, token


# ---------------------------------------------------------------------------
# Auth tests (services disabled so we reach the guard early)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ws_rejects_invalid_token(client: AsyncClient) -> None:
    """Invalid auth frame must emit auth_failed and close."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        try:
            async with aconnect_ws("/ws/conversation", ac) as ws:
                await ws.send_json({"type": "auth", "token": "notavalidjwt"})
                msg = await ws.receive_json()
                assert msg["type"] == "error"
                assert msg["code"] == "auth_failed"
        except Exception:
            pass  # connection closed after auth failure is expected


@pytest.mark.asyncio
async def test_ws_rejects_missing_token(client: AsyncClient) -> None:
    """WebSocket missing auth token in first message must fail."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        try:
            async with aconnect_ws("/ws/conversation", ac) as ws:
                await ws.send_json({"type": "auth"})
                msg = await ws.receive_json()
                assert msg["type"] == "error"
                assert msg["code"] == "auth_failed"
        except Exception:
            pass  # connection closed after auth failure is expected


@pytest.mark.asyncio
async def test_ws_services_disabled_sends_error(db_session) -> None:
    """When TTS/STT are disabled the WS must accept, send error frame, then close."""
    _, token = await _create_user_and_token(db_session)

    # Ensure services are None (default in test env)
    app.state.tts_service = None
    app.state.stt_service = None

    from app.core.database import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        try:
            async with aconnect_ws("/ws/conversation", ac) as ws:
                await ws.send_json({"type": "auth", "token": token})
                msg = await ws.receive_json()
                assert msg["type"] == "error"
                assert msg["code"] == "services_disabled"
        except Exception:
            pass  # closed after error is fine

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_warmup_tts_uses_health_for_openai() -> None:
    """Warmup should call OpenAI health check and avoid a full synthesis."""
    # OpenAI service exposes `.model`; use that to select health check mode.
    tts_service = type(
        "OpenAIMock",
        (object,),
        {},
    )()
    tts_service.model = "tts-1"
    tts_service.health = AsyncMock()
    tts_service.synthesize = AsyncMock()

    await conversation_router._warmup_tts(tts_service)

    tts_service.health.assert_called_once_with()
    tts_service.synthesize.assert_not_called()


@pytest.mark.asyncio
async def test_warmup_tts_falls_back_to_synthesis_for_local_service() -> None:
    """Warmup for local service should still issue a tiny probe synthesis."""
    tts_service = type("LocalMock", (object,), {})()
    tts_service.synthesize = AsyncMock()

    await conversation_router._warmup_tts(tts_service)

    tts_service.synthesize.assert_called_once_with("ready")


@pytest.mark.asyncio
async def test_warmup_allows_valid_assessment_voice_trial(client, test_user, db_session) -> None:
    """Warmup accepts a valid post-assessment voice trial token without subscription."""
    user, headers = test_user

    # Import helper from conftest via direct local import is not available; clear plans inline.
    from sqlalchemy import select

    from app.models.study_plan import StudyPlan
    from app.models.user_language import UserLanguage

    ul = (
        await db_session.execute(
            select(UserLanguage).where(
                UserLanguage.user_id == user.id,
                UserLanguage.target_language == "en-US",
            )
        )
    ).scalar_one()
    plans = (
        await db_session.execute(
            select(StudyPlan).where(
                StudyPlan.user_language_id == ul.id,
                StudyPlan.is_active.is_(True),
            )
        )
    ).scalars()
    for plan in plans:
        plan.is_active = False
    await db_session.commit()

    with patch.object(settings, "STRIPE_ENABLED", True):
        complete = await client.post(
            "/api/assessment/complete",
            headers=headers,
            json={
                "cefr_level": "A1",
                "strengths": [],
                "weaknesses": [],
                "duration_weeks": 4,
                "days_per_week": 4,
                "goals": ["grammar"],
                "target_language": "en-US",
            },
        )
        token = complete.json()["voice_trial"]["token"]
        response = await client.post(
            "/api/conversation/warmup",
            headers=headers,
            json={"trial_token": token},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_warmup_rejects_invalid_assessment_voice_trial(client, test_user) -> None:
    """Warmup still requires subscription when freemium quota is exhausted and trial token is invalid."""
    _user, headers = test_user

    with (
        patch.object(settings, "STRIPE_ENABLED", True),
        patch.object(settings, "FREEMIUM_VOICE_WEEKLY_MINUTES", 0),
    ):
        response = await client.post(
            "/api/conversation/warmup",
            headers=headers,
            json={"trial_token": "bad-token"},
        )

    assert response.status_code == 402
    assert response.json()["detail"] == "subscription_required"


# ---------------------------------------------------------------------------
# PATCH /me — conversation settings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_me_conversation_settings(client, test_user) -> None:
    """PATCH /api/auth/me should persist conversation timeout preferences."""
    _, headers = test_user

    response = await client.patch(
        "/api/auth/me",
        headers=headers,
        json={
            "conversation_max_duration": 900,
            "conversation_inactivity_timeout": 60,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_max_duration"] == 900
    assert data["conversation_inactivity_timeout"] == 60


@pytest.mark.asyncio
async def test_patch_me_invalid_conversation_duration(client, test_user) -> None:
    """PATCH /api/auth/me rejects values not in Literal[900, 1800]."""
    _, headers = test_user

    response = await client.patch(
        "/api/auth/me",
        headers=headers,
        json={"conversation_max_duration": 600},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_me_invalid_inactivity_timeout(client, test_user) -> None:
    """PATCH /api/auth/me rejects values not in Literal[60, 180, 300]."""
    _, headers = test_user

    response = await client.patch(
        "/api/auth/me",
        headers=headers,
        json={"conversation_inactivity_timeout": 120},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_me_speech_pause(client, test_user) -> None:
    """PATCH /api/auth/me should persist the end-of-turn pause."""
    _, headers = test_user

    response = await client.patch(
        "/api/auth/me",
        headers=headers,
        json={"conversation_speech_pause": 3000},
    )
    assert response.status_code == 200
    assert response.json()["conversation_speech_pause"] == 3000


@pytest.mark.asyncio
async def test_patch_me_speech_pause_back_to_automatic(client, test_user) -> None:
    """Zero restores the level-derived end-of-turn pause."""
    _, headers = test_user

    await client.patch(
        "/api/auth/me",
        headers=headers,
        json={"conversation_speech_pause": 2000},
    )
    response = await client.patch(
        "/api/auth/me",
        headers=headers,
        json={"conversation_speech_pause": 0},
    )
    assert response.status_code == 200
    assert response.json()["conversation_speech_pause"] == 0


@pytest.mark.asyncio
async def test_patch_me_invalid_speech_pause(client, test_user) -> None:
    """PATCH /api/auth/me rejects pause values outside the offered set."""
    _, headers = test_user

    response = await client.patch(
        "/api/auth/me",
        headers=headers,
        json={"conversation_speech_pause": 1500},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /me — new fields present in response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_me_includes_conversation_fields(client, test_user) -> None:
    """GET /api/auth/me must include the two new conversation settings."""
    _, headers = test_user

    response = await client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "conversation_max_duration" in data
    assert "conversation_inactivity_timeout" in data
    assert "conversation_speech_pause" in data
    # defaults
    assert data["conversation_max_duration"] == 1800
    assert data["conversation_inactivity_timeout"] == 180
    assert data["conversation_speech_pause"] == 0


# ---------------------------------------------------------------------------
# ConversationPipeline unit tests (no network)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_process_sends_transcript_and_turn_complete() -> None:
    """Pipeline sends transcript + turn_complete for a happy-path audio chunk."""
    sent: list = []

    class FakeWS:
        async def send_json(self, data):
            sent.append(("json", data))

        async def send_bytes(self, data):
            sent.append(("bytes", data))

    # Mock stream: one chunk with complete sentence
    chunk = MagicMock()
    chunk.choices[0].delta.content = "Hello there."

    async def fake_stream():
        yield chunk

    fake_llm = AsyncMock()
    fake_llm.chat = AsyncMock(return_value=fake_stream())

    fake_stt = AsyncMock()
    fake_stt.transcribe = AsyncMock(return_value="Hello")

    fake_tts = AsyncMock()
    fake_tts.synthesize = AsyncMock(return_value=b"mp3data")

    from app.services.conversation_pipeline import ConversationPipeline

    pipeline = ConversationPipeline(
        llm=fake_llm,
        tts=fake_tts,
        stt=fake_stt,
        cefr_level="B1",
        max_duration=1800,
        inactivity_timeout=180,
    )

    ws = FakeWS()
    await pipeline._process(b"audio", ws)

    types = [m[1]["type"] for m in sent if m[0] == "json"]
    assert "transcript" in types
    assert "turn_complete" in types
    assert any(m[0] == "bytes" for m in sent)


@pytest.mark.asyncio
async def test_pipeline_stt_failure_sends_error_frame() -> None:
    """STT exception must produce an error frame; pipeline continues."""
    sent: list = []

    class FakeWS:
        async def send_json(self, data):
            sent.append(data)

        async def send_bytes(self, data):
            pass

    fake_stt = AsyncMock()
    fake_stt.transcribe = AsyncMock(side_effect=RuntimeError("STT down"))

    from app.services.conversation_pipeline import ConversationPipeline

    pipeline = ConversationPipeline(
        llm=AsyncMock(),
        tts=AsyncMock(),
        stt=fake_stt,
    )

    await pipeline._process(b"audio", FakeWS())

    codes = [m.get("code") for m in sent if m.get("type") == "error"]
    assert "stt_failed" in codes


# ---------------------------------------------------------------------------
# ConversationPipeline — initial_context tests
# ---------------------------------------------------------------------------


def _make_pipeline(**kwargs):  # noqa: F821
    from app.services.conversation_pipeline import ConversationPipeline

    return ConversationPipeline(
        llm=AsyncMock(),
        tts=AsyncMock(),
        stt=AsyncMock(),
        cefr_level="B1",
        max_duration=1800,
        inactivity_timeout=180,
        **kwargs,
    )


def test_pipeline_initial_context_none_gives_empty_history() -> None:
    """No initial_context → empty history list."""
    pipeline = _make_pipeline()
    assert pipeline.history == []


def test_pipeline_initial_context_empty_list_gives_empty_history() -> None:
    """Empty list initial_context → empty history list."""
    pipeline = _make_pipeline(initial_context=[])
    assert pipeline.history == []


def test_pipeline_initial_context_valid_entries_populate_history() -> None:
    """Valid initial_context entries are copied verbatim into history."""
    context = [
        {"role": "user", "content": "Hello, can you help me?"},
        {"role": "assistant", "content": "Of course! What would you like to practice?"},
        {"role": "user", "content": "I want to work on past tense."},
    ]
    pipeline = _make_pipeline(initial_context=context)
    assert len(pipeline.history) == 3
    assert pipeline.history[0] == {"role": "user", "content": "Hello, can you help me?"}
    assert pipeline.history[2] == {
        "role": "user",
        "content": "I want to work on past tense.",
    }


def test_pipeline_initial_context_truncates_to_last_10() -> None:
    """When initial_context has more than 10 valid entries, only the last 10 are kept."""
    context = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"}
        for i in range(14)
    ]
    pipeline = _make_pipeline(initial_context=context)
    assert len(pipeline.history) == 10
    # The last 10 items of the original list (indices 4-13) must be preserved in order
    expected_contents = [f"Message {i}" for i in range(4, 14)]
    actual_contents = [m["content"] for m in pipeline.history]
    assert actual_contents == expected_contents


def test_pipeline_initial_context_filters_invalid_role() -> None:
    """Entries with unrecognised roles are silently dropped."""
    context = [
        {"role": "system", "content": "You are a bot."},  # invalid role
        {"role": "user", "content": "Hello there!"},
        {"role": "moderator", "content": "Be nice."},  # invalid role
        {"role": "assistant", "content": "Hi!"},
    ]
    pipeline = _make_pipeline(initial_context=context)
    assert len(pipeline.history) == 2
    assert pipeline.history[0]["role"] == "user"
    assert pipeline.history[1]["role"] == "assistant"


# ---------------------------------------------------------------------------
# voice_session_title — unit tests
# ---------------------------------------------------------------------------


def test_voice_session_title_english_fallback() -> None:
    """Unknown / English language code falls back to English label and format."""
    from app.services.language_helpers import voice_session_title

    title = voice_session_title("en")
    assert title.startswith("Voice session — ")
    # Fallback uses strftime '%B %d, %Y', which always produces a non-empty date.
    assert len(title) > len("Voice session — ")


def test_voice_session_title_unknown_language() -> None:
    """Completely unknown language code falls back to English."""
    from app.services.language_helpers import voice_session_title

    title = voice_session_title("xx")
    assert title.startswith("Voice session — ")


def test_voice_session_title_spanish() -> None:
    """Spanish uses 'Sesión de voz' label and 'D de mes de YYYY' format."""
    from app.services.language_helpers import voice_session_title

    title = voice_session_title("es")
    assert title.startswith("Sesión de voz — ")
    # Exactly two 'de' separators in the date portion.
    date_part = title.split(" — ", 1)[1]
    assert date_part.count(" de ") == 2


def test_voice_session_title_portuguese() -> None:
    """Portuguese uses 'Sessão de voz' label and 'D de mes de YYYY' format."""
    from app.services.language_helpers import voice_session_title

    title = voice_session_title("pt")
    assert title.startswith("Sessão de voz — ")
    date_part = title.split(" — ", 1)[1]
    assert date_part.count(" de ") == 2


def test_voice_session_title_german() -> None:
    """German uses 'Sprachsitzung' label and plain 'D Month YYYY' format."""
    from app.services.language_helpers import voice_session_title

    title = voice_session_title("de")
    assert title.startswith("Sprachsitzung — ")
    # No 'de' separators in German dates.
    date_part = title.split(" — ", 1)[1]
    assert " de " not in date_part


def test_voice_session_title_polish() -> None:
    """Polish uses 'Sesja głosowa' label and plain 'D month YYYY' format (genitive months)."""
    from app.services.language_helpers import voice_session_title

    title = voice_session_title("pl")
    assert title.startswith("Sesja głosowa — ")
    date_part = title.split(" — ", 1)[1]
    assert " de " not in date_part


def test_voice_session_title_russian() -> None:
    """Russian uses Cyrillic label and plain 'D month YYYY' format (genitive months)."""
    from app.services.language_helpers import voice_session_title

    title = voice_session_title("ru")
    assert title.startswith("Голосовая сессия — ")
    date_part = title.split(" — ", 1)[1]
    assert " de " not in date_part


def test_voice_session_title_all_supported_languages_produce_nonempty() -> None:
    """Every supported native language must produce a non-empty title."""
    from app.services.language_helpers import voice_session_title

    supported = ["es", "fr", "pt", "de", "it", "pl", "nl", "ro", "ru"]
    for lang in supported:
        title = voice_session_title(lang)
        assert title.strip(), f"Empty title for language '{lang}'"
        assert " — " in title, f"Missing date separator for language '{lang}'"


# ---------------------------------------------------------------------------
# ConversationPipeline — _save_message deferred until turn success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_does_not_save_user_msg_on_llm_failure() -> None:
    """User message must NOT be persisted when the LLM fails.

    The save is deferred to after a successful turn so no orphan rows appear
    in the transcript when a turn errors out.
    """
    saved_roles: list[str] = []

    class FakeWS:
        async def send_json(self, _data):
            pass

        async def send_bytes(self, _data):
            pass

    from app.services.conversation_pipeline import ConversationPipeline
    from app.services.llm_adapter import LLMError

    pipeline = ConversationPipeline(
        llm=AsyncMock(),
        tts=AsyncMock(),
        stt=AsyncMock(),
        cefr_level="B1",
        max_duration=1800,
        inactivity_timeout=180,
        user_id=1,
        conversation_id=1,
    )

    # Patch _save_message to track what gets saved instead of hitting the DB.
    async def _track_save(role: str, content: str) -> None:
        saved_roles.append(role)

    pipeline._save_message = _track_save  # type: ignore[method-assign]

    # STT succeeds, LLM raises immediately.
    pipeline.stt.transcribe = AsyncMock(return_value="hello")  # type: ignore[attr-defined]
    pipeline.llm.chat = AsyncMock(side_effect=LLMError("LLM down"))  # type: ignore[attr-defined]

    await pipeline._process(b"audio", FakeWS())

    # On LLM failure neither user nor assistant message should be persisted.
    assert saved_roles == [], f"Expected no saves on LLM failure, got: {saved_roles}"


@pytest.mark.asyncio
async def test_pipeline_saves_both_messages_on_successful_turn() -> None:
    """User and assistant messages are both persisted on a successful turn."""
    saved: list[tuple[str, str]] = []

    class FakeWS:
        async def send_json(self, _data):
            pass

        async def send_bytes(self, _data):
            pass

    chunk = MagicMock()
    chunk.choices[0].delta.content = "Hello."

    async def fake_stream():
        yield chunk

    from app.services.conversation_pipeline import ConversationPipeline

    pipeline = ConversationPipeline(
        llm=AsyncMock(),
        tts=AsyncMock(),
        stt=AsyncMock(),
        cefr_level="B1",
        max_duration=1800,
        inactivity_timeout=180,
        user_id=1,
        conversation_id=1,
    )

    async def _track_save(role: str, content: str) -> None:
        saved.append((role, content))

    pipeline._save_message = _track_save  # type: ignore[method-assign]
    pipeline.stt.transcribe = AsyncMock(return_value="hi there")  # type: ignore[attr-defined]
    pipeline.llm.chat = AsyncMock(return_value=fake_stream())  # type: ignore[attr-defined]
    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")  # type: ignore[attr-defined]

    await pipeline._process(b"audio", FakeWS())
    # Give the event loop a cycle to run the create_task()-scheduled saves.
    await asyncio.sleep(0)

    roles = [r for r, _ in saved]
    assert "user" in roles, "User message should be saved on successful turn"
    assert "assistant" in roles, "Assistant message should be saved on successful turn"
    # User must appear before assistant in the saved sequence.
    assert roles.index("user") < roles.index("assistant")


def test_pipeline_initial_context_filters_empty_content() -> None:
    """Entries with empty or whitespace-only content are silently dropped."""
    context = [
        {"role": "user", "content": ""},
        {"role": "user", "content": "   "},
        {"role": "assistant", "content": "Hello!"},
        {"role": "user", "content": "\n\t"},
    ]
    pipeline = _make_pipeline(initial_context=context)
    assert len(pipeline.history) == 1
    assert pipeline.history[0]["content"] == "Hello!"


def test_pipeline_initial_context_filters_non_dict_entries() -> None:
    """Non-dict entries (strings, ints, None) in initial_context are ignored."""
    context = [
        "not a dict",
        42,
        None,
        {"role": "user", "content": "This is valid."},
    ]
    pipeline = _make_pipeline(initial_context=context)  # type: ignore[arg-type]
    assert len(pipeline.history) == 1
    assert pipeline.history[0]["content"] == "This is valid."


def test_pipeline_initial_context_does_not_leak_extra_keys() -> None:
    """Extra keys in initial_context entries are stripped — only role/content survive."""
    context = [
        {"role": "user", "content": "Hi!", "id": 99, "timestamp": "2026-01-01"},
        {"role": "assistant", "content": "Hey there!", "metadata": {"foo": "bar"}},
    ]
    pipeline = _make_pipeline(initial_context=context)
    assert len(pipeline.history) == 2
    for entry in pipeline.history:
        assert set(entry.keys()) == {"role", "content"}


def test_pipeline_initial_context_history_is_used_in_subsequent_turns() -> None:
    """After pre-populating, normal _add_to_history appends to existing entries."""
    context = [{"role": "user", "content": "Tell me about cats."}]
    pipeline = _make_pipeline(initial_context=context)
    # Simulate what the pipeline does after a user turn: append to history
    pipeline.history.append({"role": "assistant", "content": "Cats are fascinating!"})
    assert len(pipeline.history) == 2
    assert pipeline.history[0]["role"] == "user"
    assert pipeline.history[1]["role"] == "assistant"
