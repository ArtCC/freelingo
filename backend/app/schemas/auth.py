from __future__ import annotations

import json
import re
from datetime import datetime

PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{10,25}$")


def validate_password_strength(v: str) -> str:
    if not PASSWORD_PATTERN.match(v):
        raise ValueError(
            "Password must be 10-25 characters and include at least "
            "one uppercase letter, one number, and one symbol"
        )
    return v


from pydantic import BaseModel, EmailStr, Field, field_serializer, field_validator

SUPPORTED_LANGUAGES = {
    "en",
    "es",
    "fr",
    "pt",
    "de",
    "it",
    "ru",
    "nl",
    "pl",
    "ro",
}

SUPPORTED_TARGET_LANGUAGES: set[str] = {
    "en-US",
    "en-GB",
    "de-DE",
    "es-ES",
    "fr-FR",
    "it-IT",
    "ja-JP",
    "ko-KR",
    "pt-PT",
    "zh-CN",
}


def get_available_languages() -> list[str]:
    """Return the operator-configured subset, filtered to known languages."""
    from app.core.config import settings  # noqa: PLC0415

    return [
        lang for lang in settings.AVAILABLE_TARGET_LANGUAGES if lang in SUPPORTED_TARGET_LANGUAGES
    ]


SUPPORTED_UI_LOCALES: set[str] = {
    "en",
    "es",
    "fr",
    "pt",
    "de",
    "it",
    "pl",
    "nl",
    "ro",
    "ru",
}

VALID_LEARNING_GOALS: set[str] = {
    "travel",
    "work",
    "academic",
    "daily",
    "media",
    "emigration",
    "exams",
    "social",
}


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[\w.-]+$")
    email: EmailStr
    password: str = Field(min_length=10, max_length=25)
    display_name: str | None = Field(default=None, max_length=100)
    native_language: str = Field(min_length=2, max_length=5)
    target_language: str = "en-GB"
    invite_token: str | None = None

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator("native_language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language code: {v}")
        return v

    @field_validator("target_language")
    @classmethod
    def validate_target_language(cls, v: str) -> str:
        if v not in SUPPORTED_TARGET_LANGUAGES:
            raise ValueError(
                f"Unsupported target language. Choose from: {SUPPORTED_TARGET_LANGUAGES}"
            )
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=25)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105


class RegisterResponse(BaseModel):
    id: int
    username: str
    role: str
    access_token: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str | None
    display_name: str
    role: str
    native_language: str
    target_language: str
    ui_locale: str | None = None
    is_active: bool
    is_verified: bool
    conversation_max_duration: int
    conversation_inactivity_timeout: int
    avatar: str | None = None
    bio: str | None = None
    learning_goals: list[str] | None = None
    subscription_status: str = "none"
    subscription_ends_at: datetime | None = None
    cancel_at_period_end: bool = False
    trial_used: bool = False
    assessment_voice_trial_used: bool = False
    freemium_trial_ends_at: datetime | None = None
    freemium_trial_used: bool = False
    dismissed_dashboard_banner_revision: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("learning_goals", mode="before")
    @classmethod
    def parse_learning_goals(cls, v: object) -> list[str] | None:
        if v is None:
            return None
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError, ValueError:
                pass
        return None

    @field_serializer("created_at", "subscription_ends_at")
    def serialize_datetime(self, v: datetime | None, _info):
        return v.isoformat() if v else None


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=10, max_length=25)
    native_language: str | None = Field(default=None, min_length=2, max_length=5)
    target_language: str | None = None
    ui_locale: str | None = Field(default=None, min_length=2, max_length=5)
    conversation_max_duration: int | None = None
    conversation_inactivity_timeout: int | None = None
    bio: str | None = Field(default=None, max_length=500)
    learning_goals: list[str] | None = None

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_password_strength(v)
        return v

    @field_validator("native_language")
    @classmethod
    def validate_native_language(cls, v: str | None) -> str | None:
        if v is not None and v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language code: {v}")
        return v

    @field_validator("target_language")
    @classmethod
    def validate_target_language(cls, v: str | None) -> str | None:
        if v is not None and v not in SUPPORTED_TARGET_LANGUAGES:
            raise ValueError(
                f"Unsupported target language. Choose from: {SUPPORTED_TARGET_LANGUAGES}"
            )
        return v

    @field_validator("ui_locale", mode="before")
    @classmethod
    def empty_string_to_none(cls, v: str | None) -> str | None:
        if v == "":
            return None
        return v

    @field_validator("ui_locale")
    @classmethod
    def validate_ui_locale(cls, v: str | None) -> str | None:
        if v is not None and v not in SUPPORTED_UI_LOCALES:
            raise ValueError(f"Unsupported UI locale. Choose from: {SUPPORTED_UI_LOCALES}")
        return v

    @field_validator("conversation_max_duration")
    @classmethod
    def validate_max_duration(cls, v: int | None) -> int | None:
        if v is not None and v not in (900, 1800):
            raise ValueError("conversation_max_duration must be 900 or 1800")
        return v

    @field_validator("conversation_inactivity_timeout")
    @classmethod
    def validate_inactivity_timeout(cls, v: int | None) -> int | None:
        if v is not None and v not in (60, 180, 300):
            raise ValueError("conversation_inactivity_timeout must be 60, 180, or 300")
        return v

    @field_validator("learning_goals")
    @classmethod
    def validate_learning_goals(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            for g in v:
                if g not in VALID_LEARNING_GOALS:
                    raise ValueError(f"Invalid learning goal: {g}. Valid: {VALID_LEARNING_GOALS}")
        return v


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=10, max_length=25)

    @field_validator("new_password")
    @classmethod
    def check_new_password(cls, v: str) -> str:
        return validate_password_strength(v)
