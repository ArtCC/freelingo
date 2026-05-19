from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

import anthropic as _anthropic
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.app_logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)

MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 2
REQUEST_TIMEOUT = 60.0

MAX_CONTEXT_TOKENS = {
    "openai": 128000,
    "anthropic": 200000,
    "deepseek": 128000,
    "ollama": 8192,
}


class LLMError(Exception):
    pass


class LLMTimeoutError(LLMError):
    pass


class LLMUnavailableError(LLMError):
    pass


class LLMResponseError(LLMError):
    def __init__(self, message: str, raw_response: str | None = None):
        super().__init__(message)
        self.raw_response = raw_response


class LLMContextOverflowError(LLMError):
    pass


class LLMStream:
    """Wraps an async LLM stream and captures token usage defensively.

    Usage fields (prompt_tokens, completion_tokens, total_tokens) remain None
    if the provider does not return them — callers must always treat them as
    optional and must never raise on their absence.

    The wrapper filters out usage-only chunks (choices=[]) so callers that do
    ``chunk.choices[0]`` never receive an IndexError.
    """

    def __init__(self, stream: object) -> None:
        self._stream = stream
        self.prompt_tokens: int | None = None
        self.completion_tokens: int | None = None
        self.total_tokens: int | None = None

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        async for chunk in self._stream:  # type: ignore[union-attr]
            # Defensively capture usage from every chunk (the final one for
            # OpenAI-compatible streams, or any event for other providers).
            try:
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    pt = getattr(usage, "prompt_tokens", None)
                    ct = getattr(usage, "completion_tokens", None)
                    tt = getattr(usage, "total_tokens", None)
                    if pt is not None:
                        self.prompt_tokens = pt
                    if ct is not None:
                        self.completion_tokens = ct
                    if tt is not None:
                        self.total_tokens = tt
                    elif self.prompt_tokens is not None and self.completion_tokens is not None:
                        self.total_tokens = self.prompt_tokens + self.completion_tokens
            except Exception:
                pass

            # Skip usage-only chunks (choices=[]) to prevent IndexError in
            # callers that do chunk.choices[0].delta.content.
            choices = getattr(chunk, "choices", None)
            if choices is not None and len(choices) == 0:
                continue

            yield chunk


