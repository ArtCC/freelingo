"""Comprehensive unit tests for app/services/llm_adapter.py"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# parse_llm_json
# ---------------------------------------------------------------------------


class TestParseLlmJson:
    def test_clean_json(self):
        from app.services.llm_adapter import parse_llm_json

        assert parse_llm_json('{"key": "value"}') == {"key": "value"}

    def test_json_with_surrounding_whitespace(self):
        from app.services.llm_adapter import parse_llm_json

        result = parse_llm_json('\n  {"a": 1}\n')
        assert result == {"a": 1}

    def test_json_inside_code_fences(self):
        from app.services.llm_adapter import parse_llm_json

        raw = '```\n{"hello": "world"}\n```'
        assert parse_llm_json(raw) == {"hello": "world"}

    def test_json_inside_json_code_fences(self):
        from app.services.llm_adapter import parse_llm_json

        raw = '```json\n{"x": [1, 2, 3]}\n```'
        assert parse_llm_json(raw) == {"x": [1, 2, 3]}

    def test_json_with_arrays(self):
        from app.services.llm_adapter import parse_llm_json

        assert parse_llm_json('[1, "two", true]') == [1, "two", True]

    def test_json_with_nested_objects(self):
        from app.services.llm_adapter import parse_llm_json

        raw = '{"outer": {"inner": {"deep": null}}}'
        assert parse_llm_json(raw) == {"outer": {"inner": {"deep": None}}}

    def test_invalid_json_raises(self):
        from app.services.llm_adapter import parse_llm_json

        with pytest.raises(json.JSONDecodeError):
            parse_llm_json("not json at all")

    def test_empty_string_raises(self):
        from app.services.llm_adapter import parse_llm_json

        with pytest.raises(json.JSONDecodeError):
            parse_llm_json("")

    def test_malformed_fences_raises(self):
        from app.services.llm_adapter import parse_llm_json

        with pytest.raises(json.JSONDecodeError):
            parse_llm_json("```\nbad json\n```")


# ---------------------------------------------------------------------------
# LLMStream
# ---------------------------------------------------------------------------


class FakeOpenAIChunk:
    """Simulates an OpenAI-compatible streaming chunk."""

    def __init__(self, content: str | None, usage=None):
        self.choices = []
        if content is not None:
            choice = MagicMock()
            choice.delta.content = content
            self.choices = [choice]
        self.usage = usage


class FakeUsage:
    def __init__(self, prompt_tokens: int = 10, completion_tokens: int = 5):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens


class TestLLMStream:
    async def test_yields_content_chunks(self):
        from app.services.llm_adapter import LLMStream

        async def fake_stream():
            yield FakeOpenAIChunk("Hello")
            yield FakeOpenAIChunk(" world")

        wrapped = LLMStream(fake_stream())
        parts = [c async for c in wrapped]
        assert len(parts) == 2
        assert parts[0].choices[0].delta.content == "Hello"
        assert parts[1].choices[0].delta.content == " world"

    async def test_captures_usage_from_last_chunk(self):
        from app.services.llm_adapter import LLMStream

        usage_obj = FakeUsage(prompt_tokens=20, completion_tokens=8)

        async def fake_stream():
            yield FakeOpenAIChunk("a")
            yield FakeOpenAIChunk("b", usage=usage_obj)

        wrapped = LLMStream(fake_stream())
        _ = [c async for c in wrapped]
        assert wrapped.prompt_tokens == 20
        assert wrapped.completion_tokens == 8
        assert wrapped.total_tokens == 28

    async def test_computes_total_tokens_when_not_provided(self):
        from app.services.llm_adapter import LLMStream

        class PartialUsage:
            prompt_tokens = 5
            completion_tokens = 3
            total_tokens = None

        async def fake_stream():
            yield FakeOpenAIChunk("x", usage=PartialUsage)

        wrapped = LLMStream(fake_stream())
        _ = [c async for c in wrapped]
        assert wrapped.total_tokens == 8  # 5 + 3

    async def test_skips_usage_only_chunks(self):
        from app.services.llm_adapter import LLMStream

        usage_obj = FakeUsage()

        async def fake_stream():
            yield FakeOpenAIChunk("hello")
            yield FakeOpenAIChunk(None, usage=usage_obj)  # usage-only
            yield FakeOpenAIChunk(" world")

        wrapped = LLMStream(fake_stream())
        parts = [c async for c in wrapped]
        assert len(parts) == 2
        contents = [c.choices[0].delta.content for c in parts]
        assert contents == ["hello", " world"]

    async def test_skips_empty_choices_list(self):
        """Chunks with choices=[] (usage-only) are filtered out."""
        from app.services.llm_adapter import LLMStream

        usage_obj = FakeUsage()

        async def fake_stream():
            yield FakeOpenAIChunk("keep")
            yield FakeOpenAIChunk(None, usage=usage_obj)  # choices=[] from constructor
            yield FakeOpenAIChunk(" this")

        wrapped = LLMStream(fake_stream())
        parts = [c async for c in wrapped]
        assert len(parts) == 2

    async def test_passes_through_chunks_without_choices_attr(self):
        """Chunks without a 'choices' attribute (e.g. Anthropic events) pass through."""
        from app.services.llm_adapter import LLMStream

        class AnthropicStyleChunk:
            pass  # no choices attribute at all

        async def fake_stream():
            yield FakeOpenAIChunk("keep")
            yield AnthropicStyleChunk()
            yield FakeOpenAIChunk(" this")

        wrapped = LLMStream(fake_stream())
        parts = [c async for c in wrapped]
        assert len(parts) == 3  # Anthropic-style chunks are yielded through

    async def test_usage_defaults_to_none(self):
        from app.services.llm_adapter import LLMStream

        async def fake_stream():
            yield FakeOpenAIChunk("hi")
            yield FakeOpenAIChunk("!")

        wrapped = LLMStream(fake_stream())
        _ = [c async for c in wrapped]
        assert wrapped.prompt_tokens is None
        assert wrapped.completion_tokens is None
        assert wrapped.total_tokens is None

    async def test_usage_exception_is_silent(self):
        from app.services.llm_adapter import LLMStream

        class ExplodingUsage:
            @property
            def prompt_tokens(self):
                raise RuntimeError("boom")

        async def fake_stream():
            yield FakeOpenAIChunk("a", usage=ExplodingUsage())
            yield FakeOpenAIChunk("b")

        wrapped = LLMStream(fake_stream())
        parts = [c async for c in wrapped]
        assert len(parts) == 2
        # usage remains None because the exception was caught
        assert wrapped.prompt_tokens is None


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------


class TestExceptions:
    def test_llm_error(self):
        from app.services.llm_adapter import LLMError

        e = LLMError("something went wrong")
        assert str(e) == "something went wrong"

    def test_llm_timeout_error(self):
        from app.services.llm_adapter import LLMError, LLMTimeoutError

        e = LLMTimeoutError("timed out")
        assert isinstance(e, LLMError)
        assert str(e) == "timed out"

    def test_llm_unavailable_error(self):
        from app.services.llm_adapter import LLMError, LLMUnavailableError

        e = LLMUnavailableError("down")
        assert isinstance(e, LLMError)
        assert str(e) == "down"

    def test_llm_response_error_with_raw(self):
        from app.services.llm_adapter import LLMError, LLMResponseError

        e = LLMResponseError("bad json", raw_response="<html>error</html>")
        assert isinstance(e, LLMError)
        assert e.raw_response == "<html>error</html>"

    def test_llm_response_error_without_raw(self):
        from app.services.llm_adapter import LLMResponseError

        e = LLMResponseError("bad json")
        assert e.raw_response is None

    def test_llm_context_overflow_error(self):
        from app.services.llm_adapter import LLMContextOverflowError, LLMError

        e = LLMContextOverflowError("too long")
        assert isinstance(e, LLMError)


# ---------------------------------------------------------------------------
# LLMAdapter — provider setup
# ---------------------------------------------------------------------------


class TestLLMAdapterInit:
    def test_ollama_provider(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.LLM_PROVIDER", "ollama")
        monkeypatch.setattr("app.core.config.settings.OLLAMA_BASE_URL", "http://localhost:11434")
        monkeypatch.setattr("app.core.config.settings.OLLAMA_MODEL", "llama3")

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        assert adapter.provider == "ollama"
        assert adapter.model == "llama3"
        assert adapter.client is not None

    def test_openai_provider(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.LLM_PROVIDER", "openai")
        monkeypatch.setattr("app.core.config.settings.OPENAI_API_KEY", "sk-test")
        monkeypatch.setattr("app.core.config.settings.OPENAI_MODEL", "gpt-4o-mini")

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        assert adapter.provider == "openai"
        assert adapter.model == "gpt-4o-mini"
        assert adapter.client is not None

    def test_deepseek_provider(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.LLM_PROVIDER", "deepseek")
        monkeypatch.setattr("app.core.config.settings.DEEPSEEK_API_KEY", "sk-ds")
        monkeypatch.setattr("app.core.config.settings.DEEPSEEK_MODEL", "deepseek-chat")

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        assert adapter.provider == "deepseek"
        assert adapter.model == "deepseek-chat"
        assert adapter.client is not None

    def test_anthropic_provider(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.LLM_PROVIDER", "anthropic")
        monkeypatch.setattr("app.core.config.settings.ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setattr("app.core.config.settings.ANTHROPIC_MODEL", "claude-3-5-haiku-latest")

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        assert adapter.provider == "anthropic"
        assert adapter.model == "claude-3-5-haiku-latest"
        assert adapter.client is None  # Anthropic uses _anthropic


# ---------------------------------------------------------------------------
# LLMAdapter.chat (non-streaming) — OpenAI-compatible providers
# ---------------------------------------------------------------------------


def _make_ollama_settings(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.LLM_PROVIDER", "ollama")
    monkeypatch.setattr("app.core.config.settings.OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setattr("app.core.config.settings.OLLAMA_MODEL", "llama3")


class TestChatNonStreaming:
    @pytest.mark.asyncio
    async def test_ollama_chat_returns_content(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        msg = MagicMock()
        msg.content = "Hello from Ollama!"
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message = msg

        adapter = LLMAdapter()
        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await adapter.chat([{"role": "user", "content": "Hi"}])
            assert result == "Hello from Ollama!"

    @pytest.mark.asyncio
    async def test_openai_chat_returns_content(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.LLM_PROVIDER", "openai")
        monkeypatch.setattr("app.core.config.settings.OPENAI_API_KEY", "sk-test")
        monkeypatch.setattr("app.core.config.settings.OPENAI_MODEL", "gpt-4o-mini")

        from app.services.llm_adapter import LLMAdapter

        msg = MagicMock()
        msg.content = "Hello from OpenAI!"
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message = msg

        adapter = LLMAdapter()
        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await adapter.chat([{"role": "user", "content": "Hi"}])
            assert result == "Hello from OpenAI!"

    @pytest.mark.asyncio
    async def test_empty_response_raises(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter, LLMResponseError

        msg = MagicMock()
        msg.content = ""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message = msg

        adapter = LLMAdapter()
        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ):
            with pytest.raises(LLMResponseError, match="empty response"):
                await adapter.chat([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_chat_with_special_characters(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        special = "emoji 🎉 unicode ñ ü chinese 中文 math ∑∏∫"
        msg = MagicMock()
        msg.content = special
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message = msg

        adapter = LLMAdapter()
        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await adapter.chat([{"role": "user", "content": special}])
            assert result == special

    @pytest.mark.asyncio
    async def test_chat_with_long_context(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        long_text = "a" * 10000
        msg = MagicMock()
        msg.content = long_text
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message = msg

        adapter = LLMAdapter()
        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=response,
        ):
            result = await adapter.chat([{"role": "user", "content": "test"}])
            assert result == long_text


# ---------------------------------------------------------------------------
# LLMAdapter.chat — streaming
# ---------------------------------------------------------------------------


class TestChatStreaming:
    @pytest.mark.asyncio
    async def test_streaming_returns_llm_stream(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter, LLMStream

        adapter = LLMAdapter()
        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = MagicMock()  # raw OpenAI stream
            result = await adapter.chat([{"role": "user", "content": "Hi"}], stream=True)
            assert isinstance(result, LLMStream)

    @pytest.mark.asyncio
    async def test_streaming_passes_stream_options(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = MagicMock()
            await adapter.chat([{"role": "user", "content": "Hi"}], stream=True)
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["stream"] is True
            assert call_kwargs["stream_options"] == {"include_usage": True}

    @pytest.mark.asyncio
    async def test_streaming_passes_timeout(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = MagicMock()
            await adapter.chat([{"role": "user", "content": "Hi"}], stream=True)
            assert mock_create.call_args.kwargs["timeout"] == 120.0


# ---------------------------------------------------------------------------
# LLMAdapter._anthropic_chat
# ---------------------------------------------------------------------------


def _make_anthropic_settings(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.LLM_PROVIDER", "anthropic")
    monkeypatch.setattr("app.core.config.settings.ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("app.core.config.settings.ANTHROPIC_MODEL", "claude-3-5-haiku-latest")


class TestAnthropicChat:
    @pytest.mark.asyncio
    async def test_non_streaming_returns_content(self, monkeypatch):
        _make_anthropic_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        content_block = MagicMock()
        content_block.text = "Bonjour!"
        resp = MagicMock()
        resp.content = [content_block]

        with patch.object(
            adapter._anthropic.messages,
            "create",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            result = await adapter.chat([{"role": "user", "content": "Hi"}])
            assert result == "Bonjour!"

    @pytest.mark.asyncio
    async def test_empty_response_raises(self, monkeypatch):
        _make_anthropic_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter, LLMResponseError

        adapter = LLMAdapter()
        resp = MagicMock()
        resp.content = []  # empty content list

        with patch.object(
            adapter._anthropic.messages,
            "create",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            with pytest.raises(LLMResponseError, match="empty response"):
                await adapter.chat([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_empty_content_string_raises(self, monkeypatch):
        _make_anthropic_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter, LLMResponseError

        adapter = LLMAdapter()
        resp = MagicMock()
        resp.content = [MagicMock()]
        resp.content[0].text = ""

        with patch.object(
            adapter._anthropic.messages,
            "create",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            with pytest.raises(LLMResponseError, match="empty response"):
                await adapter.chat([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_streaming_returns_llm_stream(self, monkeypatch):
        _make_anthropic_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter, LLMStream

        adapter = LLMAdapter()
        resp = MagicMock()  # represents a raw Anthropic stream

        with patch.object(
            adapter._anthropic.messages,
            "create",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            result = await adapter.chat([{"role": "user", "content": "Hi"}], stream=True)
            assert isinstance(result, LLMStream)

    @pytest.mark.asyncio
    async def test_combines_system_messages(self, monkeypatch):
        _make_anthropic_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        resp = MagicMock()
        resp.content = [MagicMock()]
        resp.content[0].text = "ok"

        with patch.object(
            adapter._anthropic.messages,
            "create",
            new_callable=AsyncMock,
            return_value=resp,
        ) as mock_create:
            await adapter.chat(
                [
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hi"},
                    {"role": "system", "content": "Also be concise."},
                ]
            )
            call_kwargs = mock_create.call_args.kwargs
            assert "system" in call_kwargs
            assert "You are helpful." in call_kwargs["system"]
            assert "Also be concise." in call_kwargs["system"]

    @pytest.mark.asyncio
    async def test_system_only_messages_injects_user_trigger(self, monkeypatch):
        """When only system messages are passed, inject a minimal user message."""
        _make_anthropic_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        resp = MagicMock()
        resp.content = [MagicMock()]
        resp.content[0].text = "ok"

        with patch.object(
            adapter._anthropic.messages,
            "create",
            new_callable=AsyncMock,
            return_value=resp,
        ) as mock_create:
            await adapter.chat(
                [
                    {"role": "system", "content": "Generate JSON."},
                ]
            )
            call_kwargs = mock_create.call_args.kwargs
            assert len(call_kwargs["messages"]) == 1
            assert call_kwargs["messages"][0]["role"] == "user"
            assert "Generate the content" in call_kwargs["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_passes_max_tokens_and_timeout(self, monkeypatch):
        _make_anthropic_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        resp = MagicMock()
        resp.content = [MagicMock()]
        resp.content[0].text = "ok"

        with patch.object(
            adapter._anthropic.messages,
            "create",
            new_callable=AsyncMock,
            return_value=resp,
        ) as mock_create:
            await adapter.chat([{"role": "user", "content": "Hi"}])
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["max_tokens"] == 4096
            assert call_kwargs["timeout"] == 120.0


# ---------------------------------------------------------------------------
# Anthropic error mapping
# ---------------------------------------------------------------------------


class TestAnthropicErrorMapping:
    @pytest.mark.asyncio
    async def test_timeout_error_mapped(self, monkeypatch):
        _make_anthropic_settings(monkeypatch)

        import anthropic as _anthropic

        from app.services.llm_adapter import LLMAdapter, LLMTimeoutError

        adapter = LLMAdapter()
        with patch.object(
            adapter._anthropic.messages,
            "create",
            new_callable=AsyncMock,
            side_effect=_anthropic.APITimeoutError("request timed out"),
        ):
            with pytest.raises(LLMTimeoutError, match="timed out"):
                await adapter.chat([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_connection_error_mapped(self, monkeypatch):
        _make_anthropic_settings(monkeypatch)

        import anthropic as _anthropic
        import httpx

        from app.services.llm_adapter import LLMAdapter, LLMUnavailableError

        req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        adapter = LLMAdapter()
        with patch.object(
            adapter._anthropic.messages,
            "create",
            new_callable=AsyncMock,
            side_effect=_anthropic.APIConnectionError(message="connection refused", request=req),
        ):
            with pytest.raises(LLMUnavailableError, match="unreachable"):
                await adapter.chat([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_rate_limit_error_mapped(self, monkeypatch):
        _make_anthropic_settings(monkeypatch)

        import anthropic as _anthropic
        import httpx

        from app.services.llm_adapter import LLMAdapter, LLMUnavailableError

        req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        resp = httpx.Response(429, request=req)
        adapter = LLMAdapter()
        with patch.object(
            adapter._anthropic.messages,
            "create",
            new_callable=AsyncMock,
            side_effect=_anthropic.RateLimitError("rate limited", response=resp, body=None),
        ):
            with pytest.raises(LLMUnavailableError, match="rate limit"):
                await adapter.chat([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_generic_status_error_mapped(self, monkeypatch):
        _make_anthropic_settings(monkeypatch)

        import anthropic as _anthropic
        import httpx

        from app.services.llm_adapter import LLMAdapter, LLMError

        req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        resp = httpx.Response(500, request=req)
        adapter = LLMAdapter()
        with patch.object(
            adapter._anthropic.messages,
            "create",
            new_callable=AsyncMock,
            side_effect=_anthropic.APIStatusError("server error", response=resp, body=None),
        ):
            with pytest.raises(LLMError, match="anthropic error"):
                await adapter.chat([{"role": "user", "content": "Hi"}])


# ---------------------------------------------------------------------------
# _call_with_retry — error classification and retry
# ---------------------------------------------------------------------------


class TestCallWithRetry:
    @pytest.mark.asyncio
    async def test_retries_on_timeout_error(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        call_count = [0]

        async def mock_create(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise TimeoutError("timeout")
            msg = MagicMock()
            msg.content = "finally works"
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message = msg
            return resp

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new=AsyncMock(side_effect=mock_create),
        ):
            result = await adapter.chat([{"role": "user", "content": "Hi"}])
            assert result == "finally works"
            assert call_count[0] == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_retries_on_connection_error(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        call_count = [0]

        async def mock_create(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("connection refused")
            msg = MagicMock()
            msg.content = "ok"
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message = msg
            return resp

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new=AsyncMock(side_effect=mock_create),
        ):
            result = await adapter.chat([{"role": "user", "content": "Hi"}])
            assert result == "ok"
            assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_retries_on_rate_limit_error(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        call_count = [0]

        async def mock_create(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("rate limit exceeded")
            msg = MagicMock()
            msg.content = "ok"
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message = msg
            return resp

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new=AsyncMock(side_effect=mock_create),
        ):
            result = await adapter.chat([{"role": "user", "content": "Hi"}])
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_gives_up_after_max_retries(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter, LLMTimeoutError

        adapter = LLMAdapter()
        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=TimeoutError("always times out"),
        ):
            with pytest.raises(LLMTimeoutError):
                await adapter.chat([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_preserves_typed_llm_error_on_retry(self, monkeypatch):
        """When an LLMError subclass is raised, it should be preserved (not re-wrapped)."""
        _make_anthropic_settings(monkeypatch)

        import anthropic as _anthropic
        import httpx

        from app.services.llm_adapter import LLMAdapter, LLMUnavailableError

        req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        resp = httpx.Response(429, request=req)

        adapter = LLMAdapter()
        # This is a persistent error; retry should exhaust attempts and then re-raise
        with patch.object(
            adapter._anthropic.messages,
            "create",
            new_callable=AsyncMock,
            side_effect=_anthropic.RateLimitError("rate limited", response=resp, body=None),
        ):
            with pytest.raises(LLMUnavailableError, match="rate limit"):
                await adapter.chat([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_raises_generic_llm_error_for_unknown_exception(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter, LLMError

        adapter = LLMAdapter()
        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=RuntimeError("unexpected internal error"),
        ):
            with pytest.raises(LLMError, match="unexpected internal error"):
                await adapter.chat([{"role": "user", "content": "Hi"}])


# ---------------------------------------------------------------------------
# structured_output
# ---------------------------------------------------------------------------


class FakeSchema(BaseModel):
    answer: str
    confidence: float


class TestStructuredOutput:
    @pytest.mark.asyncio
    async def test_parses_valid_json(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        msg = MagicMock()
        msg.content = '{"answer": "Paris", "confidence": 0.95}'
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message = msg

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            result = await adapter.structured_output(
                [{"role": "user", "content": "Capital of France?"}],
                FakeSchema,
            )
            assert isinstance(result, FakeSchema)
            assert result.answer == "Paris"
            assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_strips_markdown_fences(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        msg = MagicMock()
        msg.content = '```\n{"answer": "Berlin", "confidence": 0.8}\n```'
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message = msg

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            result = await adapter.structured_output(
                [{"role": "user", "content": "test"}],
                FakeSchema,
            )
            assert result.answer == "Berlin"
            assert result.confidence == 0.8

    @pytest.mark.asyncio
    async def test_retries_on_invalid_json(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()

        call_count = [0]

        async def mock_create(*args, **kwargs):
            call_count[0] += 1
            msg = MagicMock()
            resp = MagicMock()
            resp.choices = [MagicMock()]
            if call_count[0] == 1:
                msg.content = "not valid json at all"
                resp.choices[0].message = msg
                return resp
            else:
                msg.content = '{"answer": "Madrid", "confidence": 0.88}'
                resp.choices[0].message = msg
                return resp

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=mock_create,
        ):
            result = await adapter.structured_output(
                [{"role": "user", "content": "test"}],
                FakeSchema,
            )
            assert result.answer == "Madrid"
            assert call_count[0] == 2  # first failed, second succeeded

    @pytest.mark.asyncio
    async def test_retry_failure_raises_response_error(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter, LLMResponseError

        adapter = LLMAdapter()
        msg = MagicMock()
        msg.content = "still not json"
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message = msg

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            with pytest.raises(LLMResponseError, match="Failed to parse JSON after retry"):
                await adapter.structured_output(
                    [{"role": "user", "content": "test"}],
                    FakeSchema,
                )

    @pytest.mark.asyncio
    async def test_strips_json_prefix_in_retry(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()

        call_count = [0]

        async def mock_create(*args, **kwargs):
            call_count[0] += 1
            msg = MagicMock()
            resp = MagicMock()
            resp.choices = [MagicMock()]
            if call_count[0] == 1:
                msg.content = "bad"
                resp.choices[0].message = msg
                return resp
            else:
                msg.content = '```json\n{"answer": "Rome", "confidence": 0.9}\n```'
                resp.choices[0].message = msg
                return resp

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=mock_create,
        ):
            result = await adapter.structured_output(
                [{"role": "user", "content": "test"}],
                FakeSchema,
            )
            assert result.answer == "Rome"

    @pytest.mark.asyncio
    async def test_structured_output_passes_through_retry(self, monkeypatch):
        """Test that structured_output is wrapped in _call_with_retry so
        transient errors get retried."""
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        call_count = [0]

        async def flaky_create(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise TimeoutError("timeout")
            msg = MagicMock()
            msg.content = '{"answer": "Tokyo", "confidence": 0.85}'
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message = msg
            return resp

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=flaky_create,
        ):
            result = await adapter.structured_output(
                [{"role": "user", "content": "test"}],
                FakeSchema,
            )
            assert result.answer == "Tokyo"
            assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_adds_json_format_system_message(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        msg = MagicMock()
        msg.content = '{"answer": "Lima", "confidence": 0.75}'
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message = msg

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = resp
            await adapter.structured_output(
                [{"role": "user", "content": "test"}],
                FakeSchema,
            )
            # Verify the JSON format instruction was appended
            sent_messages = mock_create.call_args.kwargs["messages"]
            system_msgs = [m for m in sent_messages if m["role"] == "system"]
            assert len(system_msgs) >= 1
            assert any("valid JSON object" in m["content"] for m in system_msgs)


# ---------------------------------------------------------------------------
# DeepSeek provider
# ---------------------------------------------------------------------------


class TestDeepSeekProvider:
    @pytest.mark.asyncio
    async def test_deepseek_chat(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.LLM_PROVIDER", "deepseek")
        monkeypatch.setattr("app.core.config.settings.DEEPSEEK_API_KEY", "sk-ds")
        monkeypatch.setattr("app.core.config.settings.DEEPSEEK_MODEL", "deepseek-chat")

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        assert adapter.provider == "deepseek"

        msg = MagicMock()
        msg.content = "DeepSeek says hi"
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message = msg

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            result = await adapter.chat([{"role": "user", "content": "Hi"}])
            assert result == "DeepSeek says hi"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_messages_list(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter

        adapter = LLMAdapter()
        msg = MagicMock()
        msg.content = "response"
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message = msg

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            result = await adapter.chat([])
            assert result == "response"

    @pytest.mark.asyncio
    async def test_null_content_in_response(self, monkeypatch):
        _make_ollama_settings(monkeypatch)

        from app.services.llm_adapter import LLMAdapter, LLMResponseError

        adapter = LLMAdapter()
        msg = MagicMock()
        msg.content = None
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message = msg

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            with pytest.raises(LLMResponseError, match="empty response"):
                await adapter.chat([{"role": "user", "content": "Hi"}])


# ---------------------------------------------------------------------------
# LLMStream — Anthropic streaming edge case
# ---------------------------------------------------------------------------


class TestLLMStreamAnthropic:
    async def test_usage_remains_none_for_anthropic_stream(self):
        """Anthropic stream events have no conventional usage attribute."""
        from app.services.llm_adapter import LLMStream

        class AnthropicEvent:
            # No usage attribute at all
            pass

        async def fake_stream():
            yield AnthropicEvent()
            yield AnthropicEvent()

        wrapped = LLMStream(fake_stream())
        parts = [c async for c in wrapped]
        assert len(parts) == 2
        assert wrapped.prompt_tokens is None
        assert wrapped.completion_tokens is None
        assert wrapped.total_tokens is None


# ---------------------------------------------------------------------------
# Native tool streaming
# ---------------------------------------------------------------------------


class TestNativeToolStreaming:
    @pytest.mark.asyncio
    async def test_unsupported_tools_fall_back_without_retrying_them(self, monkeypatch):
        _make_ollama_settings(monkeypatch)
        from app.services.llm_adapter import LLMAdapter, LLMTool, LLMToolResult

        async def fallback_stream():
            yield FakeOpenAIChunk("Normal response.")

        adapter = LLMAdapter()
        tool = LLMTool("save_user_memory", "Save memory", {"type": "object"})

        async def executor(call):
            return LLMToolResult(call=call, content={"saved": True})

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=[RuntimeError("model does not support tools"), fallback_stream()],
        ) as create:
            stream = await adapter.chat(
                [{"role": "user", "content": "Hi"}],
                stream=True,
                tools=[tool],
                tool_executor=executor,
            )
            assert [part async for part in stream] == ["Normal response."]

        assert stream.tools_unsupported is True
        assert len(create.call_args_list) == 2
        assert "tools" in create.call_args_list[0].kwargs
        assert "tools" not in create.call_args_list[1].kwargs

    @pytest.mark.asyncio
    async def test_openai_tool_call_executes_and_continues(self, monkeypatch):
        _make_ollama_settings(monkeypatch)
        from app.services.llm_adapter import (
            LLMAdapter,
            LLMTool,
            LLMToolResult,
        )

        def tool_chunk(arguments: str, *, tool_id: str | None = None, name: str | None = None):
            function = SimpleNamespace(name=name, arguments=arguments)
            tool_call = SimpleNamespace(index=0, id=tool_id, function=function)
            delta = SimpleNamespace(content=None, tool_calls=[tool_call])
            return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=None)

        async def initial_stream():
            yield FakeOpenAIChunk("Sure. ")
            yield tool_chunk('{"content":"Likes ', tool_id="call_1", name="save_user_memory")
            yield tool_chunk('hiking"}')
            yield FakeOpenAIChunk(None, usage=FakeUsage(10, 3))

        release_continuation = asyncio.Event()

        async def continuation_stream():
            yield FakeOpenAIChunk("I will remember that.")
            await release_continuation.wait()
            yield FakeOpenAIChunk(" Thanks.")
            yield FakeOpenAIChunk(None, usage=FakeUsage(12, 4))

        adapter = LLMAdapter()
        tool = LLMTool(
            name="save_user_memory",
            description="Save memory",
            input_schema={"type": "object"},
        )

        async def executor(call):
            assert call.arguments == {"content": "Likes hiking"}
            return LLMToolResult(call=call, content={"saved": True})

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=[initial_stream(), continuation_stream()],
        ) as create:
            stream = await adapter.chat(
                [{"role": "user", "content": "I like hiking"}],
                stream=True,
                tools=[tool],
                tool_executor=executor,
            )
            iterator = stream.__aiter__()
            assert await asyncio.wait_for(anext(iterator), timeout=0.1) == "Sure. "
            assert await asyncio.wait_for(anext(iterator), timeout=0.1) == "I will remember that."
            release_continuation.set()
            assert [part async for part in iterator] == [" Thanks."]

        assert stream.tool_results[0].content == {"saved": True}
        assert stream.prompt_tokens == 22
        assert stream.completion_tokens == 7
        assert "tools" in create.call_args_list[0].kwargs
        assert "tools" not in create.call_args_list[1].kwargs
        continuation = create.call_args_list[1].kwargs["messages"]
        assert continuation[-2]["role"] == "assistant"
        assert continuation[-1]["role"] == "tool"

    @pytest.mark.asyncio
    async def test_anthropic_tool_call_uses_native_result_blocks(self, monkeypatch):
        _make_anthropic_settings(monkeypatch)
        from app.services.llm_adapter import LLMAdapter, LLMTool, LLMToolResult

        async def initial_stream():
            yield SimpleNamespace(
                type="message_start",
                message=SimpleNamespace(usage=SimpleNamespace(input_tokens=8)),
            )
            yield SimpleNamespace(
                type="content_block_start",
                index=0,
                content_block=SimpleNamespace(
                    type="tool_use",
                    id="tool_1",
                    name="save_user_memory",
                    input={},
                ),
            )
            yield SimpleNamespace(
                type="content_block_delta",
                index=0,
                delta=SimpleNamespace(
                    type="input_json_delta",
                    partial_json='{"content":"Likes tea"}',
                ),
            )
            yield SimpleNamespace(
                type="message_delta",
                usage=SimpleNamespace(output_tokens=2),
            )

        async def continuation_stream():
            yield SimpleNamespace(
                type="content_block_delta",
                index=0,
                delta=SimpleNamespace(type="text_delta", text="Thanks for sharing."),
            )

        adapter = LLMAdapter()
        tool = LLMTool("save_user_memory", "Save memory", {"type": "object"})

        async def executor(call):
            return LLMToolResult(call=call, content={"saved": True})

        with patch.object(
            adapter._anthropic.messages,
            "create",
            new_callable=AsyncMock,
            side_effect=[initial_stream(), continuation_stream()],
        ) as create:
            stream = await adapter.chat(
                [{"role": "user", "content": "I like tea"}],
                stream=True,
                tools=[tool],
                tool_executor=executor,
            )
            assert [part async for part in stream] == ["Thanks for sharing."]

        assert create.call_args_list[0].kwargs["tools"][0]["name"] == "save_user_memory"
        continuation = create.call_args_list[1].kwargs["messages"]
        assert continuation[-1]["content"][0]["type"] == "tool_result"

    @pytest.mark.asyncio
    async def test_tool_continuation_failure_falls_back_without_tools(self, monkeypatch):
        _make_ollama_settings(monkeypatch)
        from app.services.llm_adapter import LLMAdapter, LLMTool, LLMToolResult

        def tool_chunk(index: int, content: str):
            function = SimpleNamespace(name="save_user_memory", arguments=content)
            tool_call = SimpleNamespace(index=index, id=f"call_{index}", function=function)
            delta = SimpleNamespace(content=None, tool_calls=[tool_call])
            return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=None)

        async def initial_stream():
            yield tool_chunk(0, '{"content":"Likes tea"}')

        async def broken_continuation():
            raise ConnectionError("connection lost")
            yield  # pragma: no cover

        async def fallback_stream():
            yield FakeOpenAIChunk("Thanks for sharing.", usage=FakeUsage(9, 3))

        adapter = LLMAdapter()
        tool = LLMTool("save_user_memory", "Save memory", {"type": "object"})

        async def executor(call):
            return LLMToolResult(call=call, content={"saved": True})

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=[initial_stream(), broken_continuation(), fallback_stream()],
        ) as create:
            stream = await adapter.chat(
                [{"role": "user", "content": "I like tea"}],
                stream=True,
                tools=[tool],
                tool_executor=executor,
            )
            assert [part async for part in stream] == ["Thanks for sharing."]

        assert stream.tool_results[0].content == {"saved": True}
        assert stream.total_tokens == 12
        assert "tools" not in create.call_args_list[2].kwargs

    @pytest.mark.asyncio
    async def test_executes_only_first_tool_call(self, monkeypatch):
        _make_ollama_settings(monkeypatch)
        from app.services.llm_adapter import LLMAdapter, LLMTool, LLMToolResult

        async def initial_stream():
            for index in range(2):
                function = SimpleNamespace(
                    name="save_user_memory",
                    arguments=f'{{"content":"Fact {index}"}}',
                )
                tool_call = SimpleNamespace(index=index, id=f"call_{index}", function=function)
                delta = SimpleNamespace(content=None, tool_calls=[tool_call])
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=None)

        async def continuation_stream():
            yield FakeOpenAIChunk("Understood.")

        adapter = LLMAdapter()
        tool = LLMTool("save_user_memory", "Save memory", {"type": "object"})
        executed: list[str] = []

        async def executor(call):
            executed.append(call.id)
            return LLMToolResult(call=call, content={"saved": True})

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=[initial_stream(), continuation_stream()],
        ):
            stream = await adapter.chat(
                [{"role": "user", "content": "Remember these"}],
                stream=True,
                tools=[tool],
                tool_executor=executor,
            )
            assert [part async for part in stream] == ["Understood."]

        assert executed == ["call_0"]
        assert stream.tool_results[1].content == {
            "saved": False,
            "error": "tool_limit_exceeded",
        }

    @pytest.mark.asyncio
    async def test_tools_require_stream_and_executor(self, monkeypatch):
        _make_ollama_settings(monkeypatch)
        from app.services.llm_adapter import LLMAdapter, LLMTool

        adapter = LLMAdapter()
        tool = LLMTool("save_user_memory", "Save memory", {"type": "object"})
        with pytest.raises(ValueError, match="require streaming"):
            await adapter.chat([], tools=[tool])

    @pytest.mark.asyncio
    async def test_stream_iteration_connection_error_is_typed(self, monkeypatch):
        _make_ollama_settings(monkeypatch)
        from app.services.llm_adapter import (
            LLMAdapter,
            LLMTool,
            LLMToolResult,
            LLMUnavailableError,
        )

        def tool_chunk():
            function = SimpleNamespace(
                name="save_user_memory",
                arguments='{"content":"Likes tea"}',
            )
            tool_call = SimpleNamespace(index=0, id="call_1", function=function)
            delta = SimpleNamespace(content=None, tool_calls=[tool_call])
            return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=None)

        async def initial_stream():
            yield tool_chunk()

        async def broken_continuation():
            yield FakeOpenAIChunk("Partial")
            raise ConnectionError("connection lost")

        adapter = LLMAdapter()
        tool = LLMTool("save_user_memory", "Save memory", {"type": "object"})

        async def executor(call):
            return LLMToolResult(call=call, content={"saved": True})

        with patch.object(
            adapter.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=[initial_stream(), broken_continuation()],
        ) as create:
            stream = await adapter.chat(
                [{"role": "user", "content": "Hi"}],
                stream=True,
                tools=[tool],
                tool_executor=executor,
            )
            iterator = stream.__aiter__()
            assert await asyncio.wait_for(anext(iterator), timeout=0.1) == "Partial"
            with pytest.raises(LLMUnavailableError, match="unreachable"):
                await anext(iterator)
            assert len(create.call_args_list) == 2
