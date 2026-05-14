---
description: "Complete API reference for FreeLingo: all REST endpoints and the WebSocket voice conversation endpoint, grouped by router."
applyTo: "backend/**"
---

# API Endpoints — FreeLingo

All REST endpoints are prefixed under `/api`. The WebSocket endpoint is at `/ws/conversation`.

---

## Auth — `/api/auth`

| Method | Path | Rate limit | Description |
|--------|------|------------|-------------|
| POST | `/register` | 5/min (+ invite-gated) | Creates account (respects `ALLOW_REGISTRATION`, invite token, and `BLOCKED_EMAIL_DOMAINS`). Password policy: 10–25 chars, at least one uppercase letter, one number, and one symbol. Returns `access_token` + sets httpOnly refresh cookie — no separate login step needed. Rejects blocked domains or invalid password with HTTP 422. |
| POST | `/login` | 10/min | Returns access_token (JWT, 15 min) + refresh_token in httpOnly cookie (30 days) |
| POST | `/refresh` | 20/min | Rotates refresh token, returns new access_token |
| POST | `/logout` | None | Deletes refresh token from Redis, clears cookie |
| GET | `/me` | None | Returns authenticated user profile |
| PATCH | `/me` | None | Updates display_name, email, password, target_language, conversation settings |
| POST | `/me/avatar` | None | Uploads profile avatar (JPEG/PNG, max 2 MB). Stores as base64 data URL on the user record. |
| DELETE | `/me/avatar` | None | Removes profile avatar (sets to null) |
| DELETE | `/me` | None | Deletes own account and all associated data (CASCADE). Forbidden for admin accounts. |
| GET | `/quota` | None | Returns live conversation quota status for the authenticated user (sessions this week, minutes today, minutes this week) |
| GET | `/verify-email` | None | Verifies email via one-time token (query param `token`, TTL 24h in Redis) |
| POST | `/resend-verification` | 3/min | Sends a new verification email to the authenticated user |
| POST | `/forgot-password` | 5/min | Sends password reset link to the given email. Always returns 200 (anti-enumeration). |
| POST | `/reset-password` | 5/min | Resets password using one-time token (TTL 1h in Redis) |

---

## Admin — `/api/admin`

Requires `role="admin"`. All endpoints return 403 for non-admin users.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/users` | Lists users (paginated). Query params: `skip` (default 0), `limit` (default 20, max 100), `q` (search by username or email). Returns `{items, total, skip, limit}`. |
| POST | `/users` | Creates user directly (bypasses `ALLOW_REGISTRATION`) — sends verification email if `EMAIL_ENABLED=true` |
| GET | `/users/{id}` | User detail |
| PATCH | `/users/{id}` | Edit role, is_active, is_verified, display_name, conversation quotas |
| DELETE | `/users/{id}` | Deletes account and all associated data (CASCADE) |
| GET | `/users/{id}/stats` | Usage statistics: XP, streak, lessons, exercises, tokens |
| GET | `/users/{id}/quota` | Live quota status from Redis (sessions this week, minutes today, minutes this week) |
| POST | `/invite` | Generates single-use invite link (48h Redis TTL) |

---

## Assessment — `/api/assessment`

3-step onboarding flow plus end-of-level testing.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/start` | Begins adaptive quiz (LLM-generated questions, static fallback) |
| POST | `/submit` | Legacy: submits answers for CEFR evaluation |
| POST | `/evaluate` | Deterministic CEFR evaluation (no LLM — groups by difficulty) |
| POST | `/free-write` | Evaluates free-write text for CEFR placement (LLM) |
| POST | `/complete` | Persists results, creates StudyPlan |
| GET | `/level-test/questions/{plan_id}` | Generates 20-question level test (LLM, constrained to studied content) |
| POST | `/level-test/submit` | Submits level test answers → score + recommendation |
| GET | `/level-test/result/{plan_id}` | Returns test result and recommendation (`"advance"`, `"extend"`, or `"repeat"`) |

---

## Study Plan — `/api/study-plan`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/current` | User's active plan with curriculum progress |
| POST | `/generate` | Creates new plan from CEFR level, goals, and duration |
| GET | `/today` | Today's lessons (auto-generates missing lesson content via LLM on first access) |

---

## Lessons — `/api/lessons`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/{lesson_id}` | Lesson detail with exercises |
| POST | `/{lesson_id}/start` | Marks lesson as in-progress |
| POST | `/{lesson_id}/complete` | Marks as completed, updates progress and competencies |
| POST | `/exercises/{id}/answer` | Submits answer → evaluates (MC, fill, free_write, pronunciation) → returns score + feedback |

