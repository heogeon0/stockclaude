"""backtest_cache 테이블 — 종목별 백테스트 캐시 (현재 result.raw_md 마크다운만)."""

from __future__ import annotations

from typing import Any

from server.db import get_conn


def list_all() -> list[dict[str, Any]]:
    """전체 캐시 + stocks 조인."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT b.code, s.name, s.market,
                   b.result, b.computed_at, b.expires_at
              FROM backtest_cache b
              LEFT JOIN stocks s USING(code)
             ORDER BY s.market, b.code
            """
        )
        return cur.fetchall()


def get_one(code: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT b.code, s.name, s.market,
                   b.result, b.computed_at, b.expires_at
              FROM backtest_cache b
              LEFT JOIN stocks s USING(code)
             WHERE b.code = %s
            """,
            (code,),
        )
        return cur.fetchone()
