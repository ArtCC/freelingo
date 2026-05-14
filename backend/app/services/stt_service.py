import io
import logging

import httpx
import openai

logger = logging.getLogger(__name__)


class WhisperSTTService:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        # Persistent client with connection pooling and keep-alive.
        # Avoids a new TCP handshake on every STT request.
        # read timeout is high (60 s) because local Whisper can be slow on CPU.
        self._client = httpx.AsyncClient(
            limits=httpx.Limits(max_keepalive_connections=3, max_connections=5),
            timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0),
        )

    async def close(self) -> None:
        """Close the persistent HTTP client (called on app shutdown)."""
        await self._client.aclose()

    async def health(self) -> None:
        """Raise if Whisper ASR is unreachable."""
        r = await self._client.get(f"{self.base_url}/", timeout=5.0)
        r.raise_for_status()

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        mime_type: str = "audio/wav",
        language: str = "en",
    ) -> str:
        """Send audio to Whisper ASR and return the transcribed text.

        Compatible with onerahmet/openai-whisper-asr-webservice which exposes
        POST /asr?output=json&language=<code> (not the OpenAI /v1/audio/transcriptions path).
        """
        logger.debug("[stt] POST /asr — %d bytes, filename=%s lang=%s", len(audio_bytes), filename, language)
        response = await self._client.post(
            f"{self.base_url}/asr",
            params={"output": "json", "language": language, "task": "transcribe"},
            files={"audio_file": (filename, audio_bytes, mime_type)},
        )
        logger.debug("[stt] Response status: %s", response.status_code)
        response.raise_for_status()
        data = response.json()
        # Response: {"text": "...", ...}
        text = data.get("text", "").strip()
        logger.info("[stt] Transcribed: %r", text)
        return text


class OpenAISTTService:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model

    async def close(self) -> None:
        """Close the underlying OpenAI client (called on app shutdown)."""
        await self._client.close()

    async def health(self) -> None:
        """Raise if OpenAI STT is unreachable (lightweight models list call)."""
        await self._client.models.list()

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        mime_type: str = "audio/wav",
        language: str = "en",
    ) -> str:
        """Transcribe audio using OpenAI Whisper API."""
        audio_file = (filename, io.BytesIO(audio_bytes), mime_type)
        response = await self._client.audio.transcriptions.create(
            model=self.model,
            file=audio_file,
            language=language,
        )
        text = response.text.strip()
        logger.info("[stt-openai] Transcribed: %r", text)
        return text
