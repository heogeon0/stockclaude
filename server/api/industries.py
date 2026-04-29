"""/industries 라우터 — 업종 메타 + content 마크다운."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from server.api.deps import current_user_id, require_api_key
from server.repos import industries as industries_repo
from server.schemas.industry import IndustriesOut, IndustryOut

router = APIRouter(
    prefix="/industries",
    tags=["industries"],
    dependencies=[Depends(require_api_key)],
)


@router.get("", response_model=IndustriesOut)
def list_industries(
    market: str | None = None,
    holdings_only: bool = False,
    user_id: UUID = Depends(current_user_id),
) -> IndustriesOut:
    """
    industries 목록.
    - market=kr|us 필터
    - holdings_only=true 면 현재 Active 포지션이 있는 업종만
    """
    rows = industries_repo.list_all(
        market=market,
        holdings_only_user_id=user_id if holdings_only else None,
    )
    items = [_to_out(r) for r in rows]
    return IndustriesOut(industries=items, count=len(items))


@router.get("/{code}", response_model=IndustryOut)
def get_industry(code: str) -> IndustryOut:
    row = industries_repo.get_industry(code)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"industry not found: {code}")
    return _to_out(row)


def _to_out(row: dict) -> IndustryOut:
    return IndustryOut(
        code=row["code"],
        name=row["name"],
        name_en=row.get("name_en"),
        market=row.get("market"),
        parent_code=row.get("parent_code"),
        score=row.get("score"),
        content=row.get("content"),
        updated_at=row["updated_at"],
    )
