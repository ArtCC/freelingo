from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass

import anthropic as _anthropic
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.app_logger import get_logger
from app.core.config import settings
from app.services.prompts.common import (
    ANTHROPIC_SYSTEM_ONLY_TRIGGER,
    JSON_ONLY_INSTRUCTION,
    STRUCTURED_OUTPUT_RETRY_PROMPT,
)

logger = get_logger(__name__)

MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 2
REQUEST_TIMEOUT = 120.0

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


class LLMToolsUnsupportedError(LLMError):
    pass


def _is_tools_unsupported_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    messages: list[str] = []
    while current is not None:
        messages.append(str(current).lower())
        current = current.__cause__
    message = " ".join(messages)
    return any(
        marker in message
        for marker in (
            "does not support tools",
            "doesn't support tools",
            "tools are not supported",
            "tool use is not supported",
            "unsupported parameter: 'tools'",
            'unsupported parameter: "tools"',
        )
    )


@dataclass(frozen=True)
class LLMTool:
    name: str
    description: str
    input_schema: dict


@dataclass(frozen=True)
class LLMToolCall:
    id: str
    name: str
    arguments: dict
    raw_arguments: str


@dataclass(frozen=True)
class LLMToolResult:
    call: LLMToolCall
    content: dict
    is_error: bool = False


ToolExecutor = Callable[[LLMToolCall], Awaitable[LLMToolResult]]


async def _safe_stream_events(stream: object, provider: str) -> AsyncGenerator:
    """Normalize exceptions raised after a provider stream has started."""
    try:
        async for event in stream:  # type: ignore[union-attr]
            yield event
    except LLMError:
        raise
    except (TimeoutError, _anthropic.APITimeoutError) as exc:
        raise LLMTimeoutError(f"{provider} timed out while streaming") from exc
    except _anthropic.APIConnectionError as exc:
        raise LLMUnavailableError(f"{provider} is unreachable") from exc
    except _anthropic.RateLimitError as exc:
        raise LLMUnavailableError(f"{provider} rate limit exceeded") from exc
    except _anthropic.APIStatusError as exc:
        if _is_tools_unsupported_error(exc):
            raise LLMToolsUnsupportedError(f"{provider} does not support tools") from exc
        raise LLMError(f"{provider} streaming error: {exc}") from exc
    except Exception as exc:
        if _is_tools_unsupported_error(exc):
            raise LLMToolsUnsupportedError(f"{provider} does not support tools") from exc
        message = str(exc)
        if "connection" in message.lower():
            raise LLMUnavailableError(f"{provider} is unreachable") from exc
        if "rate" in message.lower():
            raise LLMUnavailableError(f"{provider} rate limit exceeded") from exc
        raise LLMError(f"{provider} streaming error: {message}") from exc


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


class AnthropicLLMStream(LLMStream):
    """Yield normalized text from an ordinary Anthropic stream."""

    async def _iterate(self):
        async for event in _safe_stream_events(self._stream, "anthropic"):
            event_type = getattr(event, "type", "")
            if event_type == "message_start":
                usage = getattr(getattr(event, "message", None), "usage", None)
                self.prompt_tokens = getattr(usage, "input_tokens", None)
            elif event_type == "message_delta":
                usage = getattr(event, "usage", None)
                self.completion_tokens = getattr(usage, "output_tokens", None)
            elif event_type == "content_block_delta":
                delta = getattr(event, "delta", None)
                if getattr(delta, "type", "") == "text_delta":
                    text = getattr(delta, "text", "")
                    if text:
                        yield text
        if self.prompt_tokens is not None or self.completion_tokens is not None:
            self.total_tokens = (self.prompt_tokens or 0) + (self.completion_tokens or 0)


