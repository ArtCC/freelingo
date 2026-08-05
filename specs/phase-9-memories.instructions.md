---
description: "Phase 9 spec - global LLM memory with native tool calling, user management, and cross-language context."
applyTo: "backend/**, frontend/**"
---

# Phase 9 - LLM Memory

## Overview

Memories are durable, global context owned by a user. Lingu can save a concise fact during text or voice conversation through the native `save_user_memory` tool, and the user can manually add, list, delete, or clear memories in Settings. The same memory collection is available in every learning language.

`study_plan_id` is nullable provenance only: it records the plan active when an AI-created memory was saved, but never scopes retrieval or management. Deleting a language deletes its study plan and sets linked memory provenance to `NULL`; it does not delete the user's memories.

The 20 most recent memories are injected into text and voice tutor prompts as escaped, untrusted background data. A successful AI save emits the existing `memory_updated` event so chat and voice can notify the user.

## Database Model

**File:** `backend/app/models/memory.py`

- `id` - Integer primary key.
- `user_id` - Required FK to `users.id` with `ON DELETE CASCADE`; indexed.
- `study_plan_id` - Nullable FK to `study_plans.id` with `ON DELETE SET NULL`; indexed provenance only.
- `content` - Required text; normalized service input is limited to 200 characters.
- `source` - Required `varchar(10)`: `chat`, `voice`, or `manual`.
- `created_at` - UTC creation timestamp used with `id` for deterministic oldest-first ordering.
- `uq_memories_user_content` - Exact unique constraint on `(user_id, content)`.

Migration `0022_memory` created the table. Phase 10 migration `0029_multi_language` added nullable plan provenance with `SET NULL`. Migration `0049_memory_user_content_unique` removes later exact duplicates per user and adds `uq_memories_user_content`.

## Memory Service

**File:** `backend/app/services/memory_service.py`

- `MAX_MEMORIES_CONTEXT = 20` - most recent memories injected into a prompt.
- `MAX_MEMORY_CHARS = 200` - maximum normalized item length.
- `MAX_MEMORIES_PER_USER = 150` - hard per-user storage cap; oldest rows are evicted first.
- `build_save_user_memory_tool()` - returns the strict native tool schema with one required `content` string and no additional properties.
- `build_memory_context(memories)` - escapes each memory and wraps the latest 20 in `<user_memories>` as untrusted data, not instructions.
- `save_memories(...)` - serializes collection mutations with a per-user row lock, normalizes and exact-deduplicates input, enforces the 150-item cap, optionally records plan provenance, and commits.
- `create_memory(...)` - creates one `manual` global memory and raises `MemoryAlreadyExistsError` for an exact duplicate.
- `execute_save_user_memory(...)` - validates and executes a native tool call, returning a structured success or error result without breaking the visible tutor response.
- `get_user_memories(db, user_id)` - returns every memory for the user, regardless of language, ordered by `created_at` and `id` ascending.
- `delete_memory(...)` - owner-scoped single deletion with an IDOR-safe not-found result and the same per-user lock used by saves.
- `clear_all_memories(...)` - deletes the user's complete global collection while holding the same per-user lock used by saves.

## Native Tool Streaming

**File:** `backend/app/services/llm_adapter.py`

`LLMAdapter.chat(..., stream=True, tools=[...], tool_executor=...)` normalizes native streaming tool calls for OpenAI-compatible providers and Anthropic:

1. The initial stream can emit visible text and one or more tool call fragments; visible text is forwarded immediately while tool metadata remains internal.
2. Tool arguments are assembled and normalized into `LLMToolCall` objects.
3. The supplied executor runs at most the first call; additional calls receive a controlled error result without being executed.
4. The adapter makes one continuation request with provider-native assistant tool-call and tool-result messages.
5. Tools are omitted from the continuation request, so only one tool round is possible.
6. Successful execution emits an immediate `LLMToolResultEvent`; visible continuation text is forwarded as soon as it arrives, while callers also retain accumulated usage and `tool_results` metadata.

Native tools require streaming and an executor. OpenAI-compatible continuation uses `assistant.tool_calls` followed by `tool` messages; Anthropic uses `tool_use` and `tool_result` content blocks.

OpenAI GPT-5.6 models use `reasoning_effort="none"` for the initial Chat Completions tool request and its continuation, because that endpoint rejects function tools with the family's default reasoning effort. This parameter is never sent to Anthropic, DeepSeek, Ollama, older OpenAI model families, or ordinary requests without tools.

