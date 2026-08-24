---
description: "Prompt architecture reference: active LLM prompts, builders, shared blocks, variables, and maintenance rules."
---

# Prompt Architecture

This spec documents the prompt architecture after the Phase 0-2 prompt organization work.
The goal of this phase was architectural: centralize prompt text and composition while preserving
the current prompt behavior.

## Goals

- Keep active LLM prompts discoverable in one package.
- Preserve existing prompt wording unless a later prompt-improvement phase explicitly changes it.
- Separate reusable technical and tutoring blocks from service orchestration code.
- Keep service modules responsible for business flow, not prompt text ownership.
- Provide tests that catch accidental prompt-composition drift.

## Location

Prompt templates and builders live in:

```text
backend/app/services/prompts/
├── __init__.py
├── assessment.py      # CEFR placement, free-write assessment, end-of-level tests
├── common.py          # shared JSON, memory, and provider-helper prompt fragments
├── comprehension.py   # reading and listening generation prompts
├── flashcards.py      # flashcard generation and word lookup prompts
├── grammar.py         # static grammar native-help prompt
├── phrasebook.py      # static phrasebook native-help prompt
├── vocabulary.py      # static vocabulary native-help prompt
├── lesson.py          # lesson generation and exercise evaluation prompts
└── tutor.py           # text tutor and voice conversation system prompts
```

Service and router modules import builders from this package and pass runtime variables into them.

## Shared Blocks

- `JSON_ONLY_INSTRUCTION` — File: `prompts/common.py`; Purpose: Appended by `llm_adapter.structured_output()` to require a JSON-only response.
- `STRUCTURED_OUTPUT_RETRY_PROMPT` — File: `prompts/common.py`; Purpose: Used by `llm_adapter` when the first structured-output response cannot be parsed.
- `ANTHROPIC_SYSTEM_ONLY_TRIGGER` — File: `prompts/common.py`; Purpose: Minimal user message for Anthropic calls where all task instructions are system messages.
- `TUTOR_DISPLAY_NAME` — File: `prompts/common.py`; Purpose: Central display name for the AI tutor persona (`Lingu`).
- `get_language_prompt_overlay()` — File: `prompts/common.py`; Purpose: Returns concise language/variant guidance for supported and readiness target languages. Injected into tutor, voice, lesson, evaluation, flashcard, comprehension, and assessment prompts. Supports canonical BCP-47 codes plus short aliases (`de`, `fr`, `es`, `it`, `pt`, `ja`, `ko`, `zh`).
- `MEMORY_SYSTEM_INSTRUCTION_BASE` — File: `prompts/common.py`; Purpose: Shared native `save_user_memory` tool policy appended to text chat and voice tutor prompts.
- `get_memory_system_instruction()` — File: `prompts/common.py`; Purpose: Returns the language-global native memory-tool policy.

`memory_service.py` remains responsible for defining and executing the native tool, formatting untrusted
memory context, and saving and retrieving global per-user memories. It re-exports the shared instruction helper.

## Language Prompt Overlays

`get_language_prompt_overlay(target_language)` centralizes concise language-specific guidance for the
current learning languages plus backend readiness targets. The overlays preserve a single base-prompt
architecture while making room for language and regional details such as American/British English,
Peninsular Spanish, European Portuguese, Standard German, French from France, standard Italian from Italy,
standard Japanese from Japan, South Korean Korean, and Mainland China Standard Mandarin with simplified
characters.

Current status: the helper and tests exist, and the overlays are injected into text tutor, voice
conversation, lesson generation, lesson evaluation, flashcard generation/lookup, reading/listening
generation, and assessment prompts. This keeps one shared prompt architecture while adding concise
language-specific guidance across all active LLM-backed learning areas. Japanese (`ja-JP`), Korean
(`ko-KR`), and Mainland Chinese (`zh-CN`) overlays are covered by tests for prompt-readiness work and have
ISO alias support (`ja`, `ko`, `zh`).

## Active Prompt Builders

