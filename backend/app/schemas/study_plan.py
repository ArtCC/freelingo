from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_serializer


class StudyPlanGoal(BaseModel):
    goal: str


class GenerateStudyPlanRequest(BaseModel):
    cefr_level: str
    goals: list[str] = ["grammar", "vocabulary", "reading", "writing"]
    duration_weeks: int = 12
    days_per_week: int = 4
    weaknesses: list[str] = []
    strengths: list[str] = []
    target_language: str | None = None


class DayPlan(BaseModel):
    day: int
    lesson_type: str
    title: str
    objectives: list[str]
    estimated_minutes: int
    unit_id: str = ""
    grammar_points: list[str] = []
    vocabulary_set_ids: list[str] = []


class WeekPlan(BaseModel):
    week: int
    theme: str
    days: list[DayPlan]


class GeneratedPlan(BaseModel):
    title: str
    cefr_level: str = ""
    duration_weeks: int = 12
    days_per_week: int = 4
    ends_with_test: bool = True
    weekly_plan: list[WeekPlan]


class StudyPlanResponse(BaseModel):
    id: int
    user_id: int
    cefr_level: str
    goals: list[str]
    duration_weeks: int
    days_per_week: int
    current_unit: str
    progress_day: int = 0
    generated_plan: dict
    is_active: bool
    completion_test_taken: bool
    completion_test_score: float | None
    completion_test_recommendation: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def serialize_created_at(self, v: datetime, _info):
        return v.isoformat()


class TodayLesson(BaseModel):
    id: int | None = None
    title: str
    lesson_type: str
    week: int
    day: int
    objectives: list[str]
    estimated_minutes: int
    unit_id: str = ""
    is_completed: bool = False


class TodayResponse(BaseModel):
    plan_id: int
    cefr_level: str
    lessons: list[TodayLesson]
    progress_day: int = 0
    total_days: int = 0
    pending_count: int = 0


class PendingLessonResponse(BaseModel):
    id: int
    title: str
    lesson_type: str
    week_number: int
    day_number: int

    model_config = {"from_attributes": True}


class PlanLessonResponse(BaseModel):
    id: int
    title: str
    lesson_type: str
    week_number: int
    day_number: int
    unit_id: str | None
    is_completed: bool

    model_config = {"from_attributes": True}
