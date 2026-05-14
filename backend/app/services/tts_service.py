from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from collections.abc import AsyncIterator

import httpx
import openai

logger = logging.getLogger(__name__)

_TTS_CACHE_MAX = 128  # max entries in the in-memory LRU cache


class _TTSCache:
    """Bounded LRU cache for TTS audio bytes (asyncio-safe — single-threaded event loop).

    Uses an OrderedDict so that recently-used entries are moved to the end and
    the least-recently-used entry (front of the dict) is evicted when the cache
    is full.
    """

    def __init__(self, maxsize: int = _TTS_CACHE_MAX) -> None:
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._maxsize = maxsize

    @staticmethod
    def _key(text: str, voice: str) -> str:
        return hashlib.md5(f"{voice}\x00{text}".encode(), usedforsecurity=False).hexdigest()  # noqa: S324

    def get(self, text: str, voice: str) -> bytes | None:
        k = self._key(text, voice)
        if k not in self._cache:
            return None
        self._cache.move_to_end(k)
        return self._cache[k]

    def put(self, text: str, voice: str, audio: bytes) -> None:
        k = self._key(text, voice)
        self._cache[k] = audio
        self._cache.move_to_end(k)
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)


class KokoroTTSService:
    def __init__(self, base_url: str, voice: str) -> None:
        self.base_url = base_url
        self.voice = voice
        self._cache = _TTSCache()
        # Persistent client with connection pooling and keep-alive.
        # Avoids a new TCP handshake on every TTS request.
        self._client = httpx.AsyncClient(
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            timeout=httpx.Timeout(connect=5.0, read=20.0, write=5.0, pool=5.0),
        )

    async def close(self) -> None:
        """Close the persistent HTTP client (called on app shutdown)."""
        await self._client.aclose()

    async def health(self) -> None:
        """Raise if Kokoro is unreachable."""
        r = await self._client.get(f"{self.base_url}/v1/models", timeout=5.0)
        r.raise_for_status()

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        """Return full MP3 audio bytes (LRU-cached)."""
        effective_voice = voice or self.voice
        cached = self._cache.get(text, effective_voice)
        if cached is not None:
            logger.debug("[tts-kokoro] Cache hit for %d chars", len(text))
            return cached

        response = await self._client.post(
            f"{self.base_url}/v1/audio/speech",
            json={
                "model": "kokoro",
                "input": text,
                "voice": effective_voice,
                "response_format": "mp3",
            },
        )
        response.raise_for_status()
        audio = response.content
        self._cache.put(text, effective_voice, audio)
        return audio

    async def synthesize_stream(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        """Stream MP3 chunks from Kokoro, populating the LRU cache on completion."""
        effective_voice = voice or self.voice
        cached = self._cache.get(text, effective_voice)
        if cached is not None:
            logger.debug("[tts-kokoro] Cache hit (stream) for %d chars", len(text))
            yield cached
            return

        chunks: list[bytes] = []
        async with self._client.stream(
            "POST",
            f"{self.base_url}/v1/audio/speech",
            json={
                "model": "kokoro",
                "input": text,
                "voice": effective_voice,
                "response_format": "mp3",
            },
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(chunk_size=4096):
                chunks.append(chunk)
                yield chunk

        if chunks:
            self._cache.put(text, effective_voice, b"".join(chunks))


class OpenAITTSService:
    def __init__(self, api_key: str, model: str, voice: str, speed: float = 1.0) -> None:
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            # Hard cap: avoids the 600-second default wait when api.openai.com is
            # unreachable or slow.  The pipeline layer (asyncio.timeout) provides
            # a tighter per-sentence deadline; this is the absolute safety net.
            timeout=httpx.Timeout(30.0, connect=5.0),
        )
        self.model = model
        self.voice = voice
        self.speed = speed
        self._cache = _TTSCache()

    async def close(self) -> None:
        """Close the underlying OpenAI client (called on app shutdown)."""
        await self._client.close()

    async def health(self) -> None:
        """Raise if OpenAI TTS is unreachable (lightweight models list call)."""
        await self._client.models.list()

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        """Return full MP3 audio bytes (LRU-cached)."""
        effective_voice = voice or self.voice
        cached = self._cache.get(text, effective_voice)
        if cached is not None:
            logger.debug("[tts-openai] Cache hit for %d chars", len(text))
            return cached

        chunks: list[bytes] = []
        async with self._client.audio.speech.with_streaming_response.create(
            model=self.model,
            voice=effective_voice,
            input=text,
            response_format="mp3",
            speed=self.speed,
        ) as response:
            async for chunk in response.iter_bytes(chunk_size=4096):
                chunks.append(chunk)

        audio = b"".join(chunks)
        self._cache.put(text, effective_voice, audio)
        return audio

    async def synthesize_stream(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        """Stream MP3 chunks from OpenAI TTS, populating the LRU cache on completion."""
        effective_voice = voice or self.voice
        cached = self._cache.get(text, effective_voice)
        if cached is not None:
            logger.debug("[tts-openai] Cache hit (stream) for %d chars", len(text))
            yield cached
            return

        chunks: list[bytes] = []
        async with self._client.audio.speech.with_streaming_response.create(
            model=self.model,
            voice=effective_voice,
            input=text,
            response_format="mp3",
            speed=self.speed,
        ) as response:
            async for chunk in response.iter_bytes(chunk_size=4096):
                chunks.append(chunk)
                yield chunk

        if chunks:
            self._cache.put(text, effective_voice, b"".join(chunks))
