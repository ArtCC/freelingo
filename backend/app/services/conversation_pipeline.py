from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.core.app_logger import get_logger
from app.services.language_helpers import (
    get_iso639,
    get_language_name,
    get_native_language_name,
)
from app.services.llm_adapter import (
    LLMError,
    LLMStream,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.services.memory_service import (
    build_memory_context,
    parse_memory_marker,
    save_memories,
    strip_memory_marker,
)
from app.services.prompts.common import get_language_prompt_overlay
from app.services.prompts.tutor import build_conversation_system_prompt
from app.services.quota_service import record_session_seconds
from app.utils.db import db_session

if TYPE_CHECKING:
    from fastapi import WebSocket

logger = get_logger(__name__)

TTS_MAX_RETRIES = 1
TTS_RETRY_DELAY_SECONDS = 0.2

WARNING_ADVANCE_SECONDS = 60  # How many seconds before timeout to send the warning


def _build_conversation_system_prompt(
    *,
    student_name: str,
    cefr_level: str,
    native_language: str,
    target_language_name: str,
    user_context: str,
    memory_context: str,
    language_prompt_overlay: str = "",
) -> str:
    return build_conversation_system_prompt(
        student_name=student_name,
        cefr_level=cefr_level,
        native_language=native_language,
        target_language_name=target_language_name,
        user_context=user_context,
        memory_context=memory_context,
        language_prompt_overlay=language_prompt_overlay,
    )


class ConversationPipeline:
    """
    Orchestrates STT → LLM → TTS streaming with barge-in and session timeout.
    """

    def __init__(
        self,
        llm: object,
        tts: object,
        stt: object,
        cefr_level: str = "B1",
        native_language: str = "es",
        target_language: str = "en-GB",
        student_name: str = "Student",
        max_duration: int = 1800,
        inactivity_timeout: int = 180,
        initial_context: list[dict] | None = None,
        user_id: int | None = None,
        conversation_id: int | None = None,
        bio: str | None = None,
        learning_goals: str | None = None,
        memories: list | None = None,
        voice: str = "",
        study_plan_id: int | None = None,
    ) -> None:
        self.llm = llm
        self.tts = tts
        self.stt = stt
        self._voice = voice
        self._stt_language = get_iso639(target_language)
        self._target_language = target_language
        self._user_id = user_id
        self._conversation_id = conversation_id
        self._study_plan_id = study_plan_id
        # Build user context section
        _ctx_parts: list[str] = []
        if learning_goals:
            try:
                import json as _json  # noqa: PLC0415

                goals = _json.loads(learning_goals)
                if isinstance(goals, list) and goals:
                    _ctx_parts.append(f"Learning goals: {', '.join(goals)}")
            except ValueError, TypeError:
                pass
        if bio and bio.strip():
            _ctx_parts.append(f"About the student: {bio.strip()}")
        user_context = (
            ("\nStudent context:\n" + "\n".join(f"- {p}" for p in _ctx_parts) + "\n")
            if _ctx_parts
            else ""
        )
        memory_context = build_memory_context(memories or [])
        target_language_name = get_language_name(target_language)
        language_prompt_overlay = get_language_prompt_overlay(target_language)
        self.system_prompt = _build_conversation_system_prompt(
            student_name=student_name,
            cefr_level=cefr_level,
            native_language=get_native_language_name(native_language),
            target_language_name=target_language_name,
            user_context=user_context,
            memory_context=memory_context,
            language_prompt_overlay=language_prompt_overlay,
        )
        self.max_duration = max_duration
        self.inactivity_timeout = inactivity_timeout
        self._redis: object | None = None  # injected after construction
        self._recorded = False
        self._freemium_voice = False

        self.current_task: asyncio.Task | None = None
        # Pre-populate history from optional chat context
        if initial_context:
            self.history: list[dict] = [
                {"role": m["role"], "content": m["content"]}
                for m in initial_context
                if isinstance(m, dict)
                and m.get("role") in ("user", "assistant")
                and isinstance(m.get("content"), str)
                and m["content"].strip()
            ][-10:]
        else:
            self.history = []
        self._session_start = time.monotonic()
        self._last_activity = time.monotonic()
        self._timer_tasks: list[asyncio.Task] = []
        self._pending_saves: list[asyncio.Task] = []
        self._inactivity_warning_sent = False
        self._send_lock = asyncio.Lock()
        self._turn_id = 0
        self._client_close_reason: str | None = None

    @staticmethod
    def _fmt_exc(exc: Exception) -> str:
        return f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _task_state(task: asyncio.Task | None) -> str:
        if task is None:
            return "none"
        if task.cancelled():
            return "cancelled"
        if task.done():
            if task.exception() is not None:
                return "done:error"
            return "done"
        return "running"

    async def _send_json(self, ws: WebSocket, data: dict) -> None:
        async with self._send_lock:
            await ws.send_json(data)

    def _next_turn_id(self) -> int:
        self._turn_id += 1
        return self._turn_id

    async def _send_status(self, ws: WebSocket, turn_id: int, value: str) -> None:
        await self._send_json(ws, {"type": "status", "value": value, "turn_id": turn_id})

    @staticmethod
    def _extract_speech_text(raw_text: str) -> str:
        stripped = strip_memory_marker(raw_text)
        cleaned = ConversationPipeline._clean_sentence(stripped).strip()
        if cleaned:
            return cleaned

        fallback = stripped.strip().replace("<<MEMORY>>", "").replace("<<ENDMEMORY>>", "")
        return fallback.strip()

    async def _safe_send_bytes(self, ws: WebSocket, data: bytes) -> bool:
        try:
            async with self._send_lock:
                await ws.send_bytes(data)
            return True
        except RuntimeError as exc:
            logger.debug("[pipeline] Socket closed while sending audio: %s", exc)
            return False
        except Exception as exc:
            logger.debug("[pipeline] Audio send failed: %s", self._fmt_exc(exc))
            return False

    async def _close_ws(self, ws: WebSocket, code: int = 1000) -> None:
        logger.debug("[pipeline] Closing websocket with code=%s", code)
        async with self._send_lock:
            await ws.close(code=code)

    async def _synthesize_chunk(self, text: str) -> bytes:
        attempts = TTS_MAX_RETRIES + 1
        trace_id = uuid.uuid4().hex[:10]
        logger.info(
            "[pipeline] TTS request scheduling — trace=%s len=%d attempts=%d",
            trace_id,
            len(text),
            attempts,
        )
        for attempt in range(1, attempts + 1):
            try:
                logger.debug(
                    "[pipeline] TTS request start: len=%d chars, attempt=%d/%d",
                    len(text),
                    attempt,
                    attempts,
                )
                audio = await self.tts.synthesize(text, self._voice or None, self._stt_language)
                if not audio:
                    raise RuntimeError("TTS returned empty audio payload")
                return audio
            except TimeoutError:
                if attempt >= attempts:
                    logger.warning(
                        "[pipeline] TTS request timed out (%d/%d attempts)",
                        attempt,
                        attempts,
                    )
                    raise
                logger.warning(
                    "[pipeline] TTS request timed out (%d/%d); retrying",
                    attempt,
                    attempts,
                )
                await asyncio.sleep(TTS_RETRY_DELAY_SECONDS * attempt)
            except asyncio.CancelledError:
                logger.warning(
                    "[pipeline] TTS request cancelled: trace=%s len=%d attempt=%d",
                    trace_id,
                    len(text),
                    attempt,
                )
                raise
            except GeneratorExit:
                logger.warning(
                    "[pipeline] TTS request interrupted by GeneratorExit: trace=%s len=%d attempt=%d",
                    trace_id,
                    len(text),
                    attempt,
                )
                raise
            except Exception as exc:
                if attempt >= attempts:
                    raise
                logger.warning(
                    "[pipeline] TTS request failed (%d/%d): %s",
                    attempt,
                    attempts,
                    exc,
                )
                await asyncio.sleep(TTS_RETRY_DELAY_SECONDS * attempt)

    @staticmethod
    def _split_tts_sentences(text: str) -> list[str]:
        """Split assistant text into ordered TTS chunks using full stops."""
        chunks: list[str] = []
        start = 0
        for idx, char in enumerate(text):
            if char != ".":
                continue
            sentence = text[start : idx + 1].strip()
            if sentence:
                chunks.append(sentence)
            start = idx + 1

        tail = text[start:].strip()
        if tail:
            chunks.append(tail)

        return chunks or ([text.strip()] if text.strip() else [])

    async def _synthesize_and_send_response(
        self,
        ws: WebSocket,
        *,
        text: str,
        turn_id: int,
        transcript_payload: dict,
    ) -> tuple[int, int, bool, bool]:
        """Synthesize ordered sentence chunks and send the transcript after first audio."""
        chunks_sent = 0
        audio_bytes_sent = 0
        transcript_sent = False
        send_aborted = False

        for idx, sentence in enumerate(self._split_tts_sentences(text), start=1):
            try:
                audio = await self._synthesize_chunk(sentence)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "[pipeline] TTS sentence failed after retry: turn_id=%s sentence=%s error=%s",
                    turn_id,
                    idx,
                    self._fmt_exc(exc),
                )
                continue

            send_ok = await self._safe_send_bytes(ws, audio)
            if not send_ok:
                logger.warning(
                    "[pipeline] Audio send failed and remaining chunks are being aborted: turn_id=%s",
                    turn_id,
                )
                send_aborted = True
                break

            chunks_sent += 1
            audio_bytes_sent += len(audio)

            if not transcript_sent:
                await self._send_json(ws, transcript_payload)
                transcript_sent = True

        if chunks_sent == 0 and not transcript_sent and not send_aborted:
            logger.warning(
                "[pipeline] All TTS sentence chunks failed; publishing text-only transcript: turn_id=%s",
                turn_id,
            )
            await self._send_json(ws, transcript_payload)
            transcript_sent = True

        return chunks_sent, audio_bytes_sent, transcript_sent, send_aborted

    @staticmethod
    def _clean_sentence(raw_sentence: str) -> str:
        """Strip memory markers from a sentence buffer using pure string ops."""
        raw = raw_sentence

        # 1. Strip complete <<MEMORY>>...<<ENDMEMORY>> blocks
        while "<<MEMORY>>" in raw:
            start = raw.find("<<MEMORY>>")
            end = raw.find("<<ENDMEMORY>>", start + 10)
            if end != -1:
                raw = raw[:start] + raw[end + 13 :]
            else:
                raw = raw[:start]
                break

        # 2. Strip any orphan markers (counterpart split across sentence boundary)
        for orphan in ("<<MEMORY>>", "<<ENDMEMORY>>"):
            idx = raw.find(orphan)
            if idx != -1:
                raw = raw[:idx]

        # 3. Strip partial marker prefixes from the end of the text
        for marker in ("<<MEMORY>>", "<<ENDMEMORY>>"):
            for pi in range(len(marker), 0, -1):
                if raw.endswith(marker[:pi]):
                    raw = raw[:-pi]
                    break

        return raw.strip()

    async def _greet(self, ws: WebSocket) -> None:
        """Generate and stream an opening greeting from the assistant."""
        turn_id = self._next_turn_id()
        trigger = {
            "role": "user",
            "content": "[Session started. Greet the student warmly and naturally — one or two sentences max — and invite them to speak.]",
        }
        messages = (
            [{"role": "system", "content": self.system_prompt}] + self.history[-20:] + [trigger]
        )

        try:
            full_response = ""
            llm_stream = await self.llm.chat(messages, stream=True)
            async for chunk in llm_stream:
                token = chunk.choices[0].delta.content or ""
                full_response += token
            clean_full_response = self._extract_speech_text(full_response)
            if not clean_full_response:
                return
            await self._send_status(ws, turn_id, "thinking")

            (
                chunks_sent,
                _audio_bytes,
                transcript_sent,
                send_aborted,
            ) = await self._synthesize_and_send_response(
                ws,
                text=clean_full_response,
                turn_id=turn_id,
                transcript_payload={
                    "type": "transcript",
                    "role": "assistant",
                    "text": clean_full_response,
                    "final": True,
                    "turn_id": turn_id,
                },
            )
            if send_aborted or not transcript_sent:
                return

            self.history.append({"role": "assistant", "content": clean_full_response})
            self._pending_saves.append(
                asyncio.create_task(self._save_message("assistant", clean_full_response))
            )
            await self._send_status(ws, turn_id, "listening")
            await self._send_json(ws, {"type": "turn_complete", "turn_id": turn_id})
        except asyncio.CancelledError:
            logger.warning(
                "[pipeline] Greeting cancelled for turn_id=%s",
                turn_id,
            )
            raise
        except Exception as exc:
            logger.error("[pipeline] Greeting failed: %s", exc)

    async def run(self, ws: WebSocket) -> None:
        """Main loop: starts timeout watchers then handles incoming messages."""
        logger.info("[pipeline] Conversation loop starting")
        self._timer_tasks = [
            asyncio.create_task(self._max_duration_watcher(ws)),
            asyncio.create_task(self._inactivity_watcher(ws)),
        ]
        self.current_task = asyncio.create_task(self._greet(ws))
        try:
            while True:
                try:
                    data = await ws.receive()
                except RuntimeError:
                    # Client disconnected — ws.receive() raises RuntimeError after disconnect
                    logger.info("[pipeline] ws.receive raised RuntimeError — disconnect")
                    break
                except Exception as exc:
                    logger.error("[pipeline] ws.receive failed: %s", self._fmt_exc(exc))
                    break
                if data.get("type") == "websocket.disconnect":
                    logger.info("[pipeline] websocket.disconnect event received")
                    break
                if "bytes" in data:
                    await self.handle_audio(data["bytes"], ws)
                elif "text" in data:
                    msg = json.loads(data["text"])
                    if msg.get("type") == "client_event":
                        if msg.get("event") == "session_close_request":
                            self._client_close_reason = msg.get("reason", "manual")
                            logger.info(
                                "[pipeline] Client requested session close: reason=%s",
                                self._client_close_reason,
                            )
                            break
                        logger.debug("[pipeline] Received unknown client_event: %s", msg)
                        continue
                    if msg.get("type") == "interrupt":
                        await self.cancel_current()
                        await self._send_json(ws, {"type": "interrupted"})
        finally:
            logger.info(
                "[pipeline] Conversation loop ending: current_task=%s",
                self._task_state(self.current_task),
            )
            logger.info(
                "[pipeline] Session close reason=%s",
                self._client_close_reason or "peer_disconnect/unknown",
            )
            await self.cancel_current()
            for t in self._timer_tasks:
                t.cancel()

    async def handle_audio(self, audio_bytes: bytes, ws: WebSocket) -> None:
        self._last_activity = time.monotonic()
        self._inactivity_warning_sent = False  # reset on new activity
        logger.debug(
            "[pipeline] Audio chunk received (%d bytes); current_task=%s",
            len(audio_bytes),
            self._task_state(self.current_task),
        )
        # Barge-in: cancel ongoing response if a new audio chunk arrives
        if self.current_task and not self.current_task.done():
            logger.info(
                "[pipeline] Barge-in requested: canceling active turn before STT",
            )
            await self.cancel_current()
            logger.info("[pipeline] Barge-in: previous turn cancelled")
            await self._send_json(ws, {"type": "barge_in"})
        self.current_task = asyncio.create_task(self._process(audio_bytes, ws))

    async def _process(self, audio_bytes: bytes, ws: WebSocket) -> None:
        turn_t0 = time.perf_counter()
        turn_id = self._next_turn_id()
        stt_ms: float | None = None
        llm_ms: float | None = None
        tts_send_ms: float | None = None
        tts_bytes: int = 0
        tts_chunks_sent = 0
        assistant_transcript_sent = False
        send_aborted = False

        # 1. STT
        try:
            await self._send_status(ws, turn_id, "transcribing")
            stt_t0 = time.perf_counter()
            user_text = await self.stt.transcribe(
                audio_bytes, "audio.wav", "audio/wav", self._stt_language
            )
            stt_ms = (time.perf_counter() - stt_t0) * 1000
            logger.info("[pipeline] STT result: %r", user_text)
        except Exception as exc:
            logger.error("[pipeline] STT failed: %s", exc)
            logger.info(
                "pipeline_turn_metrics",
                stage="stt_failed",
                stt_ms=round(stt_ms, 1) if stt_ms is not None else None,
                llm_ms=None,
                tts_send_ms=None,
                tts_chunks_sent=0,
                tts_audio_bytes=0,
                turn_total_ms=round((time.perf_counter() - turn_t0) * 1000, 1),
            )
            await self._send_json(
                ws,
                {
                    "type": "error",
                    "code": "stt_failed",
                    "message": str(exc),
                    "turn_id": turn_id,
                },
            )
            return

        user_text = user_text.strip()
        if not user_text:
            logger.info("[pipeline] Empty STT result — ignoring audio chunk")
            await self._send_status(ws, turn_id, "listening")
            return

        await self._send_json(
            ws,
            {
                "type": "transcript",
                "role": "user",
                "text": user_text,
                "final": True,
                "turn_id": turn_id,
            },
        )

        # 2. Streaming LLM
        self.history.append({"role": "user", "content": user_text})
        # NOTE: user message is intentionally saved *after* a successful turn
        # (alongside the assistant reply) so no orphan rows are written on
        # LLM failures or barge-in cancellations.
        messages = [{"role": "system", "content": self.system_prompt}] + self.history[-20:]

        full_response = ""
        clean_full_response = ""
        try:
            await self._send_status(ws, turn_id, "thinking")

            llm_t0 = time.perf_counter()
            llm_stream = await self.llm.chat(messages, stream=True)
            async for chunk in llm_stream:
                token = chunk.choices[0].delta.content or ""
                full_response += token
            llm_ms = (time.perf_counter() - llm_t0) * 1000

            clean_full_response = self._extract_speech_text(full_response)
            if clean_full_response:
                tts_send_t0 = time.perf_counter()
                (
                    tts_chunks_sent,
                    tts_bytes,
                    assistant_transcript_sent,
                    send_aborted,
                ) = await self._synthesize_and_send_response(
                    ws,
                    text=clean_full_response,
                    turn_id=turn_id,
                    transcript_payload={
                        "type": "transcript",
                        "role": "assistant",
                        "text": clean_full_response,
                        "final": True,
                        "turn_id": turn_id,
                    },
                )
                tts_send_ms = (time.perf_counter() - tts_send_t0) * 1000
                if send_aborted or not assistant_transcript_sent:
                    logger.warning(
                        "[pipeline] No assistant audio was sent and turn is being aborted: turn_id=%s",
                        turn_id,
                    )
                    self.history.pop()
                    await self._send_json(
                        ws,
                        {
                            "type": "error",
                            "code": "tts_failed",
                            "message": "Failed to synthesize assistant audio.",
                            "turn_id": turn_id,
                        },
                    )
                    return
            else:
                logger.warning(
                    "[pipeline] Skipping TTS synthesis because assistant text is empty after cleaning"
                )
                self.history.pop()
                await self._send_status(ws, turn_id, "listening")
                await self._send_json(ws, {"type": "turn_complete", "turn_id": turn_id})
                return

            # Persist token usage best-effort (never blocks the response)
            self._pending_saves.append(asyncio.create_task(self._save_usage(llm_stream)))

        except asyncio.CancelledError:
            logger.warning(
                "[pipeline] Turn cancelled before completion: turn_id=%s",
                turn_id,
            )
            raise
        except (LLMTimeoutError, LLMUnavailableError, LLMError) as exc:
            logger.error("[pipeline] LLM failed: %s", exc)
            logger.info(
                "pipeline_turn_metrics",
                stage="llm_failed",
                stt_ms=round(stt_ms, 1) if stt_ms is not None else None,
                llm_ms=round(llm_ms, 1) if llm_ms is not None else None,
                tts_send_ms=round(tts_send_ms, 1) if tts_send_ms is not None else None,
                tts_chunks_sent=tts_chunks_sent,
                tts_audio_bytes=tts_bytes,
                turn_total_ms=round((time.perf_counter() - turn_t0) * 1000, 1),
            )
            await self._send_json(
                ws,
                {
                    "type": "error",
                    "code": "llm_failed",
                    "message": str(exc),
                    "turn_id": turn_id,
                },
            )
            if self.history and self.history[-1]["role"] == "user":
                self.history.pop()
            return
        except Exception as exc:
            logger.error("[pipeline] TTS failed: %s", exc)
            logger.info(
                "pipeline_turn_metrics",
                stage="tts_failed",
                stt_ms=round(stt_ms, 1) if stt_ms is not None else None,
                llm_ms=round(llm_ms, 1) if llm_ms is not None else None,
                tts_send_ms=round(tts_send_ms, 1) if tts_send_ms is not None else None,
                tts_chunks_sent=tts_chunks_sent,
                tts_audio_bytes=tts_bytes,
                turn_total_ms=round((time.perf_counter() - turn_t0) * 1000, 1),
            )
            await self._send_json(
                ws,
                {
                    "type": "error",
                    "code": "tts_failed",
                    "message": str(exc),
                    "turn_id": turn_id,
                },
            )
            if self.history and self.history[-1]["role"] == "user":
                self.history.pop()
            return

        self.history.append({"role": "assistant", "content": clean_full_response})
        # Persist both sides of the turn together — only reached on success.
        self._pending_saves.append(asyncio.create_task(self._save_message("user", user_text)))
        self._pending_saves.append(
            asyncio.create_task(self._save_message("assistant", clean_full_response))
        )

        # Extract and persist memories (best-effort, in background)
        memory_items = parse_memory_marker(full_response)
        memory_updated = False
        if memory_items and self._user_id:
            try:
                async with db_session() as db_mem:
                    saved = await save_memories(
                        db_mem,
                        self._user_id,
                        memory_items,
                        "voice",
                        study_plan_id=self._study_plan_id,
                    )
                    if saved:
                        memory_updated = True
            except Exception:
                logger.debug("[pipeline] Failed to save memories — ignored")

        logger.info("[pipeline] Turn complete — assistant: %r", clean_full_response[:120])
        logger.info(
            "pipeline_turn_metrics",
            stage="ok",
            stt_ms=round(stt_ms, 1) if stt_ms is not None else None,
            llm_ms=round(llm_ms, 1) if llm_ms is not None else None,
            tts_send_ms=round(tts_send_ms, 1) if tts_send_ms is not None else None,
            tts_chunks_sent=tts_chunks_sent,
            tts_audio_bytes=tts_bytes,
            turn_total_ms=round((time.perf_counter() - turn_t0) * 1000, 1),
        )
        await self._send_status(ws, turn_id, "listening")

        if memory_updated:
            await self._send_json(ws, {"type": "memory_updated", "turn_id": turn_id})

        await self._send_json(ws, {"type": "turn_complete", "turn_id": turn_id})

    async def _save_usage(self, stream: object) -> None:
        """Persists token usage from an LLMStream to the DB.

        Completely defensive — silently ignores any error, including:
        - stream not being an LLMStream instance
        - provider not returning usage (all fields None)
        - DB connectivity issues
        """
        if self._user_id is None:
            return
        try:
            if not isinstance(stream, LLMStream):
                return
            if stream.prompt_tokens is None and stream.completion_tokens is None:
                return
            # Lazy import to avoid circular imports
            from app.models.llm_usage import LLMUsage  # noqa: PLC0415

            async with db_session() as db:
                db.add(
                    LLMUsage(
                        user_id=self._user_id,
                        source="conversation",
                        prompt_tokens=stream.prompt_tokens,
                        completion_tokens=stream.completion_tokens,
                        total_tokens=stream.total_tokens,
                        study_plan_id=self._study_plan_id,
                    )
                )
                await db.commit()
        except Exception:
            logger.debug("[pipeline] Failed to save token usage — ignored")

    async def _save_message(self, role: str, content: str) -> None:
        """Persists a conversation transcript message to chat_history.

        Completely defensive — silently ignores any error.
        The save is sent to the background via asyncio.create_task so it never
        blocks the voice pipeline.
        """
        if self._user_id is None or self._conversation_id is None:
            return
        try:
            from sqlalchemy import update  # noqa: PLC0415

            from app.models.chat_history import ChatHistory  # noqa: PLC0415
            from app.models.conversation import Conversation  # noqa: PLC0415

            async with db_session() as db:
                db.add(
                    ChatHistory(
                        user_id=self._user_id,
                        conversation_id=self._conversation_id,
                        role=role,
                        content=content,
                        study_plan_id=self._study_plan_id,
                        target_language=self._target_language,
                    )
                )
                await db.execute(
                    update(Conversation)
                    .where(Conversation.id == self._conversation_id)
                    .values(updated_at=datetime.now(UTC).replace(tzinfo=None))
                )
                await db.commit()
        except Exception:
            logger.debug("[pipeline] Failed to save message — ignored")

    async def cancel_current(self) -> None:
        if self.current_task and not self.current_task.done():
            logger.debug(
                "[pipeline] cancel_current: cancelling task state=%s",
                self._task_state(self.current_task),
            )
            self.current_task.cancel()
            try:
                await self.current_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.debug("[pipeline] cancel_current await failed: %s", self._fmt_exc(exc))
        if self.history and self.history[-1]["role"] == "user":
            self.history.pop()

    async def cleanup(self) -> None:
        # Record actual session duration once, best-effort
        if not self._recorded:
            self._recorded = True
            elapsed = int(time.monotonic() - self._session_start)
            if self._redis is not None and self._user_id is not None and elapsed > 0:
                try:
                    await record_session_seconds(self._redis, self._user_id, elapsed)
                except Exception:
                    logger.debug("[pipeline] Failed to record session seconds — ignored")
                if self._freemium_voice:
                    try:
                        from app.services.freemium_service import record_voice_usage

                        await record_voice_usage(self._redis, self._user_id, elapsed)
                    except Exception:
                        logger.debug("[pipeline] Failed to record freemium voice seconds — ignored")
        await self.cancel_current()
        for t in self._timer_tasks:
            t.cancel()
        # Wait for any in-flight DB saves (transcripts, token usage) so they
        # are not silently cancelled when the event loop shuts down the task.
        if self._pending_saves:
            await asyncio.gather(*self._pending_saves, return_exceptions=True)
        logger.debug("[pipeline] Cleanup complete")

    # --- Timeout watchers ---

    async def _max_duration_watcher(self, ws: WebSocket) -> None:
        """Closes session after max_duration seconds, with a 60s warning."""
        warn_at = self.max_duration - WARNING_ADVANCE_SECONDS
        if warn_at > 0:
            await asyncio.sleep(warn_at)
            logger.info(
                "[pipeline] Max duration warning — %ss remaining",
                WARNING_ADVANCE_SECONDS,
            )
            await self._send_json(
                ws,
                {
                    "type": "session_warning",
                    "reason": "max_duration",
                    "remaining_seconds": WARNING_ADVANCE_SECONDS,
                },
            )
            await asyncio.sleep(WARNING_ADVANCE_SECONDS)
        else:
            await asyncio.sleep(self.max_duration)
        logger.info("[pipeline] Session ended by max_duration")
        await self._send_json(ws, {"type": "session_end", "reason": "max_duration"})
        await self._close_ws(ws, code=1000)

    async def _inactivity_watcher(self, ws: WebSocket) -> None:
        """Closes session if user is silent for inactivity_timeout seconds."""
        while True:
            await asyncio.sleep(5)  # check every 5 seconds
            elapsed = time.monotonic() - self._last_activity
            remaining = self.inactivity_timeout - elapsed

            if 0 < remaining <= WARNING_ADVANCE_SECONDS and not self._inactivity_warning_sent:
                self._inactivity_warning_sent = True
                logger.info("[pipeline] Inactivity warning — %ds remaining", int(remaining))
                await self._send_json(
                    ws,
                    {
                        "type": "session_warning",
                        "reason": "inactivity",
                        "remaining_seconds": int(remaining),
                    },
                )

            if elapsed >= self.inactivity_timeout:
                logger.info("[pipeline] Session ended by inactivity (elapsed %.0fs)", elapsed)
                await self._send_json(ws, {"type": "session_end", "reason": "inactivity"})
                await self._close_ws(ws, code=1000)
                return
