"""backtest_cache 응답 스키마."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from server.schemas.common import Market


class BacktestCacheRow(BaseModel):
    code: str
    name: str | None = None
    market: Market | None = None
    raw_md: str | None = None
    computed_at: datetime
    expires_at: datetime | None = None


class BacktestListOut(BaseModel):
    rows: list[BacktestCacheRow] = Field(default_factory=list)
    count: int = 0
