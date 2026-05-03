"""헬스체크 — 모든 MCP 도구·스크래퍼·DB·데이터 신선도 일괄 점검.

목적: 운영 중 어떤 도구가 깨져있는지 가시화 (54 MCP + 9 scrapers + DB 정합 + 신선도).

실행:
    uv run python -m server.jobs.healthcheck             # 전체
    uv run python -m server.jobs.healthcheck --quick     # 빠른 (discovery 제외)

MCP 도구로도 등록 (`healthcheck`) — Claude 가 호출 가능.
"""

from __future__ import annotations

import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Callable

KR_PING_CODE = "005930"  # 삼성전자
US_PING_TICKER = "NVDA"


def _ping(fn: Callable, *args: Any, **kwargs: Any) -> dict:
    """단일 함수 ping — 시간 측정 + 에러 capture.

    응답이 dict 이고 'error' 키만 있거나 'error' 가 truthy 면 fail 로 분류 (도구가
    예외를 raise 하지 않고 error 키로 반환하는 패턴 처리).
    """
    t0 = time.time()
    try:
        result = fn(*args, **kwargs)
        elapsed = time.time() - t0
        # 응답 안에 error 키가 있으면 soft fail
        if isinstance(result, dict) and result.get("error"):
            return {
                "status": "fail",
                "duration_s": round(elapsed, 2),
                "error": f"soft_fail: {str(result.get('error'))[:180]}",
            }
        # preview
        if isinstance(result, dict):
            preview = f"keys={list(result.keys())[:5]}"
        elif isinstance(result, list):
            preview = f"len={len(result)}"
        elif result is None:
            preview = "None"
        else:
            preview = str(result)[:80]
        return {"status": "ok", "duration_s": round(elapsed, 2), "preview": preview}
    except Exception as e:
        return {
            "status": "fail",
            "duration_s": round(time.time() - t0, 2),
            "error": f"{type(e).__name__}: {e}"[:200],
        }


# ─────────────────────────────────────────────
# MCP 도구 ping
# ─────────────────────────────────────────────


def check_mcp_tools_kr() -> dict:
    """KR 종목 (005930) 으로 조회/분석 도구 ping."""
    from server.mcp import server as s

    code = KR_PING_CODE
    return {
        "get_stock_context": _ping(s.get_stock_context, code),
        "realtime_price": _ping(s.realtime_price, code),
        "kis_current_price": _ping(s.kis_current_price, code),
        "compute_indicators": _ping(s.compute_indicators, code),
        "compute_signals": _ping(s.compute_signals, code),
        "compute_financials": _ping(s.compute_financials, code, years=1),
        "compute_score": _ping(s.compute_score, code),
        "analyze_volatility": _ping(s.analyze_volatility, code),
        "analyze_flow": _ping(s.analyze_flow, code),
        "detect_events": _ping(s.detect_events, code),
        "get_analyst_consensus": _ping(s.get_analyst_consensus, code),
        "list_analyst_reports": _ping(s.list_analyst_reports, code, days=90),
        "analyze_consensus_trend": _ping(s.analyze_consensus_trend, code, days=90),
        "analyze_position": _ping(s.analyze_position, code),
        "get_kr_disclosures": _ping(s.get_kr_disclosures, code, days=7),
        "get_kr_insider_trades": _ping(s.get_kr_insider_trades, code),
        "get_kr_major_shareholders": _ping(s.get_kr_major_shareholders, code),
    }


def check_mcp_tools_us() -> dict:
    """US 종목 (NVDA) 으로 조회/분석 도구 ping."""
    from server.mcp import server as s

    code = US_PING_TICKER
    return {
        "get_stock_context": _ping(s.get_stock_context, code),
        "kis_us_quote": _ping(s.kis_us_quote, code),
        "compute_indicators": _ping(s.compute_indicators, code),
        "compute_signals": _ping(s.compute_signals, code),
        "compute_financials": _ping(s.compute_financials, code, years=1),
        "compute_score": _ping(s.compute_score, code),
        "analyze_volatility": _ping(s.analyze_volatility, code),
        "detect_events": _ping(s.detect_events, code),
        "get_analyst_consensus": _ping(s.get_analyst_consensus, code),
        "analyze_consensus_trend": _ping(s.analyze_consensus_trend, code, days=90),
        "analyze_position": _ping(s.analyze_position, code),
        "get_us_disclosures": _ping(s.get_us_disclosures, code, days=7),
        "get_us_insider_trades": _ping(s.get_us_insider_trades, code, days=30),
    }


