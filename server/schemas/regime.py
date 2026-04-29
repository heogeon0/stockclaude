"""시장 국면(regime) 응답 스키마."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from server.schemas.common import Market


class RegimeOut(BaseModel):
    """KR/US 공통 — analysis.regime 의 한글 키를 영문으로 매핑."""

    market: Market
    label: str  # "강한 상승장" / "상승장" / "전환기" / "하락장"
    momentum_on: bool
    conditions_met: int  # 통과 조건 수
    total_conditions: int  # KR: 4, US: 5
    checks: dict[str, bool] = Field(default_factory=dict)
    details: dict[str, Any] = Field(default_factory=dict)
    interpretation: str | None = None
    error: str | None = None
    computed_at: datetime