class LLMToolStream(LLMStream):
    """Normalize provider streams and execute at most one native-tool round."""

    def __init__(
        self,
        adapter: LLMAdapter,
        stream: object,
        messages: list[dict],
        tools: list[LLMTool],
        tool_executor: ToolExecutor,
        *,
        tools_unsupported: bool = False,
    ) -> None:
        super().__init__(stream)
        self._adapter = adapter
        self._messages = messages
        self._tools = tools
        self._tool_executor = tool_executor
        self.tool_calls: list[LLMToolCall] = []
        self.tool_results: list[LLMToolResult] = []
        self.tools_unsupported = tools_unsupported

    def _add_usage(self, prompt: int | None, completion: int | None) -> None:
        if prompt is not None:
            self.prompt_tokens = (self.prompt_tokens or 0) + prompt
        if completion is not None:
            self.completion_tokens = (self.completion_tokens or 0) + completion
        if self.prompt_tokens is not None or self.completion_tokens is not None:
            self.total_tokens = (self.prompt_tokens or 0) + (self.completion_tokens or 0)

    async def _provider_text_and_calls(
        self, stream: object, *, collect_calls: bool
    ) -> AsyncGenerator[str]:
        calls: dict[int, dict[str, str]] = {}
        prompt_tokens: int | None = None
        completion_tokens: int | None = None

        async for event in _safe_stream_events(stream, self._adapter.provider):
            if self._adapter.provider == "anthropic":
                event_type = getattr(event, "type", "")
                if event_type == "message_start":
                    usage = getattr(getattr(event, "message", None), "usage", None)
                    prompt_tokens = getattr(usage, "input_tokens", None)
                elif event_type == "message_delta":
                    usage = getattr(event, "usage", None)
                    completion_tokens = getattr(usage, "output_tokens", None)
                elif event_type == "content_block_start" and collect_calls:
                    block = getattr(event, "content_block", None)
                    if getattr(block, "type", "") == "tool_use":
                        index = int(getattr(event, "index", len(calls)))
                        initial_input = getattr(block, "input", None)
                        calls[index] = {
                            "id": str(getattr(block, "id", f"tool_{index}")),
                            "name": str(getattr(block, "name", "")),
                            "arguments": json.dumps(initial_input) if initial_input else "",
                        }
                elif event_type == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    delta_type = getattr(delta, "type", "")
                    if delta_type == "text_delta":
                        text = getattr(delta, "text", "")
                        if text:
                            yield text
                    elif delta_type == "input_json_delta" and collect_calls:
                        index = int(getattr(event, "index", 0))
                        call = calls.setdefault(
                            index,
                            {"id": f"tool_{index}", "name": "", "arguments": ""},
                        )
                        call["arguments"] += str(getattr(delta, "partial_json", ""))
                continue

            usage = getattr(event, "usage", None)
            if usage is not None:
                prompt_tokens = getattr(usage, "prompt_tokens", None)
                completion_tokens = getattr(usage, "completion_tokens", None)
            choices = getattr(event, "choices", None)
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            text = getattr(delta, "content", None)
            if text:
                yield text
            if not collect_calls:
                continue
            tool_deltas = getattr(delta, "tool_calls", None)
            if not isinstance(tool_deltas, (list, tuple)):
                continue
            for tool_delta in tool_deltas:
                index = int(getattr(tool_delta, "index", 0))
                call = calls.setdefault(
                    index,
                    {"id": f"tool_{index}", "name": "", "arguments": ""},
                )
                tool_id = getattr(tool_delta, "id", None)
                if tool_id:
                    call["id"] = str(tool_id)
                function = getattr(tool_delta, "function", None)
                name = getattr(function, "name", None)
                arguments = getattr(function, "arguments", None)
                if name:
                    call["name"] += str(name)
                if arguments:
                    call["arguments"] += str(arguments)

        self._add_usage(prompt_tokens, completion_tokens)
        if collect_calls:
            for raw_call in (calls[index] for index in sorted(calls)):
                try:
                    arguments = json.loads(raw_call["arguments"] or "{}")
                    if not isinstance(arguments, dict):
                        arguments = {}
                except json.JSONDecodeError:
                    arguments = {}
                self.tool_calls.append(
                    LLMToolCall(
                        id=raw_call["id"],
                        name=raw_call["name"],
                        arguments=arguments,
                        raw_arguments=raw_call["arguments"],
                    )
                )

    async def _iterate(self):
        initial_parts: list[str] = []
        visible_text_emitted = False
        try:
            async for text in self._provider_text_and_calls(self._stream, collect_calls=True):
                initial_parts.append(text)
                visible_text_emitted = True
                yield text
        except LLMToolsUnsupportedError:
            if visible_text_emitted:
                logger.warning(
                    "%s rejected tools after visible text was streamed; "
                    "cannot retry without duplicating output",
                    self._adapter.provider,
                    exc_info=True,
                )
                raise
            logger.info(
                "%s model rejected native tools; continuing without them", self._adapter.provider
            )
            self.tools_unsupported = True
            fallback = await self._adapter._call_with_retry(
                self._adapter._do_chat,
                self._messages,
                True,
                None,
            )
            async for text in self._provider_text_and_calls(fallback, collect_calls=False):
                yield text
            return

        if not self.tool_calls:
            return

        for index, call in enumerate(self.tool_calls):
            if index > 0:
                self.tool_results.append(
                    LLMToolResult(
                        call=call,
                        content={"saved": False, "error": "tool_limit_exceeded"},
                        is_error=True,
                    )
                )
                continue
            try:
                result = await self._tool_executor(call)
            except Exception:
                logger.exception("LLM tool executor failed for %s", call.name)
                result = LLMToolResult(
                    call=call,
                    content={"saved": False, "error": "tool_execution_failed"},
                    is_error=True,
                )
            self.tool_results.append(result)

        initial_text = "".join(initial_parts)
        continuation_messages = self._adapter._build_tool_continuation(
            self._messages,
            initial_text,
            self.tool_calls,
            self.tool_results,
        )
        try:
            continuation = await self._adapter._call_with_retry(
                self._adapter._do_chat,
                continuation_messages,
                True,
                None,
            )
            async for text in self._provider_text_and_calls(
                continuation,
                collect_calls=False,
            ):
                visible_text_emitted = True
                yield text
        except LLMError:
            if visible_text_emitted:
                logger.warning(
                    "%s tool continuation failed after visible text was streamed; "
                    "cannot retry without duplicating output",
                    self._adapter.provider,
                    exc_info=True,
                )
                raise
            logger.warning(
                "%s tool continuation failed; retrying the turn without tools",
                self._adapter.provider,
                exc_info=True,
            )
            fallback = await self._adapter._call_with_retry(
                self._adapter._do_chat,
                self._messages,
                True,
                None,
            )
            async for text in self._provider_text_and_calls(fallback, collect_calls=False):
                yield text


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

    async def _call_with_retry(self, fn, *args, tools_requested: bool = False, **kwargs):
        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                return await fn(*args, **kwargs)
            except LLMError as e:
                if tools_requested and _is_tools_unsupported_error(e):
                    raise LLMToolsUnsupportedError(f"{self.provider} does not support tools") from e
                # Already a typed LLM error raised by a provider-specific
                # handler (e.g. _anthropic_chat). Preserve the type instead of
                # re-wrapping into a generic LLMError.
                last_error = e
            except TimeoutError:
                last_error = LLMTimeoutError(f"{self.provider} timed out after {REQUEST_TIMEOUT}s")
            except Exception as e:
                if tools_requested and _is_tools_unsupported_error(e):
                    raise LLMToolsUnsupportedError(f"{self.provider} does not support tools") from e
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
        self,
        messages: list[dict],
        stream: bool = False,
        *,
        tools: list[LLMTool] | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> str | AsyncGenerator:
        if tools and (not stream or tool_executor is None):
            raise ValueError("Native tools require streaming and a tool executor")
        tools_unsupported = False
        try:
            result = await self._call_with_retry(
                self._do_chat,
                messages,
                stream,
                tools,
                tools_requested=bool(tools),
            )
        except LLMToolsUnsupportedError:
            logger.info("%s model rejected native tools; continuing without them", self.provider)
            result = await self._call_with_retry(self._do_chat, messages, stream, None)
            tools_unsupported = True
        if not stream:
            return result
        if tools and tool_executor:
            return LLMToolStream(
                self,
                result,
                messages,
                tools,
                tool_executor,
                tools_unsupported=tools_unsupported,
            )
        if self.provider == "anthropic":
            return AnthropicLLMStream(result)
        return LLMStream(result)

    async def _do_chat(
        self,
        messages: list[dict],
        stream: bool = False,
        tools: list[LLMTool] | None = None,
    ):
        if self.provider == "anthropic":
            return await self._anthropic_chat(messages, stream, tools)

        # For Ollama, OpenAI and DeepSeek (all OpenAI-compatible):
        # pass stream_options so the final chunk includes token usage.
        # Defensively build kwargs to stay compatible with older SDK versions.
        extra: dict = {}
        if stream:
            extra["stream_options"] = {"include_usage": True}
        if tools:
            extra["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
                for tool in tools
            ]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=stream,
            timeout=REQUEST_TIMEOUT,
            **extra,
        )
        if stream:
            return response

        content = response.choices[0].message.content
        if not content:
            raise LLMResponseError("LLM returned empty response")
        return content

    async def structured_output(self, messages: list[dict], schema: type[BaseModel]) -> BaseModel:
        # Use JSON mode for all providers — more reliable across versions
        return await self._structured_via_json(messages, schema)

    async def _structured_via_json(
        self, messages: list[dict], schema: type[BaseModel]
    ) -> BaseModel:
        messages_with_format = messages + [
            {
                "role": "system",
                "content": JSON_ONLY_INSTRUCTION,
            }
        ]

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
            retry_messages = messages_with_format + [
                {
                    "role": "user",
                    "content": STRUCTURED_OUTPUT_RETRY_PROMPT.format(error=str(e)),
                }
            ]
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
                    raw_response=raw2 if "raw2" in locals() else raw,
                ) from e2

    def _build_tool_continuation(
        self,
        messages: list[dict],
        initial_text: str,
        calls: list[LLMToolCall],
        results: list[LLMToolResult],
    ) -> list[dict]:
        if self.provider == "anthropic":
            assistant_content: list[dict] = []
            if initial_text:
                assistant_content.append({"type": "text", "text": initial_text})
            assistant_content.extend(
                {
                    "type": "tool_use",
                    "id": call.id,
                    "name": call.name,
                    "input": call.arguments,
                }
                for call in calls
            )
            tool_results = [
                {
                    "type": "tool_result",
                    "tool_use_id": result.call.id,
                    "content": json.dumps(result.content),
                    "is_error": result.is_error,
                }
                for result in results
            ]
            return messages + [
                {"role": "assistant", "content": assistant_content},
                {"role": "user", "content": tool_results},
            ]

        assistant_tool_calls = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": call.raw_arguments or json.dumps(call.arguments),
                },
            }
            for call in calls
        ]
        continuation = messages + [
            {
                "role": "assistant",
                "content": initial_text or None,
                "tool_calls": assistant_tool_calls,
            }
        ]
        continuation.extend(
            {
                "role": "tool",
                "tool_call_id": result.call.id,
                "content": json.dumps(result.content),
            }
            for result in results
        )
        return continuation

    async def _anthropic_chat(
        self,
        messages: list[dict],
        stream: bool = False,
        tools: list[LLMTool] | None = None,
    ):
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
            user_messages = [{"role": "user", "content": ANTHROPIC_SYSTEM_ONLY_TRIGGER}]

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
        if tools:
            kwargs["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
                for tool in tools
            ]

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
            raise LLMUnavailableError("anthropic rate limit exceeded. Try again later.") from e
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