def check_mcp_tools_portfolio() -> dict:
    """포트 단위 도구 ping."""
    from server.mcp import server as s

    return {
        "get_portfolio": _ping(s.get_portfolio),
        "list_daily_positions": _ping(s.list_daily_positions),
        "list_trades": _ping(s.list_trades, limit=5),
        "list_tradable_stocks": _ping(s.list_tradable_stocks, limit=5),
        "detect_market_regime": _ping(s.detect_market_regime),
        "portfolio_correlation": _ping(s.portfolio_correlation, days=30),
        "detect_portfolio_concentration": _ping(s.detect_portfolio_concentration),
        "check_base_freshness": _ping(s.check_base_freshness),
        "get_weekly_context": _ping(s.get_weekly_context, weeks=4),
        "get_macro_indicators_us": _ping(s.get_macro_indicators_us, ["DFF", "CPIAUCSL"]),
        "get_macro_indicators_kr": _ping(s.get_macro_indicators_kr, ["722Y001"]),
        "get_yield_curve": _ping(s.get_yield_curve),
        "get_fx_rate": _ping(s.get_fx_rate),
        "get_economic_calendar": _ping(s.get_economic_calendar),
        "compute_industry_metrics": _ping(s.compute_industry_metrics, "반도체"),
    }


def check_mcp_tools_discovery(skip: bool = False) -> dict:
    """발굴 도구 ping (시간 오래 걸림 — US ~3분)."""
    if skip:
        return {"_skipped": "quick mode"}
    from server.mcp import server as s

    return {
        "rank_momentum_wide_kr": _ping(s.rank_momentum_wide, market="kr", top_n=5),
        "rank_momentum_wide_us": _ping(
            s.rank_momentum_wide,
            market="us",
            top_n=5,
            min_market_cap_usd=100_000_000_000,
        ),
        "screen_stocks": _ping(s.screen_stocks, market="kr", limit=5),
    }


# ─────────────────────────────────────────────
# Scrapers ping
# ─────────────────────────────────────────────


def check_scrapers() -> dict:
    """각 스크래퍼 직접 호출 ping."""
    results: dict = {}

    # KIS
    try:
        from server.scrapers import kis

        t0 = time.time()
        price = kis.fetch_current_price(KR_PING_CODE)
        results["kis"] = {
            "status": "ok",
            "duration_s": round(time.time() - t0, 2),
            "preview": f"price={price.get('price')}" if isinstance(price, dict) else str(price)[:60],
        }
    except Exception as e:
        results["kis"] = {"status": "fail", "error": f"{type(e).__name__}: {e}"[:200]}

    # DART
    try:
        from server.scrapers import dart

        t0 = time.time()
        df = dart.fetch_disclosures(KR_PING_CODE, days=7)
        results["dart"] = {
            "status": "ok",
            "duration_s": round(time.time() - t0, 2),
            "preview": f"disclosures={len(df) if df is not None else 0}",
        }
    except Exception as e:
        results["dart"] = {"status": "fail", "error": f"{type(e).__name__}: {e}"[:200]}

    # naver
    try:
        from server.scrapers import naver

        t0 = time.time()
        df = naver.fetch_daily(KR_PING_CODE, pages=1)
        results["naver"] = {
            "status": "ok",
            "duration_s": round(time.time() - t0, 2),
            "preview": f"rows={len(df) if df is not None else 0}",
        }
    except Exception as e:
        results["naver"] = {"status": "fail", "error": f"{type(e).__name__}: {e}"[:200]}

    # KRX
    try:
        from server.scrapers import krx

        t0 = time.time()
        cap = krx.fetch_market_cap(KR_PING_CODE)
        results["krx"] = {
            "status": "ok",
            "duration_s": round(time.time() - t0, 2),
            "preview": f"cap_keys={list(cap.keys())[:3] if isinstance(cap, dict) else 'N/A'}",
        }
    except Exception as e:
        results["krx"] = {"status": "fail", "error": f"{type(e).__name__}: {e}"[:200]}

    # yfinance
    try:
        from server.scrapers import yfinance_client as yf

        t0 = time.time()
        df = yf.fetch_ohlcv(US_PING_TICKER, period="5d")
        results["yfinance"] = {
            "status": "ok",
            "duration_s": round(time.time() - t0, 2),
            "preview": f"rows={len(df) if df is not None else 0}",
        }
    except Exception as e:
        results["yfinance"] = {"status": "fail", "error": f"{type(e).__name__}: {e}"[:200]}

    # Finnhub
    try:
        from server.scrapers import finnhub

        t0 = time.time()
        cons = finnhub.fetch_consensus(US_PING_TICKER)
        results["finnhub"] = {
            "status": "ok",
            "duration_s": round(time.time() - t0, 2),
            "preview": f"keys={list(cons.keys())[:3] if isinstance(cons, dict) else 'N/A'}",
        }
    except Exception as e:
        results["finnhub"] = {"status": "fail", "error": f"{type(e).__name__}: {e}"[:200]}

    # FRED
    try:
        from server.scrapers import fred

        t0 = time.time()
        macro = fred.fetch_macro_indicators(["DGS10"])  # 10년물 1개만
        results["fred"] = {
            "status": "ok",
            "duration_s": round(time.time() - t0, 2),
            "preview": f"keys={list(macro.keys())[:3] if isinstance(macro, dict) else 'N/A'}",
        }
    except Exception as e:
        results["fred"] = {"status": "fail", "error": f"{type(e).__name__}: {e}"[:200]}

    # EDGAR
    try:
        from server.scrapers import edgar

        t0 = time.time()
        df = edgar.fetch_disclosures(US_PING_TICKER, days=7)
        results["edgar"] = {
            "status": "ok",
            "duration_s": round(time.time() - t0, 2),
            "preview": f"rows={len(df) if df is not None else 0}",
        }
    except Exception as e:
        results["edgar"] = {"status": "fail", "error": f"{type(e).__name__}: {e}"[:200]}

    return results


