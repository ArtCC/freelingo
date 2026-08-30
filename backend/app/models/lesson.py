from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (
        UniqueConstraint(
            "study_plan_id",
            "week_number",
            "day_number",
            "title",
            name="uq_lessons_plan_week_day_title",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    study_plan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("study_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    lesson_type: Mapped[str] = mapped_column(String(50), nullable=False)
    cefr_level: Mapped[str] = mapped_column(String(10), nullable=False)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    content: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lesson_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exercise_type: Mapped[str] = mapped_column(String(50), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSON, nullable=True, default=list)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    user_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrections: Mapped[list | None] = mapped_column(JSON, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
