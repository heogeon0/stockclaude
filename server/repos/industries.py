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
                   score, content,
                   cycle_phase, momentum_rs_3m, momentum_rs_6m, leader_followers,
                   avg_per, avg_pbr, avg_roe, avg_op_margin, vol_baseline_30d,
                   updated_at, expires_at
              FROM industries WHERE code = %s
            """,
            (code,),
        )
        return cur.fetchone()


def list_freshness_for_codes(codes: list[str]) -> dict[str, dict[str, Any]]:
    """code → {code, name, updated_at, expires_at} dict batch (#26 perf).

    `check_base_freshness` 의 산업 만기 일괄 검사용. 단일 SELECT IN (...)
    으로 N 산업당 1 query 호출 (이전: get_industry × N).

    빈 codes → 빈 dict.
    """
    if not codes:
        return {}
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT code, name, updated_at, expires_at
              FROM industries
             WHERE code = ANY(%s)
            """,
            (list(codes),),
        )
        return {row["code"]: row for row in cur.fetchall()}


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
    cycle_phase: str | None = None,
    momentum_rs_3m: float | None = None,
    momentum_rs_6m: float | None = None,
    leader_followers: dict | None = None,
    avg_per: float | None = None,
    avg_pbr: float | None = None,
    avg_roe: float | None = None,
    avg_op_margin: float | None = None,
    vol_baseline_30d: float | None = None,
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
                                     meta, market_specific, score, content,
                                     cycle_phase, momentum_rs_3m, momentum_rs_6m, leader_followers,
                                     avg_per, avg_pbr, avg_roe, avg_op_margin, vol_baseline_30d)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET
              name = EXCLUDED.name,
              name_en = COALESCE(EXCLUDED.name_en, industries.name_en),
              parent_code = COALESCE(EXCLUDED.parent_code, industries.parent_code),
              meta = COALESCE(EXCLUDED.meta, industries.meta),
              market_specific = COALESCE(EXCLUDED.market_specific, industries.market_specific),
              score = COALESCE(EXCLUDED.score, industries.score),
              content = COALESCE(EXCLUDED.content, industries.content),
              cycle_phase = COALESCE(EXCLUDED.cycle_phase, industries.cycle_phase),
              momentum_rs_3m = COALESCE(EXCLUDED.momentum_rs_3m, industries.momentum_rs_3m),
              momentum_rs_6m = COALESCE(EXCLUDED.momentum_rs_6m, industries.momentum_rs_6m),
              leader_followers = COALESCE(EXCLUDED.leader_followers, industries.leader_followers),
              avg_per = COALESCE(EXCLUDED.avg_per, industries.avg_per),
              avg_pbr = COALESCE(EXCLUDED.avg_pbr, industries.avg_pbr),
              avg_roe = COALESCE(EXCLUDED.avg_roe, industries.avg_roe),
              avg_op_margin = COALESCE(EXCLUDED.avg_op_margin, industries.avg_op_margin),
              vol_baseline_30d = COALESCE(EXCLUDED.vol_baseline_30d, industries.vol_baseline_30d),
              updated_at = now()
            """,
            (
                code, market, name, name_en, parent_code,
                Jsonb(meta) if meta is not None else None,
                Jsonb(market_specific) if market_specific is not None else None,
                score, content,
                cycle_phase, momentum_rs_3m, momentum_rs_6m,
                Jsonb(leader_followers) if leader_followers is not None else None,
                avg_per, avg_pbr, avg_roe, avg_op_margin, vol_baseline_30d,
            ),
        )
