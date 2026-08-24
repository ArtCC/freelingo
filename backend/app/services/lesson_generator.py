import json
import re
from typing import Any

from app.data.curriculum import get_curriculum
from app.schemas.lessons import (
    ExerciseContent,
    FillBlankEvaluation,
    FreeWriteEvaluation,
    LessonContent,
    PronunciationEvaluation,
)
from app.services.language_helpers import get_language_name, get_native_language_name
from app.services.llm_adapter import llm_adapter
from app.services.prompts import lesson as lesson_prompts
from app.services.prompts.common import get_language_prompt_overlay
from app.services.prompts.lesson import (
    build_fill_blank_eval_prompt,
    build_free_write_eval_prompt,
    build_lesson_generation_prompt,
    build_pronunciation_eval_prompt,
    build_regenerate_exercise_prompt,
)

LESSON_GENERATION_PROMPT = lesson_prompts.LESSON_GENERATION_PROMPT
FILL_BLANK_EVAL_PROMPT = lesson_prompts.FILL_BLANK_EVAL_PROMPT
FREE_WRITE_EVAL_PROMPT = lesson_prompts.FREE_WRITE_EVAL_PROMPT
PRONUNCIATION_EVAL_PROMPT = lesson_prompts.PRONUNCIATION_EVAL_PROMPT


PREVIOUS_LESSONS_LIMIT = 6
PREVIOUS_LESSON_SENTENCES = 3
PREVIOUS_LESSON_WORDS = 6
PREVIOUS_LESSON_TRAPS = 2
PREVIOUS_LESSON_FOCUS_CHARS = 140
PREVIOUS_LESSON_TEXT_CHARS = 120
UNIT_VOCABULARY_LIMIT = 40