- `build_tutor_system_prompt()` — File: `prompts/tutor.py`; Caller: `routers/chat.py`; Role sent to LLM: `system`; Output expectation: Streaming conversational text response.
- `build_conversation_system_prompt()` — File: `prompts/tutor.py`; Caller: `services/conversation_pipeline.py`; Role sent to LLM: `system`; Output expectation: Streaming voice-safe tutor response.
- `build_lesson_generation_prompt()` — File: `prompts/lesson.py`; Caller: `services/lesson_generator.py`; Role sent to LLM: `system` via `structured_output`; Output expectation: `LessonContent` JSON, including optional lesson-level `native_explanation` with translated explanation, common traps, and mini-glossary, optional per-exercise `native_explanation` and `native_hint` strings, and enriched vocabulary items with optional native-language translation/example support. It composes two conditional blocks through `build_lesson_type_guidance()` and `build_previous_lessons_block()`, and takes the grammar-exercise share from `build_grammar_exercise_ratio()`.
- `build_regenerate_exercise_prompt()` — File: `prompts/lesson.py`; Caller: `services/lesson_generator.py`; Role sent to LLM: `system` via `structured_output`; Output expectation: `ExerciseContent` JSON for replacing one invalid unanswered lesson exercise with the same exercise type.
- `build_native_explanation_on_demand_prompt()` — File: `prompts/lesson.py`; Caller: `routers/lessons.py`; Role sent to LLM: `user` via `structured_output`; Output expectation: `NativeExplanationResponse` JSON for translating an existing lesson explanation on demand.
- `build_native_exercise_explanation_on_demand_prompt()` — File: `prompts/lesson.py`; Caller: `routers/lessons.py`; Role sent to LLM: `user` via `structured_output`; Output expectation: `NativeExerciseExplanationResponse` JSON for generating one missing exercise-level native explanation on demand.
- `build_native_exercise_hint_on_demand_prompt()` — File: `prompts/lesson.py`; Caller: `routers/lessons.py`; Role sent to LLM: `user` via `structured_output`; Output expectation: `NativeExerciseHintResponse` JSON for generating one missing pre-answer native hint on demand without revealing the answer.
- `build_grammar_native_help_prompt()` — File: `prompts/grammar.py`; Caller: `routers/grammar.py`; Role sent to LLM: `user` via `structured_output`; Output expectation: `GrammarNativeHelpContentResponse` JSON for native-language study support from a static grammar topic.
- `build_phrasebook_native_help_prompt()` — File: `prompts/phrasebook.py`; Caller: `routers/phrasebook.py`; Role sent to LLM: `user` via `structured_output`; Output expectation: `PhrasebookNativeHelpContentResponse` JSON for native-language usage support from a phrasebook category.
- `build_vocabulary_native_help_prompt()` — File: `prompts/vocabulary.py`; Caller: `routers/vocabulary.py`; Role sent to LLM: `user` via `structured_output`; Output expectation: `VocabularyNativeHelpContentResponse` JSON for native-language study support from a vocabulary set.
- `build_fill_blank_eval_prompt()` — File: `prompts/lesson.py`; Caller: `services/lesson_generator.py`; Role sent to LLM: `system` via `structured_output`; Output expectation: `FillBlankEvaluation` JSON.
- `build_free_write_eval_prompt()` — File: `prompts/lesson.py`; Caller: `services/lesson_generator.py`; Role sent to LLM: `system` via `structured_output`; Output expectation: `FreeWriteEvaluation` JSON.
- `build_pronunciation_eval_prompt()` — File: `prompts/lesson.py`; Caller: `services/lesson_generator.py`; Role sent to LLM: `system` via `structured_output`; Output expectation: `PronunciationEvaluation` JSON.
- `build_flashcard_generation_prompt()` — File: `prompts/flashcards.py`; Caller: `services/flashcard_sm2.py`; Role sent to LLM: `system` via `structured_output`; Output expectation: `FlashcardGenerateResponse` JSON.
- `build_word_lookup_prompt()` — File: `prompts/flashcards.py`; Caller: `services/flashcard_sm2.py`; Role sent to LLM: `system` via `structured_output`; Output expectation: `FlashcardCreate` JSON.
- `build_listening_generation_prompt()` — File: `prompts/comprehension.py`; Caller: `services/listening_service.py`; Role sent to LLM: `user` via `structured_output`; Output expectation: `ListeningGenerationResponse` JSON.
- `build_reading_generation_prompt()` — File: `prompts/comprehension.py`; Caller: `services/reading_service.py`; Role sent to LLM: `user` via `structured_output`; Output expectation: `ReadingGenerationResponse` JSON.
- `build_free_write_assessment_prompt()` — File: `prompts/assessment.py`; Caller: `services/assessment.py`; Role sent to LLM: `system`; Output expectation: Raw JSON parsed by assessment service.
- `build_end_of_level_test_prompt()` — File: `prompts/assessment.py`; Caller: `services/assessment.py`; Role sent to LLM: `system`; Output expectation: Raw JSON with `questions`.
- `build_legacy_assessment_quiz_prompt()` — File: `prompts/assessment.py`; Caller: `routers/assessment.py`; Role sent to LLM: `system` via `structured_output`; Output expectation: `LegacyQuizResponse` JSON.
- `build_legacy_assessment_eval_user_prompt()` — File: `prompts/assessment.py`; Caller: `routers/assessment.py`; Role sent to LLM: `user` via `structured_output`; Output expectation: JSON user payload for legacy assessment evaluation.

