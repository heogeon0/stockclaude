"""stock_daily 테이블 (일일 분석)."""

from __future__ import annotations

from datetime import date as date_cls
from decimal import Decimal
from typing import Any
from uuid import UUID

import pandas as pd
from psycopg.types.json import Jsonb

from server.db import get_conn


def get_latest(user_id: UUID, code: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT * FROM stock_daily
             WHERE user_id = %s AND code = %s
             ORDER BY date DESC LIMIT 1
            """,
            (user_id, code),
        )
        return cur.fetchone()


def get_by_date(user_id: UUID, code: str, date: date_cls) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM stock_daily WHERE user_id=%s AND code=%s AND date=%s",
            (user_id, code, date),
        )
        return cur.fetchone()


def get_recent_ohlcv_df(user_id: UUID, code: str, days: int = 400) -> pd.DataFrame:
    """analysis 모듈이 계산에 쓸 DataFrame."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT date, open, high, low, close, volume
              FROM stock_daily
             WHERE user_id = %s AND code = %s
               AND open IS NOT NULL
             ORDER BY date DESC LIMIT %s
            """,
            (user_id, code, days),
        )
        rows = cur.fetchall()
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("date").reset_index(drop=True)
        # analysis 함수가 한글 컬럼명 기대 (기존 skill 관행)
        df = df.rename(
            columns={
                "date": "날짜",
                "open": "시가",
                "high": "고가",
                "low": "저가",
                "close": "종가",
                "volume": "거래량",
            }
        )
    return df


def upsert_ohlcv(
    user_id: UUID,
    code: str,
    date: date_cls,
    open_: Decimal | float,
    high: Decimal | float,
    low: Decimal | float,
    close: Decimal | float,
    volume: int,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO stock_daily (user_id, code, date, open, high, low, close, volume)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, code, date) DO UPDATE SET
              open = EXCLUDED.open, high = EXCLUDED.high,
              low = EXCLUDED.low, close = EXCLUDED.close,
              volume = EXCLUDED.volume
            """,
            (user_id, code, date, open_, high, low, close, volume),
        )


def upsert_indicators(
    user_id: UUID,
    code: str,
    date: date_cls,
    indicators: dict,
    ichimoku: dict | None = None,
) -> None:
    """compute_all() 결과를 컬럼에 매핑해 저장."""
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE stock_daily SET
              rsi14 = %s, stoch_k = %s, stoch_d = %s,
              adx = %s, atr14 = %s,
              macd = %s, macd_signal = %s, macd_hist = %s,
              bb_upper = %s, bb_middle = %s, bb_lower = %s,
              sma5 = %s, sma20 = %s, sma60 = %s, sma120 = %s, sma200 = %s,
              ichimoku = COALESCE(%s, ichimoku)
            WHERE user_id = %s AND code = %s AND date = %s
            """,
            (
                indicators.get("rsi14"), indicators.get("stoch_k"), indicators.get("stoch_d"),
                indicators.get("adx"), indicators.get("atr14"),
                indicators.get("macd"), indicators.get("macd_signal"), indicators.get("macd_hist"),
                indicators.get("bb_upper"), indicators.get("bb_middle"), indicators.get("bb_lower"),
                indicators.get("sma5"), indicators.get("sma20"), indicators.get("sma60"),
                indicators.get("sma120"), indicators.get("sma200"),
                Jsonb(ichimoku) if ichimoku is not None else None,
                user_id, code, date,
            ),
        )


def upsert_signals(
    user_id: UUID,
    code: str,
    date: date_cls,
    signals: list[dict],
    verdict: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE stock_daily SET
              signals = %s, verdict = COALESCE(%s, verdict)
            WHERE user_id = %s AND code = %s AND date = %s
            """,
            (Jsonb(signals), verdict, user_id, code, date),
        )


def list_report_dates(user_id: UUID) -> list[date_cls]:
    """리포트(content 또는 verdict) 존재 날짜 DESC."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT DISTINCT date
              FROM stock_daily
             WHERE user_id = %s
               AND (content IS NOT NULL OR verdict IS NOT NULL)
             ORDER BY date DESC
            """,
            (user_id,),
        )
        return [row["date"] for row in cur.fetchall()]


def list_reports_on_date(
    user_id: UUID,
    date: date_cls,
    *,
    only_active_positions: bool = True,
    market: str | None = None,
) -> list[dict[str, Any]]:
    """해당 날짜의 종목별 stock_daily + 종목명/market join. market 지정 시 필터."""
    with get_conn() as conn:
        if only_active_positions:
            cur = conn.execute(
                """
                SELECT sd.code, s.name, s.market, sd.date,
                       sd.verdict, sd.signals, sd.content
                  FROM stock_daily sd
                  JOIN stocks s USING(code)
                  JOIN positions p
                    ON p.user_id = sd.user_id AND p.code = sd.code
                 WHERE sd.user_id = %s AND sd.date = %s
                   AND p.status = 'Active'
                   AND (%s::text IS NULL OR s.market = %s)
                 ORDER BY p.cost_basis DESC NULLS LAST
                """,
                (user_id, date, market, market),
            )
        else:
            cur = conn.execute(
                """
                SELECT sd.code, s.name, s.market, sd.date,
                       sd.verdict, sd.signals, sd.content
                  FROM stock_daily sd
                  JOIN stocks s USING(code)
                 WHERE sd.user_id = %s AND sd.date = %s
                   AND (%s::text IS NULL OR s.market = %s)
                 ORDER BY s.name
                """,
                (user_id, date, market, market),
            )
        return cur.fetchall()


def latest_report_date(user_id: UUID) -> date_cls | None:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT MAX(date) AS d
              FROM stock_daily
             WHERE user_id = %s
               AND (content IS NOT NULL OR verdict IS NOT NULL)
            """,
            (user_id,),
        )
        row = cur.fetchone()
        return row["d"] if row else None


def upsert_content(user_id: UUID, code: str, date: date_cls, content: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO stock_daily (user_id, code, date, content)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, code, date) DO UPDATE SET content = EXCLUDED.content
            """,
            (user_id, code, date, content),
        )
