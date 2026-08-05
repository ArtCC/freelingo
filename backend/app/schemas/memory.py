from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=200)

    @field_validator("content", mode="before")
    @classmethod
    def normalize_content(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class MemoryOut(BaseModel):
    id: int
    content: str
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoryListResponse(BaseModel):
    memories: list[MemoryOut]


class ClearAllResponse(BaseModel):
    deleted: int
