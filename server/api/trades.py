"""/trades 라우터."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from server.api.deps import current_user_id, require_api_key
from server.repos import trades
from server.schemas.trade import TradeCreate, TradeOut

router = APIRouter(
    prefix="/trades",
    tags=["trades"],
    dependencies=[Depends(require_api_key)],
)


@router.post("", response_model=TradeOut)
def create_trade(
    trade: TradeCreate,
    user_id: UUID = Depends(current_user_id),
) -> TradeOut:
    """단건 매매 기록. 트리거가 positions·realized_pnl 자동 갱신."""
    tid = trades.record_trade(
        user_id=user_id,
        code=trade.code,
        side=trade.side,
        qty=trade.qty,
        price=trade.price,
        executed_at=trade.executed_at,
        trigger_note=trade.trigger_note,
        fees=trade.fees,
    )
    row = next((t for t in trades.list_by_user(user_id, limit=1) if t["id"] == tid), None)
    assert row is not None
    return TradeOut(**row)


@router.get("", response_model=list[TradeOut])
def list_trades(
    code: str | None = None,
    since: datetime | None = None,
    limit: int = Query(50, le=500),
    user_id: UUID = Depends(current_user_id),
) -> list[TradeOut]:
    rows = trades.list_by_user(user_id, since=since, code=code, limit=limit)
    return [TradeOut(**r) for r in rows]