# ─────────────────────────────────────────────
# DB 정합성
# ─────────────────────────────────────────────


def check_db_integrity() -> dict:
    """DB 정합성 점검."""
    from server.db import pool

    results: dict = {}
    with pool.connection() as conn, conn.cursor() as cur:
        # 1. stocks NULL industry_code (active)
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM stocks "
            "WHERE industry_code IS NULL AND status='active'"
        )
        results["stocks_null_industry"] = cur.fetchone()["cnt"]

        # 2. cash_balance vs trades 정합 (#7 검증)
        # trades 자체엔 currency 없음 — stocks.currency 를 JOIN
        for currency in ("KRW", "USD"):
            cur.execute(
                "SELECT amount FROM cash_balance WHERE currency=%s", (currency,)
            )
            row = cur.fetchone()
            cash = float(row["amount"]) if row and row["amount"] is not None else 0.0
            cur.execute(
                """
                SELECT COALESCE(SUM(
                  CASE WHEN t.side='sell' THEN t.qty * t.price - COALESCE(t.fees, 0)
                       ELSE -(t.qty * t.price + COALESCE(t.fees, 0))
                  END
                ), 0) AS net
                FROM trades t
                JOIN stocks s ON s.code = t.code
                WHERE s.currency=%s
                """,
                (currency,),
            )
            net_trades = float(cur.fetchone()["net"])
            results[f"cash_balance_{currency}"] = {
                "cash": cash,
                "trades_net_flow": net_trades,
                "note": "cash 와 net_trades 직접 비교 X — 시작잔고 + net_trades + 환전 = 현재 cash",
            }

        # 3. positions by status
        cur.execute(
            "SELECT status, COUNT(*) AS cnt FROM positions GROUP BY status ORDER BY status"
        )
        results["positions_by_status"] = {r["status"]: r["cnt"] for r in cur.fetchall()}

        # 4. orphan positions
        cur.execute(
            """
            SELECT COUNT(*) AS cnt FROM positions p
            LEFT JOIN stocks s ON s.code = p.code
            WHERE s.code IS NULL
            """
        )
        results["orphan_positions"] = cur.fetchone()["cnt"]

    return results


# ─────────────────────────────────────────────
# 데이터 신선도
# ─────────────────────────────────────────────


