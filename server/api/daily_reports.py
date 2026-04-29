"""/daily-reports 라우터 — 보유 종목별 일일 분석 리포트."""

from __future__ import annotations

from datetime import date as date_cls
from uuid import UUID

from fastapi import APIRouter, Depends

from server.api.deps import current_user_id, require_google_user
from server.repos import stock_daily
from server.schemas.common import Market
from server.schemas.daily_report import (
    DailyReportDatesOut,
    DailyReportOut,
    DailyReportsOut,
)

router = APIRouter(
    prefix="/daily-reports",
    tags=["daily-reports"],
    dependencies=[Depends(require_google_user)],
)


@router.get("", response_model=DailyReportsOut)
def list_daily_reports(
    date: date_cls | None = None,
    include_closed: bool = False,
    market: Market | None = None,
    user_id: UUID = Depends(current_user_id),
) -> DailyReportsOut:
    """
    해당 날짜의 보유 종목별 일일 리포트.
    date 생략 시 가장 최신 리포트 날짜로 fallback.
    include_closed=True 면 Close 포지션도 포함 (기본: Active only).
    market 지정 시 해당 시장만 (kr / us).
    """
    target = date or stock_daily.latest_report_date(user_id)
    if target is None:
        return DailyReportsOut(date=None, reports=[])

    rows = stock_daily.list_reports_on_date(
        user_id,
        target,
        only_active_positions=not include_closed,
        market=market,
    )
    return DailyReportsOut(
        date=target,
        reports=[_to_out(r) for r in rows],
    )


@router.get("/dates", response_model=DailyReportDatesOut)
def list_daily_report_dates(
    user_id: UUID = Depends(current_user_id),
) -> DailyReportDatesOut:
    """리포트 존재 날짜 목록 (DESC)."""
    dates = stock_daily.list_report_dates(user_id)
    return DailyReportDatesOut(dates=dates)


def _to_out(row: dict) -> DailyReportOut:
    return DailyReportOut(
        code=row["code"],
        name=row.get("name"),
        market=row.get("market"),
        date=row["date"],
        verdict=row.get("verdict"),
        signals=row.get("signals") or [],
        content=row.get("content"),
    )
