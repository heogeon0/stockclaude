"""users 테이블."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from server.db import get_conn


def get_user(user_id: UUID) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT id, email, kis_app_key, kis_account_no, created_at FROM users WHERE id = %s",
            (user_id,),
        )
        return cur.fetchone()


def get_user_id_by_email(email: str) -> UUID | None:
    """email 로 user_id 조회. 없으면 None."""
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT id FROM users WHERE LOWER(email) = LOWER(%s)",
            (email,),
        )
        row = cur.fetchone()
        return row["id"] if row else None


def get_or_create_by_email(email: str) -> UUID:
    """email 로 user 조회. 없으면 신규 user 생성 후 UUID 반환.

    멀티유저 확장 대비 — ALLOWED_EMAILS 화이트리스트 통과한 email 이라도
    DB 에 처음 보이는 사람이면 자동으로 user row 생성.
    1인 운영 시점에선 마이그레이션 후 본인 email 이미 있으니 항상 첫 줄에서 종료.
    """
    existing = get_user_id_by_email(email)
    if existing is not None:
        return existing
    new_id = uuid4()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (id, email) VALUES (%s, %s) ON CONFLICT (email) DO NOTHING",
            (new_id, email.lower()),
        )
    # ON CONFLICT 시 다른 process 가 동시에 만들었을 수 있으니 재조회
    return get_user_id_by_email(email) or new_id


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
