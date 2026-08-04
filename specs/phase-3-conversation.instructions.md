---
description: "Phase 3 specification for FreeLingo: real-time voice conversation via WebSocket pipeline — VAD in browser (vad-react/ONNX threaded WASM), STT transcription, LLM response generation, TTS synthesis, AudioContext playback, stable turn-state handling, and configurable session timeouts."
---

# Phase 3 — Real-Time Voice Conversation

## Objective

A real-time voice conversation mode where the user speaks naturally and the AI responds in audio with conversational latency (~800 ms–1.3 s end-to-end on GPU). No push-to-talk buttons — Voice Activity Detection (VAD) automatically detects when the user has finished speaking. The entire pipeline (STT → LLM → TTS) runs through a single WebSocket connection orchestrated by the backend.

---

## Pipeline overview

```
BROWSER                                        BACKEND
┌─────────────────────┐       WebSocket       ┌───────────────────────────┐
│ Mic → VAD           │ ←──────────────────→  │ /ws/conversation          │
│  onSpeechEnd        │     audio chunks       │                           │
│  float32ToWav()     │ ────────────────────→  │ 1. STT (Whisper /asr)    │
│  WS.send(wav bytes) │                        │    WAV → text             │
│                     │     mp3 chunks          │                           │
│ AudioContext Queue  │ ←────────────────────  │ 2. LLM streaming          │
│  gapless playback   │                        │    text → response chunks │
│  barge-in cancel    │                        │                           │
└─────────────────────┘                        │ 3. Sentence splitter      │
                                               │    chunk → sentences      │
                                               │                           │
                                               │ 4. TTS (Kokoro)           │
                                               │    sentence → MP3         │
                                               │                           │
                                               │ 5. Send MP3 to browser    │
                                               │                           │
                                               │ Timeout watchers:         │
                                               │  - max duration           │
                                               │  - inactivity             │
                                               └───────────────────────────┘
```

---

## Frontend — ConversationMode

### Architecture

The `ConversationMode` component is dynamically imported with `ssr: false` (no server-side rendering) because it depends on browser-only APIs: `WebSocket`, `AudioContext`, `MediaRecorder`, and WebAssembly (for VAD).

### VAD (Voice Activity Detection)

- **Library**: `@ricky0123/vad-react` (React hooks for `@ricky0123/vad-web`)
- **Model**: Silero VAD v5 (ONNX)
- **Runtime**: onnxruntime-web **1.25.1 threaded WASM** (requires `SharedArrayBuffer`)
- **Detection**: `useMicVAD` hook with `onSpeechEnd` callback — fires automatically when the user stops speaking

**COOP/COEP headers**: Threaded WASM requires `SharedArrayBuffer`, which browsers only expose when the page has specific cross-origin isolation headers. The Next.js config adds:

- `Cross-Origin-Opener-Policy: same-origin`
- `Cross-Origin-Embedder-Policy: credentialless`

These are set globally in `next.config.ts` via the `headers()` function.

**VAD model files**: ONNX WASM binaries (`.wasm`) and model files are copied from `node_modules` to `public/vad/` by the `copy-vad-models.js` postinstall script. The script runs automatically after `npm install` and is re-executed in the Docker builder stage to ensure files are present at build time.

### Audio processing

- `float32ToWav(samples, sampleRate)`: encodes Float32Array PCM audio (16kHz mono from VAD) to WAV ArrayBuffer format for STT ingestion
- `createAudioQueue(ctx, onIdle)`: manages audio playback using Web Audio API. Schedules MP3 chunks with `AudioBufferSourceNode`, tracks pending chunks and active sources, and calls `onIdle` only after playback has fully drained. The UI uses that callback to clear the assistant speaking indicator from real playback completion.

### Barge-in support

Automatic barge-in is disabled by default in the frontend (`ENABLE_CONVERSATION_BARGE_IN=false`) to prioritise stable turn completion. When an assistant turn is active — including gaps while the backend is generating chunked TTS audio — accepted VAD speech is ignored instead of cancelling the tutor turn. The backend still supports explicit `interrupt` messages and `barge_in` handling for future/manual interruption flows.

### Transcript bubbles

Each turn (user speech and AI response) is rendered as a `TranscriptBubble` in a scrollable list. Shows:

- Role label ("You" / "AI Tutor")
- Spoken/preview text (streaming indicator while AI is generating)
- Bubbles are color-coded: user (accent) / AI (muted background)

### Session timeout UI

Two timeout mechanisms with visual warnings:

- **Max duration**: total session length (default 30 min), configurable per user
- **Inactivity**: silent period before disconnect (default 3 min), configurable per user

At T-60 seconds, a `SessionTimeoutBanner` appears with a countdown. When the timeout fires, the WebSocket sends a `session_end` message and disconnects.

