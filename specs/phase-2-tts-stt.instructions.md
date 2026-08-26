---
description: "Phase 2 specification for FreeLingo: provider-selectable TTS and STT integration with multilingual pronunciation exercises, flashcard speaking mode, and frontend audio components."
---

# Phase 2 — TTS and STT

## Objective

Provide voice synthesis (TTS) and speech recognition (STT) behind backend proxies, with independently selectable local or OpenAI providers. Users can listen to natural target-language pronunciation and practice speaking by recording their voice without exposing provider credentials to the frontend.

---

## Service architecture

```
Browser                          Backend                      Docker services
┌──────────┐    HTTP    ┌──────────────────────┐   HTTP    ┌───────────────┐
│AudioPlayer│ ────────→ │ POST /api/tts        │ ────────→ │ Kokoro-FastAPI│
│          │ ←──────── │ (audio/mpeg binary)   │ ←──────── │ :8880         │
└──────────┘            │                      │           └───────────────┘
                        │ apps/core/tts_service│
┌──────────┐    HTTP    │                      │   HTTP    ┌───────────────┐
│VoiceRec- │ ────────→ │ POST /api/stt        │ ────────→ │ Whisper ASR   │
│ order    │ ←──────── │ (multipart/form-data) │ ←──────── │ :9000         │
└──────────┘            └──────────────────────┘           └───────────────┘
```

The backend acts as the sole gateway — the frontend never calls Kokoro, faster-whisper, or OpenAI speech APIs directly. TTS and STT are always active; `TTS_PROVIDER` and `STT_PROVIDER` independently select the local or OpenAI adapter.

---

## TTS Service — Kokoro-FastAPI

### Docker service

- **Image**: `ghcr.io/remsky/kokoro-fastapi-gpu:latest` (default, CUDA GPU)
- **CPU image**: `ghcr.io/remsky/kokoro-fastapi-cpu:latest` (remove `deploy` block for CPU hosts)
- **API**: OpenAI TTS-compatible (`POST /v1/audio/speech`)
- **Parameters**: `model`, `input` (text), `voice`, `response_format` (mp3)
- **Available voices**: `af_heart`, `af_sky`, `bf_emma`, `bm_george`, and others
- **Audio format**: MP3 return
- **Performance**: GPU strongly recommended; CPU fallback works but with significant speed degradation

### Backend integration (`app/services/tts_service.py`)

The `TTSService` class wraps the Kokoro HTTP API:

- `synthesize(text, voice)` → returns raw MP3 bytes
- HTTP POST to `{base_url}/v1/audio/speech` with JSON body
- 30-second timeout
- Raises on non-2xx responses

### Backend router (`app/routers/tts.py`)

- **Endpoint**: `POST /api/tts`
- **Rate limit**: 20 requests/minute
- **Request**: `{ "text": string, "voice": string? }`
- **Response**: `audio/mpeg` binary content
- **Auth**: Requires valid access token
- **Guard**: Returns 503 if the configured TTS service is unavailable
- **Voice preview text**: OpenAI voice previews introduce the AI tutor as Lingu, using the shared `TUTOR_DISPLAY_NAME` prompt constant.

---

## STT Service — Whisper ASR

### Docker service

- **Image**: `onerahmet/openai-whisper-asr-webservice:latest-gpu` (default, CUDA GPU)
- **CPU image**: `onerahmet/openai-whisper-asr-webservice:latest` (remove `deploy` block; use smaller model)
- **API**: **NOT** OpenAI-compatible — uses custom endpoint `POST /asr?output=json&language=<iso>&task=transcribe`
- **Form field**: `audio_file` (multipart file upload with filename)
- **Default model**: `large-v3-turbo` (best speed/accuracy ratio, ~8× faster than `large-v3`)
- **Engine**: `faster_whisper` or `ctranslate2`, controlled via `STT_ENGINE` env variable

