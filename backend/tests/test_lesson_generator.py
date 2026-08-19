"""Unit tests for lesson generator service helpers and LLM-backed functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.lessons import (
    ExerciseContent,
    FillBlankEvaluation,
    FreeWriteEvaluation,
    LessonContent,
    PronunciationEvaluation,
)


class TestGetValidGrammarSlugs:
    def test_english_returns_non_empty_set(self):
        from app.services.lesson_generator import get_valid_grammar_slugs

        slugs = get_valid_grammar_slugs("en-GB")
        assert isinstance(slugs, set)
        assert len(slugs) > 0

    def test_spanish_returns_non_empty_set(self):
        from app.services.lesson_generator import get_valid_grammar_slugs

        slugs = get_valid_grammar_slugs("es-ES")
        assert isinstance(slugs, set)
        assert len(slugs) > 0

    def test_french_returns_non_empty_set(self):
        from app.services.lesson_generator import get_valid_grammar_slugs

        slugs = get_valid_grammar_slugs("fr")
        assert isinstance(slugs, set)
        assert len(slugs) > 0


class TestGenerateLesson:
    @pytest.mark.asyncio
    async def test_generates_lesson_with_mocked_llm(self):
        from app.services.lesson_generator import generate_lesson

        mock_lesson = LessonContent(
            lesson_type="grammar",
            title="Present Simple",
            cefr_level="A1",
            unit_id="a1_unit_1",
            explanation={
                "text": "The present simple is used for habits.",
                "key_points": ["It describes routines.", "It uses base form."],
                "examples": [{"sentence": "I walk every day.", "note": "Habitual action"}],
            },
            exercises=[
                ExerciseContent(
                    type="multiple_choice",
                    question="She ___ to school.",
                    options=["go", "goes", "going", "went"],
                    correct="goes",
                    explanation="Third person singular uses -es.",
                ),
                ExerciseContent(
                    type="fill_blank",
                    question="I ___ to the park every Sunday.",
                    options=None,
                    correct="go",
                    explanation="Use base form after 'I'.",
                ),
            ],
            vocabulary=[
                {
                    "word": "walk",
                    "definition": "caminar",
                    "example": "I walk to school.",
                }
            ],
            grammar_refs=["present-simple"],
        )

        with patch(
            "app.services.lesson_generator.llm_adapter.structured_output",
            AsyncMock(return_value=mock_lesson),
        ):
            result = await generate_lesson(
                cefr_level="A1",
                lesson_type="grammar",
                topic="Present Simple",
                week=1,
                day=1,
                unit_id="a1_unit_1",
                grammar_points=["present-simple"],
                target_language="en-GB",
            )

        assert result.lesson_type == "grammar"
        assert result.title == "Present Simple"
        assert len(result.exercises) == 2
        assert result.grammar_refs == ["present-simple"]

    @pytest.mark.asyncio
    async def test_sanitizes_fill_blank_when_question_missing_blank(self):
        from app.services.lesson_generator import generate_lesson

        mock_lesson = LessonContent(
            lesson_type="grammar",
            title="Fill Blank",
            cefr_level="A1",
            unit_id="a1_unit_1",
            explanation={"text": "test", "key_points": ["test"], "examples": []},
            exercises=[
                ExerciseContent(
                    type="fill_blank",
                    question="Choose the correct word:",
                    options=None,
                    correct="is",
                    explanation="___ a cat. (to be)",
                ),
            ],
            vocabulary=[],
            grammar_refs=[],
        )

        with patch(
            "app.services.lesson_generator.llm_adapter.structured_output",
            AsyncMock(return_value=mock_lesson),
        ):
            result = await generate_lesson(
                cefr_level="A1",
                lesson_type="grammar",
                topic="Test",
                week=1,
                day=1,
                target_language="en-GB",
            )

        question = result.exercises[0].question
        assert "___" in question
        assert "a cat" in question

    def test_rejects_multiple_choice_without_options(self):
        with pytest.raises(ValueError, match="multiple_choice exercises must include"):
            ExerciseContent(
                type="multiple_choice",
                question="Choose the correct answer.",
                options=[],
                correct="geht",
            )

    def test_rejects_multiple_choice_correct_answer_outside_options(self):
        with pytest.raises(ValueError, match="correct answer must match"):
            ExerciseContent(
                type="multiple_choice",
                question="Choose the correct answer.",
                options=["gehe", "gehst", "gehen"],
                correct="geht",
            )

    def test_rejects_exercise_without_question(self):
        with pytest.raises(ValueError, match="must include a question"):
            ExerciseContent(
                type="free_write",
                question=" ",
                options=None,
                correct="A short model answer.",
            )

    def test_rejects_fill_blank_without_blank(self):
        with pytest.raises(ValueError, match="fill_blank exercises must include"):
            ExerciseContent(
                type="fill_blank",
                question="Complete the sentence.",
                options=None,
                correct="ist",
                explanation="Use the verb sein.",
            )

    @pytest.mark.asyncio
    async def test_filters_invalid_grammar_refs(self):
        from app.services.lesson_generator import (
            generate_lesson,
            get_valid_grammar_slugs,
        )

        _ = get_valid_grammar_slugs("en-GB")

        mock_lesson = LessonContent(
            lesson_type="grammar",
            title="Test",
            cefr_level="A1",
            unit_id="a1_unit_1",
            explanation={"text": "test", "key_points": ["test"], "examples": []},
            exercises=[],
            vocabulary=[],
            grammar_refs=["valid-slug", "made-up-slug-xyz-123"],
        )

        with patch(
            "app.services.lesson_generator.llm_adapter.structured_output",
            AsyncMock(return_value=mock_lesson),
        ):
            result = await generate_lesson(
                cefr_level="A1",
                lesson_type="grammar",
                topic="Test",
                week=1,
                day=1,
                target_language="en-GB",
            )

        assert "made-up-slug-xyz-123" not in result.grammar_refs

    def test_hint_reveals_answer_detects_literal_answer(self):
        from app.services.lesson_generator import hint_reveals_answer

        assert hint_reveals_answer("Piensa en la forma bin.", "bin") is True
        assert hint_reveals_answer("Fíjate en el sujeto y el verbo.", "bin") is False
        assert hint_reveals_answer("Busca una frase completa.", "in") is False
        assert hint_reveals_answer("La preposición es in.", "in") is True


class TestEvaluateFreeWrite:
    @pytest.mark.asyncio
    async def test_evaluates_free_write(self):
        from app.services.lesson_generator import evaluate_free_write

        mock_eval = FreeWriteEvaluation(
            score=0.85,
            feedback="Good job!",
            corrections=[
                {
                    "original": "I goes",
                    "corrected": "I go",
                    "explanation": "Use base form.",
                }
            ],
        )

        with patch(
            "app.services.lesson_generator.llm_adapter.structured_output",
            AsyncMock(return_value=mock_eval),
        ):
            result = await evaluate_free_write(
                cefr_level="A1",
                prompt="Describe your day.",
                criteria=["use present simple", "at least 3 sentences"],
                answer="I go to school. I study. I play.",
                target_language="en-GB",
            )

        assert result.score == 0.85
        assert len(result.corrections) == 1
        assert result.corrections[0]["corrected"] == "I go"


class TestEvaluatePronunciation:
    @pytest.mark.asyncio
    async def test_evaluates_pronunciation(self):
        from app.services.lesson_generator import evaluate_pronunciation

        mock_eval = PronunciationEvaluation(
            score=0.9,
            feedback="Great pronunciation!",
            is_correct=True,
        )

        with patch(
            "app.services.lesson_generator.llm_adapter.structured_output",
            AsyncMock(return_value=mock_eval),
        ):
            result = await evaluate_pronunciation(
                cefr_level="A1",
                target="Hello, how are you?",
                transcription="Hello, how are you?",
                target_language="en-GB",
            )

        assert result.is_correct is True
        assert result.score == 0.9

    @pytest.mark.asyncio
    async def test_evaluates_pronunciation_incorrect(self):
        from app.services.lesson_generator import evaluate_pronunciation

        mock_eval = PronunciationEvaluation(
            score=0.3,
            feedback="Try again.",
            is_correct=False,
        )

        with patch(
            "app.services.lesson_generator.llm_adapter.structured_output",
            AsyncMock(return_value=mock_eval),
        ):
            result = await evaluate_pronunciation(
                cefr_level="B1",
                target="Where is the station?",
                transcription="Where is station",
                target_language="en-GB",
            )

        assert result.is_correct is False
        assert result.score == 0.3


class TestEvaluateFillBlank:
    @pytest.mark.asyncio
    async def test_evaluates_fill_blank_correct(self):
        from app.services.lesson_generator import evaluate_fill_blank

        mock_eval = FillBlankEvaluation(
            is_correct=True,
            score=1.0,
            feedback="Correct!",
        )

        with patch(
            "app.services.lesson_generator.llm_adapter.structured_output",
            AsyncMock(return_value=mock_eval),
        ) as mock_structured:
            result = await evaluate_fill_blank(
                cefr_level="A1",
                question="I ___ a student.",
                correct_answer="am",
                student_answer="am",
                target_language="en-GB",
                native_language="es",
            )

        assert result.is_correct is True
        assert result.score == 1.0
        prompt = mock_structured.await_args.args[0][0]["content"]
        assert "Student native language: Spanish" in prompt
        assert "Write all feedback in Spanish" in prompt

    @pytest.mark.asyncio
    async def test_evaluates_fill_blank_incorrect(self):
        from app.services.lesson_generator import evaluate_fill_blank

        mock_eval = FillBlankEvaluation(
            is_correct=False,
            score=0.0,
            feedback="The correct answer is 'am'.",
        )

        with patch(
            "app.services.lesson_generator.llm_adapter.structured_output",
            AsyncMock(return_value=mock_eval),
        ):
            result = await evaluate_fill_blank(
                cefr_level="A1",
                question="I ___ a student.",
                correct_answer="am",
                student_answer="is",
                target_language="en-GB",
            )

        assert result.is_correct is False
        assert result.score == 0.0


class TestBuildPreviousLessonsSummary:
    def test_returns_empty_string_without_previous_lessons(self):
        from app.services.lesson_generator import build_previous_lessons_summary

        assert build_previous_lessons_summary([]) == ""

    def test_summarizes_explanation_examples_vocabulary_and_traps(self):
        from app.services.lesson_generator import build_previous_lessons_summary

        summary = build_previous_lessons_summary(
            [
                {
                    "title": "Perfekt — Lektion 1",
                    "lesson_type": "grammar",
                    "content": {
                        "explanation": {
                            "text": "Das Perfekt bildet man mit haben oder sein.",
                            "examples": [
                                {"sentence": "Wir haben ein Hotel gebucht."},
                                {"sentence": "Ich bin nach Berlin gefahren."},
                            ],
                        },
                        "native_explanation": {
                            "common_traps": [{"mistake": "haben instead of sein"}]
                        },
                        "vocabulary": [{"word": "die Reise"}, {"word": "buchen"}],
                    },
                }
            ]
        )

        assert '- "Perfekt — Lektion 1" (grammar)' in summary
        assert "explained: Das Perfekt bildet man mit haben oder sein." in summary
        assert "Wir haben ein Hotel gebucht. | Ich bin nach Berlin gefahren." in summary
        assert "vocabulary taught: die Reise, buchen" in summary
        assert "common traps listed: haben instead of sein" in summary
        assert "Vocabulary already introduced in this unit: die Reise, buchen" in summary

    def test_caps_lessons_sentences_and_deduplicates_vocabulary(self):
        from app.services.lesson_generator import (
            PREVIOUS_LESSONS_LIMIT,
            build_previous_lessons_summary,
        )

        lessons = [
            {
                "title": f"Lektion {index}",
                "lesson_type": "grammar",
                "content": {
                    "explanation": {
                        "examples": [{"sentence": f"Satz {index}-{n}"} for n in range(5)]
                    },
                    "vocabulary": [{"word": "buchen"}, {"word": f"Wort {index}"}],
                },
            }
            for index in range(PREVIOUS_LESSONS_LIMIT + 3)
        ]

        summary = build_previous_lessons_summary(lessons)

        assert "Lektion 0" not in summary
        assert f"Lektion {PREVIOUS_LESSONS_LIMIT + 2}" in summary
        assert summary.count('" (grammar)') == PREVIOUS_LESSONS_LIMIT
        assert "Satz 8-2" in summary
        assert "Satz 8-3" not in summary
        unit_words = summary.rsplit("Vocabulary already introduced in this unit: ", 1)[1]
        assert unit_words.count("buchen") == 1

    def test_truncates_long_text_and_collapses_whitespace(self):
        from app.services.lesson_generator import (
            PREVIOUS_LESSON_FOCUS_CHARS,
            build_previous_lessons_summary,
        )

        summary = build_previous_lessons_summary(
            [
                {
                    "title": "Lektion 1",
                    "lesson_type": "reading",
                    "content": {"explanation": {"text": "sehr\n  lang " * 200}},
                }
            ]
        )

        explained = next(line for line in summary.splitlines() if "explained:" in line)
        assert "\n" not in explained
        assert len(explained.strip()) <= PREVIOUS_LESSON_FOCUS_CHARS + len("explained: ")
        assert explained.endswith("…")

    def test_tolerates_missing_and_malformed_content(self):
        from app.services.lesson_generator import build_previous_lessons_summary

        summary = build_previous_lessons_summary(
            [
                {"title": "Lektion 1", "lesson_type": "grammar", "content": None},
                {"title": None, "lesson_type": None, "content": {"explanation": []}},
                {"content": {"vocabulary": ["not-a-dict", {"word": "buchen"}]}},
            ]
        )

        assert '- "Lektion 1" (grammar)' in summary
        assert '- "untitled" (unknown)' in summary
        assert "vocabulary taught: buchen" in summary


class TestGenerateLessonPreviousLessons:
    @staticmethod
    def _lesson_content() -> LessonContent:
        return LessonContent(
            lesson_type="reading",
            title="Perfekt — Lektion 3",
            cefr_level="A2",
            unit_id="a2_unit_1",
            explanation={"text": "Text.", "key_points": [], "examples": []},
            exercises=[
                ExerciseContent(
                    type="multiple_choice",
                    question="Frage?",
                    options=["a", "b"],
                    correct="a",
                    explanation="Weil.",
                )
            ],
            vocabulary=[],
            grammar_refs=[],
        )

    @pytest.mark.asyncio
    async def test_previous_unit_lessons_reach_the_prompt(self):
        from app.services.lesson_generator import generate_lesson

        mock_llm = AsyncMock(return_value=self._lesson_content())
        with patch("app.services.lesson_generator.llm_adapter.structured_output", mock_llm):
            await generate_lesson(
                cefr_level="A2",
                lesson_type="reading",
                topic="Perfekt",
                week=1,
                day=3,
                unit_id="a2_unit_1",
                target_language="de-DE",
                previous_lessons=[
                    {
                        "title": "Perfekt — Lektion 1",
                        "lesson_type": "grammar",
                        "content": {
                            "explanation": {
                                "examples": [{"sentence": "Wir haben ein Hotel gebucht."}]
                            }
                        },
                    }
                ],
            )

        prompt = mock_llm.await_args.args[0][0]["content"]
        assert "ALREADY GENERATED LESSONS OF THIS UNIT" in prompt
        assert "Wir haben ein Hotel gebucht." in prompt

    @pytest.mark.asyncio
    async def test_first_lesson_of_a_unit_gets_no_previous_lessons_block(self):
        from app.services.lesson_generator import generate_lesson

        mock_llm = AsyncMock(return_value=self._lesson_content())
        with patch("app.services.lesson_generator.llm_adapter.structured_output", mock_llm):
            await generate_lesson(
                cefr_level="A2",
                lesson_type="grammar",
                topic="Perfekt",
                week=1,
                day=1,
                unit_id="a2_unit_1",
                target_language="de-DE",
            )

        prompt = mock_llm.await_args.args[0][0]["content"]
        assert "PREVIOUS_LESSONS" not in prompt
        assert 'LESSON TYPE FOCUS — this is a "grammar" lesson:' in prompt