## Prompt Inventory

- Text tutor — Template: `build_tutor_system_prompt()`; Current behavior: Lingu text tutor with mandatory scope, content policy, persona lock, progress context, optional user context, optional memories, target-language-only response, language-specific overlay guidance, and no emoji/pictographic output.
- Voice tutor — Template: `build_conversation_system_prompt()`; Current behavior: Lingu voice conversation partner with the same safety core, language-specific overlay guidance, shorter spoken responses, restrained correction policy, follow-up questions, and TTS-safe plain text.
- Memory — Template: `MEMORY_SYSTEM_INSTRUCTION_BASE`; Current behavior: Allows one native `save_user_memory` tool round for a new durable student fact, stores concise self-contained facts in the user's configured native language so Settings remains readable regardless of the learning language, and requires a visible continuation after the tool result.
- Lesson generation — Template: `LESSON_GENERATION_PROMPT`; Current behavior: Generates structured lesson JSON constrained by CEFR level, target language, curriculum unit, grammar points, vocabulary sets, exercise schema, valid grammar slugs, and language-specific overlay guidance. A per-type focus block derived from `lesson_type` states what the explanation, exercise mix, and vocabulary of a `grammar`, `vocabulary`, `reading`, `writing`, `listening`, or `review` lesson must emphasise, with a generic fallback for unknown types. The same `lesson_type` sets the `grammar_exercise_ratio` of the strict constraints, so the exercise mix a focus block asks for cannot collide with the minimum share of grammar-targeting exercises. When the unit already has generated lessons, a delimited summary of them is injected with instructions not to reuse their example sentences, explanation angle, situations, or common traps; `review` lessons keep recycling the unit's material but must do it with new sentences and contexts. The router passes the user's native language so the model can also return lesson-level `native_explanation` with translated explanation, common traps, and a mini-glossary; newly generated exercises remain in the target language and may include concise native-language `native_explanation` strings and non-answer-revealing `native_hint` strings. Lesson vocabulary keeps word/definition/example in the target language and can add native-language translation, example translation, note, plus optional reading/pronunciation guide.
- Exercise regeneration — Template: `REGENERATE_EXERCISE_PROMPT`; Current behavior: Replaces one technically invalid unanswered lesson exercise using existing lesson explanation, vocabulary, and invalid exercise data as context. The replacement keeps the same exercise type, follows the same option/correct-answer constraints as lesson generation, and may include native-language support fields.
- Native lesson explanation — Template: `NATIVE_EXPLANATION_ON_DEMAND`; Current behavior: Translates an existing lesson `explanation` JSON into the user's native language for lessons at any CEFR level, preserving target-language example sentences, adding native-language common traps and mini-glossary support, and caching the result on the lesson.
- Native exercise explanation — Template: `NATIVE_EXERCISE_EXPLANATION_ON_DEMAND`; Current behavior: Generates one concise native-language clarification for an existing exercise from its type, question, correct answer, and target-language explanation, then caches it in `lesson.content.exercises[*].native_explanation`.
- Native exercise hint — Template: `NATIVE_EXERCISE_HINT_ON_DEMAND`; Current behavior: Generates one short native-language hint for an existing exercise from its type, question, options, correct answer, and target-language explanation, with explicit rules not to reveal or literally include the answer, then caches it in `lesson.content.exercises[*].native_hint`.
- Grammar native help — Template: `GRAMMAR_NATIVE_HELP_PROMPT`; Current behavior: Creates concise native-language support for static grammar topics, preserving target-language examples while generating summary, explanation, key points, common traps, mini-glossary, and example notes. The result is cached globally by resource/native-language key.
- Phrasebook native help — Template: `PHRASEBOOK_NATIVE_HELP_PROMPT`; Current behavior: Creates practical native-language support for static phrasebook categories, preserving target-language phrases while generating usage tips, register notes, phrase notes, common traps, and mini-glossary entries. The result is cached globally by resource/native-language key.
- Vocabulary native help — Template: `VOCABULARY_NATIVE_HELP_PROMPT`; Current behavior: Creates concise native-language support for static vocabulary sets, preserving target-language words and examples while generating study tips, word notes, common traps, mini-glossary entries, and practice prompts. The result is cached globally by resource/native-language key.
- Lesson fill-blank evaluation — Template: `FILL_BLANK_EVAL_PROMPT`; Current behavior: Evaluates a fill-blank answer leniently for minor spelling/case variation and contractions, with language-specific overlay guidance. Dynamic exercise fields are delimited and treated as data only.
- Lesson free-write evaluation — Template: `FREE_WRITE_EVAL_PROMPT`; Current behavior: Scores a writing answer and returns feedback plus correction objects, with language-specific overlay guidance. Dynamic exercise fields are delimited and treated as data only.
- Pronunciation evaluation — Template: `PRONUNCIATION_EVAL_PROMPT`; Current behavior: Compares target phrase to STT transcription and returns score, feedback, and correctness, with language-specific overlay guidance. Dynamic exercise fields are delimited and treated as data only.
- Flashcard generation — Template: `FLASHCARD_GEN_PROMPT`; Current behavior: Generates target-language vocabulary flashcards with native-language definition/translation, strict word cleanup rules, and centralized language-specific overlay guidance. The requested topic is delimited as data only.
- Word lookup — Template: `WORD_LOOKUP_PROMPT`; Current behavior: Generates one flashcard from a selected word and context sentence, with centralized language-specific overlay guidance. The selected word and context are delimited as data only.
- Listening generation — Template: `LISTENING_GENERATION_PROMPT`; Current behavior: Generates plain-prose listening text and five multiple-choice comprehension questions with language-specific overlay guidance and language-aware length guidance.
- Reading generation — Template: `READING_GENERATION_PROMPT`; Current behavior: Generates plain-prose reading text and five multiple-choice comprehension questions with language-specific overlay guidance and language-aware length guidance.
- Free-write assessment — Template: `FREE_WRITE_ASSESSMENT_PROMPT`; Current behavior: Evaluates placement writing with adjusted level, writing score, analysis, strengths, weaknesses, and language-specific overlay guidance. Student prompt/answer fields are delimited as data only.
- End-of-level test — Template: `END_OF_LEVEL_TEST_PROMPT`; Current behavior: Generates a 20-question test covering studied grammar and vocabulary for the current CEFR level with language-specific overlay guidance.
- Legacy assessment quiz — Template: `LEGACY_ASSESSMENT_QUIZ_PROMPT`; Current behavior: Generates an adaptive CEFR quiz for legacy assessment flow with language-specific overlay guidance.
- Legacy assessment evaluation — Template: `LEGACY_ASSESSMENT_EVAL_PROMPT` and `LEGACY_ASSESSMENT_EVAL_USER_PROMPT`; Current behavior: Evaluates legacy assessment answers with an explicit JSON quiz/answers payload, a fixed JSON response schema, and an additional language-specific system overlay when available. Answers the learner marked as "I don't know" are described as declared knowledge gaps that must never be scored as correct, in contrast with incorrect answers, which can still show partial knowledge.

