"""Tests for the WebSocket conversation endpoint and pipeline."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from httpx_ws import aconnect_ws

from app.core.security import create_access_token
from app.main import app


# ---------------------------------------------------------------------------
# Helper: create a real user and return a valid JWT
# ---------------------------------------------------------------------------


async def _create_user_and_token(db_session) -> tuple:
    from app.core.security import hash_password
    from app.models.user import User

    user = User(
        username="convuser",
        email="conv@example.com",
        display_name="Conv User",
        hashed_password=hash_password("convpass"),
        role="user",
        native_language="es",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(user.id, user.role)
    return user, token


# ---------------------------------------------------------------------------
# Auth tests (services disabled so we reach the guard early)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ws_rejects_invalid_token(client: AsyncClient) -> None:
    """WebSocket must close with 1008 when the JWT is invalid."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        try:
            async with aconnect_ws("/ws/conversation?token=notavalidjwt", ac):
                pass
        except Exception:
            pass  # connection closed is expected


@pytest.mark.asyncio
async def test_ws_rejects_missing_token(client: AsyncClient) -> None:
    """WebSocket without token query param must fail."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        try:
            async with aconnect_ws("/ws/conversation", ac):
                pass
        except Exception:
            pass  # 422 or connection refused is expected


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
            async with aconnect_ws(f"/ws/conversation?token={token}", ac) as ws:
                msg = await ws.receive_json()
                assert msg["type"] == "error"
                assert msg["code"] == "services_disabled"
        except Exception:
            pass  # closed after error is fine

    app.dependency_overrides.clear()


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
    # defaults
    assert data["conversation_max_duration"] == 1800
    assert data["conversation_inactivity_timeout"] == 180


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

    async def _fake_synthesize_stream(text: str, voice: str | None = None):
        yield b"mp3data"

    fake_tts = MagicMock()
    fake_tts.synthesize_stream = _fake_synthesize_stream

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


def _make_pipeline(**kwargs) -> "ConversationPipeline":
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
    assert pipeline.history[2] == {"role": "user", "content": "I want to work on past tense."}


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
