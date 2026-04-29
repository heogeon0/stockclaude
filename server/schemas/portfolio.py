"""포트폴리오 집계 스키마."""

from __future__ import annotations

from datetime import date as date_cls
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from server.schemas.stock import PositionOut


class PortfolioOut(BaseModel):
    positions: list[PositionOut]
    cash: dict[str, Decimal] = Field(default_factory=dict)
    kr_total_krw: Decimal
    us_total_usd: Decimal
    realized_pnl: dict[str, Decimal] = Field(default_factory=dict)


class ConcentrationCheckIn(BaseModel):
    code: str
    qty: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)


class ConcentrationCheckOut(BaseModel):
    ok: bool
    new_weight_pct: Decimal
    current_weights: dict[str, Decimal]
    violations: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ConcentrationAlertOut(BaseModel):
    """단일 종목 비중 초과 경고."""

    code: str
    name: str | None = None
    weight_pct: float
    threshold_pct: float
    severity: Literal["warning", "critical"]
    message: str


class ConcentrationAlertsOut(BaseModel):
    alerts: list[ConcentrationAlertOut] = Field(default_factory=list)
    count: int = 0
    threshold_pct: float = 25.0


class PortfolioDailySummaryOut(BaseModel):
    """portfolio_snapshots v11 narrative 응답.

    중첩 JSONB (per_stock_summary / risk_flags / action_plan) 는
    DB 스키마가 JSONB 라 그대로 통과시킨다 — 프론트 TS 가 구조 책임.
    """

    date: date_cls
    headline: str | None = None
    per_stock_summary: list[dict[str, Any]] = Field(default_factory=list)
    risk_flags: list[dict[str, Any]] = Field(default_factory=list)
    action_plan: list[dict[str, Any]] = Field(default_factory=list)
    summary_content: str | None = None
