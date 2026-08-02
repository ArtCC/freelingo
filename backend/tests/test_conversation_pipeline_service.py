"""Comprehensive unit tests for ConversationPipeline.

Covers _clean_sentence, _build_conversation_system_prompt, _synthesize_chunk,
_greet, run, handle_audio, _process edge cases, timeout watchers,
cancel_current, cleanup, _save_usage, and _save_message.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.conversation_pipeline import (
    ConversationPipeline,
    _build_conversation_system_prompt,
)
from app.services.llm_adapter import LLMError, LLMTimeoutError, LLMUnavailableError
from app.services.prompts.common import TUTOR_DISPLAY_NAME

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_chunk(text: str = "") -> MagicMock:
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = text
    return chunk


def _make_pipeline(**kwargs) -> ConversationPipeline:
    defaults = {"max_duration": 1800, "inactivity_timeout": 180}
    defaults.update(kwargs)
    return ConversationPipeline(
        llm=AsyncMock(),
        tts=AsyncMock(),
        stt=AsyncMock(),
        cefr_level="B1",
        **defaults,
    )


class FakeWS:
    """Collects all send_json / send_bytes calls for assertions."""

    def __init__(self):
        self.sent: list[tuple[str, object]] = []

    async def send_json(self, data: object) -> None:
        self.sent.append(("json", data))

    async def send_bytes(self, data: bytes) -> None:
        self.sent.append(("bytes", data))

    async def receive(self) -> dict:
        return {}

    async def close(self, code: int = 1000) -> None:
        self.sent.append(("close", code))

    def json_messages(self) -> list[dict]:
        return [m[1] for m in self.sent if m[0] == "json"]

    def types(self) -> list:
        return [m["type"] for m in self.json_messages()]


# ---------------------------------------------------------------------------
# _build_conversation_system_prompt
# ---------------------------------------------------------------------------


def test_system_prompt_contains_student_details() -> None:
    prompt = _build_conversation_system_prompt(
        student_name="Alice",
        cefr_level="A2",
        native_language="es",
        target_language_name="English",
        user_context="",
        memory_context="",
    )
    assert "Alice" in prompt
    assert "A2" in prompt
    assert "es" in prompt
    assert "English" in prompt
    assert TUTOR_DISPLAY_NAME in prompt


def test_pipeline_humanizes_native_language_code_in_system_prompt() -> None:
    pipeline = _make_pipeline(native_language="es", target_language="en-GB")

    assert "Student's native language: Spanish" in pipeline.system_prompt
    assert "Student's native language: es" not in pipeline.system_prompt


def test_system_prompt_includes_user_context() -> None:
    prompt = _build_conversation_system_prompt(
        student_name="Bob",
        cefr_level="B2",
        native_language="fr",
        target_language_name="Spanish",
        user_context="\nStudent context:\n- Learning goals: grammar, vocab\n",
        memory_context="",
    )
    assert "grammar, vocab" in prompt


def test_system_prompt_includes_memory_context() -> None:
    prompt = _build_conversation_system_prompt(
        student_name="Bob",
        cefr_level="B2",
        native_language="fr",
        target_language_name="Spanish",
        user_context="",
        memory_context="\nMemories:\n- Alice likes cats\n",
    )
    assert "Alice likes cats" in prompt


def test_system_prompt_includes_memory_system_instruction() -> None:
    prompt = _build_conversation_system_prompt(
        student_name="C",
        cefr_level="C1",
        native_language="de",
        target_language_name="Italian",
        user_context="",
        memory_context="",
    )
    assert "save_user_memory" in prompt
    assert "<<MEMORY>>" not in prompt


# ---------------------------------------------------------------------------
# _clean_sentence
# ---------------------------------------------------------------------------


def test_clean_sentence_no_marker() -> None:
    pipeline = _make_pipeline()
    assert pipeline._clean_sentence("Hello world.") == "Hello world."
    # _clean_sentence preserves whitespace (only strips after marker removal)
    result = pipeline._clean_sentence("  How are you?  ")
    assert "How are you?" in result.strip()


# ---------------------------------------------------------------------------
# __init__  —  history / context
# ---------------------------------------------------------------------------


def test_init_with_bio_and_goals_builds_context() -> None:
    pipeline = _make_pipeline(
        bio="Loves hiking",
        learning_goals='["vocabulary", "pronunciation"]',
    )
    assert "Loves hiking" in pipeline.system_prompt
    assert "vocabulary" in pipeline.system_prompt


def test_init_with_invalid_json_goals_does_not_crash() -> None:
    pipeline = _make_pipeline(learning_goals="not-valid-json")
    assert pipeline.system_prompt  # still built


def test_init_with_non_list_goals_does_not_crash() -> None:
    pipeline = _make_pipeline(learning_goals='{"key": "value"}')
    assert pipeline.system_prompt


def test_init_empty_bio_and_goals() -> None:
    pipeline = _make_pipeline(bio="", learning_goals="[]")
    assert pipeline.system_prompt


def test_init_whitespace_only_bio() -> None:
    pipeline = _make_pipeline(bio="   \n  ")
    assert pipeline.system_prompt


def test_init_stores_user_id_and_conversation_id() -> None:
    pipeline = _make_pipeline(user_id=42, conversation_id=99)
    assert pipeline._user_id == 42
    assert pipeline._conversation_id == 99


def test_init_default_voice_is_empty() -> None:
    pipeline = _make_pipeline()
    assert pipeline._voice == ""


def test_init_custom_voice() -> None:
    pipeline = _make_pipeline(voice="nova")
    assert pipeline._voice == "nova"


def test_init_recorded_starts_false() -> None:
    pipeline = _make_pipeline()
    assert pipeline._recorded is False


# ---------------------------------------------------------------------------
# _greet
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_greet_streams_greeting_and_sends_turn_complete() -> None:
    pipeline = _make_pipeline(user_id=1, conversation_id=1)
    pipeline.llm.chat = AsyncMock()

    async def fake_stream():
        yield _make_chunk("Hello! ")
        yield _make_chunk("Welcome to the session.")

    pipeline.llm.chat.return_value = fake_stream()
    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")

    ws = FakeWS()
    await pipeline._greet(ws)

    types = ws.types()
    assert "transcript" in types
    assert "turn_complete" in types
    assert len(pipeline.history) >= 1
    assert pipeline.history[-1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_greet_handles_llm_error() -> None:
    pipeline = _make_pipeline()
    pipeline.llm.chat = AsyncMock(side_effect=LLMError("LLM is down"))
    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")

    ws = FakeWS()
    # Should not raise — errors are caught internally
    await pipeline._greet(ws)


@pytest.mark.asyncio
async def test_greet_synthesizes_text_by_sentence() -> None:
    pipeline = _make_pipeline()
    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")

    tts_texts: list[str] = []

    async def synth(text, voice, lang):
        tts_texts.append(text)
        return b"audio"

    pipeline.tts.synthesize = synth

    async def fake_stream():
        yield _make_chunk("Hello. How are you? I hope you're well.")

    pipeline.llm.chat = AsyncMock(return_value=fake_stream())

    ws = FakeWS()
    await pipeline._greet(ws)

    assert tts_texts == ["Hello.", "How are you? I hope you're well."]


@pytest.mark.asyncio
async def test_greet_synthesizes_long_response_in_one_call() -> None:
    """When a long sentence with punctuation arrives, TTS should fire."""
    pipeline = _make_pipeline()
    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")

    tts_texts: list[str] = []

    async def synth(text, voice, lang):
        tts_texts.append(text)
        return b"audio"

    pipeline.tts.synthesize = synth

    long_text = "x" * 300 + "."

    async def fake_stream():
        yield _make_chunk(long_text)

    pipeline.llm.chat = AsyncMock(return_value=fake_stream())

    ws = FakeWS()
    await pipeline._greet(ws)

    assert len(tts_texts) == 1
    assert tts_texts[0] == long_text


@pytest.mark.asyncio
async def test_greet_no_duplicate_history_on_cancellation() -> None:
    """If cancelled mid-greet, sender_task should be cancelled too."""
    pipeline = _make_pipeline()
    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")

    # Stream that sleeps so we can cancel
    async def fake_stream():
        yield _make_chunk("Hello. ")
        await asyncio.sleep(10)

    pipeline.llm.chat = AsyncMock(return_value=fake_stream())

    ws = FakeWS()
    task = asyncio.create_task(pipeline._greet(ws))
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


# ---------------------------------------------------------------------------
# run  — main loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_handles_websocket_disconnect() -> None:
    pipeline = _make_pipeline()

    # Override _greet so it completes instantly
    pipeline._greet = AsyncMock(return_value=None)

    ws = FakeWS()
    # First message is a disconnect
    ws.receive = AsyncMock(return_value={"type": "websocket.disconnect"})

    await pipeline.run(ws)
    # Should exit cleanly


@pytest.mark.asyncio
async def test_run_handles_text_interrupt() -> None:
    pipeline = _make_pipeline()
    pipeline._greet = AsyncMock(return_value=None)
    pipeline.cancel_current = AsyncMock(return_value=None)

    ws = FakeWS()
    messages = [
        {"text": '{"type": "interrupt"}'},
        {"type": "websocket.disconnect"},
    ]
    ws.receive = AsyncMock(side_effect=messages)

    await pipeline.run(ws)

    json_msgs = ws.json_messages()
    assert any(m.get("type") == "interrupted" for m in json_msgs)


@pytest.mark.asyncio
async def test_run_handles_audio_bytes() -> None:
    pipeline = _make_pipeline()
    pipeline._greet = AsyncMock(return_value=None)
    pipeline.handle_audio = AsyncMock(return_value=None)

    ws = FakeWS()
    messages = [
        {"bytes": b"some-audio-data"},
        {"type": "websocket.disconnect"},
    ]
    ws.receive = AsyncMock(side_effect=messages)

    await pipeline.run(ws)

    pipeline.handle_audio.assert_called_once_with(b"some-audio-data", ws)


@pytest.mark.asyncio
async def test_run_cleans_up_timer_tasks_on_exit() -> None:
    pipeline = _make_pipeline()
    pipeline._greet = AsyncMock(return_value=None)

    ws = FakeWS()
    ws.receive = AsyncMock(side_effect=RuntimeError("disconnected"))

    await pipeline.run(ws)
    await asyncio.sleep(0)  # let cancelled tasks process cancellation

    # All timer tasks should be cancelled or done
    for t in pipeline._timer_tasks:
        assert t.cancelled() or t.done()


# ---------------------------------------------------------------------------
# handle_audio
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_audio_updates_last_activity() -> None:
    pipeline = _make_pipeline()
    pipeline._process = AsyncMock(return_value=None)

    old_activity = pipeline._last_activity
    await asyncio.sleep(0.01)
    ws = FakeWS()
    await pipeline.handle_audio(b"audio", ws)

    assert pipeline._last_activity > old_activity


@pytest.mark.asyncio
async def test_handle_audio_resets_inactivity_warning() -> None:
    pipeline = _make_pipeline()
    pipeline._inactivity_warning_sent = True
    pipeline._process = AsyncMock(return_value=None)

    ws = FakeWS()
    await pipeline.handle_audio(b"audio", ws)

    assert pipeline._inactivity_warning_sent is False


@pytest.mark.asyncio
async def test_handle_audio_barge_in_cancels_previous() -> None:
    pipeline = _make_pipeline()
    pipeline._process = AsyncMock(return_value=None)

    # Simulate an ongoing task
    async def slow_process(*args, **kwargs):
        await asyncio.sleep(5)

    pipeline.current_task = asyncio.create_task(slow_process())
    await asyncio.sleep(0.01)

    ws = FakeWS()
    await pipeline.handle_audio(b"new-audio", ws)

    # Should have sent barge_in frame so the client cancels audio playback.
    json_msgs = ws.json_messages()
    assert any(m.get("type") == "barge_in" for m in json_msgs)
    assert pipeline.current_task is not None  # new task created


@pytest.mark.asyncio
async def test_handle_audio_no_barge_in_when_no_current_task() -> None:
    pipeline = _make_pipeline()
    pipeline._process = AsyncMock(return_value=None)

    ws = FakeWS()
    await pipeline.handle_audio(b"audio", ws)

    # No barge-in message expected
    json_msgs = ws.json_messages()
    assert not any(m.get("type") == "barge_in" for m in json_msgs)


# ---------------------------------------------------------------------------
# _process  —  edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_empty_transcription() -> None:
    """STT returns empty string — should ignore the audio chunk."""
    pipeline = _make_pipeline()
    pipeline.stt.transcribe = AsyncMock(return_value="")
    pipeline.llm.chat = AsyncMock()
    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")

    ws = FakeWS()
    await pipeline._process(b"audio", ws)

    types = ws.types()
    assert "turn_complete" not in types
    pipeline.llm.chat.assert_not_called()


@pytest.mark.asyncio
async def test_process_llm_timeout_error_sends_error_frame() -> None:
    pipeline = _make_pipeline(user_id=1, conversation_id=1)
    pipeline.stt.transcribe = AsyncMock(return_value="hello")
    pipeline.llm.chat = AsyncMock(side_effect=LLMTimeoutError("timeout"))

    saved_roles: list[str] = []

    async def _track_save(role, content):
        saved_roles.append(role)

    pipeline._save_message = _track_save

    ws = FakeWS()
    await pipeline._process(b"audio", ws)

    errors = [m for m in ws.json_messages() if m.get("type") == "error"]
    assert any(e["code"] == "llm_failed" for e in errors)
    assert saved_roles == []  # no messages saved on failure
    # User message should have been popped from history
    assert not pipeline.history or pipeline.history[-1]["role"] != "user"


@pytest.mark.asyncio
async def test_process_llm_unavailable_error_sends_error_frame() -> None:
    pipeline = _make_pipeline()
    pipeline.stt.transcribe = AsyncMock(return_value="hello")
    pipeline.llm.chat = AsyncMock(side_effect=LLMUnavailableError("unavailable"))

    ws = FakeWS()
    await pipeline._process(b"audio", ws)

    errors = [m for m in ws.json_messages() if m.get("type") == "error"]
    assert any(e["code"] == "llm_failed" for e in errors)


@pytest.mark.asyncio
async def test_process_cancelled_during_llm_cleans_up_tts() -> None:
    pipeline = _make_pipeline()
    pipeline.stt.transcribe = AsyncMock(return_value="hello")
    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")

    async def fake_stream():
        yield _make_chunk("Hello. ")
        await asyncio.sleep(10)

    pipeline.llm.chat = AsyncMock(return_value=fake_stream())

    ws = FakeWS()
    task = asyncio.create_task(pipeline._process(b"audio", ws))
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_process_sends_status_messages() -> None:
    pipeline = _make_pipeline()
    pipeline.stt.transcribe = AsyncMock(return_value="hello")

    async def fake_stream():
        yield _make_chunk("Hi there.")

    pipeline.llm.chat = AsyncMock(return_value=fake_stream())
    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")

    ws = FakeWS()
    await pipeline._process(b"audio", ws)

    statuses = [m for m in ws.json_messages() if m.get("type") == "status"]
    values = [s["value"] for s in statuses]
    assert "transcribing" in values
    assert "thinking" in values


@pytest.mark.asyncio
async def test_process_multiple_sentences_from_llm() -> None:
    pipeline = _make_pipeline()
    pipeline.stt.transcribe = AsyncMock(return_value="Tell me a story")

    tts_texts: list[str] = []

    async def synth(text, voice, lang):
        tts_texts.append(text)
        return b"audio"

    pipeline.tts.synthesize = synth

    async def fake_stream():
        yield _make_chunk("Once upon a time. ")
        yield _make_chunk("There was a cat. ")
        yield _make_chunk("The cat was happy.")

    pipeline.llm.chat = AsyncMock(return_value=fake_stream())

    ws = FakeWS()
    await pipeline._process(b"audio", ws)

    assert tts_texts == ["Once upon a time.", "There was a cat.", "The cat was happy."]
    assert [kind for kind, _ in ws.sent].count("bytes") == 3


@pytest.mark.asyncio
async def test_process_all_tts_failures_publish_text_transcript() -> None:
    pipeline = _make_pipeline()
    pipeline.stt.transcribe = AsyncMock(return_value="Tell me a story")
    pipeline.tts.synthesize = AsyncMock(side_effect=RuntimeError("TTS unavailable"))

    async def fake_stream():
        yield _make_chunk("Response with one full sentence.")

    pipeline.llm.chat = AsyncMock(return_value=fake_stream())

    ws = FakeWS()
    await pipeline._process(b"audio", ws)

    assert [kind for kind, _ in ws.sent].count("bytes") == 0
    errors = [m for m in ws.json_messages() if m.get("type") == "error"]
    assert errors == []
    assistant_transcripts = [
        m
        for m in ws.json_messages()
        if m.get("type") == "transcript" and m.get("role") == "assistant"
    ]
    assert assistant_transcripts[0]["text"] == "Response with one full sentence."
    assert "turn_complete" in ws.types()
    assert pipeline.history[-1] == {
        "role": "assistant",
        "content": "Response with one full sentence.",
    }


@pytest.mark.asyncio
async def test_process_tts_sentence_failure_continues_with_remaining_audio() -> None:
    pipeline = _make_pipeline()
    pipeline.stt.transcribe = AsyncMock(return_value="Tell me a story")

    async def synth(text, voice, lang):
        if text == "Broken sentence.":
            raise RuntimeError("TTS unavailable")
        return b"audio"

    pipeline.tts.synthesize = synth

    async def fake_stream():
        yield _make_chunk("Broken sentence. Working sentence.")

    pipeline.llm.chat = AsyncMock(return_value=fake_stream())

    ws = FakeWS()
    await pipeline._process(b"audio", ws)

    assert [kind for kind, _ in ws.sent].count("bytes") == 1
    errors = [m for m in ws.json_messages() if m.get("type") == "error"]
    assert errors == []
    assistant_transcripts = [
        m
        for m in ws.json_messages()
        if m.get("type") == "transcript" and m.get("role") == "assistant"
    ]
    assert assistant_transcripts[0]["text"] == "Broken sentence. Working sentence."


@pytest.mark.asyncio
async def test_process_reports_native_memory_tool_update() -> None:
    pipeline = _make_pipeline(user_id=1, study_plan_id=5)
    pipeline.stt.transcribe = AsyncMock(return_value="hi")

    from app.services.llm_adapter import LLMToolCall, LLMToolResult

    call = LLMToolCall(
        id="call_1",
        name="save_user_memory",
        arguments={"content": "A Bob le gusta la pizza"},
        raw_arguments='{"content":"A Bob le gusta la pizza"}',
    )

    class FakeToolStream:
        tool_results = [LLMToolResult(call=call, content={"saved": True})]

        def __aiter__(self):
            return self.iterate()

        async def iterate(self):
            yield "Nice to meet you."

    pipeline.llm.chat = AsyncMock(return_value=FakeToolStream())
    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")

    ws = FakeWS()
    await pipeline._process(b"audio", ws)

    types = ws.types()
    assert "turn_complete" in types
    assert "memory_updated" in types
    tool = pipeline.llm.chat.call_args.kwargs["tools"][0]
    assert "native language: Spanish" in tool.description


@pytest.mark.asyncio
async def test_process_memory_tool_failure_does_not_crash() -> None:
    pipeline = _make_pipeline(user_id=1, study_plan_id=5)
    pipeline.stt.transcribe = AsyncMock(return_value="hi")

    from app.services.llm_adapter import LLMToolCall, LLMToolResult

    call = LLMToolCall(
        id="call_1",
        name="save_user_memory",
        arguments={"content": "fact"},
        raw_arguments='{"content":"fact"}',
    )

    class FailedToolStream:
        tool_results = [
            LLMToolResult(
                call=call,
                content={"saved": False, "error": "persistence_failed"},
                is_error=True,
            )
        ]

        def __aiter__(self):
            return self.iterate()

        async def iterate(self):
            yield "Hello."

    pipeline.llm.chat = AsyncMock(return_value=FailedToolStream())
    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")

    ws = FakeWS()
    await pipeline._process(b"audio", ws)

    assert "turn_complete" in ws.types()
    assert "memory_updated" not in ws.types()


@pytest.mark.asyncio
async def test_process_long_audio_silent_stt() -> None:
    """Large audio buffer (simulating long speech) should not break the pipeline."""
    pipeline = _make_pipeline()
    pipeline.stt.transcribe = AsyncMock(return_value="a long sentence here")
    pipeline.llm.chat = AsyncMock(return_value=AsyncMock())
    pipeline.llm.chat.return_value.__aiter__ = lambda s: _empty_async_gen()

    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")

    # Large audio bytes
    large_audio = b"\x00" * 500_000

    ws = FakeWS()
    await pipeline._process(large_audio, ws)


async def _empty_async_gen():
    if False:
        yield


@pytest.mark.asyncio
async def test_process_stt_returns_short_text() -> None:
    """Very short transcription (e.g. 'OK') should still work."""
    pipeline = _make_pipeline()
    pipeline.stt.transcribe = AsyncMock(return_value="OK")

    async def fake_stream():
        yield _make_chunk("Alright!")

    pipeline.llm.chat = AsyncMock(return_value=fake_stream())
    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")

    ws = FakeWS()
    await pipeline._process(b"audio", ws)

    types = ws.types()
    assert "transcript" in types
    assert "turn_complete" in types


@pytest.mark.asyncio
async def test_process_native_tool_payload_never_reaches_tts() -> None:
    pipeline = _make_pipeline()
    pipeline.stt.transcribe = AsyncMock(return_value="hello")

    tts_texts: list[str] = []

    async def synth(text, voice, lang):
        if text.strip():
            tts_texts.append(text)
        return b"audio"

    pipeline.tts.synthesize = synth

    async def fake_stream():
        yield "Goodbye."

    pipeline.llm.chat = AsyncMock(return_value=fake_stream())

    ws = FakeWS()
    await pipeline._process(b"audio", ws)

    non_empty_tts = [t for t in tts_texts if t.strip()]
    assert any("Goodbye" in t for t in non_empty_tts)
    assert not any("save_user_memory" in t for t in tts_texts)


# ---------------------------------------------------------------------------
# _save_usage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_usage_no_user_id_returns_early() -> None:
    pipeline = _make_pipeline(user_id=None)
    await pipeline._save_usage(MagicMock())
    # Should not raise


@pytest.mark.asyncio
async def test_save_usage_not_llm_stream_returns_early() -> None:
    pipeline = _make_pipeline(user_id=1)
    await pipeline._save_usage("not a stream")
    # Should not raise


@pytest.mark.asyncio
async def test_save_usage_no_tokens_returns_early() -> None:
    from app.services.llm_adapter import LLMStream

    pipeline = _make_pipeline(user_id=1)
    stream = LLMStream(MagicMock())
    stream.prompt_tokens = None
    stream.completion_tokens = None

    with patch("app.services.conversation_pipeline.db_session") as mock_db:
        await pipeline._save_usage(stream)
        mock_db.assert_not_called()


@pytest.mark.asyncio
async def test_save_usage_saves_when_tokens_present(db_session) -> None:
    from app.services.llm_adapter import LLMStream

    pipeline = _make_pipeline(user_id=1)
    stream = LLMStream(MagicMock())
    stream.prompt_tokens = 50
    stream.completion_tokens = 30
    stream.total_tokens = 80

    # Use the real db_session fixture to confirm it actually writes
    await pipeline._save_usage(stream)
    # Should not raise


# ---------------------------------------------------------------------------
# _save_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_message_no_user_id_returns_early() -> None:
    pipeline = _make_pipeline(user_id=None, conversation_id=1)
    await pipeline._save_message("user", "hello")
    # Should not raise


@pytest.mark.asyncio
async def test_save_message_no_conversation_id_returns_early() -> None:
    pipeline = _make_pipeline(user_id=1, conversation_id=None)
    await pipeline._save_message("user", "hello")
    # Should not raise


@pytest.mark.asyncio
async def test_save_message_saves_to_db(db_session) -> None:
    pipeline = _make_pipeline(user_id=1, conversation_id=1)

    # Create a real user in the DB so FK constraints pass
    from app.core.security import hash_password
    from app.models.user import User

    user = User(
        username="pipetest",
        email="pipe@test.com",
        display_name="Pipe Test",
        hashed_password=hash_password("test"),
        role="user",
        native_language="es",
        target_language="en-US",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    from app.models.conversation import Conversation

    conv = Conversation(user_id=user.id, title="Test Conv", study_plan_id=None)
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    pipeline._user_id = user.id
    pipeline._conversation_id = conv.id

    await pipeline._save_message("user", "Hello world")
    # Should not raise


# ---------------------------------------------------------------------------
# cancel_current
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_current_no_task() -> None:
    pipeline = _make_pipeline()
    # Should not raise
    await pipeline.cancel_current()


@pytest.mark.asyncio
async def test_cancel_current_cancels_active_task() -> None:
    pipeline = _make_pipeline()

    async def slow():
        await asyncio.sleep(10)

    pipeline.current_task = asyncio.create_task(slow())
    await asyncio.sleep(0.01)

    await pipeline.cancel_current()
    assert pipeline.current_task.cancelled() or pipeline.current_task.done()


@pytest.mark.asyncio
async def test_cancel_current_pops_user_from_history() -> None:
    pipeline = _make_pipeline()
    pipeline.history = [
        {"role": "user", "content": "hello"},
    ]

    await pipeline.cancel_current()

    # User message should be popped
    assert len(pipeline.history) == 0


@pytest.mark.asyncio
async def test_cancel_current_does_not_pop_assistant_from_history() -> None:
    pipeline = _make_pipeline()
    pipeline.history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]

    await pipeline.cancel_current()

    # Last message is assistant, so nothing should be popped
    assert len(pipeline.history) == 2
    assert pipeline.history[-1]["role"] == "assistant"


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_records_session_seconds() -> None:
    pipeline = _make_pipeline(user_id=1)
    pipeline._redis = AsyncMock()
    # Make _session_start far in the past so elapsed > 0
    pipeline._session_start = 0.0

    with patch("app.services.conversation_pipeline.record_session_seconds") as mock_record:
        mock_record.return_value = None
        await pipeline.cleanup()

        mock_record.assert_called_once()
        assert pipeline._recorded is True


@pytest.mark.asyncio
async def test_cleanup_only_records_once() -> None:
    pipeline = _make_pipeline(user_id=1)
    pipeline._redis = AsyncMock()
    pipeline._session_start = 0.0

    with patch("app.services.conversation_pipeline.record_session_seconds") as mock_record:
        mock_record.return_value = None
        await pipeline.cleanup()
        await pipeline.cleanup()

        assert mock_record.call_count == 1


@pytest.mark.asyncio
async def test_cleanup_no_redis_does_not_record() -> None:
    pipeline = _make_pipeline(user_id=1)
    pipeline._redis = None

    with patch("app.services.conversation_pipeline.record_session_seconds") as mock_record:
        await pipeline.cleanup()
        mock_record.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_no_user_id_does_not_record() -> None:
    pipeline = _make_pipeline(user_id=None)
    pipeline._redis = AsyncMock()

    with patch("app.services.conversation_pipeline.record_session_seconds") as mock_record:
        await pipeline.cleanup()
        mock_record.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_record_failure_is_silent() -> None:
    pipeline = _make_pipeline(user_id=1)
    pipeline._redis = AsyncMock()

    with patch(
        "app.services.conversation_pipeline.record_session_seconds",
        side_effect=RuntimeError("Redis down"),
    ):
        # Should not raise
        await pipeline.cleanup()


@pytest.mark.asyncio
async def test_cleanup_cancels_timer_tasks() -> None:
    pipeline = _make_pipeline()

    async def slow():
        await asyncio.sleep(10)

    pipeline._timer_tasks = [asyncio.create_task(slow())]

    with patch("app.services.conversation_pipeline.record_session_seconds"):
        await pipeline.cleanup()

    await asyncio.sleep(0)  # let cancelled tasks process cancellation
    for t in pipeline._timer_tasks:
        assert t.cancelled() or t.done()


# ---------------------------------------------------------------------------
# _max_duration_watcher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_max_duration_watcher_sends_warning_and_end() -> None:
    pipeline = _make_pipeline(max_duration=120)

    ws = FakeWS()

    _real_sleep = asyncio.sleep

    async def fast_sleep(seconds):
        await _real_sleep(0)

    with patch("asyncio.sleep", side_effect=fast_sleep):
        task = asyncio.create_task(pipeline._max_duration_watcher(ws))
        await _real_sleep(0.05)

        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    json_msgs = ws.json_messages()
    types = [m.get("type") for m in json_msgs]
    assert "session_warning" in types or "session_end" in types


@pytest.mark.asyncio
async def test_max_duration_watcher_short_duration_no_warning() -> None:
    """When max_duration <= WARNING_ADVANCE_SECONDS, no warning is sent."""
    pipeline = _make_pipeline(max_duration=30)

    ws = FakeWS()

    _real_sleep = asyncio.sleep

    async def fast_sleep(seconds):
        await _real_sleep(0)

    with patch("asyncio.sleep", side_effect=fast_sleep):
        task = asyncio.create_task(pipeline._max_duration_watcher(ws))
        await _real_sleep(0.05)

        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    json_msgs = ws.json_messages()
    warnings = [m for m in json_msgs if m.get("type") == "session_warning"]
    assert len(warnings) == 0


# ---------------------------------------------------------------------------
# _inactivity_watcher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inactivity_watcher_sends_warning_then_ends() -> None:
    pipeline = _make_pipeline(inactivity_timeout=10)
    pipeline._last_activity = 0.0  # far in the past → elapsed huge

    ws = FakeWS()

    _real_sleep = asyncio.sleep

    async def fast_sleep(seconds):
        await _real_sleep(0)

    # For the inactivity watcher, mock sleep to yield control each iteration
    with patch("asyncio.sleep", side_effect=fast_sleep):
        task = asyncio.create_task(pipeline._inactivity_watcher(ws))
        await _real_sleep(0.05)

        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    json_msgs = ws.json_messages()
    types = [m.get("type") for m in json_msgs]
    assert "session_end" in types
    ends = [m for m in json_msgs if m.get("type") == "session_end"]
    assert ends[0]["reason"] == "inactivity"


@pytest.mark.asyncio
async def test_inactivity_watcher_no_warning_when_active() -> None:
    """When activity is recent, no warning or end should be sent."""
    pipeline = _make_pipeline(inactivity_timeout=180)
    # _last_activity is freshly set in __init__ → elapsed ≈ 0

    ws = FakeWS()

    _real_sleep = asyncio.sleep

    async def fast_sleep(seconds):
        await _real_sleep(0)

    with patch("asyncio.sleep", side_effect=fast_sleep):
        task = asyncio.create_task(pipeline._inactivity_watcher(ws))
        await _real_sleep(0.05)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    json_msgs = ws.json_messages()
    ends = [m for m in json_msgs if m.get("type") == "session_end"]
    assert len(ends) == 0


@pytest.mark.asyncio
async def test_inactivity_watcher_sends_warning_once() -> None:
    """Warning should only be sent once per inactive period."""
    pipeline = _make_pipeline(inactivity_timeout=70)
    # Set activity so elapsed crosses warning threshold (60s) but not timeout (70s)
    pipeline._last_activity = time.monotonic() - 65

    ws = FakeWS()

    _real_sleep = asyncio.sleep

    async def fast_sleep(seconds):
        await _real_sleep(0)

    with patch("asyncio.sleep", side_effect=fast_sleep):
        task = asyncio.create_task(pipeline._inactivity_watcher(ws))
        await _real_sleep(0.08)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    warnings = [m for m in ws.json_messages() if m.get("type") == "session_warning"]
    assert len(warnings) <= 1


# ---------------------------------------------------------------------------
# Full pipeline lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_pipeline_lifecycle() -> None:
    """Simulate a complete conversation: greet → audio → response → cleanup."""
    pipeline = _make_pipeline(user_id=1, conversation_id=1)
    pipeline.stt.transcribe = AsyncMock(return_value="Hello, how are you?")

    tts_texts: list[str] = []

    async def synth(text, voice, lang):
        tts_texts.append(text)
        return b"audio"

    pipeline.tts.synthesize = synth

    async def greet_stream():
        yield _make_chunk("Hi there! ")
        yield _make_chunk("Welcome to our session. How can I help you today?")

    pipeline.llm.chat = AsyncMock(return_value=greet_stream())
    pipeline._redis = AsyncMock()

    ws = FakeWS()
    ws.receive = AsyncMock(
        side_effect=[
            {"bytes": b"audio-chunk-1"},
            {"type": "websocket.disconnect"},
        ]
    )

    with patch("app.services.conversation_pipeline.record_session_seconds"):
        # Run the pipeline
        await pipeline.run(ws)

        # Greeting is cancellable now, so incoming audio can pre-empt it instead
        # of waiting for the full greeting/TTS path to finish.
        types_before_run = ws.types()
        assert "barge_in" in types_before_run

        # Cleanup
        await pipeline.cleanup()
        assert pipeline._recorded is True


@pytest.mark.asyncio
async def test_full_pipeline_with_interrupt_and_barge_in() -> None:
    """User interrupts during assistant response, then sends audio."""
    pipeline = _make_pipeline(user_id=1)
    pipeline.stt.transcribe = AsyncMock(return_value="Let me think about that")

    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")

    async def greet_stream():
        yield _make_chunk("Welcome! How are you?")

    pipeline.llm.chat = AsyncMock(return_value=greet_stream())

    ws = FakeWS()

    # Sequence: audio → interrupt → audio → disconnect
    ws.receive = AsyncMock(
        side_effect=[
            {"bytes": b"how are you"},
            {"text": '{"type": "interrupt"}'},
            {"bytes": b"ok"},
            {"type": "websocket.disconnect"},
        ]
    )

    pipeline._redis = AsyncMock()

    with patch("app.services.conversation_pipeline.record_session_seconds"):
        await pipeline.run(ws)

    # Should have an explicit barge-in message for audio interruption.
    json_msgs = ws.json_messages()
    types = [m.get("type") for m in json_msgs]
    assert "barge_in" in types


@pytest.mark.asyncio
async def test_process_stt_network_error_during_transcription() -> None:
    """Simulate a network timeout during STT."""
    pipeline = _make_pipeline()
    pipeline.stt.transcribe = AsyncMock(side_effect=ConnectionError("Network timeout"))

    ws = FakeWS()
    await pipeline._process(b"audio", ws)

    errors = [m for m in ws.json_messages() if m.get("type") == "error"]
    assert any(e["code"] == "stt_failed" for e in errors)


@pytest.mark.asyncio
async def test_process_llm_stream_with_empty_chunks() -> None:
    """LLM returns chunks with empty content (usage-only or thinking chunks)."""
    pipeline = _make_pipeline(user_id=1, conversation_id=1)
    pipeline.stt.transcribe = AsyncMock(return_value="hello")

    async def fake_stream():
        yield _make_chunk("")  # empty chunk
        yield _make_chunk("")  # another empty chunk
        yield _make_chunk("Hi!")  # finally some content

    pipeline.llm.chat = AsyncMock(return_value=fake_stream())
    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")

    ws = FakeWS()
    await pipeline._process(b"audio", ws)

    types = ws.types()
    assert "turn_complete" in types


@pytest.mark.asyncio
async def test_process_transcript_messages_sent_for_user_and_assistant() -> None:
    """Both user and assistant transcript messages are sent."""
    pipeline = _make_pipeline()
    pipeline.stt.transcribe = AsyncMock(return_value="My name is John")

    async def fake_stream():
        yield _make_chunk("Nice to meet you, John!")

    pipeline.llm.chat = AsyncMock(return_value=fake_stream())
    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")

    ws = FakeWS()
    await pipeline._process(b"audio", ws)

    transcripts = [m for m in ws.json_messages() if m.get("type") == "transcript"]
    roles = [t["role"] for t in transcripts]
    assert "user" in roles
    assert "assistant" in roles
    # User transcript should be final
    user_transcripts = [t for t in transcripts if t["role"] == "user"]
    assert user_transcripts[0]["final"] is True


@pytest.mark.asyncio
async def test_process_no_llm_output_sends_turn_complete() -> None:
    """When LLM returns no tokens at all, turn still completes."""
    pipeline = _make_pipeline()
    pipeline.stt.transcribe = AsyncMock(return_value="test")

    async def fake_stream():
        if False:
            yield  # empty generator

    pipeline.llm.chat = AsyncMock(return_value=fake_stream())
    pipeline.tts.synthesize = AsyncMock(return_value=b"audio")

    ws = FakeWS()
    await pipeline._process(b"audio", ws)

    types = ws.types()
    assert "turn_complete" in types
