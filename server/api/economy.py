"""/economy 라우터 — 거시 기본·일일 지표."""

from __future__ import annotations

from datetime import date as date_cls

from fastapi import APIRouter, Depends

from server.api.deps import require_api_key
from server.repos import economy as economy_repo
from server.schemas.common import Market
from server.schemas.economy import EconomyBaseOut, EconomyDailyOut

router = APIRouter(
    prefix="/economy",
    tags=["economy"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/base", response_model=EconomyBaseOut | None)
def get_economy_base(market: Market) -> EconomyBaseOut | None:
    row = economy_repo.get_base(market)
    if row is None:
        return None
    return EconomyBaseOut(
        market=row["market"],
        context=row.get("context") or {},
        content=row.get("content"),
        updated_at=row["updated_at"],
    )


@router.get("/daily", response_model=EconomyDailyOut | None)
def get_economy_daily(
    market: Market,
    date: date_cls | None = None,
) -> EconomyDailyOut | None:
    """date 생략 시 최신 1건. 없으면 null."""
    if date is not None:
        row = economy_repo.get_daily(market, date)
    else:
        row = economy_repo.get_daily_latest(market)
    if row is None:
        return None
    return EconomyDailyOut(
        market=row["market"],
        date=row["date"],
        index_values=row.get("index_values") or {},
        foreign_net=row.get("foreign_net"),
        institution_net=row.get("institution_net"),
        events=row.get("events") or [],
        content=row.get("content"),
    )
