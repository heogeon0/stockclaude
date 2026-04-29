"""/regime 라우터 — 시장 국면 (KR/US)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Response

from server.analysis.regime import kospi_regime, sp500_regime
from server.api.deps import require_google_user
from server.schemas.common import Market
from server.schemas.regime import RegimeOut

router = APIRouter(prefix="/regime", tags=["regime"], dependencies=[Depends(require_google_user)])


@router.get("", response_model=RegimeOut)
def get_regime(market: Market, response: Response) -> RegimeOut:
    """시장 국면. 5~30초 비용 — 클라이언트 캐싱 권장 (Cache-Control: max-age=300)."""
    raw = kospi_regime() if market == "kr" else sp500_regime()
    response.headers["Cache-Control"] = "max-age=300"
    return _to_out(market, raw)


def _to_out(market: Market, raw: dict[str, Any]) -> RegimeOut:
    """analysis.regime 한글 키 → 영문 Pydantic 매핑."""
    label = raw.get("국면", "")
    momentum_on = bool(raw.get("모멘텀_가동", False))
    conditions_met, total = _parse_pass_ratio(raw.get("통과_조건수"), market)
    return RegimeOut(
        market=market,
        label=label or ("오류" if raw.get("오류") else ""),
        momentum_on=momentum_on,
        conditions_met=conditions_met,
        total_conditions=total,
        checks=raw.get("체크") or {},
        details=raw.get("세부") or {},
        interpretation=raw.get("해석"),
        error=raw.get("오류"),
        computed_at=datetime.now(tz=timezone.utc),
    )


def _parse_pass_ratio(s: str | None, market: Market) -> tuple[int, int]:
    """'3/4' 형식 → (3, 4). 파싱 실패 시 시장별 기본 분모로."""
    default_total = 4 if market == "kr" else 5
    if not s or "/" not in s:
        return 0, default_total
    try:
        a, b = s.split("/", 1)
        return int(a), int(b)
    except (ValueError, TypeError):
        return 0, default_total
