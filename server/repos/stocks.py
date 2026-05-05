"""stocks 마스터 테이블."""

from __future__ import annotations

from typing import Any

from server.db import get_conn


def get_stock(code: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT code, market, name, name_en, ticker, sector, industry_code,
                   listing_market, currency, status, created_at, updated_at
              FROM stocks WHERE code = %s
            """,
            (code,),
        )
        return cur.fetchone()


def list_for_codes(codes: list[str]) -> dict[str, dict[str, Any]]:
    """code → row dict batch (#26 perf — N+1 query 제거).

    `check_base_freshness` 의 holdings industry_code lookup 일괄 처리용.
    단일 SELECT IN (...) 으로 N 종목당 1 query 호출.

    빈 codes → 빈 dict.
    """
    if not codes:
        return {}
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT code, name, market, industry_code, currency, status
              FROM stocks
             WHERE code = ANY(%s)
            """,
            (list(codes),),
        )
        return {row["code"]: row for row in cur.fetchall()}


def list_by_market(market: str, status: str = "active") -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT code, market, name, ticker, industry_code, currency
              FROM stocks
             WHERE market = %s AND status = %s
             ORDER BY code
            """,
            (market, status),
        )
        return cur.fetchall()


def list_by_industry(industry_code: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT code, name, market, ticker
              FROM stocks WHERE industry_code = %s AND status = 'active'
             ORDER BY code
            """,
            (industry_code,),
        )
        return cur.fetchall()


def upsert_stock(
    code: str,
    market: str,
    name: str,
    industry_code: str | None = None,
    ticker: str | None = None,
    listing_market: str | None = None,
    currency: str = "KRW",
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO stocks (code, market, name, ticker, industry_code, listing_market, currency)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET
              market = EXCLUDED.market,
              name = EXCLUDED.name,
              ticker = EXCLUDED.ticker,
              industry_code = EXCLUDED.industry_code,
              listing_market = EXCLUDED.listing_market,
              currency = EXCLUDED.currency
            """,
            (code, market, name, ticker, industry_code, listing_market, currency),
        )
