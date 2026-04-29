"""watch_levels 테이블."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from server.db import get_conn


def list_by_code(user_id: UUID, code: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT level_key, price, qty_to_trade, expected_pnl, note,
                   status, triggered_at, triggered_price
              FROM watch_levels
             WHERE user_id = %s AND code = %s
             ORDER BY price DESC
            """,
            (user_id, code),
        )
        return cur.fetchall()


def list_pending(user_id: UUID) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT user_id, code, level_key, price, qty_to_trade, note
              FROM watch_levels
             WHERE user_id = %s AND status = 'pending'
             ORDER BY code, price DESC
            """,
            (user_id,),
        )
        return cur.fetchall()


def upsert(
    user_id: UUID,
    code: str,
    level_key: str,
    price: Decimal | float,
    qty_to_trade: Decimal | float | None = None,
    expected_pnl: Decimal | float | None = None,
    note: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO watch_levels (user_id, code, level_key, price, qty_to_trade, expected_pnl, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, code, level_key) DO UPDATE SET
              price = EXCLUDED.price,
              qty_to_trade = EXCLUDED.qty_to_trade,
              expected_pnl = EXCLUDED.expected_pnl,
              note = COALESCE(EXCLUDED.note, watch_levels.note),
              status = 'pending',
              updated_at = now()
            """,
            (user_id, code, level_key, price, qty_to_trade, expected_pnl, note),
        )


def mark_triggered(
    user_id: UUID, code: str, level_key: str,
    triggered_price: Decimal | float, when: datetime | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE watch_levels SET
              status = 'triggered',
              triggered_at = COALESCE(%s, now()),
              triggered_price = %s,
              updated_at = now()
            WHERE user_id = %s AND code = %s AND level_key = %s
            """,
            (when, triggered_price, user_id, code, level_key),
        )


def cancel(user_id: UUID, code: str, level_key: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE watch_levels SET status='cancelled', updated_at=now()
            WHERE user_id=%s AND code=%s AND level_key=%s
            """,
            (user_id, code, level_key),
        )
