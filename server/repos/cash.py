"""cash_balance 테이블."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from server.db import get_conn


def get_balance(user_id: UUID, currency: str) -> Decimal:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT amount FROM cash_balance WHERE user_id = %s AND currency = %s",
            (user_id, currency),
        )
        row = cur.fetchone()
        return row["amount"] if row else Decimal(0)


def get_all(user_id: UUID) -> dict[str, Decimal]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT currency, amount FROM cash_balance WHERE user_id = %s",
            (user_id,),
        )
        return {row["currency"]: row["amount"] for row in cur.fetchall()}


def set_balance(user_id: UUID, currency: str, amount: Decimal | float | str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO cash_balance (user_id, currency, amount) VALUES (%s, %s, %s)
            ON CONFLICT (user_id, currency) DO UPDATE SET
              amount = EXCLUDED.amount,
              updated_at = now()
            """,
            (user_id, currency, amount),
        )


def adjust(user_id: UUID, currency: str, delta: Decimal | float | str) -> Decimal:
    """잔고 증감 (매매 후 수동 sync용). Returns: 갱신 후 잔고."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO cash_balance (user_id, currency, amount) VALUES (%s, %s, %s)
            ON CONFLICT (user_id, currency) DO UPDATE SET
              amount = cash_balance.amount + EXCLUDED.amount,
              updated_at = now()
            RETURNING amount
            """,
            (user_id, currency, delta),
        )
        return cur.fetchone()["amount"]