---

## Flashcards — `/api/flashcards`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/due` | Cards pending review today (SM-2 ordering) |
| GET | `/all` | All user's flashcards |
| POST | `/` | Creates flashcard manually |
| POST | `/{card_id}/review` | Records SM-2 review (quality 0–5) |
| POST | `/generate` | Generates N flashcards via LLM with native-language translations |

---

## Chat — `/api/chat`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/conversations` | Lists user's text chat conversations |
| POST | `/conversations` | Creates new conversation |
| DELETE | `/conversations/{id}` | Deletes conversation and its messages (CASCADE) |
| GET | `/conversations/{id}/messages` | Returns messages for a conversation |
| POST | `/` | Sends message → streams AI tutor response (SSE) |
| GET | `/history` | All chat history (legacy) |

---

## Progress — `/api/progress`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/summary` | Streak, XP, skills breakdown |
| GET | `/history` | Daily progress for last 90 days |
| GET | `/competencies` | Per-unit competency scores and mastery status |

---

## TTS — `/api/tts`

| Method | Path | Rate limit | Description |
|--------|------|------------|-------------|
| POST | `/tts` | 20/min | Text → MP3 audio. Uses Kokoro TTS (local) or OpenAI TTS, controlled by `TTS_PROVIDER`. |

---

## STT — `/api/stt`

| Method | Path | Rate limit | Description |
|--------|------|------------|-------------|
| POST | `/stt` | 20/min | Audio → transcribed text. Uses faster-whisper (local) or OpenAI Whisper, controlled by `STT_PROVIDER`. |

---

## Contact — `/api/contact`

| Method | Path | Rate limit | Description |
|--------|------|------------|-------------|
| POST | `/contact` | 5/hour | Submits a contact form. Body: `{ email, subject, description }`. Forwards the message to `CONTACT_EMAIL` via SMTP. Returns 204 on success, 502 if email sending fails. No auth required. |

---

## WebSocket — `/ws/conversation`

Full-duplex voice conversation pipeline.

**Authentication**: After the WebSocket handshake is accepted, the client must send a JSON message `{"type": "auth", "token": "<access_token>"}` within 10 seconds. If missing, malformed, or invalid, the server closes the connection with code 1008.

**Message flow**: Client sends audio chunks → STT transcription → LLM generates response (streamed) → sentence-level TTS → MP3 audio chunks returned.

**Client → Server message types:**

| Type | Payload | Description |
|------|---------|-------------|
| `auth` | `{"token": "<jwt>"}` | First message — authenticates the session |
| `interrupt` | `{}` | Optional control message sent on speech-start to cancel the current assistant turn immediately |
| binary frame | raw audio bytes | WAV audio chunk from VAD |

**Server → Client message types:**

| Type | Payload | Description |
|------|---------|-------------|
| `status` | `{"value": "transcribing"|"thinking"}` | Pipeline stage update |
| `transcript` | `{"role": "user"|"assistant", "text": "...", "final": true|false}` | User final transcript or assistant partial/final transcript |
| `tts_stream_start` | `{}` | Start of assistant audio stream for current turn |
| binary frame | binary | MP3 audio chunks for assistant turn |
| `tts_stream_end` | `{}` | End of assistant audio stream for current turn |
| `barge_in` | `{}` | Current response cancelled because of new user input |
| `turn_complete` | `{}` | Assistant turn fully completed (text + audio queued/sent) |
| `session_warning` | `{"reason": "inactivity"|"max_duration", "remaining_seconds": N}` | Timeout warning at 60 s (or remaining inactivity seconds) |
| `session_end` | `{"reason": "..."}` | Session closed by server |
| `error` | `{"code": "...", "message": "..."}` | Pipeline/auth/quota/service error |

**Features:**
- **Barge-in**: new audio input cancels ongoing TTS playback
- **VAD**: browser-level voice activity detection (`@ricky0123/vad-react` + onnxruntime-web threaded WASM)
- **Gapless playback**: `AudioQueue` schedules consecutive `AudioBufferSourceNode`s
- **Session timeouts**: max duration (default 30 min) and inactivity (default 3 min), each with 60 s warning
- **In-memory history**: last 20 messages kept for LLM context during session (not persisted to DB)
- **Warmup**: `POST /api/conversation/warmup` pre-heats TTS and STT models before opening the WebSocket
- **Start safety**: frontend only opens the WebSocket after VAD/mic startup succeeds; if mic permission/init fails, session start is aborted
