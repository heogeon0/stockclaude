"""rule_catalog 테이블 — 매매 룰 single source-of-truth.

라운드: 2026-05 weekly-review overhaul
옛 한글 enum CHECK + INT[] 분산 → 단일 테이블 통일.
LLM 이 register_rule MCP 로 새 룰 추가 가능 (학습→격상→카탈로그 자동 확장).
"""

from __future__ import annotations

from typing import Any

from server.db import get_conn


VALID_CATEGORIES = ("entry", "exit", "manage")
VALID_STATUSES = ("active", "deprecated")


def get_by_id(rule_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM rule_catalog WHERE id = %s", (rule_id,),
        )
        return cur.fetchone()


def get_by_enum_name(enum_name: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM rule_catalog WHERE enum_name = %s", (enum_name,),
        )
        return cur.fetchone()


def get_by_id_or_name(id_or_name: int | str) -> dict[str, Any] | None:
    """INT 면 id 조회, str 이고 숫자면 id 조회, str 이면 enum_name 조회."""
    if isinstance(id_or_name, int):
        return get_by_id(id_or_name)
    if isinstance(id_or_name, str) and id_or_name.isdigit():
        return get_by_id(int(id_or_name))
    return get_by_enum_name(id_or_name)


def list_active(category: str | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        if category:
            if category not in VALID_CATEGORIES:
                raise ValueError(f"invalid category: {category}")
            cur = conn.execute(
                """
                SELECT id, enum_name, category, description, display_order
                  FROM rule_catalog
                 WHERE status = 'active' AND category = %s
                 ORDER BY display_order, id
                """,
                (category,),
            )
        else:
            cur = conn.execute(
                """
                SELECT id, enum_name, category, description, display_order
                  FROM rule_catalog
                 WHERE status = 'active'
                 ORDER BY category, display_order, id
                """,
            )
        return cur.fetchall()


def list_all(
    category: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    where = []
    params: list = []
    if category:
        if category not in VALID_CATEGORIES:
            raise ValueError(f"invalid category: {category}")
        where.append("category = %s")
        params.append(category)
    if status:
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {status}")
        where.append("status = %s")
        params.append(status)
    sql = "SELECT * FROM rule_catalog"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY category, display_order, id"
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchall()


def register(
    enum_name: str,
    category: str,
    description: str | None = None,
    display_order: int | None = None,
) -> dict[str, Any]:
    """새 룰 등록.

    검증:
      - enum_name UNIQUE (중복 시 에러)
      - category 3 enum
      - display_order None 시 max+1 자동
    """
    if category not in VALID_CATEGORIES:
        raise ValueError(f"invalid category: {category}, must be {VALID_CATEGORIES}")
    if not enum_name or not enum_name.strip():
        raise ValueError("enum_name 비어있을 수 없음")
    if len(enum_name) > 100:
        raise ValueError("enum_name 100자 초과 불가")

    with get_conn() as conn:
        # 중복 체크
        cur = conn.execute("SELECT id FROM rule_catalog WHERE enum_name = %s", (enum_name,))
        if cur.fetchone():
            raise ValueError(f"enum_name 이미 존재: {enum_name}")

        # display_order 자동
        if display_order is None:
            cur = conn.execute("SELECT COALESCE(MAX(display_order), 0) + 1 AS next FROM rule_catalog")
            display_order = cur.fetchone()["next"]

        # id 자동 (max+1)
        cur = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next FROM rule_catalog")
        new_id = cur.fetchone()["next"]

        conn.execute(
            """
            INSERT INTO rule_catalog (id, enum_name, category, description, display_order)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (new_id, enum_name, category, description, display_order),
        )

    return get_by_id(new_id)


def update(
    rule_id: int,
    *,
    description: str | None = None,
    display_order: int | None = None,
) -> dict[str, Any] | None:
    """description / display_order 만 갱신. None 인 필드 미반영."""
    if not get_by_id(rule_id):
        raise ValueError(f"rule_id 없음: {rule_id}")

    fields = []
    params: list = []
    if description is not None:
        fields.append("description = %s")
        params.append(description)
    if display_order is not None:
        fields.append("display_order = %s")
        params.append(display_order)
    if not fields:
        return get_by_id(rule_id)
    params.append(rule_id)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE rule_catalog SET {', '.join(fields)} WHERE id = %s",
            tuple(params),
        )
    return get_by_id(rule_id)


def deprecate(rule_id: int, reason: str | None = None) -> dict[str, Any] | None:
    """soft delete — status='deprecated'. 옛 trades 보존 + 신규 사용 차단."""
    if not get_by_id(rule_id):
        raise ValueError(f"rule_id 없음: {rule_id}")
    desc_suffix = f" [DEPRECATED: {reason}]" if reason else " [DEPRECATED]"
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE rule_catalog
               SET status = 'deprecated',
                   description = COALESCE(description, '') || %s
             WHERE id = %s
            """,
            (desc_suffix, rule_id),
        )
    return get_by_id(rule_id)
