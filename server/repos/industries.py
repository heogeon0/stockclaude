"""industries 테이블."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from server.db import get_conn


def get_industry(code: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT code, market, name, name_en, parent_code, meta, market_specific,
                   score, content, updated_at, expires_at
              FROM industries WHERE code = %s
            """,
            (code,),
        )
        return cur.fetchone()


def list_by_market(market: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT code, market, name, parent_code, score FROM industries"
    params: tuple = ()
    if market:
        sql += " WHERE market = %s"
        params = (market,)
    sql += " ORDER BY code"
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall()


def list_all(
    market: str | None = None,
    holdings_only_user_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """content 포함 전체 필드 반환.

    holdings_only_user_id 지정 시 해당 유저의 Active 포지션 종목들의
    stocks.industry_code 와 매칭되는 industries 만.
    """
    conditions: list[str] = []
    params: list[Any] = []

    if market:
        conditions.append("i.market = %s")
        params.append(market)

    if holdings_only_user_id is not None:
        conditions.append(
            "i.code IN (SELECT DISTINCT s.industry_code FROM stocks s "
            "JOIN positions p ON p.code = s.code "
            "WHERE p.user_id = %s AND p.status = 'Active' AND s.industry_code IS NOT NULL)"
        )
        params.append(holdings_only_user_id)

    sql = (
        "SELECT i.code, i.market, i.name, i.name_en, i.parent_code, "
        "       i.score, i.content, i.updated_at "
        "  FROM industries i"
    )
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY i.market, i.code"

    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchall()


def upsert(
    code: str,
    market: str | None,
    name: str,
    *,
    name_en: str | None = None,
    parent_code: str | None = None,
    meta: dict | None = None,
    market_specific: dict | None = None,
    score: int | None = None,
    content: str | None = None,
) -> None:
    # meta / market_specific NOT NULL 가능 대응: None이면 기존 값 유지 (없으면 {})
    if meta is None or market_specific is None:
        existing = get_industry(code)
        if meta is None:
            meta = (existing.get("meta") if existing else None) or {}
        if market_specific is None:
            market_specific = (existing.get("market_specific") if existing else None) or {}

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO industries (code, market, name, name_en, parent_code,
                                     meta, market_specific, score, content)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET
              name = EXCLUDED.name,
              name_en = COALESCE(EXCLUDED.name_en, industries.name_en),
              parent_code = COALESCE(EXCLUDED.parent_code, industries.parent_code),
              meta = COALESCE(EXCLUDED.meta, industries.meta),
              market_specific = COALESCE(EXCLUDED.market_specific, industries.market_specific),
              score = COALESCE(EXCLUDED.score, industries.score),
              content = COALESCE(EXCLUDED.content, industries.content),
              updated_at = now()
            """,
            (
                code, market, name, name_en, parent_code,
                Jsonb(meta) if meta is not None else None,
                Jsonb(market_specific) if market_specific is not None else None,
                score, content,
            ),
        )
