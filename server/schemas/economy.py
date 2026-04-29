"""economy_base / economy_daily 응답 스키마."""

from __future__ import annotations

from datetime import date as date_cls, datetime
from typing import Any

from pydantic import BaseModel, Field

from server.schemas.common import Market


class EconomyBaseOut(BaseModel):
    market: Market
    context: dict[str, Any] = Field(default_factory=dict)
    content: str | None = None
    updated_at: datetime


class EconomyDailyOut(BaseModel):
    market: Market
    date: date_cls
    index_values: dict[str, Any] = Field(default_factory=dict)
    foreign_net: int | None = None
    institution_net: int | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    content: str | None = None
