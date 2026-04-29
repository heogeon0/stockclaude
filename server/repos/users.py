"""users 테이블."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from server.db import get_conn


def get_user(user_id: UUID) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT id, email, kis_app_key, kis_account_no, created_at FROM users WHERE id = %s",
            (user_id,),
        )
        return cur.fetchone()


def upsert_user(user_id: UUID, email: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO users (id, email) VALUES (%s, %s)
            ON CONFLICT (id) DO UPDATE SET
              email = COALESCE(EXCLUDED.email, users.email)
            """,
            (user_id, email),
        )
