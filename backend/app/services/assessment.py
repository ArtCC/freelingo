from __future__ import annotations

from app.data.curriculum import CEFR_LEVELS
from app.schemas.assessment import (
    AnswerRecord,
    AssessmentResult,
    FreeWriteEvalRequest,
)
from app.services.language_helpers import get_language_name
from app.services.llm_adapter import (
    LLMError,
    LLMResponseError,
    llm_adapter,
)
from app.services.prompts import assessment as assessment_prompts
from app.services.prompts.assessment import (
    build_end_of_level_test_prompt,
    build_free_write_assessment_prompt,
)
from app.services.prompts.common import get_language_prompt_overlay

END_OF_LEVEL_TEST_PROMPT = assessment_prompts.END_OF_LEVEL_TEST_PROMPT
FREE_WRITE_ASSESSMENT_PROMPT = assessment_prompts.FREE_WRITE_ASSESSMENT_PROMPT


def evaluate_adaptive_quiz(answers: list[AnswerRecord]) -> AssessmentResult:
    """
    Deterministic CEFR evaluation — no LLM calls.

    answers: list of AnswerRecord(question_id, skill, difficulty, correct)
    Returns: AssessmentResult with skill_profile and overall CEFR level.

    Algorithm:
    - Group answers by CEFR difficulty level.
    - Determine highest level where score >= 0.6 with at least 2 questions.
    - Build per-skill profile (grammar, vocabulary, reading).
    - An answer marked dont_know is a declared knowledge gap: it never counts as correct, and a
      skill where the learner declared a gap on at least half of the questions is a weakness even
      when the remaining answers keep its score above the usual threshold.
    """
    level_scores: dict[str, dict] = {level: {"correct": 0, "total": 0} for level in CEFR_LEVELS}
    skill_scores: dict[str, list[int]] = {
        "grammar": [],
        "vocabulary": [],
        "reading": [],
    }
    skill_gaps: dict[str, int] = {skill: 0 for skill in skill_scores}

    for a in answers:
        # A declared gap is never knowledge, whatever the client sent alongside it.
        correct = a.correct and not a.dont_know

        level = a.difficulty.upper()
        if level in level_scores:
            level_scores[level]["total"] += 1
            if correct:
                level_scores[level]["correct"] += 1

        skill = a.skill.lower()
        if skill in skill_scores:
            skill_scores[skill].append(1 if correct else 0)
            if a.dont_know:
                skill_gaps[skill] += 1

    # Determine CEFR: highest level with >= 2 questions and >= 60% correct
    cefr_level = "A1"
    for level in CEFR_LEVELS:
        s = level_scores[level]
        if s["total"] >= 2 and s["correct"] / s["total"] >= 0.6:
            cefr_level = level

    skill_profile = {
        skill: round(sum(scores) / len(scores), 2) if scores else 0.0
        for skill, scores in skill_scores.items()
    }
    overall_score = round(sum(skill_profile.values()) / len(skill_profile), 2)
    strengths = [s for s, v in skill_profile.items() if v >= 0.65]
    weaknesses = [
        s
        for s, v in skill_profile.items()
        if v < 0.45 or (skill_scores[s] and skill_gaps[s] / len(skill_scores[s]) >= 0.5)
    ]

    return AssessmentResult(
        cefr_level=cefr_level,
        score=overall_score,
        skill_profile=skill_profile,
        strengths=strengths,
        weaknesses=weaknesses,
        analysis="",  # filled only when optional free-write is submitted
    )


async def evaluate_free_write(
    req: FreeWriteEvalRequest,
    target_language: str = "en-GB",
) -> dict:
    """Optional LLM call for the single free-write question at the end of the quiz."""
    target_language_name = get_language_name(target_language)
    prompt = build_free_write_assessment_prompt(
        preliminary_level=req.preliminary_level,
        prompt=req.writing_prompt,
        answer=req.student_answer,
        target_language_name=target_language_name,
        language_prompt_overlay=get_language_prompt_overlay(target_language),
    )
    try:
        raw = await llm_adapter.chat(
            [{"role": "system", "content": prompt}],
        )
        import json  # noqa: PLC0415

        return json.loads(raw)
    except LLMResponseError as e:
        raise LLMError(f"Free-write evaluation failed: {e}") from e
    except Exception as e:  # noqa: BLE001
        # Catches json.JSONDecodeError (not a subclass of LLMResponseError).
        # LLMTimeoutError / LLMUnavailableError are re-raised as-is since they
        # are already LLMError subclasses and the router handles them specifically.
        if isinstance(e, LLMError):
            raise
        raise LLMError(f"Free-write evaluation failed: malformed JSON response: {e}") from e


async def generate_level_test_questions(
    cefr_level: str,
    grammar_points_studied: list[str],
    vocabulary_sets_studied: list[str],
    target_language: str = "en-GB",
) -> list[dict]:
    """
    LLM-generated 20-question level completion test in the target language.
    Questions are exclusive to the studied grammar/vocabulary at cefr_level.
    """
    import json  # noqa: PLC0415

    target_language_name = get_language_name(target_language)

    idx = CEFR_LEVELS.index(cefr_level) if cefr_level in CEFR_LEVELS else 0
    next_level = CEFR_LEVELS[idx + 1] if idx + 1 < len(CEFR_LEVELS) else "higher levels"

    prompt = build_end_of_level_test_prompt(
        cefr_level=cefr_level,
        target_language_name=target_language_name,
        grammar_points_studied=", ".join(grammar_points_studied) or "all grammar for this level",
        vocabulary_sets_studied=", ".join(vocabulary_sets_studied)
        or "all vocabulary for this level",
        next_level=next_level,
        language_prompt_overlay=get_language_prompt_overlay(target_language),
    )
    try:
        raw = await llm_adapter.chat([{"role": "system", "content": prompt}])
        data = json.loads(raw)
        return data.get("questions", [])
    except LLMResponseError as e:
        raise LLMError(f"Level test generation failed: {e}") from e
    except Exception as e:  # noqa: BLE001
        # Catches json.JSONDecodeError (not a subclass of LLMResponseError).
        # LLMTimeoutError / LLMUnavailableError are re-raised as-is.
        if isinstance(e, LLMError):
            raise
        raise LLMError(f"Level test generation failed: malformed JSON response: {e}") from e
