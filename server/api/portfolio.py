"""/portfolio 라우터."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends

from datetime import date as date_cls

from server.analysis.events import detect_concentration_alerts
from server.api.deps import current_user_id, require_google_user
from server.repos import cash, portfolio, portfolio_snapshots, positions, trades
from server.schemas.portfolio import (
    ConcentrationAlertOut,
    ConcentrationAlertsOut,
    PortfolioDailySummaryOut,
    PortfolioOut,
)
from server.schemas.stock import PositionOut

router = APIRouter(
    prefix="/portfolio",
    tags=["portfolio"],
    dependencies=[Depends(require_google_user)],
)

PositionStatus = Literal["active", "all"]
DEFAULT_CONCENTRATION_THRESHOLD_PCT = 25.0


@router.get("", response_model=PortfolioOut)
def get_portfolio(
    status: PositionStatus = "active",
    user_id: UUID = Depends(current_user_id),
) -> PortfolioOut:
    data = portfolio.compute_current_weights(user_id)
    realized = trades.total_realized_by_market(user_id)

    if status == "all":
        all_positions = positions.list_all(user_id)
        out_positions = [_pos_from_all(p) for p in all_positions]
    else:
        out_positions = [_pos_active(p) for p in data["positions"]]

    return PortfolioOut(
        positions=out_positions,
        cash=data["cash"],
        kr_total_krw=data["kr_total_krw"],
        us_total_usd=data["us_total_usd"],
        realized_pnl={
            "KRW": realized.get("kr", Decimal(0)),
            "USD": realized.get("us", Decimal(0)),
        },
    )


@router.get("/concentration-alerts", response_model=ConcentrationAlertsOut)
def get_concentration_alerts(
    threshold_pct: float = DEFAULT_CONCENTRATION_THRESHOLD_PCT,
    user_id: UUID = Depends(current_user_id),
) -> ConcentrationAlertsOut:
    """단일 종목 비중이 threshold_pct(기본 25%) 초과인 포지션 리스트."""
    active = positions.list_active(user_id)
    cash_data = cash.get_all(user_id)
    raw_alerts = detect_concentration_alerts(
        [dict(p) for p in active],
        {k: float(v) for k, v in cash_data.items()},
        threshold_pct=threshold_pct,
    )
    alerts = [_to_alert(a) for a in raw_alerts]
    return ConcentrationAlertsOut(
        alerts=alerts,
        count=len(alerts),
        threshold_pct=threshold_pct,
    )


@router.get("/daily-summary", response_model=PortfolioDailySummaryOut | None)
def get_daily_summary(
    date: date_cls | None = None,
    user_id: UUID = Depends(current_user_id),
) -> PortfolioDailySummaryOut | None:
    """
    portfolio_snapshots (v11 narrative) 단건 조회.
    date 지정: 해당 날짜. 없으면 최신 스냅샷.
    스냅샷이 없으면 null 반환 (404 아님).
    """
    if date is not None:
        snap = portfolio_snapshots.get(user_id, date)
    else:
        snap = portfolio_snapshots.get_latest(user_id)
    if snap is None:
        return None
    return PortfolioDailySummaryOut(
        date=snap["date"],
        headline=snap.get("headline"),
        per_stock_summary=snap.get("per_stock_summary") or [],
        risk_flags=snap.get("risk_flags") or [],
        action_plan=snap.get("action_plan") or [],
        summary_content=snap.get("summary_content"),
    )


def _to_alert(raw: dict) -> ConcentrationAlertOut:
    weight = float(raw["weight_pct"])
    threshold = float(raw["threshold"])
    name = raw.get("name") or raw["code"]
    return ConcentrationAlertOut(
        code=raw["code"],
        name=raw.get("name"),
        weight_pct=weight,
        threshold_pct=threshold,
        severity=raw["severity"],
        message=f"{name} 비중 {weight:.1f}% > 상한 {threshold:.0f}%",
    )


def _pos_active(p: dict) -> PositionOut:
    return PositionOut(
        code=p["code"],
        name=p.get("name"),
        market=p.get("market"),
        currency=p.get("currency"),
        qty=p["qty"],
        avg_price=p["avg_price"],
        cost_basis=p.get("cost_basis"),
        status="Active",
    )


def _pos_from_all(p: dict) -> PositionOut:
    return PositionOut(
        code=p["code"],
        name=p.get("name"),
        market=p.get("market"),
        currency=None,
        qty=p["qty"],
        avg_price=p["avg_price"],
        cost_basis=p.get("cost_basis"),
        status=p["status"],
        style=p.get("style"),
        tags=p.get("tags") or [],
    )
