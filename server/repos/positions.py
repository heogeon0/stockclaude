"""
positions 테이블.
qty·avg_price·cost_basis·status·entered_at·updated_at 은 trades 트리거가 관리.
수동 UPDATE 대상은 스타일 파라미터·태그·entry_context 만.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from server.db import get_conn


def get_position(user_id: UUID, code: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT user_id, code, qty, avg_price, cost_basis, status,
                   style, stop_loss_pct, trailing_method, pyramiding_max_stages,
                   use_time_checkpoints, technical_weight, thesis_weight, target_horizon_days,
                   tags, entry_context, entered_at, updated_at
              FROM positions
             WHERE user_id = %s AND code = %s
            """,
            (user_id, code),
        )
        return cur.fetchone()


def list_active(user_id: UUID) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT p.user_id, p.code, s.name, s.market, s.currency,
                   p.qty, p.avg_price, p.cost_basis, p.status,
                   p.style, p.stop_loss_pct, p.trailing_method, p.pyramiding_max_stages,
                   p.use_time_checkpoints, p.technical_weight, p.thesis_weight,
                   p.target_horizon_days, p.tags, p.entered_at
              FROM positions p JOIN stocks s USING(code)
             WHERE p.user_id = %s AND p.status = 'Active'
             ORDER BY p.cost_basis DESC NULLS LAST
            """,
            (user_id,),
        )
        return cur.fetchall()


def list_all(user_id: UUID) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT p.user_id, p.code, s.name, s.market, p.qty, p.avg_price,
                   p.cost_basis, p.status, p.style, p.tags, p.entered_at, p.updated_at
              FROM positions p JOIN stocks s USING(code)
             WHERE p.user_id = %s
             ORDER BY p.status, p.cost_basis DESC NULLS LAST
            """,
            (user_id,),
        )
        return cur.fetchall()


def list_daily_scope(user_id: UUID) -> list[dict[str, Any]]:
    """
    /stock-daily 스코프 — Active + Pending. Close 제외.
    daily 보고서·base 만기 검사 대상 일괄 반환.
    """
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT p.user_id, p.code, s.name, s.market, s.currency,
                   p.qty, p.avg_price, p.cost_basis, p.status,
                   p.style, p.stop_loss_pct, p.trailing_method, p.pyramiding_max_stages,
                   p.use_time_checkpoints, p.technical_weight, p.thesis_weight,
                   p.target_horizon_days, p.tags, p.entered_at
              FROM positions p JOIN stocks s USING(code)
             WHERE p.user_id = %s AND p.status IN ('Active', 'Pending')
             ORDER BY
               CASE p.status WHEN 'Active' THEN 0 ELSE 1 END,
               p.cost_basis DESC NULLS LAST
            """,
            (user_id,),
        )
        return cur.fetchall()


def update_params(
    user_id: UUID,
    code: str,
    *,
    style: str | None = None,
    stop_loss_pct: Decimal | float | None = None,
    trailing_method: str | None = None,
    pyramiding_max_stages: int | None = None,
    use_time_checkpoints: bool | None = None,
    technical_weight: Decimal | float | None = None,
    thesis_weight: Decimal | float | None = None,
    target_horizon_days: int | None = None,
    tags: list[str] | None = None,
    entry_context: dict | None = None,
) -> None:
    """
    수치 파라미터만 갱신. qty/avg_price/cost_basis/status 는 트리거 관리 대상.
    None 으로 전달된 항목은 건드리지 않음 (COALESCE).
    """
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE positions SET
              style                  = COALESCE(%s, style),
              stop_loss_pct          = COALESCE(%s, stop_loss_pct),
              trailing_method        = COALESCE(%s, trailing_method),
              pyramiding_max_stages  = COALESCE(%s, pyramiding_max_stages),
              use_time_checkpoints   = COALESCE(%s, use_time_checkpoints),
              technical_weight       = COALESCE(%s, technical_weight),
              thesis_weight          = COALESCE(%s, thesis_weight),
              target_horizon_days    = COALESCE(%s, target_horizon_days),
              tags                   = COALESCE(%s, tags),
              entry_context          = COALESCE(%s, entry_context),
              updated_at             = now()
            WHERE user_id = %s AND code = %s
            """,
            (
                style, stop_loss_pct, trailing_method, pyramiding_max_stages,
                use_time_checkpoints, technical_weight, thesis_weight,
                target_horizon_days, tags,
                Jsonb(entry_context) if entry_context is not None else None,
                user_id, code,
            ),
        )
