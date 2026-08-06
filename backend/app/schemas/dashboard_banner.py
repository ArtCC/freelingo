from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DashboardBannerLocale = Literal["en", "es", "fr", "pt", "de", "it", "ru", "nl", "pl", "ro"]


class DashboardBannerTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(max_length=160)
    subtitle: str = Field(max_length=240)
    description: str = Field(max_length=2000)

    @field_validator("title", "subtitle", "description")
    @classmethod
    def strip_nonblank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Banner text must not be blank")
        return value


class DashboardBannerTranslations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    en: DashboardBannerTranslation
    es: DashboardBannerTranslation
    fr: DashboardBannerTranslation
    pt: DashboardBannerTranslation
    de: DashboardBannerTranslation
    it: DashboardBannerTranslation
    ru: DashboardBannerTranslation
    nl: DashboardBannerTranslation
    pl: DashboardBannerTranslation
    ro: DashboardBannerTranslation


class DashboardBannerTranslateRequest(DashboardBannerTranslation):
    source_locale: DashboardBannerLocale


class DashboardBannerTranslationResponse(BaseModel):
    translations: DashboardBannerTranslations


class DashboardBannerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_locale: DashboardBannerLocale
    is_active: bool
    translations: DashboardBannerTranslations


class DashboardBannerPublicResponse(BaseModel):
    revision: int
    translations: DashboardBannerTranslations


class DashboardBannerAdminResponse(DashboardBannerPublicResponse):
    source_locale: DashboardBannerLocale
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardBannerDismissRequest(BaseModel):
    revision: int = Field(ge=1)