## Dynamic Variables

Common variables:

- `target_language_name`: human-readable target language, derived from BCP-47 code. Regional variants are preserved where behaviourally relevant: `en-US` → `English (US)`, `en-GB` → `English (UK)`, `es-ES` → `Spanish (Spain)`, and `pt-PT` → `European Portuguese`.
- `cefr_level` or `level`: learner level.
- `native_language`: user's native language, converted from stored code to a human-readable name before prompt injection where relevant.
- `student_name`: display name or username.
- `user_context`: learning goals and bio; explicitly non-authoritative.
- `memory_context`: global per-user saved memories, escaped and explicitly treated as non-authoritative data.
- `memory_tools_enabled`: tutor and voice-tutor switch that appends the native memory-tool policy only when the corresponding LLM request actually offers `save_user_memory`; no-tools fallback and greeting prompts retain memory context without advertising the unavailable tool.
- `language_prompt_overlay`: concise language/variant guidance injected into tutor, voice tutor, lesson, evaluation, flashcard, comprehension, and assessment prompts.
- `length_guidance`: reading/listening length string derived from `language_helpers.get_comprehension_length_guidance()`, using word counts for word-spaced targets and character ranges for Japanese/Mainland Chinese.

Domain-specific variables:

- Tutor: `total_xp`, `streak`, `lessons_today`, `skills`.
- Lesson generation: `lesson_type`, `topic`, `unit_id`, `grammar_points`, `vocabulary_set_ids`, `week`, `day`, `valid_slugs`, `previous_lessons_summary` (summary of the already generated lessons of the same unit, built by `lesson_generator.build_previous_lessons_summary()`; the per-lesson detail is capped at the 6 most recent, while the vocabulary list that closes it spans every sibling), optional `native_language_name` for lesson-level and per-exercise `native_explanation`, per-exercise `native_hint`, and native-language vocabulary support.
- Exercise regeneration: `cefr_level`, `target_language_name`, `native_language_name`, `lesson_type`, `topic`, `exercise_type`, `lesson_explanation`, `lesson_vocabulary`, `invalid_exercise`, and `language_prompt_overlay`.
- Native explanation generation: `target_language_name`, `native_language_name`, and delimited source explanation JSON.
- Native exercise explanation generation: `target_language_name`, `native_language_name`, `exercise_type`, `question`, `correct_answer`, and target-language `explanation`.
- Native exercise hint generation: `target_language_name`, `native_language_name`, `exercise_type`, `question`, `options`, `correct_answer`, and target-language `explanation`.
- Grammar native help: `target_language_name`, `native_language_name`, and delimited static grammar topic JSON.
- Phrasebook native help: `target_language_name`, `native_language_name`, and delimited static phrasebook category JSON.
- Vocabulary native help: `target_language_name`, `native_language_name`, and delimited static vocabulary set JSON.
- Lesson evaluation: `question`, `correct_answer`, `student_answer`, `prompt`, `criteria`, `answer`, `target`, `transcription`.
- Flashcards: `topic`, `count`, `word`, `context`, `lang_hint` (backward-compatible builder parameter; production uses centralized `language_prompt_overlay`).
- Reading/listening: `exercise_type`, `exercise_type_desc`, `topic`, `word_count`, `length_guidance`.
- Assessment: `preliminary_level`, `next_level`, `grammar_points_studied`, `vocabulary_sets_studied`, `session_id`, `quiz`, `answers`.

