"""/score-weights 라우터 — 스코어 가중치 조회 (defaults, overrides, applied)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from server.api.deps import require_api_key
from server.repos import score_weights as repo
from server.schemas.score_weights import (
    AppliedWeightsOut,
    AppliedWeightsRow,
    ScoreWeightDefaultsOut,
    ScoreWeightDefaultsRow,
    ScoreWeightOverrideRow,
    ScoreWeightOverridesOut,
    Timeframe,
)

router = APIRouter(
    prefix="/score-weights",
    tags=["score-weights"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/defaults", response_model=ScoreWeightDefaultsOut)
def list_defaults() -> ScoreWeightDefaultsOut:
    rows = repo.list_all_defaults()
    return ScoreWeightDefaultsOut(
        rows=[ScoreWeightDefaultsRow(**r) for r in rows],
    )


@router.get("/overrides", response_model=ScoreWeightOverridesOut)
def list_overrides(
    active_only: bool = Query(default=True, description="false 면 만료된 것 포함"),
) -> ScoreWeightOverridesOut:
    rows = repo.list_overrides(include_expired=not active_only)
    return ScoreWeightOverridesOut(
        overrides=[ScoreWeightOverrideRow(**r) for r in rows],
        count=len(rows),
    )


@router.get("/applied", response_model=AppliedWeightsOut)
def get_applied(
    code: str = Query(..., description="종목 코드"),
    timeframe: Timeframe = Query(..., description="day-trade / swing / long-term / momentum"),
) -> AppliedWeightsOut:
    """종목·타임프레임별 최종 적용 가중치 (override + default 병합)."""
    try:
        result = repo.get_applied(code, timeframe)
    except AssertionError as e:
        raise HTTPException(400, str(e))
    weights = result["weights"]
    sources = result["sources"]
    rows = [
        AppliedWeightsRow(dim=d, weight=w, source=sources.get(d, "default"))
        for d, w in weights.items()
    ]
    return AppliedWeightsOut(code=code, timeframe=timeframe, rows=rows)
