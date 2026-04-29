"""
trades 테이블.
단건 INSERT 전제 (multi-row 시 트리거 타이밍 이슈).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from server.db import get_conn


def record_trade(
    user_id: UUID,
    code: str,
    side: str,  # 'buy' | 'sell'
    qty: Decimal | float | str,
    price: Decimal | float | str,
    executed_at: datetime,
    trigger_note: str | None = None,
    fees: Decimal | float | str = 0,
    rule_category: str | None = None,
) -> int:
    """단건 INSERT. realized_pnl·positions 재계산은 트리거가 처리.

    rule_category: 카탈로그 enum (references/rule-catalog.md). CHECK constraint 가 강제.
    Returns: inserted trade id.
    """
    assert side in ("buy", "sell"), f"invalid side: {side}"
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO trades (user_id, code, side, qty, price, executed_at, trigger_note, fees, rule_category)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, code, side, qty, price, executed_at, trigger_note, fees, rule_category),
        )
        row = cur.fetchone()
        assert row is not None
        return row["id"]


def list_by_user(
    user_id: UUID,
    since: datetime | None = None,
    code: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    sql = """
        SELECT t.id, t.code, s.name, s.market, t.side, t.qty, t.price,
               t.executed_at, t.trigger_note, t.realized_pnl, t.fees, t.created_at
          FROM trades t
          LEFT JOIN stocks s USING(code)
         WHERE t.user_id = %s
    """
    params: list[Any] = [user_id]
    if since:
        sql += " AND t.executed_at >= %s"
        params.append(since)
    if code:
        sql += " AND t.code = %s"
        params.append(code)
    sql += " ORDER BY t.executed_at DESC, t.id DESC LIMIT %s"
    params.append(limit)

    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall()


def total_realized_by_market(user_id: UUID) -> dict[str, Decimal]:
    """KR (KRW 합), US (USD 합) 누적 실현손익 반환."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT s.market, COALESCE(SUM(t.realized_pnl), 0) AS realized
              FROM trades t JOIN stocks s USING(code)
             WHERE t.user_id = %s AND t.side = 'sell'
             GROUP BY s.market
            """,
            (user_id,),
        )
        return {row["market"]: row["realized"] for row in cur.fetchall()}
