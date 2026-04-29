"""매매 관련 스키마."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from server.schemas.common import Market, Side


class TradeCreate(BaseModel):
    code: str
    side: Side
    qty: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)
    executed_at: datetime
    trigger_note: str | None = None
    fees: Decimal = Decimal(0)


class TradeOut(BaseModel):
    id: int
    code: str
    name: str | None = None
    market: Market | None = None
    side: Side
    qty: Decimal
    price: Decimal
    executed_at: datetime
    trigger_note: str | None = None
    realized_pnl: Decimal | None = None
    fees: Decimal
    created_at: datetime
