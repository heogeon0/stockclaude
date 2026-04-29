"""weekly_reviews 응답 스키마.

JSONB 컬럼(win_rate, rule_evaluations, highlights, next_week_actions)
은 dict/list 통과 — 프론트 TS 가 구조 책임.
"""

from __future__ import annotations

from datetime import date as date_cls, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class WeeklyReviewListItem(BaseModel):
    week_start: date_cls
    week_end: date_cls
    trade_count: int
    realized_pnl_kr: Decimal | None = None
    realized_pnl_us: Decimal | None = None
    unrealized_pnl_kr: Decimal | None = None
    unrealized_pnl_us: Decimal | None = None
    headline: str | None = None
    created_at: datetime


class WeeklyReviewListOut(BaseModel):
    reviews: list[WeeklyReviewListItem]
    count: int


class WeeklyReviewOut(BaseModel):
    week_start: date_cls
    week_end: date_cls
    trade_count: int
    realized_pnl_kr: Decimal | None = None
    realized_pnl_us: Decimal | None = None
    unrealized_pnl_kr: Decimal | None = None
    unrealized_pnl_us: Decimal | None = None
    win_rate: dict[str, Any] = Field(default_factory=dict)
    rule_evaluations: list[dict[str, Any]] = Field(default_factory=list)
    highlights: list[dict[str, Any]] = Field(default_factory=list)
    next_week_actions: list[dict[str, Any]] = Field(default_factory=list)
    headline: str | None = None
    content: str | None = None
    created_at: datetime
    updated_at: datetime


class WeeklyContextLatest(BaseModel):
    week_start: date_cls | None = None
    week_end: date_cls | None = None
    headline: str | None = None
    highlights: list[dict[str, Any]] = Field(default_factory=list)
    pending_actions: list[dict[str, Any]] = Field(default_factory=list)


class WeeklyRollingStats(BaseModel):
    weeks_count: int
    rule_win_rates: dict[str, dict[str, Any]] = Field(default_factory=dict)
    total_realized_pnl_kr: float = 0.0
    avg_weekly_pnl_kr: float = 0.0
    trade_count_total: int = 0


class WeeklyContextOut(BaseModel):
    latest_review: WeeklyContextLatest | None = None
    rolling_stats: WeeklyRollingStats
    carryover_actions: list[dict[str, Any]] = Field(default_factory=list)