Memory is best-effort. Any tool-enabled request or stream failure before visible text retries the same turn without tools and does not expose the memory failure to the user. Only explicit tool incompatibility, recognized through wrapped provider error wording, disables tools for later turns in the current voice session; transient fallbacks probe tools again next turn. Known incompatibility or continuation failure after visible text emits `LLMStreamReset` so consumers discard the partial response before a complete no-tools retry. Fallback prompts retain saved-memory context but omit `save_user_memory` instructions, and a fallback with no visible text raises `LLMResponseError`. A generic provider stream failure after visible text remains a normal LLM error when it cannot be attributed to tool handling. The first successfully completed tool-capable stream logs availability once per process; executor failures remain internal failed tool results.

## Prompt Policy

**File:** `backend/app/services/prompts/common.py`

The shared memory instruction tells Lingu to call `save_user_memory` only for a genuinely new, durable fact useful in future interactions. It forbids temporary details, uncertain inferences, summaries, instructions, and duplicates. AI-created memories are concise, self-contained facts in the user's configured native language, regardless of the language currently being learned. Chat and voice append this policy only when the request offers the native tool; greetings and no-tools fallbacks keep saved-memory context but omit the tool instruction. The tutor must continue its visible response after the tool result and must not claim success after a failed save.

The old `<<MEMORY>>...<<ENDMEMORY>>` marker parser and stream-stripping flow no longer exists.

## Text Chat

**File:** `backend/app/routers/chat.py`

Each request loads the user's global memories in an independent best-effort session, builds the untrusted context block, and enables `save_user_memory` with source `chat` and the active plan ID as optional provenance. Visible text is forwarded progressively and tool fragments remain internal. `{"response_reset": true}` clears invalid partial text before fallback tokens, while a committed save emits `{"memory_updated": true}` immediately and survives a later reset or error. Failed or skipped memory work emits no confirmation. Only a non-empty completed response is persisted; fallback failure emits an error without an assistant row. The frontend dismisses stale word selection on reset and disables selecting the active streaming response.

## Voice Conversation

**File:** `backend/app/services/conversation_pipeline.py`

Voice uses the same native tool and provider-normalized continuation with source `voice`. The pipeline refreshes the user's complete global memory collection at the start of every turn. Explicit incompatibility disables tools for the remaining WebSocket session; a transient fallback does not. Tool payloads and reset partials never enter TTS or transcripts. A successful committed save emits `{"type": "memory_updated"}` exactly once even if continuation later fails or the turn is cancelled, while failed saves emit nothing.

Text and voice render the same informational `MemorySavedToast` after a confirmed save. The toast says that Lingu saved a new memory and that it can be reviewed in Settings, uses a polite live region for assistive technology, hides after 3.5 seconds, restarts its single cleanup-safe timer, and remounts the live status so consecutive saves are announced. It does not expose the stored fact on screen or require interaction before disappearing.

## REST API

**File:** `backend/app/routers/memories.py`

All endpoints require `get_current_user`. They are not subscription-gated and are available regardless of Stripe, freemium, or maintenance state.

- `GET /api/memories` - 60/minute. Returns all global memories oldest-first.
- `POST /api/memories` - 10/minute. Body: `{content: string}` with trimmed length 1-200. Creates source `manual`, returns 201, or 409 `memory_already_exists` for an exact duplicate.
- `DELETE /api/memories/{memory_id}` - 60/minute. Returns 204 or owner-safe 404.
- `DELETE /api/memories` - 10/minute. Returns `{deleted: int}` for the complete global collection.

Schemas are `MemoryCreate`, `MemoryOut`, `MemoryListResponse`, and `ClearAllResponse` in `backend/app/schemas/memory.py`.

## Settings UI

**Files:**

- `frontend/src/app/(app)/settings/memories/page.tsx`
- `frontend/src/lib/memories.ts`
- `frontend/src/types/api.ts`
- `frontend/src/components/ui/confirm-dialog.tsx`

The dedicated Settings page explains that memories are shared across learning languages. It supports manual creation, a 200-character input limit, localized source labels, deterministic list updates, individual deletion, and clear-all confirmation. Loading, retry, duplicate, mutation, success, and error states are surfaced rather than silently ignored. Mutation controls are disabled while another mutation is active, and the confirmation dialog exposes busy/error state with focus management and keyboard containment.

All memory management and language-deletion preservation copy is translated in the ten supported UI locales.

## Limits And Configuration

No environment variables are added. The 20-context, 200-character, and 150-storage limits are constants in `memory_service.py`.

## Test Coverage

Backend and frontend tests cover the strict tool schema, escaped context, manual creation and duplicate handling, validation, ownership, global retrieval, in-batch deduplication, FIFO hard-cap behavior, immediate native text/voice result events, cancellation-safe confirmation, wrapped incompatibility wording, reset-and-fallback behavior, empty fallback rejection, one-call execution, per-session voice capability state, global cross-language behavior, language-deletion preservation, memory API helpers, robust Settings states, visible SSE reset transitions, streaming selection, and truncated SSE detection.
