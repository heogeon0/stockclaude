"""/backtest 라우터 — backtest_cache 노출 (현재 result.raw_md 마크다운)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from server.api.deps import require_api_key
from server.repos import backtest_cache as repo
from server.schemas.backtest import BacktestCacheRow, BacktestListOut

router = APIRouter(
    prefix="/backtest",
    tags=["backtest"],
    dependencies=[Depends(require_api_key)],
)


@router.get("", response_model=BacktestListOut)
def list_backtests() -> BacktestListOut:
    rows = repo.list_all()
    items = [_to_out(r) for r in rows]
    return BacktestListOut(rows=items, count=len(items))


@router.get("/{code}", response_model=BacktestCacheRow)
def get_backtest(code: str) -> BacktestCacheRow:
    row = repo.get_one(code)
    if not row:
        raise HTTPException(404, f"backtest not found: {code}")
    return _to_out(row)


def _to_out(row: dict) -> BacktestCacheRow:
    result = row.get("result") or {}
    raw_md = result.get("raw_md") if isinstance(result, dict) else None
    return BacktestCacheRow(
        code=row["code"],
        name=row.get("name"),
        market=row.get("market"),
        raw_md=raw_md,
        computed_at=row["computed_at"],
        expires_at=row.get("expires_at"),
    )
