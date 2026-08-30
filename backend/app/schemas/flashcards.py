from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_serializer


class FlashcardCreate(BaseModel):
    word: str
    definition: str
    example_sentence: str
    translation: str


class FlashcardBulkCreate(BaseModel):
    flashcards: list[FlashcardCreate]


class FlashcardBulkResponse(BaseModel):
    created: int


class FlashcardReview(BaseModel):
    quality: int


class FlashcardFromWordRequest(BaseModel):
    word: str
    context: str = ""
    cefr_level: str = "B1"


class FlashcardGenerateRequest(BaseModel):
    topic: str
    count: int = Field(default=5, ge=1, le=20)
    cefr_level: str = "B1"


class FlashcardResponse(BaseModel):
    id: int
    user_id: int
    study_plan_id: int
    word: str
    definition: str
    example_sentence: str
    translation: str
    source: Optional[str] = None
    ease_factor: float
    interval: int
    repetitions: int
    next_review: date
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("next_review")
    def serialize_next_review(self, v: date, _info):
        return v.isoformat()

    @field_serializer("created_at")
    def serialize_created_at(self, v: datetime, _info):
        return v.isoformat()


class FlashcardFromWordResponse(FlashcardResponse):
    already_saved: bool = False


class FlashcardListResponse(BaseModel):
    due: list[FlashcardResponse]
    total: int


class VocabularyListResponse(BaseModel):
    items: list[FlashcardResponse]
    total: int
    page: int
    pages: int


class GeneratedFlashcard(BaseModel):
    word: str
    definition: str
    example_sentence: str
    translation: str


class FlashcardGenerateResponse(BaseModel):
    flashcards: list[GeneratedFlashcard]