> **Important**: The STT endpoint was corrected in v1.2.0 from the nonexistent OpenAI-compatible `/v1/audio/transcriptions` to the actual `/asr` endpoint of the `onerahmet/openai-whisper-asr-webservice` image. The OpenAI API format is not supported by this service.

### Backend integration (`app/services/stt_service.py`)

The local and OpenAI STT service classes share one explicit-language contract:

- `transcribe(audio_bytes, filename, mime_type, *, language)` → returns transcribed text string; `language` is required and has no fallback
- Local HTTP POST to `POST /asr?output=json&language=<iso>&task=transcribe`; OpenAI passes the same ISO code in its transcription request
- Multipart upload with `audio_file` field
- 60-second timeout
- Raises on non-2xx responses

### Backend router (`app/routers/stt.py`)

- **Endpoint**: `POST /api/stt`
- **Rate limit**: 20 requests/minute
- **Request**: `multipart/form-data` with required `audio` and PostgreSQL-range positive integer `study_plan_id` fields
- **Response**: `{ "text": string }`
- **Auth**: Requires valid access token
- **Language resolution**: verifies the plan belongs to the user, reads its persisted BCP-47 `target_language`, and maps it to ISO 639-1
- **Errors**: 404 for a missing or foreign plan, 413 for audio over 50 MiB, 422 for invalid multipart context, and 503 when STT is unavailable

---

## Environment variables (`.env` additions)

- `TTS_PROVIDER` — Default: `local`; Purpose: Select `local` Kokoro or `openai` TTS
- `TTS_BASE_URL` — Default: `http://kokoro:8880`; Purpose: Kokoro service URL
- `TTS_VOICE` — Default: `af_heart`; Purpose: Default TTS voice
- `STT_PROVIDER` — Default: `local`; Purpose: Select `local` faster-whisper or `openai` STT
- `STT_BASE_URL` — Default: `http://whisper:9000`; Purpose: Whisper service URL
- `STT_MODEL` — Default: `large-v3-turbo`; Purpose: Whisper model (also: `tiny.en`, `small`, `medium`, `large-v3`)
- `STT_ENGINE` — Default: `faster_whisper`; Purpose: Inference engine (`faster_whisper` or `ctranslate2`)
- `OPENAI_API_KEY` — Required when either speech provider is `openai`
- `OPENAI_TTS_MODEL`, `OPENAI_TTS_VOICE`, `OPENAI_STT_MODEL` — OpenAI speech model and voice overrides

The Phase 3 voice conversation WebSocket requires both configured provider services to initialize successfully.

---

## Frontend components

### AudioPlayer (`components/ui/AudioPlayer.tsx`)

Reusable button component for TTS playback:

- Calls `POST /api/tts` with text and optional voice override
- Receives `audio/mpeg` binary
- Plays via browser `Audio` API (`new Audio(blobUrl).play()`)
- Cleans up `ObjectURL` on playback end
- Shows loading spinner during TTS generation

Used in:

- **Flashcards**: 🔊 button on each card for word pronunciation
- **Lessons**: 🔊 button on example sentences and vocabulary items
- **Pronunciation exercises**: the target sentence always has audio

### VoiceRecorder (`components/ui/VoiceRecorder.tsx`)

Reusable button component for STT recording:

- Requires the resource-owning `studyPlanId` prop
- Requests microphone via `navigator.mediaDevices.getUserMedia()` with echo cancellation, noise suppression, and automatic gain control
- Captures PCM samples with the Web Audio API, resamples to 16 kHz, and encodes a WAV upload
- Maximum recording length: configurable via `maxSeconds` prop (default 5 s); WebSocket voice conversation uses its separate continuous capture pipeline
- Stops automatically after max duration
- Captures `studyPlanId` and the result handler at recording start, then uploads WAV audio and that immutable `study_plan_id` via `POST /api/stt` as multipart/form-data
- Awaits synchronous or asynchronous parent handling of the transcribed text before returning to idle
- Stops media resources, including a permission stream that resolves after cancellation, and aborts an in-flight STT request when unmounted
- Shows recording indicator (animated red dot)

