"""position_docs 테이블 (thesis·action_rules·memo 서술)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from server.db import get_conn


def get(user_id: UUID, code: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT thesis, action_rules, memo, updated_at FROM position_docs WHERE user_id=%s AND code=%s",
            (user_id, code),
        )
        return cur.fetchone()


def upsert(
    user_id: UUID,
    code: str,
    *,
    thesis: str | None = None,
    action_rules: str | None = None,
    memo: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO position_docs (user_id, code, thesis, action_rules, memo)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, code) DO UPDATE SET
              thesis = COALESCE(EXCLUDED.thesis, position_docs.thesis),
              action_rules = COALESCE(EXCLUDED.action_rules, position_docs.action_rules),
              memo = COALESCE(EXCLUDED.memo, position_docs.memo),
              updated_at = now()
            """,
            (user_id, code, thesis, action_rules, memo),
        )
