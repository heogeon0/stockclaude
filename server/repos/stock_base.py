"""stock_base 테이블 (중장기 분석)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from psycopg.types.json import Jsonb

from server.db import get_conn


def get_base(code: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT code, total_score, financial_score, industry_score, economy_score, grade,
                   fair_value_min, fair_value_avg, fair_value_max,
                   analyst_target_avg, analyst_target_max, analyst_consensus_count,
                   per, pbr, psr, ev_ebitda, roe, roa, op_margin, net_margin,
                   debt_ratio, eps, bps, dividend_yield, market_cap,
                   fundamentals_extra, narrative, risks, scenarios, content,
                   updated_at, expires_at
              FROM stock_base WHERE code = %s
            """,
            (code,),
        )
        return cur.fetchone()


def list_by_grade(grade: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT sb.code, s.name, sb.total_score, sb.grade,
                   sb.per, sb.pbr, sb.roe, sb.op_margin
              FROM stock_base sb JOIN stocks s USING(code)
             WHERE sb.grade = %s
             ORDER BY sb.total_score DESC
            """,
            (grade,),
        )
        return cur.fetchall()


def upsert_base(
    code: str,
    *,
    total_score: int | None = None,
    financial_score: int | None = None,
    industry_score: int | None = None,
    economy_score: int | None = None,
    grade: str | None = None,
    fair_value_avg: Decimal | None = None,
    analyst_target_avg: Decimal | None = None,
    analyst_target_max: Decimal | None = None,
    analyst_consensus_count: int | None = None,
    # 재무지표
    per: Decimal | None = None,
    pbr: Decimal | None = None,
    roe: Decimal | None = None,
    op_margin: Decimal | None = None,
    # 서술
    narrative: str | None = None,
    risks: str | None = None,
    scenarios: str | None = None,
    content: str | None = None,
    fundamentals_extra: dict | None = None,
) -> None:
    # fundamentals_extra NOT NULL 제약 대응: None이면 기존 값 유지 (없으면 {})
    if fundamentals_extra is None:
        existing = get_base(code)
        fundamentals_extra = (existing.get("fundamentals_extra") if existing else None) or {}

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO stock_base (
                code, total_score, financial_score, industry_score, economy_score, grade,
                fair_value_avg, analyst_target_avg, analyst_target_max, analyst_consensus_count,
                per, pbr, roe, op_margin,
                narrative, risks, scenarios, content, fundamentals_extra
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET
              total_score = COALESCE(EXCLUDED.total_score, stock_base.total_score),
              financial_score = COALESCE(EXCLUDED.financial_score, stock_base.financial_score),
              industry_score = COALESCE(EXCLUDED.industry_score, stock_base.industry_score),
              economy_score = COALESCE(EXCLUDED.economy_score, stock_base.economy_score),
              grade = COALESCE(EXCLUDED.grade, stock_base.grade),
              fair_value_avg = COALESCE(EXCLUDED.fair_value_avg, stock_base.fair_value_avg),
              analyst_target_avg = COALESCE(EXCLUDED.analyst_target_avg, stock_base.analyst_target_avg),
              analyst_target_max = COALESCE(EXCLUDED.analyst_target_max, stock_base.analyst_target_max),
              analyst_consensus_count = COALESCE(EXCLUDED.analyst_consensus_count, stock_base.analyst_consensus_count),
              per = COALESCE(EXCLUDED.per, stock_base.per),
              pbr = COALESCE(EXCLUDED.pbr, stock_base.pbr),
              roe = COALESCE(EXCLUDED.roe, stock_base.roe),
              op_margin = COALESCE(EXCLUDED.op_margin, stock_base.op_margin),
              narrative = COALESCE(EXCLUDED.narrative, stock_base.narrative),
              risks = COALESCE(EXCLUDED.risks, stock_base.risks),
              scenarios = COALESCE(EXCLUDED.scenarios, stock_base.scenarios),
              content = COALESCE(EXCLUDED.content, stock_base.content),
              fundamentals_extra = COALESCE(EXCLUDED.fundamentals_extra, stock_base.fundamentals_extra),
              updated_at = now()
            """,
            (
                code, total_score, financial_score, industry_score, economy_score, grade,
                fair_value_avg, analyst_target_avg, analyst_target_max, analyst_consensus_count,
                per, pbr, roe, op_margin,
                narrative, risks, scenarios, content,
                Jsonb(fundamentals_extra) if fundamentals_extra is not None else None,
            ),
        )