---

## Pronunciation exercises

### New exercise type: `pronunciation`

Added to the exercise mix in lesson content. Properties:

- `target_sentence`: the target-language text to pronounce
- `hint`: guidance about the sound or pattern to practice (e.g. "Focus on the 'th' sound")

User flow:

1. Student sees the target sentence
2. Presses 🔊 to hear the correct pronunciation (TTS)
3. Presses microphone button to record their own pronunciation
4. Recording and `lesson.study_plan_id` are sent to `/api/stt`; the backend derives the target language from that plan
5. Transcribed text is compared to the target sentence by the LLM
6. Score (0.0–1.0) and detailed feedback are returned

The pronunciation evaluation prompt (`PRONUNCIATION_EVAL_PROMPT` in `services/lesson_generator.py`) instructs the LLM to assess the match between expected and transcribed text, accounting for phonetic similarity and common pronunciation errors for the student's native language.

### Scoring guidelines

- 0.9–1.0 — Meaning: Excellent; Criteria: Near-native pronunciation, all phonemes correct
- 0.7–0.89 — Meaning: Good; Criteria: Minor errors, understandable
- 0.4–0.69 — Meaning: Needs work; Criteria: Several phoneme errors, still intelligible
- 0.0–0.39 — Meaning: Poor; Criteria: Mostly unintelligible or no speech detected

---

## Flashcards speaking mode

An additional review mode on the `/flashcards` page:

- Shows the native-language definition and target-language example (not the answer word)
- User speaks the word aloud
- STT transcribes the audio
- Transcription is compared to the correct word
- SM-2 quality rating derived from the match: `5` for exact match, `2` for incorrect
- Works alongside standard mode (written recall)

---

## Frontend API proxies

Both TTS and STT use dedicated Next.js Route Handlers to avoid issues with Next.js rewrites buffering or transforming binary/multipart data:

- TTS — Route Handler: `src/app/api/tts/route.ts`; Purpose: Forwards binary audio without transformation
- STT — Route Handler: `src/app/api/stt/route.ts`; Purpose: Forwards multipart form-data preserving file attachment and propagates request cancellation to the backend

Both proxies attach the `Authorization` header from the auth store and forward the response body unchanged.

---

## GPU vs CPU

Both services default to GPU images with CUDA support. For CPU-only hosts:

- Kokoro TTS — CPU image: `ghcr.io/remsky/kokoro-fastapi-cpu:latest`; Additional changes: Remove the `deploy.resources.reservations.devices` block
- Whisper STT — CPU image: `onerahmet/openai-whisper-asr-webservice:latest`; Additional changes: Remove the `deploy` block; use `STT_MODEL=small` for multilingual plans, or `tiny.en` only for English-only deployments

The `deploy` block must be removed entirely on CPU hosts — Docker will error if it references NVIDIA devices without the NVIDIA runtime installed.

---

## Phase 2 completion criteria (all met by v1.2.0)

- [x] Kokoro returns audio correctly from the backend (`POST /api/tts`)
- [x] Whisper transcribes browser-recorded audio correctly (`POST /api/stt`)
- [x] Local STT uses the correct API: `POST /asr?output=json&language=<iso>&task=transcribe`, with explicit plan-derived language (not the OpenAI API path)
- [x] Audio button functional in flashcards and lessons
- [x] Pronunciation recording and evaluation operational
- [x] Flashcard speaking mode functional
- [x] Frontend API proxies handle binary and multipart correctly
- [x] Endpoints and the conversation WebSocket reject requests when their configured speech services are unavailable
- [x] GPU used by both services (CPU-only hosts supported with compose changes)
- [x] No regressions in Phase 1 features
