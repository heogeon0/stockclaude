"""industries 테이블 응답 스키마."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from server.schemas.common import Market


class IndustryOut(BaseModel):
    code: str
    name: str
    name_en: str | None = None
    market: Market | None = None
    parent_code: str | None = None
    score: int | None = None
    content: str | None = None
    updated_at: datetime


class IndustriesOut(BaseModel):
    industries: list[IndustryOut]
    count: int = 0
