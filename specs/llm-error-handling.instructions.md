---
description: "LLM error handling strategy for FreeLingo: failure mode taxonomy, retry logic, context overflow mitigation, user-facing error messages, and HTTP status code mapping for all LLM providers."
applyTo: "backend/app/services/llm_adapter.py, backend/app/services/*.py"
---

# LLM Error Handling — FreeLingo

## Failure scenarios

The LLM can fail in multiple ways. Every endpoint that calls the LLM must handle these scenarios gracefully:

- \***\*Malformed JSON** — LLM returns invalid or unparseable JSON for `structured_output`\*\* — Likelihood: High (especially Ollama with small models). Impact: Blocks quiz/plan/lesson/flashcard generation
- \***\*Timeout** — LLM takes > 120 s to respond (common on CPU-only Ollama)\*\* — Likelihood: Medium (CPU-only). Impact: Blocks any LLM-dependent request
- \***\*Empty response** — LLM returns no content (null or empty string)\*\* — Likelihood: Low. Impact: Blocks generation, user sees no progress
- \***\*Hallucinated schema** — JSON response has wrong structure, missing fields, or extra fields\*\* — Likelihood: Medium. Impact: Causes Pydantic validation failure
- \***\*Context overflow** — prompt exceeds model token limit (especially Gemma 3 12B, Ollama)\*\* — Likelihood: Medium (long conversations). Impact: Blocks chat, assessment with large context
- \***\*Service unavailable** — Ollama or API down, unreachable\*\* — Likelihood: Low (local) / Medium (API). Impact: Blocks all LLM-dependent features
- \***\*Rate limited** — OpenAI, Anthropic, or DeepSeek quota exceeded\*\* — Likelihood: Medium (external APIs). Impact: Blocks requests temporarily

---

## Error taxonomy

Custom exception hierarchy in `llm_adapter.py`:

- `LLMError` — Parent: `Exception`; Raised when: Base class for all LLM errors
- `LLMTimeoutError` — Parent: `LLMError`; Raised when: Request exceeds 120 s timeout after all retries
- `LLMUnavailableError` — Parent: `LLMError`; Raised when: Connection error or rate limit from provider
- `LLMResponseError` — Parent: `LLMError`; Raised when: Malformed response, empty content, invalid JSON, missing fields. Carries `raw_response` for debugging
- `LLMContextOverflowError` — Parent: `LLMError`; Raised when: Prompt exceeds model's max context tokens

---

## Retry strategy

The LLM adapter implements automatic retry for transient errors:

- **Max retries**: 2 (up to 3 total attempts)
- **Backoff**: exponential — delay = 2 s × (attempt + 1): 2 s, then 4 s
- **Timeout per attempt**: 120 seconds
- **Retryable errors**: timeouts, connection errors, rate limits (from provider)
- **Non-retryable errors**: malformed JSON (handled separately with correction prompt), context overflow (prevention is better)

### Retry flow

```
Attempt 1 ──→ fails (timeout/connection/rate limit)
    ↓ 2 s delay
Attempt 2 ──→ fails
    ↓ 4 s delay
Attempt 3 ──→ fails → raise appropriate LLM*Error
```

---

## Structured output recovery

For providers that don't support native structured output (Ollama, DeepSeek), structured JSON is obtained via a two-step process:

1. **First attempt**: Send the prompt with an appended instruction to return ONLY valid JSON (no markdown fences, no extra text). Parse the response.
2. **On parse failure**: Strip markdown code fences if present (`json ... `). Attempt JSON decode and Pydantic validation.
3. **Retry with correction**: If step 2 fails, send a follow-up message telling the LLM exactly what was wrong ("That response was not valid JSON. Error: ...") and request pure JSON again.
4. **If retry also fails**: Raise `LLMResponseError` with the raw response for debugging.

For providers with native structured output (OpenAI, Anthropic via `beta.chat.completions.parse`), the API handles schema enforcement natively.

## Native tool recovery

Memory tools are optional capabilities and must not break text or voice tutoring:

- OpenAI GPT-5.6 requests that include native tools use Chat Completions with `reasoning_effort="none"`, as required for function tools on that endpoint. Other providers and model families do not receive this parameter.
- A known tool incompatibility is non-fatal and is not retried as the same invalid request.
- Any tool-enabled request or stream failure before visible output retries the original turn without tools. The capability issue is logged with provider, model, and reason at `INFO` and is not exposed to the user.
- The first tool-capable stream that completes successfully logs `Native tools available for provider=... model=...` once per process, making positive capability visible without producing one entry per turn.
- Voice remembers the fallback only for the current WebSocket session and omits tools on later turns; a new session probes support again.
- A failed tool continuation retries without tools before visible output. After partial continuation output, the partial response is kept to avoid both duplication and a user-visible turn failure.
- A persistence or executor failure is returned only to the model as a failed tool result; the visible response continues without a memory confirmation event.

---

## Context overflow mitigation

Each provider has a maximum context window. The adapter tracks these limits and applies message trimming before every call:

- Ollama — 8192 (varies per model — Gemma 3 12B: 8192)
- OpenAI — 128,000
- DeepSeek — 128,000
- Anthropic — 200,000

**Trimming algorithm**: Estimate token count as `len(content) / 4` (rough heuristic for English). If total exceeds the limit, drop the oldest user/assistant messages first, always preserving:

- The system message
- The last 2 exchanges (user + assistant)

This is a proactive strategy — `LLMContextOverflowError` is declared in the exception hierarchy but the trimming prevents it from ever being raised.

---

## HTTP status code mapping

Each LLM error type maps to a specific HTTP status and user-facing message:

- Malformed JSON after retry — HTTP Status: 502 Bad Gateway; User Message: "The AI returned an invalid response. Please try again."
- Timeout (> 120 s, all retries exhausted) — HTTP Status: 504 Gateway Timeout; User Message: "The AI took too long. Check that Ollama is running or try a smaller model."
- Service unreachable — HTTP Status: 503 Service Unavailable; User Message: "AI service is not reachable. Make sure Ollama is running."
- Provider rate limited — HTTP Status: 429 Too Many Requests; User Message: "Too many requests to the AI provider. Please wait a moment."
- Context overflow — HTTP Status: 413 Payload Too Large; User Message: "The conversation is too long. Start a new session."
- Empty response — HTTP Status: 502 Bad Gateway; User Message: "The AI returned no content. Try rephrasing your request."

---

## Service-layer integration

Every service that calls the LLM (assessment, study_plan_generator, lesson_generator, flashcard_sm2, chat, conversation_pipeline) wraps its calls in try/except blocks that catch the LLM error hierarchy and translate to appropriate HTTP exceptions or WebSocket error messages:

- **REST endpoints**: catch → log error → raise `HTTPException` with appropriate status code
- **SSE chat stream**: catch within the async generator → yield `data: [ERROR] ...\n\n` in the SSE stream
- **WebSocket conversation**: catch → send `{"type": "error", "message": "..."}` and continue (does not disconnect)

All errors are logged at the service layer with the raw response attached (for `LLMResponseError`) to enable debugging.

---

## Anthropic-specific handling

Anthropic's SDK (`AsyncAnthropic`) has a different API shape than the OpenAI-compatible clients:

- `system` message is extracted from the message list and passed as a separate parameter (Anthropic API convention)
- Maximum tokens parameter: always 4096 (controllable, hardcoded default)
- Response format: `response.content[0].text` (not `response.choices[0].message.content` as in OpenAI)
- Streaming: same async generator pattern, but chunk structure differs internally

These differences are abstracted inside the adapter — the rest of the application is unaware of which provider is active.
