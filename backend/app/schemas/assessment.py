from __future__ import annotations

from pydantic import BaseModel

# ── Quiz question (static bank shape — mirrored from assessment-bank.ts) ──────


class QuizQuestion(BaseModel):
    id: str
    skill: str  # grammar | vocabulary | reading
    difficulty: str  # CEFRLevel
    question: str
    options: list[str]  # exactly 4
    correct: str  # matches one option exactly
    grammar_slug: str | None = None


class QuizResponse(BaseModel):
    questions: list[QuizQuestion]


# ── Submission ─────────────────────────────────────────────────────────────────


class AnswerRecord(BaseModel):
    """One answered question from the adaptive quiz."""

    question_id: str
    skill: str  # grammar | vocabulary | reading
    difficulty: str  # CEFRLevel
    correct: bool
    dont_know: bool = False  # learner declared a knowledge gap instead of guessing


class AssessmentSubmitRequest(BaseModel):
    answers: list[AnswerRecord]


# ── Result ─────────────────────────────────────────────────────────────────────


class AssessmentResult(BaseModel):
    cefr_level: str
    score: float
    skill_profile: dict[str, float] = {}  # {grammar: 0.7, vocabulary: 0.5, reading: 0.6}
    strengths: list[str] = []
    weaknesses: list[str] = []
    analysis: str = ""


# ── Free-write evaluation ──────────────────────────────────────────────────────


class FreeWriteEvalRequest(BaseModel):
    preliminary_level: str
    writing_prompt: str
    student_answer: str


# ── Completion (saves result + creates plan) ───────────────────────────────────


class AssessmentCompleteRequest(BaseModel):
    cefr_level: str
    skill_profile: dict[str, float] = {}
    strengths: list[str] = []
    weaknesses: list[str] = []
    duration_weeks: int = 12
    days_per_week: int = 4
    goals: list[str] = ["grammar", "vocabulary", "reading", "writing"]
    target_language: str | None = (
        None  # Phase 10: explicit language avoids relying on users.target_language
    )


class AssessmentVoiceTrialRequest(BaseModel):
    target_language: str | None = None


# ── Level test ─────────────────────────────────────────────────────────────────


class LevelTestSubmitRequest(BaseModel):
    plan_id: int
    answers: list[AnswerRecord]


class LevelTestResult(BaseModel):
    score: float
    recommendation: str  # advance | extend | repeat
    next_level: str | None = None


# ── Assessment bank (static question bank served to frontend) ──────────────────


class AssessmentBankQuestion(BaseModel):
    """A single question from the static assessment bank."""

    id: str
    skill: str
    difficulty: str
    question: str
    options: list[str]
    correct: str
    grammar_slug: str | None = None


class AssessmentBankResponse(BaseModel):
    questions: list[AssessmentBankQuestion]
