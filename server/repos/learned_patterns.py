"""learned_patterns 테이블 — weekly_review 의 자연어 인사이트 → 정량 메모리.

v7 (2026-05) 신설. G6 결정 (추론 자연어, 결론 정량) 의 일부.
- 동일 패턴이 반복 발견되면 occurrences ↑
- promotion_status: observation → rule_candidate → principle / user_principle
- per-stock-analysis 가 user_principle / principle 카테고리 인용 의무
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import Any

from server.db import get_conn


def get_by_tag(tag: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT id, tag, description, occurrences, win_rate, sample_count,
                   first_seen, last_seen, promotion_status, related_rule_ids,
                   created_at, updated_at
              FROM learned_patterns WHERE tag = %s
            """,
            (tag,),
        )
        return cur.fetchone()


def list_by_status(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    sql = (
        "SELECT id, tag, description, occurrences, win_rate, sample_count, "
        "       first_seen, last_seen, promotion_status, related_rule_ids "
        "  FROM learned_patterns"
    )
    params: tuple = ()
    if status:
        sql += " WHERE promotion_status = %s"
        params = (status,)
    sql += " ORDER BY last_seen DESC NULLS LAST LIMIT %s"
    params = params + (limit,)
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall()


def append(
    tag: str,
    description: str,
    *,
    outcome: str | None = None,            # 'win' | 'loss' | 'neutral'
    trade_id: int | None = None,
    related_rule_ids: list[int] | None = None,
) -> None:
    """패턴 발견 시 호출. 기존 tag 면 occurrences/sample_count 누적, 신규면 INSERT.

    win_rate 는 outcome 'win' 누적 / sample_count 로 자동 산출.
    """
    today = date_cls.today()
    is_win = 1 if outcome == "win" else 0
    is_sample = 1 if outcome in ("win", "loss") else 0

    with get_conn() as conn:
        # 기존 tag 조회
        cur = conn.execute(
            "SELECT id, occurrences, sample_count, win_rate FROM learned_patterns WHERE tag = %s",
            (tag,),
        )
        row = cur.fetchone()

        if row:
            # 누적 갱신
            new_occ = (row.get("occurrences") or 1) + 1
            new_sample = (row.get("sample_count") or 0) + is_sample
            # win_rate 재계산: 기존 win_rate × 기존 sample_count + 이번 win → / 새 sample_count
            old_wins = int((row.get("win_rate") or 0) * (row.get("sample_count") or 0)) if row.get("win_rate") else 0
            new_wins = old_wins + is_win
            new_win_rate = (new_wins / new_sample) if new_sample > 0 else None

            conn.execute(
                """
                UPDATE learned_patterns SET
                  description = %s,
                  occurrences = %s,
                  sample_count = %s,
                  win_rate = %s,
                  last_seen = %s,
                  related_rule_ids = COALESCE(%s, related_rule_ids),
                  updated_at = now()
                WHERE tag = %s
                """,
                (
                    description, new_occ, new_sample, new_win_rate, today,
                    related_rule_ids, tag,
                ),
            )
        else:
            # 신규
            conn.execute(
                """
                INSERT INTO learned_patterns (
                  tag, description, occurrences, win_rate, sample_count,
                  first_seen, last_seen, promotion_status, related_rule_ids
                ) VALUES (%s, %s, 1, %s, %s, %s, %s, 'observation', %s)
                """,
                (
                    tag, description,
                    (1.0 if is_win and is_sample else (0.0 if is_sample else None)),
                    is_sample,
                    today, today,
                    related_rule_ids,
                ),
            )


def list_promote_candidates(
    min_sample: int = 5,
    min_win_rate: float = 0.6,
) -> list[dict[str, Any]]:
    """자동 격상 후보 — sample 5+ 도달 + win_rate 임계 이상.

    라운드: 2026-05 weekly-review overhaul
    Phase 2 회고 시 사용자에게 격상 제안 (자동 격상은 안 함).

    promotion 룰:
      - observation → rule_candidate: occurrences >= min_sample + win_rate >= min_win_rate
      - rule_candidate → principle: occurrences >= min_sample*2 + win_rate >= min_win_rate + 0.1
    """
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT id, tag, description, occurrences, win_rate, sample_count,
                   first_seen, last_seen, promotion_status, related_rule_ids,
                   CASE
                     WHEN promotion_status = 'observation'
                          AND sample_count >= %s
                          AND COALESCE(win_rate, 0) >= %s
                       THEN 'rule_candidate'
                     WHEN promotion_status = 'rule_candidate'
                          AND sample_count >= %s
                          AND COALESCE(win_rate, 0) >= %s
                       THEN 'principle'
                     ELSE NULL
                   END AS suggested_status
              FROM learned_patterns
             WHERE promotion_status IN ('observation','rule_candidate')
               AND sample_count >= %s
               AND COALESCE(win_rate, 0) >= %s
             ORDER BY sample_count DESC, win_rate DESC NULLS LAST
            """,
            (
                min_sample, min_win_rate,
                min_sample * 2, min_win_rate + 0.1,
                min_sample, min_win_rate,
            ),
        )
        return [r for r in cur.fetchall() if r.get("suggested_status")]


def promote(tag: str, new_status: str) -> None:
    """promotion_status 갱신. 'observation' → 'rule_candidate' → 'principle' / 'user_principle'."""
    if new_status not in ("observation", "rule_candidate", "principle", "user_principle"):
        raise ValueError(f"invalid promotion_status: {new_status}")
    with get_conn() as conn:
        conn.execute(
            "UPDATE learned_patterns SET promotion_status = %s, updated_at = now() WHERE tag = %s",
            (new_status, tag),
        )
