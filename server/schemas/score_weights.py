"""스코어 가중치 응답 스키마."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

Timeframe = Literal["day-trade", "swing", "long-term", "momentum"]
Dim = Literal["재무", "산업", "경제", "기술", "밸류에이션"]
WeightSource = Literal["default", "user", "claude", "backtest"]


class ScoreWeightDefaultsRow(BaseModel):
    timeframe: Timeframe
    dim: Dim
    weight: Decimal


class ScoreWeightDefaultsOut(BaseModel):
    rows: list[ScoreWeightDefaultsRow] = Field(default_factory=list)


class ScoreWeightOverrideRow(BaseModel):
    code: str
    name: str | None = None
    timeframe: Timeframe
    dim: Dim
    weight: Decimal
    source: Literal["user", "claude", "backtest"] | None = None
    reason: str | None = None
    expires_at: datetime | None = None
    updated_at: datetime


class ScoreWeightOverridesOut(BaseModel):
    overrides: list[ScoreWeightOverrideRow] = Field(default_factory=list)
    count: int = 0


class AppliedWeightsRow(BaseModel):
    dim: Dim
    weight: Decimal
    source: WeightSource


class AppliedWeightsOut(BaseModel):
    code: str
    timeframe: Timeframe
    rows: list[AppliedWeightsRow] = Field(default_factory=list)