def _compact(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return f"{text[: limit - 1].rstrip()}…" if len(text) > limit else text


def _as_list(value: Any) -> list[Any]:
    """Return the value only when it is a list.

    The lesson content schema types the explanation blocks as free-form dictionaries, so a model
    response can put a scalar where a list of examples, words, or traps is expected.
    """
    return value if isinstance(value, list) else []


def build_previous_lessons_summary(previous_lessons: list[dict[str, Any]]) -> str:
    """Summarize the already generated lessons of a unit.

    The summary is injected into the generation prompt so a new lesson can avoid repeating the
    explanations, example sentences, vocabulary, and common traps its siblings already used.
    """
    entries: list[str] = []
    unit_words: list[str] = []
    seen_words: set[str] = set()

    # The vocabulary of the whole unit is collected from every previous lesson; only the most
    # recent ones are described in detail, so the summary stays inside the prompt budget.
    detailed_from = max(len(previous_lessons) - PREVIOUS_LESSONS_LIMIT, 0)

    for index, previous in enumerate(previous_lessons):
        content = previous.get("content")
        content = content if isinstance(content, dict) else {}

        words = [
            _compact(item.get("word"), 40)
            for item in _as_list(content.get("vocabulary"))
            if isinstance(item, dict) and item.get("word")
        ]
        for word in words:
            key = word.casefold()
            if key not in seen_words:
                seen_words.add(key)
                unit_words.append(word)

        if index < detailed_from:
            continue

        explanation = content.get("explanation")
        explanation = explanation if isinstance(explanation, dict) else {}
        native_explanation = content.get("native_explanation")
        native_explanation = native_explanation if isinstance(native_explanation, dict) else {}

        title = _compact(previous.get("title"), 80) or "untitled"
        lesson_type = _compact(previous.get("lesson_type"), 20) or "unknown"
        lines = [f'- "{title}" ({lesson_type})']

        focus = _compact(explanation.get("text"), PREVIOUS_LESSON_FOCUS_CHARS)
        if focus:
            lines.append(f"  explained: {focus}")

        sentences = [
            _compact(example.get("sentence"), PREVIOUS_LESSON_TEXT_CHARS)
            for example in _as_list(explanation.get("examples"))
            if isinstance(example, dict) and example.get("sentence")
        ][:PREVIOUS_LESSON_SENTENCES]
        if sentences:
            lines.append(f"  example sentences used: {' | '.join(sentences)}")

        if words:
            lines.append(f"  vocabulary taught: {', '.join(words[:PREVIOUS_LESSON_WORDS])}")

        traps = [
            _compact(trap.get("mistake"), 90)
            for trap in _as_list(native_explanation.get("common_traps"))
            if isinstance(trap, dict) and trap.get("mistake")
        ][:PREVIOUS_LESSON_TRAPS]
        if traps:
            lines.append(f"  common traps listed: {' | '.join(traps)}")

        entries.append("\n".join(lines))

    if not entries:
        return ""
    summary = "\n".join(entries)
    if unit_words:
        joined = ", ".join(unit_words[:UNIT_VOCABULARY_LIMIT])
        summary = f"{summary}\n\nVocabulary already introduced in this unit: {joined}"
    return summary


def hint_reveals_answer(native_hint: str | None, correct_answer: str | None) -> bool:
    if not native_hint or not correct_answer:
        return False
    hint = native_hint.casefold()
    answers = [part.strip().casefold() for part in correct_answer.split("/")]
    for answer in answers:
        if not answer:
            continue
        if re.search(r"\s", answer) or not answer.replace("'", "").isalnum():
            if answer in hint:
                return True
            continue
        if re.search(rf"(?<!\w){re.escape(answer)}(?!\w)", hint):
            return True
    return False


def get_valid_grammar_slugs(target_language: str = "en-GB") -> set[str]:
    """Return the set of valid grammar slugs for a given target language."""
    curriculum = get_curriculum(target_language)
    return {slug for units in curriculum.values() for unit in units for slug in unit.grammar_points}


async def generate_lesson(
    cefr_level: str,
    lesson_type: str,
    topic: str,
    week: int,
    day: int,
    unit_id: str = "",
    grammar_points: list[str] | None = None,
    vocabulary_set_ids: list[str] | None = None,
    target_language: str = "en-GB",
    native_language: str | None = None,
    previous_lessons: list[dict[str, Any]] | None = None,
) -> LessonContent:
    gp_str = ", ".join(grammar_points) if grammar_points else "none specified"
    vs_str = ", ".join(vocabulary_set_ids) if vocabulary_set_ids else "general"
    target_language_name = get_language_name(target_language)
    native_language_name = get_native_language_name(native_language) if native_language else "none"
    language_prompt_overlay = get_language_prompt_overlay(target_language)
    valid_slugs = get_valid_grammar_slugs(target_language)
    valid_slugs_str = ", ".join(sorted(valid_slugs))
    prompt = build_lesson_generation_prompt(
        cefr_level=cefr_level,
        target_language_name=target_language_name,
        native_language_name=native_language_name,
        lesson_type=lesson_type,
        topic=topic,
        unit_id=unit_id or "—",
        grammar_points=gp_str,
        vocabulary_set_ids=vs_str,
        week=week,
        day=day,
        valid_slugs=valid_slugs_str,
        language_prompt_overlay=language_prompt_overlay,
        previous_lessons_summary=build_previous_lessons_summary(previous_lessons or []),
    )

    lesson = await llm_adapter.structured_output(
        [{"role": "system", "content": prompt}],
        LessonContent,
    )
    lesson.grammar_refs = [s for s in lesson.grammar_refs if s in valid_slugs]
    # Sanitize fill_blank exercises: question MUST contain ___ (the gapped sentence).
    # If the LLM put the instruction in question and the actual sentence in explanation,
    # swap them so the user always sees the gapped sentence in the UI.
    for ex in lesson.exercises:
        if ex.type == "fill_blank" and "___" not in ex.question:
            if ex.explanation and "___" in ex.explanation:
                ex.question, ex.explanation = ex.explanation, ex.question
        if hint_reveals_answer(ex.native_hint, ex.correct):
            ex.native_hint = None
    return lesson


async def regenerate_exercise(
    *,
    cefr_level: str,
    lesson_type: str,
    topic: str,
    exercise_type: str,
    lesson_explanation: dict[str, Any],
    lesson_vocabulary: list[dict[str, Any]] | None,
    invalid_exercise: dict[str, Any],
    target_language: str = "en-GB",
    native_language: str | None = None,
) -> ExerciseContent:
    target_language_name = get_language_name(target_language)
    native_language_name = get_native_language_name(native_language) if native_language else "none"
    language_prompt_overlay = get_language_prompt_overlay(target_language)
    options_schema = {
        "multiple_choice": '["option 1", "option 2", "option 3", "option 4"]',
        "fill_blank": "null",
        "free_write": '["grading criterion 1", "grading criterion 2"]',
        "pronunciation": '["short pronunciation hint"]',
    }.get(exercise_type, "null")
    prompt = build_regenerate_exercise_prompt(
        cefr_level=cefr_level,
        target_language_name=target_language_name,
        native_language_name=native_language_name,
        lesson_type=lesson_type,
        topic=topic,
        exercise_type=exercise_type,
        lesson_explanation=json.dumps(lesson_explanation or {}, ensure_ascii=False),
        lesson_vocabulary=json.dumps(lesson_vocabulary or [], ensure_ascii=False),
        invalid_exercise=json.dumps(invalid_exercise, ensure_ascii=False),
        options_schema=options_schema,
        language_prompt_overlay=language_prompt_overlay,
    )

    exercise = await llm_adapter.structured_output(
        [{"role": "system", "content": prompt}],
        ExerciseContent,
    )
    if exercise.type != exercise_type:
        raise ValueError("Regenerated exercise type does not match original type")
    if exercise.type == "fill_blank" and "___" not in exercise.question:
        if exercise.explanation and "___" in exercise.explanation:
            exercise.question, exercise.explanation = (
                exercise.explanation,
                exercise.question,
            )
    if hint_reveals_answer(exercise.native_hint, exercise.correct):
        exercise.native_hint = None
    return exercise


async def evaluate_free_write(
    cefr_level: str,
    prompt: str,
    criteria: list[str],
    answer: str,
    target_language: str = "en-GB",
    native_language: str | None = None,
) -> FreeWriteEvaluation:
    target_language_name = get_language_name(target_language)
    native_language_name = (
        get_native_language_name(native_language) if native_language else "English"
    )
    language_prompt_overlay = get_language_prompt_overlay(target_language)
    eval_prompt = build_free_write_eval_prompt(
        cefr_level=cefr_level,
        target_language_name=target_language_name,
        native_language_name=native_language_name,
        prompt=prompt,
        criteria=", ".join(criteria),
        answer=answer,
        language_prompt_overlay=language_prompt_overlay,
    )

    result = await llm_adapter.structured_output(
        [{"role": "system", "content": eval_prompt}],
        FreeWriteEvaluation,
    )
    return result


async def evaluate_pronunciation(
    cefr_level: str,
    target: str,
    transcription: str,
    target_language: str = "en-GB",
    native_language: str | None = None,
) -> PronunciationEvaluation:
    target_language_name = get_language_name(target_language)
    native_language_name = (
        get_native_language_name(native_language) if native_language else "English"
    )
    language_prompt_overlay = get_language_prompt_overlay(target_language)
    eval_prompt = build_pronunciation_eval_prompt(
        cefr_level=cefr_level,
        target_language_name=target_language_name,
        native_language_name=native_language_name,
        target=target,
        transcription=transcription,
        language_prompt_overlay=language_prompt_overlay,
    )
    result = await llm_adapter.structured_output(
        [{"role": "system", "content": eval_prompt}],
        PronunciationEvaluation,
    )
    return result


async def evaluate_fill_blank(
    cefr_level: str,
    question: str,
    correct_answer: str,
    student_answer: str,
    target_language: str = "en-GB",
    native_language: str | None = None,
) -> FillBlankEvaluation:
    target_language_name = get_language_name(target_language)
    native_language_name = (
        get_native_language_name(native_language) if native_language else "English"
    )
    language_prompt_overlay = get_language_prompt_overlay(target_language)
    eval_prompt = build_fill_blank_eval_prompt(
        cefr_level=cefr_level,
        target_language_name=target_language_name,
        native_language_name=native_language_name,
        question=question,
        correct_answer=correct_answer,
        student_answer=student_answer,
        language_prompt_overlay=language_prompt_overlay,
    )
    result = await llm_adapter.structured_output(
        [{"role": "system", "content": eval_prompt}],
        FillBlankEvaluation,
    )
    return result