---

## Backend — WebSocket endpoint

### Connection (`/ws/conversation`)

- **Protocol**: WebSocket
- **Auth**: After the WebSocket handshake is accepted, the client sends a JSON message `{"type": "auth", "token": "<access_token>"}` within 10 seconds. Sending the token in the URL is intentionally avoided to prevent it from appearing in server access logs.
- **Guard**: rejects connection with code 1008 if the auth message is missing/invalid, or with code 1011 if the configured TTS or STT service is unavailable
- **Database**: uses an async session context manager for the user lookup (reads `conversation_max_duration`, `conversation_inactivity_timeout`, and `assessment_voice_trial_used` from User model)
- **Post-assessment demo**: unsubscribed hosted users may connect with a valid `voice_trial_token` from assessment completion or the existing-plan assessment screen; the backend caps that session to `ASSESSMENT_VOICE_TRIAL_DURATION_SECONDS` (default `300`) and marks `assessment_voice_trial_used=true` when the WebSocket starts.

### Message types

- Client → Server — Type: binary; Description: WAV audio frame (float32 PCM, 16kHz mono)
- Client → Server — Type: `interrupt`; Description: Optional manual interruption message; cancels current generation
- Server → Client — Type: `status`; Description: Pipeline state (`transcribing`, `thinking`, `speaking`, `listening`)
- Server → Client — Type: `transcript`; Description: User STT result and assistant final text
- Server → Client — Type: binary; Description: MP3 audio chunk for the assistant turn
- Server → Client — Type: `barge_in`; Description: Current response cancelled, new input being processed
- Server → Client — Type: `turn_complete`; Description: Assistant turn completed server-side after audio has been generated and sent
- Server → Client — Type: `session_warning`; Description: Timeout warning (60 s remaining)
- Server → Client — Type: `session_end`; Description: Session terminated by timeout
- Server → Client — Type: `error`; Description: Pipeline error with message

---

## Pipeline implementation (`app/services/conversation_pipeline.py`)

### Initialization

On WebSocket connect:

1. Decode JWT, fetch user from DB
2. Read user's `conversation_max_duration` and `conversation_inactivity_timeout` from the User model
3. Build system prompt with conversation partner persona (same CEFR-aware, no-emoji rule as chat tutor)
4. Start timeout watchers

### Main loop

1. **Start greeting task**: generate the initial assistant greeting as a cancellable background task while the receive loop starts immediately
2. **Receive audio**: read binary frame from WebSocket, reset inactivity timer
3. **Barge-in check**: if an explicit interrupt/new audio arrives while a backend task is active, cancel it and send `barge_in` so the client can stop playback. The current frontend ignores VAD detections during active assistant turns.
4. **STT**: send WAV bytes to STT service → get transcribed text; empty/whitespace STT results are ignored and do not trigger LLM/TTS
5. **Context building**: prepend system prompt + last 20 messages (in-memory)
6. **Memory refresh and LLM response**: reload the user's global memories for this turn, inject the latest 20 as untrusted context, and collect the assistant response from the normalized LLM stream. Lingu may execute one native `save_user_memory` tool round with the active plan ID retained only as provenance, then continue the visible response.
7. **TTS synthesis**: split the complete assistant response on full stops and synthesize ordered sentence chunks sequentially
8. **Send audio first**: send each MP3 binary frame to the browser as soon as that sentence audio is ready
9. **Send transcript**: send the complete AI text as final `transcript` immediately after the first audio chunk is generated and sent, avoiding visible text without associated audio
10. **Append to history/persist**: store the user+assistant exchange in memory and persist successful turns to `chat_history`

Native tool payloads are never sent to TTS or transcript output. A successful save sends `memory_updated` before `turn_complete`, and the next turn immediately sees the refreshed global collection, including manual memories and memories created while another learning language was active.

All server writes to the WebSocket are serialized through a single send lock. This prevents timeout watchers, TTS sender tasks, transcript events, and close frames from writing concurrently to the same connection.

### Assistant text/audio ordering

Assistant text is not sent to the frontend before at least one TTS audio chunk succeeds unless all sentence-level TTS attempts fail. The backend first generates the full LLM response, splits it into sentence chunks using full stops, synthesizes each chunk in order, sends the first successful binary audio frame, and only then emits the complete final assistant `transcript`. If every TTS chunk fails after its retry, the backend publishes the complete assistant transcript as a text-only fallback and completes the tutor turn. This avoids showing text ahead of available audio in the normal path, while still surfacing the tutor response if voice synthesis is unavailable for that turn.

### Timeout watchers

Two asyncio tasks run concurrently with the main pipeline loop:

