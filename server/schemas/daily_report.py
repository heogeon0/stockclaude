"""일일 리포트(stock_daily.content) 응답 스키마."""

from __future__ import annotations

from datetime import date as date_cls

from pydantic import BaseModel, Field

from server.schemas.common import Market, Verdict


class DailyReportOut(BaseModel):
    """stock_daily 한 행의 대시보드용 슬림 뷰."""

    code: str
    name: str | None = None
    market: Market | None = None
    date: date_cls
    verdict: Verdict | None = None
    signals: list[dict] = Field(default_factory=list)
    content: str | None = None


class DailyReportsOut(BaseModel):
    date: date_cls | None = None
    reports: list[DailyReportOut] = Field(default_factory=list)


class DailyReportDatesOut(BaseModel):
    dates: list[date_cls] = Field(default_factory=list)
