"""weekly_strategy 테이블 — 5번째 모드 (사용자 + LLM 브레인스토밍).

v8 (2026-05) 신설. 학습 사이클의 시작점:
  월요일 brainstorm (사용자 + LLM 협업)
    → 일일 운영 (per-stock-analysis 가 weekly_strategy 인용)
    → weekly_review (전략 평가)
    → 다음 월요일 brainstorm

carry-over: 미작성 주는 직전 작성 row 반환 + carry_over=True 플래그.
"""

from __future__ import annotations

from datetime import date as date_cls, timedelta
from typing import Any

from psycopg.types.json import Jsonb

from server.config import settings
from server.db import get_conn


def _monday_of(d: date_cls) -> date_cls:
    """주어진 날짜의 월요일 (KST 가정)."""
    return d - timedelta(days=d.weekday())


def get_by_week(week_start: date_cls, user_id: str | None = None) -> dict[str, Any] | None:
    uid = user_id or settings.stock_user_id
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT id, user_id, week_start, market_outlook,
                   focus_themes, rules_to_emphasize, rules_to_avoid,
                   position_targets, risk_caps, notes, brainstorm_log,
                   approved_at, created_at
              FROM weekly_strategy
             WHERE user_id = %s AND week_start = %s
            """,
            (uid, week_start),
        )
        return cur.fetchone()


def get_current(user_id: str | None = None, today: date_cls | None = None) -> dict[str, Any] | None:
    """이번 주 (오늘 기준 월요일) 의 strategy. 미작성 시 직전 작성 row + carry_over=True.

    반환:
      - 있으면: {row..., carry_over: False}
      - 직전이 있으면: {row..., carry_over: True, current_week_start: this_monday}
      - 둘 다 없으면: None
    """
    uid = user_id or settings.stock_user_id
    base = today or date_cls.today()
    this_monday = _monday_of(base)

    # 1) 이번 주 row
    current = get_by_week(this_monday, user_id=uid)
    if current:
        return {**current, "carry_over": False}

    # 2) 직전 작성 row
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT id, user_id, week_start, market_outlook,
                   focus_themes, rules_to_emphasize, rules_to_avoid,
                   position_targets, risk_caps, notes, brainstorm_log,
                   approved_at, created_at
              FROM weekly_strategy
             WHERE user_id = %s AND week_start < %s
             ORDER BY week_start DESC LIMIT 1
            """,
            (uid, this_monday),
        )
        prev = cur.fetchone()

    if prev:
        return {**prev, "carry_over": True, "current_week_start": this_monday}

    return None


def list_strategies(weeks: int = 12, user_id: str | None = None) -> list[dict[str, Any]]:
    uid = user_id or settings.stock_user_id
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT id, week_start, market_outlook, focus_themes,
                   rules_to_emphasize, rules_to_avoid, approved_at
              FROM weekly_strategy
             WHERE user_id = %s
             ORDER BY week_start DESC
             LIMIT %s
            """,
            (uid, weeks),
        )
        return cur.fetchall()


def upsert(
    week_start: date_cls,
    *,
    user_id: str | None = None,
    market_outlook: str | None = None,
    focus_themes: list | None = None,
    rules_to_emphasize: list | None = None,
    rules_to_avoid: list | None = None,
    position_targets: dict | None = None,
    risk_caps: dict | None = None,
    notes: str | None = None,
    brainstorm_log: str | None = None,
) -> None:
    uid = user_id or settings.stock_user_id

    ft_j = Jsonb(focus_themes) if focus_themes is not None else None
    re_j = Jsonb(rules_to_emphasize) if rules_to_emphasize is not None else None
    ra_j = Jsonb(rules_to_avoid) if rules_to_avoid is not None else None
    pt_j = Jsonb(position_targets) if position_targets is not None else None
    rc_j = Jsonb(risk_caps) if risk_caps is not None else None

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO weekly_strategy (
                user_id, week_start, market_outlook,
                focus_themes, rules_to_emphasize, rules_to_avoid,
                position_targets, risk_caps, notes, brainstorm_log,
                approved_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (user_id, week_start) DO UPDATE SET
              market_outlook     = COALESCE(EXCLUDED.market_outlook, weekly_strategy.market_outlook),
              focus_themes       = COALESCE(EXCLUDED.focus_themes, weekly_strategy.focus_themes),
              rules_to_emphasize = COALESCE(EXCLUDED.rules_to_emphasize, weekly_strategy.rules_to_emphasize),
              rules_to_avoid     = COALESCE(EXCLUDED.rules_to_avoid, weekly_strategy.rules_to_avoid),
              position_targets   = COALESCE(EXCLUDED.position_targets, weekly_strategy.position_targets),
              risk_caps          = COALESCE(EXCLUDED.risk_caps, weekly_strategy.risk_caps),
              notes              = COALESCE(EXCLUDED.notes, weekly_strategy.notes),
              brainstorm_log     = COALESCE(EXCLUDED.brainstorm_log, weekly_strategy.brainstorm_log),
              approved_at        = now()
            """,
            (
                uid, week_start, market_outlook,
                ft_j, re_j, ra_j, pt_j, rc_j,
                notes, brainstorm_log,
            ),
        )