- Max duration — Default: 1800 s (30 min); User-configurable: `conversation_max_duration` (from user table); Warning: 60 s warning via `session_warning` message
- Post-assessment demo duration — 300 s (5 min), enforced by backend regardless of the user's normal `conversation_max_duration`.
- Inactivity — Default: 180 s (3 min); User-configurable: `conversation_inactivity_timeout` (from user table); Warning: 60 s warning via `session_warning` message

The inactivity timer resets on each received audio chunk. When either timeout fires, a `session_end` message is sent and the WebSocket connection is closed cleanly.

### Structured logging

Pipeline events are logged with structured prefixes:

- `[conversation]` — connection lifecycle (connect, disconnect, auth errors)
- `[pipeline]` — flow events (STT completed, sentence flush, barge-in, timeout)
- `[stt]` — STT request/response details

Log level is controlled by the `LOG_LEVEL` environment variable (default `INFO`). Set to `DEBUG` for detailed pipeline tracing.

### Error handling

- `RuntimeError` from `ws.receive()` on client disconnect: caught and handled gracefully (no crash)
- STT failures: send error message to client, do not disconnect
- Empty STT results: ignore the audio chunk and return to listening without generating an assistant reply
- LLM failures: send error message, continue loop
- TTS failures: each sentence chunk has one retry; failed chunks are skipped so later chunks can still play. If every sentence chunk fails, the complete assistant transcript is published as a text-only fallback and the turn completes normally.
- Total STT → response latency target: < 2 s on GPU, < 4 s on CPU

### Conversation history

Voice conversations are **persisted incrementally** to the same `chat_history` table used by text chats. Each user utterance (STT result) and each completed assistant response is saved via `asyncio.create_task` as a `ChatHistory` row linked to a `Conversation` record with `source='voice'`. This makes voice sessions visible and reviewable in the tutor chat sidebar alongside text conversations — users can click a past voice session to read the full transcript, or continue it in voice mode.

---

## Configuration per user

Users configure their voice conversation preferences from `/settings`:

- Conversation max duration — Default: 30 min; Range: 1–60 min; Purpose: Total session length
- Conversation inactivity timeout — Default: 3 min; Range: 1–10 min; Purpose: Silence before auto-disconnect

Settings are stored in the User model (`conversation_max_duration`, `conversation_inactivity_timeout` columns) and updatable via `PATCH /api/auth/me`. The WebSocket reads them on each new connection.

---

## Frontend dependencies

- `@ricky0123/vad-react` — Version: ^0.0.36; Purpose: React hooks for VAD (wraps vad-web)
- `@ricky0123/vad-web` — Version: ^0.0.30; Purpose: VAD WebAssembly engine (Silero VAD v5 ONNX)
- `onnxruntime-web` — Version: 1.25.1 (threaded WASM); Purpose: ONNX model runtime for VAD
- Web Audio API — Version: Browser built-in; Purpose: Gapless audio playback via AudioContext
- MediaRecorder API — Version: Browser built-in; Purpose: Microphone stream capture

---

## Deployment notes

- **`NEXT_PUBLIC_API_URL`**: passed as Docker build ARG and baked at `next build` so the WebSocket URL resolves correctly, even on separate-subdomain deployments
- **CI/CD**: the `NEXT_PUBLIC_API_URL` secret is wired into the GitHub Actions `docker-publish.yml` frontend build step
- **VAD models in Docker**: the `copy-vad-models.js` postinstall script is re-executed in the Docker builder stage after `COPY frontend/` to ensure `.wasm` and `.mjs` files are present in the build output

---

## Phase 3 completion criteria (all met by v1.2.1)

- [x] WebSocket `/ws/conversation` accepts connections with JWT auth
- [x] WebSocket rejects connections if TTS or STT is disabled
- [x] Full STT → LLM → TTS pipeline works end-to-end
- [x] VAD automatically detects speech start/end (no push-to-talk)
- [x] Barge-in protocol supported; automatic frontend barge-in is disabled by default for stability
- [x] Assistant transcript is emitted only after the first successful TTS audio chunk has been generated and sent
- [x] Audio playback via `AudioQueue` tracks real queue idle state before clearing speaking UI
- [x] COOP + COEP headers enable `SharedArrayBuffer` for threaded ONNX WASM
- [x] Session timeout watchers (max duration + inactivity) with 60 s warnings
- [x] Timeout settings configurable per user from `/settings`
- [x] Structured logging across the pipeline (`LOG_LEVEL` controlled)
- [x] `NEXT_PUBLIC_API_URL` baked at build time for correct WebSocket URL resolution
- [x] VAD model files copied to `public/vad/` via postinstall script
- [x] No regressions in Phase 1 and Phase 2 features