class LLMAdapter:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        if self.provider == "ollama":
            self.client = AsyncOpenAI(
                base_url=f"{settings.OLLAMA_BASE_URL}/v1",
                api_key="ollama",
            )
            self.model = settings.OLLAMA_MODEL
        elif self.provider == "openai":
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = settings.OPENAI_MODEL
        elif self.provider == "deepseek":
            self.client = AsyncOpenAI(
                base_url="https://api.deepseek.com/v1",
                api_key=settings.DEEPSEEK_API_KEY,
            )
            self.model = settings.DEEPSEEK_MODEL
        elif self.provider == "anthropic":
            self._anthropic = _anthropic.AsyncAnthropic(
                api_key=settings.ANTHROPIC_API_KEY,
                # Retries are handled by _call_with_retry; disable the SDK's
                # built-in retry logic to avoid exponential back-off stacking.
                max_retries=0,
            )
            self.client = None
            self.model = settings.ANTHROPIC_MODEL

    async def _call_with_retry(self, fn, *args, **kwargs):
        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                return await fn(*args, **kwargs)
            except LLMError as e:
                # Already a typed LLM error raised by a provider-specific
                # handler (e.g. _anthropic_chat). Preserve the type instead of
                # re-wrapping into a generic LLMError.
                last_error = e
            except TimeoutError:
                last_error = LLMTimeoutError(f"{self.provider} timed out after {REQUEST_TIMEOUT}s")
            except Exception as e:
                error_msg = str(e)
                if "connection" in error_msg.lower():
                    last_error = LLMUnavailableError(
                        f"{self.provider} is unreachable. Check that the service is running."
                    )
                elif "rate" in error_msg.lower():
                    last_error = LLMUnavailableError(
                        f"{self.provider} rate limit exceeded. Try again later."
                    )
                else:
                    last_error = LLMError(f"{self.provider} error: {error_msg}")

            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY_SECONDS * (attempt + 1))

        raise last_error

    async def chat(
        self, messages: list[dict], stream: bool = False
    ) -> str | AsyncGenerator:
        return await self._call_with_retry(self._do_chat, messages, stream)

    async def _do_chat(self, messages: list[dict], stream: bool = False):
        if self.provider == "anthropic":
            result = await self._anthropic_chat(messages, stream)
            # Wrap in LLMStream so callers always get a uniform interface.
            # Anthropic events have a different structure so usage will remain
            # None, but no code will break.
            return LLMStream(result) if stream else result

        # For Ollama, OpenAI and DeepSeek (all OpenAI-compatible):
        # pass stream_options so the final chunk includes token usage.
        # Defensively build kwargs to stay compatible with older SDK versions.
        extra: dict = {}
        if stream:
            extra["stream_options"] = {"include_usage": True}

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=stream,
            timeout=REQUEST_TIMEOUT,
            **extra,
        )
        if stream:
            return LLMStream(response)

        content = response.choices[0].message.content
        if not content:
            raise LLMResponseError("LLM returned empty response")
        return content

    async def structured_output(
        self, messages: list[dict], schema: type[BaseModel]
    ) -> BaseModel:
        # Use JSON mode for all providers — more reliable across versions
        return await self._structured_via_json(messages, schema)

    async def _structured_via_json(
        self, messages: list[dict], schema: type[BaseModel]
    ) -> BaseModel:
        messages_with_format = messages + [{
            "role": "system",
            "content": (
                "IMPORTANT: Respond with ONLY a valid JSON object. "
                "No markdown, no code fences, no extra text."
            ),
        }]

        raw = await self._call_with_retry(self._do_chat, messages_with_format, False)

        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return schema.model_validate(json.loads(cleaned))
        except (json.JSONDecodeError, ValueError) as e:
            retry_messages = messages_with_format + [{
                "role": "user",
                "content": (
                    f"That response was not valid JSON. Error: {str(e)}. "
                    "Please return ONLY the JSON object."
                ),
            }]
            try:
                raw2 = await self._call_with_retry(self._do_chat, retry_messages, False)
                cleaned2 = (
                    raw2.strip()
                    .removeprefix("```json")
                    .removeprefix("```")
                    .removesuffix("```")
                    .strip()
                )
                return schema.model_validate(json.loads(cleaned2))
            except Exception as e2:
                raise LLMResponseError(
                    f"Failed to parse JSON after retry: {str(e2)}",
                    raw_response=raw2 if 'raw2' in locals() else raw,
                ) from e2

    async def _anthropic_chat(self, messages: list[dict], stream: bool = False):
        # Combine ALL system messages so that extra instructions (e.g. the
        # JSON format hint appended by _structured_via_json) are not silently
        # dropped by a naive next()-based extraction.
        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        system = "\n\n".join(system_parts) if system_parts else None
        user_messages = [m for m in messages if m["role"] != "system"]

        # Anthropic requires at least one user message. When callers pass only
        # system messages (e.g. structured_output with a single system prompt),
        # inject a minimal trigger so the API call succeeds. All task
        # instructions are already in the system parameter.
        if not user_messages:
            user_messages = [{"role": "user", "content": "Generate the content as specified."}]

        kwargs: dict = dict(
            model=self.model,
            messages=user_messages,
            max_tokens=4096,
            stream=stream,
            timeout=REQUEST_TIMEOUT,
        )
        # Only pass system when present — Anthropic SDK does not accept None.
        if system is not None:
            kwargs["system"] = system

        # Map Anthropic SDK exceptions to our internal error types so that
        # _call_with_retry can classify and retry them correctly.
        # Exception hierarchy per SDK docs:
        #   APITimeoutError, APIConnectionError, RateLimitError < APIStatusError < APIError
        try:
            response = await self._anthropic.messages.create(**kwargs)
        except _anthropic.APITimeoutError as e:
            raise LLMTimeoutError(f"anthropic timed out after {REQUEST_TIMEOUT}s") from e
        except _anthropic.APIConnectionError as e:
            raise LLMUnavailableError(
                "anthropic is unreachable. Check that the service is running."
            ) from e
        except _anthropic.RateLimitError as e:
            raise LLMUnavailableError(
                "anthropic rate limit exceeded. Try again later."
            ) from e
        except _anthropic.APIStatusError as e:
            raise LLMError(f"anthropic error: {e}") from e

        if stream:
            return response
        content = response.content[0].text if response.content else ""
        if not content:
            raise LLMResponseError("Anthropic returned empty response")
        return content


llm_adapter = LLMAdapter()


def parse_llm_json(raw: str) -> dict:
    """Strip optional code fences and parse JSON from LLM output."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        # parts[1] is the content inside the fences (may start with "json\n")
        cleaned = parts[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return json.loads(cleaned.strip())
