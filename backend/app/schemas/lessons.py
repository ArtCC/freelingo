from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, field_serializer, model_validator


class ExerciseContent(BaseModel):
    type: str
    question: str
    options: list[str] | None = None
    correct: str
    explanation: str | None = None
    native_explanation: str | None = None
    native_hint: str | None = None

    @model_validator(mode="after")
    def validate_exercise_content(self) -> Self:
        if not self.question.strip():
            raise ValueError("exercises must include a question")
        if not self.correct.strip():
            raise ValueError("exercises must include a correct answer")
        if self.type == "fill_blank" and "___" not in self.question:
            if self.explanation and "___" in self.explanation:
                self.question, self.explanation = self.explanation, self.question
            else:
                raise ValueError("fill_blank exercises must include ___ in the question")
        if self.type != "multiple_choice":
            return self
        options = [option for option in (self.options or []) if option.strip()]
        if len(options) < 2:
            raise ValueError("multiple_choice exercises must include at least two options")
        if self.correct not in options:
            raise ValueError("multiple_choice correct answer must match one option exactly")
        self.options = options
        return self


class LessonVocabularyItem(BaseModel):
    word: str
    definition: str
    example: str
    translation: str | None = None
    example_translation: str | None = None
    note: str | None = None
    reading: str | None = None


class LessonContent(BaseModel):
    lesson_type: str
    title: str
    cefr_level: str
    explanation: dict
    native_explanation: dict | None = None
    exercises: list[ExerciseContent]
    vocabulary: list[LessonVocabularyItem] | None = None
    grammar_refs: list[str] = []
    unit_id: str | None = None


class LessonResponse(BaseModel):
    id: int
    study_plan_id: int
    title: str
    lesson_type: str
    cefr_level: str
    week_number: int
    day_number: int
    content: dict
    is_completed: bool
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_serializer("completed_at")
    def serialize_completed_at(self, v: datetime | None, _info):
        return v.isoformat() if v else None


class ExerciseResponse(BaseModel):
    id: int
    lesson_id: int
    exercise_type: str
    question: str
    options: list | None = None
    correct_answer: str
    user_answer: str | None = None
    score: float | None = None
    feedback: str | None = None
    corrections: list[FreeWriteCorrection] | None = None
    explanation: str | None = None
    native_explanation: str | None = None
    native_hint: str | None = None
    answered_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_serializer("answered_at")
    def serialize_answered_at(self, v: datetime | None, _info):
        return v.isoformat() if v else None


class LessonDetailResponse(BaseModel):
    lesson: LessonResponse
    exercises: list[ExerciseResponse]


class ExerciseAnswerRequest(BaseModel):
    answer: str


class FreeWriteCorrection(BaseModel):
    original: str = ""
    corrected: str = ""
    explanation: str = ""


class ExerciseAnswerResponse(BaseModel):
    id: int
    score: float
    feedback: str
    correct_answer: str
    corrections: list[FreeWriteCorrection] | None = None


class FreeWriteEvaluation(BaseModel):
    score: float
    feedback: str
    corrections: list[FreeWriteCorrection]


class FillBlankEvaluation(BaseModel):
    is_correct: bool
    score: float
    feedback: str


class PronunciationEvaluation(BaseModel):
    score: float
    feedback: str
    is_correct: bool


class NativeExplanationResponse(BaseModel):
    text: str
    key_points: list[str]
    examples: list[dict]
    common_traps: list[dict] | None = None
    mini_glossary: list[dict] | None = None


class NativeExerciseExplanationResponse(BaseModel):
    native_explanation: str


class NativeExerciseHintResponse(BaseModel):
    native_hint: str