## Dynamic Data Delimiters

Prompts that include user-controlled or LLM-generated exercise data wrap those fields in explicit
sentinel blocks such as `<<<STUDENT_ANSWER ... STUDENT_ANSWER`, `<<<QUESTION ... QUESTION`,
`<<<TOPIC ... TOPIC`, or `<<<CONTEXT ... CONTEXT`. The surrounding instruction states that these
fields are data only and must not override the prompt.

This delimiter pattern is currently used for:

- Lesson evaluation prompts: fill-blank, free-write, and pronunciation fields.
- Lesson generation: the summary of already generated lessons of the same curriculum unit.
- Flashcard prompts: generated topic, selected word, and context sentence.
- Grammar native help: static grammar topic JSON.
- Phrasebook native help: static phrasebook category JSON.
- Vocabulary native help: static vocabulary set JSON.
- Free-write assessment: writing prompt and student answer.

Legacy assessment evaluation sends the quiz and answers as serialized JSON inside the user message
instead of a Python object representation.

## Behavior-Critical Prompts

The following prompts are behavior-critical and should not be changed casually:

- Text tutor and voice tutor system prompts.
- Native memory-tool instruction.
- Lesson generation prompt and exercise schema.
- Fill-blank, free-write, and pronunciation evaluation prompts.
- Flashcard generation and word lookup prompts.
- Reading/listening generation prompts.
- Assessment generation/evaluation prompts.

Changes to these prompts can alter LLM output quality, safety behavior, schema validity, grading, or
student-facing language. Treat such edits as product behavior changes.

## Maintenance Rules

1. Prefer adding or editing prompt text in `backend/app/services/prompts/`, not in routers.
2. Keep service modules focused on assembling runtime variables and handling LLM responses.
3. Do not duplicate safety, JSON-only, memory, or provider-helper prompt fragments.
4. Preserve current prompt text during architecture-only refactors.
5. If a prompt change intentionally changes behavior, document the reason and expected improvement.
6. For target-language or CEFR improvements, add explicit tests proving the right block is injected.
7. For schema-producing prompts, keep `structured_output()` or explicit JSON parsing tests in place.
8. Do not remove backward-compatible constants/imports until tests and specs are updated together.
9. User-controlled or generated text inserted into a prompt should be delimited and described as
   non-authoritative data.

## Tests

Prompt architecture is covered by:

- `backend/tests/test_prompts.py` for builder/wrapper equivalence, shared block checks, target-language
  injection, dynamic-data delimiter checks, legacy assessment payload JSON, the global native-memory-tool policy, and omission of that policy when tools are disabled.
- Existing conversation pipeline prompt tests in `backend/tests/test_conversation_pipeline_service.py`.
- Existing service tests that mock LLM calls and validate parsed outputs.

Recommended validation for prompt-only architecture changes:

```bash
python3 -m compileall backend/app backend/alembic -q
./.venv/bin/pytest backend/tests/test_prompts.py backend/tests/test_conversation_pipeline_service.py -q --no-cov
```

The project-level backend test command enforces total coverage. Running only a subset can fail the
coverage threshold even when the selected tests pass.