def check_data_freshness() -> dict:
    """데이터 신선도 점검."""
    from server.db import pool

    results: dict = {}
    with pool.connection() as conn, conn.cursor() as cur:
        # stock_daily 최근
        cur.execute("SELECT MAX(date) AS max_date FROM stock_daily")
        results["stock_daily_max"] = str(cur.fetchone()["max_date"])

        # 보유·감시 종목별 stock_daily 최근
        cur.execute(
            """
            SELECT s.code, s.name, MAX(d.date) AS last_date
            FROM stocks s
            LEFT JOIN stock_daily d ON d.code = s.code
            WHERE s.status='active' AND s.code IN (
                SELECT DISTINCT code FROM positions WHERE status IN ('Active', 'Pending')
            )
            GROUP BY s.code, s.name
            ORDER BY last_date NULLS FIRST
            """
        )
        results["per_stock_daily_freshness"] = [
            {"code": r["code"], "name": r["name"], "last_date": str(r["last_date"])}
            for r in cur.fetchall()
        ]

        # economy_base
        cur.execute("SELECT market, updated_at FROM economy_base ORDER BY market")
        results["economy_base_freshness"] = [
            {"market": r["market"], "updated_at": str(r["updated_at"])}
            for r in cur.fetchall()
        ]

        # stale stock_base (30일+)
        cur.execute(
            """
            SELECT s.code, s.name, b.updated_at,
                   EXTRACT(EPOCH FROM (NOW() - b.updated_at)) / 86400 AS age_days
            FROM stock_base b
            JOIN stocks s ON s.code = b.code
            WHERE b.updated_at < NOW() - INTERVAL '30 days'
            ORDER BY b.updated_at
            LIMIT 10
            """
        )
        results["stale_stock_base_30d_plus"] = [
            {
                "code": r["code"],
                "name": r["name"],
                "updated_at": str(r["updated_at"]),
                "age_days": int(r["age_days"]) if r["age_days"] else None,
            }
            for r in cur.fetchall()
        ]

        # analyst_reports 최근
        cur.execute("SELECT MAX(published_at) AS max_date FROM analyst_reports")
        row = cur.fetchone()
        results["analyst_reports_max"] = (
            str(row["max_date"]) if row and row["max_date"] else None
        )

    return results


# ─────────────────────────────────────────────
# 종합 + 요약
# ─────────────────────────────────────────────


def _summarize(result: dict) -> dict:
    """결과 요약 — pass/fail 카운트."""
    summary: dict = {}
    for category, data in result.items():
        if category in ("timestamp", "summary"):
            continue
        if not isinstance(data, dict):
            continue
        ok = sum(1 for v in data.values() if isinstance(v, dict) and v.get("status") == "ok")
        fail = sum(
            1 for v in data.values() if isinstance(v, dict) and v.get("status") == "fail"
        )
        summary[category] = {"ok": ok, "fail": fail, "total": ok + fail}
    return summary


def run_healthcheck(quick: bool = False) -> dict:
    """전체 헬스체크 실행."""
    # DB pool 미리 열기 (스크립트 직접 실행 시 — MCP 서버 안에선 이미 열려 있음)
    try:
        from server.db import open_pool
        open_pool()
    except Exception:
        pass

    result: dict = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "mode": "quick" if quick else "full",
    }

    # 카테고리별 try/except — 한 카테고리 실패해도 다른 건 진행
    for label, fn, kwargs in [
        ("mcp_tools_kr", check_mcp_tools_kr, {}),
        ("mcp_tools_us", check_mcp_tools_us, {}),
        ("mcp_tools_portfolio", check_mcp_tools_portfolio, {}),
        ("mcp_tools_discovery", check_mcp_tools_discovery, {"skip": quick}),
        ("scrapers", check_scrapers, {}),
        ("db_integrity", check_db_integrity, {}),
        ("data_freshness", check_data_freshness, {}),
    ]:
        try:
            result[label] = fn(**kwargs)
        except Exception as e:
            result[label] = {
                "_error": f"{type(e).__name__}: {e}",
                "_traceback": traceback.format_exc()[:500],
            }

    result["summary"] = _summarize(result)
    return result


if __name__ == "__main__":
    import json

    quick = "--quick" in sys.argv
    out = run_healthcheck(quick=quick)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
