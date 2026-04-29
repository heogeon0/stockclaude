"""/stocks/* 라우터."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from server.api.deps import current_user_id, require_api_key
from server.repos import (
    analyst,
    positions,
    stock_base,
    stock_daily,
    stocks,
    watch_levels,
)
from server.schemas.stock import (
    PositionOut,
    StockBaseOut,
    StockContextOut,
    StockDailyOut,
    StockOut,
    WatchLevelOut,
)

router = APIRouter(
    prefix="/stocks",
    tags=["stocks"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/{code}", response_model=StockOut)
def get_stock(code: str) -> StockOut:
    row = stocks.get_stock(code)
    if not row:
        raise HTTPException(404, f"stock not found: {code}")
    return StockOut(**row)


@router.get("/{code}/base", response_model=StockBaseOut)
def get_stock_base_endpoint(code: str) -> StockBaseOut:
    """종목 기본 분석 단건 (score/grade/FV/analyst_target/밸류에이션/narrative·risks·scenarios·content).
    context 번들과 달리 analyst/watch_levels 제외 — 아코디언 펼침 때 lazy fetch 용."""
    row = stock_base.get_base(code)
    if not row:
        raise HTTPException(404, f"stock_base not found: {code}")
    return StockBaseOut(**row)


@router.get("/{code}/context", response_model=StockContextOut)
def get_stock_context(
    code: str,
    user_id: UUID = Depends(current_user_id),
) -> StockContextOut:
    """Claude가 분석 시작 시 호출하는 번들."""
    stock_row = stocks.get_stock(code)
    if not stock_row:
        raise HTTPException(404, f"stock not found: {code}")

    base_row = stock_base.get_base(code)
    daily_row = stock_daily.get_latest(user_id, code)
    pos_row = positions.get_position(user_id, code)
    levels = watch_levels.list_by_code(user_id, code) if pos_row else []
    consensus = analyst.get_consensus(code)

    return StockContextOut(
        stock=StockOut(**stock_row),
        base=StockBaseOut(**base_row) if base_row else None,
        latest_daily=_daily_to_out(code, daily_row) if daily_row else None,
        position=_pos_to_out(pos_row) if pos_row else None,
        watch_levels=[WatchLevelOut(**lv) for lv in levels],
        analyst_consensus=consensus,
    )


def _pos_to_out(row: dict) -> PositionOut:
    return PositionOut(
        code=row["code"],
        name=row.get("name"),
        market=row.get("market"),
        currency=row.get("currency"),
        qty=row["qty"],
        avg_price=row["avg_price"],
        cost_basis=row.get("cost_basis"),
        status=row["status"],
        style=row.get("style"),
        stop_loss_pct=row.get("stop_loss_pct"),
        trailing_method=row.get("trailing_method"),
        tags=row.get("tags") or [],
    )


def _daily_to_out(code: str, row: dict) -> StockDailyOut:
    return StockDailyOut(
        code=code,
        date=row["date"],
        open=row.get("open"),
        high=row.get("high"),
        low=row.get("low"),
        close=row.get("close"),
        volume=row.get("volume"),
        rsi14=row.get("rsi14"),
        macd=row.get("macd"),
        sma20=row.get("sma20"),
        sma60=row.get("sma60"),
        verdict=row.get("verdict"),
        signals=row.get("signals") or [],
        content=row.get("content"),
    )
