"""공통 스키마."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

Market = Literal["kr", "us"]
Currency = Literal["KRW", "USD"]
Side = Literal["buy", "sell"]
Grade = Literal["Premium", "Standard", "Cautious", "Defensive"]
Status = Literal["Active", "Pending", "Close"]
Style = Literal["day-trade", "swing", "long-term", "momentum"]
Verdict = Literal["강한매수", "매수우세", "중립", "매도우세", "강한매도"]


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


class OkResponse(BaseModel):
    ok: bool = True
    message: str | None = None
