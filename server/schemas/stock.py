"""종목 관련 스키마."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from server.schemas.common import Currency, Grade, Market, Status, Style, Verdict


class StockOut(BaseModel):
    code: str
    market: Market
    name: str
    ticker: str | None = None
    sector: str | None = None
    industry_code: str | None = None
    listing_market: str | None = None
    currency: Currency
    status: str


class StockBaseOut(BaseModel):
    code: str
    total_score: int | None = None
    financial_score: int | None = None
    industry_score: int | None = None
    economy_score: int | None = None
    grade: Grade | None = None
    fair_value_min: Decimal | None = None
    fair_value_avg: Decimal | None = None
    fair_value_max: Decimal | None = None
    analyst_target_avg: Decimal | None = None
    analyst_target_max: Decimal | None = None
    analyst_consensus_count: int | None = None
    per: Decimal | None = None
    pbr: Decimal | None = None
    psr: Decimal | None = None
    roe: Decimal | None = None
    op_margin: Decimal | None = None
    narrative: str | None = None
    risks: str | None = None
    scenarios: str | None = None
    content: str | None = None
    updated_at: datetime | None = None


class PositionOut(BaseModel):
    code: str
    name: str | None = None
    market: Market | None = None
    currency: Currency | None = None
    qty: Decimal
    avg_price: Decimal
    cost_basis: Decimal | None = None
    status: Status
    style: Style | None = None
    stop_loss_pct: Decimal | None = None
    trailing_method: str | None = None
    tags: list[str] = Field(default_factory=list)


class WatchLevelOut(BaseModel):
    level_key: str
    price: Decimal
    qty_to_trade: Decimal | None = None
    note: str | None = None
    status: str = "pending"


class StockDailyOut(BaseModel):
    code: str
    date: date
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    volume: int | None = None
    rsi14: Decimal | None = None
    macd: Decimal | None = None
    sma20: Decimal | None = None
    sma60: Decimal | None = None
    verdict: Verdict | None = None
    signals: list[dict] = Field(default_factory=list)
    content: str | None = None


class StockContextOut(BaseModel):
    """Claude 가 분석 시작할 때 호출하는 번들 응답."""
    stock: StockOut
    base: StockBaseOut | None = None
    latest_daily: StockDailyOut | None = None
    position: PositionOut | None = None
    watch_levels: list[WatchLevelOut] = Field(default_factory=list)
    analyst_consensus: dict[str, Any] | None = None
