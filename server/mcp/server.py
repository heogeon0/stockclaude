"""
MCP 서버 — Claude가 stock-manager DB를 조작하는 창구.

FastMCP stdio 전송. Claude Code mcp.json 에 등록:

  {
    "mcpServers": {
      "stock-manager": {
        "command": "uv",
        "args": ["run", "python", "-m", "server.mcp.server"],
        "cwd": "/path/to/stockclaude"
      }
    }
  }

툴 그룹:
  ■ 조회: get_portfolio, get_stock_context, get_applied_weights
  ■ 분석: compute_indicators, compute_signals, check_concentration,
          propose_position_params
  ■ 쓰기: record_trade, save_daily_report, override_score_weights
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd
from fastmcp import FastMCP

from server.analysis.concentration import check_concentration as _check_conc
from server.analysis.indicators import compute_all, price_context
from server.analysis.signals import analyze_all, summarize
from server.config import settings
from server.db import open_pool
from server.repos import (
    analyst,
    cash,
    portfolio,
    portfolio_snapshots,
    positions,
    score_weights,
    stock_base,
    stock_daily,
    stocks,
    trades,
    watch_levels,
)
from server.analysis.concentration import position_planner
from server.analysis.consensus import rating_wave, target_price_trend
from server.analysis.correlation import diversification_metrics
from server.analysis.events import (
    detect_52week_break,
    detect_concentration_alerts,
    detect_rating_changes,
    earnings_proximity,
)
from server.analysis.financials import (
    compute_financial_ratios,
    compute_financial_score,
    compute_growth_rates,
    detect_earnings_surprise,
    summarize_health,
)
from server.analysis.flow import analyze_investor_flow
from server.analysis.momentum import momentum_score
from server.analysis.regime import kospi_regime
from server.analysis.scoring import (
    score_financial,
    score_industry,
    score_macro,
    score_technical,
    score_valuation,
    total_grade,
)
from server.analysis.volatility import (
    classify_vol_regime,
    compute_beta,
    compute_drawdown,
    parkinson_volatility,
    realized_volatility,
)
from server.repos import economy, industries
from server.scrapers import dart, kis, naver


def _build_mcp() -> FastMCP:
    """transport 모드에 따라 FastMCP 인스턴스 구성.

    - stdio (로컬 Claude Code): auth 없음. 자식 프로세스 신뢰.
    - streamable-http (원격 배포): GoogleProvider OAuth + 이메일 화이트리스트.
      `MCP_BASE_URL`, `GOOGLE_CLIENT_ID/SECRET`, `ALLOWED_EMAILS` 필수.
    """
    if not settings.mcp_remote_enabled:
        return FastMCP("stock-manager")

    missing = [
        name
        for name, val in [
            ("MCP_BASE_URL", settings.mcp_base_url),
            ("GOOGLE_CLIENT_ID", settings.google_client_id),
            ("GOOGLE_CLIENT_SECRET", settings.google_client_secret),
            ("ALLOWED_EMAILS", settings.allowed_emails),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(
            f"streamable-http 모드에 필수 env 누락: {', '.join(missing)}"
        )

    from server.mcp.auth import build_google_oauth_provider

    auth = build_google_oauth_provider(
        client_id=settings.google_client_id,  # type: ignore[arg-type]
        client_secret=settings.google_client_secret,  # type: ignore[arg-type]
        base_url=settings.mcp_base_url,  # type: ignore[arg-type]
        allowed_emails=settings.allowed_emails_list,
    )
    return FastMCP("stock-manager", auth=auth)


mcp: FastMCP = _build_mcp()


def _is_us_ticker(code: str) -> bool:
    """KR 6자리 숫자 / US 알파벳 자동 판정."""
    return not (code.isdigit() and len(code) == 6)


def _fetch_ohlcv(code: str, days: int = 400) -> "pd.DataFrame":
    """KR/US 자동 분기 OHLCV fetch — KIS 우선 + naver/yfinance fallback.

    전략:
    - KR + days ≤ 150: KIS `fetch_period_ohlcv` (공식 + 안정)
    - KR + days > 150 or KIS 실패: naver `fetch_daily` (분할 부담 없음)
    - US + days ≤ 100: KIS `fetch_us_daily` (공식)
    - US + days > 100 or KIS 실패: yfinance `fetch_ohlcv`

    KIS 100건 한도 회피 + naver/yfinance 차단 위험 분산.
    모든 source 가 한글 컬럼 (`날짜/시가/고가/저가/종가/거래량`) 으로 normalize.
    """
    from datetime import date, timedelta

    if _is_us_ticker(code):
        # US: KIS 우선 (100건), 실패/초과 시 yfinance
        if days <= 100:
            try:
                df = kis.fetch_us_daily(code, days=days)
                if df is not None and not df.empty:
                    return df
            except Exception:
                pass
        from server.scrapers import yfinance_client as yfc
        if days <= 35:
            period = "1mo"
        elif days <= 95:
            period = "3mo"
        elif days <= 190:
            period = "6mo"
        elif days <= 380:
            period = "1y"
        elif days <= 760:
            period = "2y"
        else:
            period = "5y"
        return yfc.fetch_ohlcv(code, period=period)

    # KR: KIS 우선 (150일 이내), 초과/실패 시 naver
    if days <= 150:
        try:
            df = kis.fetch_period_ohlcv(
                code,
                period="D",
                start_date=date.today() - timedelta(days=days + 50),
            )
            if df is not None and not df.empty:
                return df
        except Exception:
            pass
    return naver.fetch_daily(code, pages=max(days // 10, 1))


def _dec(x: Any) -> float | None:
    if x is None:
        return None
    return float(x)


def _row_safe(row: dict | None) -> dict | None:
    """Decimal/datetime 을 JSON-friendly 값으로 변환."""
    if row is None:
        return None
    out: dict = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


# =====================================================================
# analyze_position 응답 size 가드 (#23, GS 147KB token 한도 사례)
# =====================================================================

# 최근 90일 raw rows 다대량 종목 (예: GS Form 4 다발) 대비.
# total_count + truncated 메타 동반으로 LLM 이 cap 인지 가능.
DISCLOSURES_MAX_ROWS = 20  # 14일치 raw — Big-tech 8-K 폭증 대비
INSIDER_MAX_ROWS = 20      # 90일치 raw — Form 4 다발 종목 대비


def _truncate_rows(rows: list[dict], max_rows: int) -> dict:
    """rows 리스트를 cap + 메타 명시. count = 표시 행 수, total_count = 원본 행 수.

    `truncated: True` 시 LLM 이 별도 MCP (`get_us_insider_trades` / `get_kr_disclosures`)
    호출로 풀 행 조회 가능 — analyze_position 안에서는 응답 size 보호 우선.
    """
    if not rows:
        return {"rows": [], "count": 0, "truncated": False}
    if len(rows) <= max_rows:
        return {"rows": rows, "count": len(rows), "truncated": False}
    return {
        "rows": rows[:max_rows],
        "count": max_rows,
        "total_count": len(rows),
        "truncated": True,
    }


def _json_safe(obj: Any) -> Any:
    """numpy/pandas/Decimal/datetime 을 재귀적으로 JSON 원시 타입으로 변환.

    MCP structured output 은 표준 JSON 타입만 허용하므로
    signal dict 처럼 내부에 numpy scalar/DataFrame 값이 섞일 수 있는
    반환값은 반드시 이 함수로 왕복 처리해야 outputSchema 오류를 피함.
    """
    import math

    # numpy / pandas 는 optional 이지만 이 프로젝트에선 항상 로드됨
    try:
        import numpy as np
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            f = float(obj)
            return None if math.isnan(f) or math.isinf(f) else f
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return [_json_safe(x) for x in obj.tolist()]
    except ImportError:
        pass

    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, float):
        return None if math.isnan(obj) or math.isinf(obj) else obj
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    return obj


# =====================================================================
# 조회 툴
# =====================================================================

@mcp.tool
def get_portfolio() -> dict:
    """
    현재 유저의 전체 포트폴리오 (Active 포지션·현금·실현이익).
    KR/US 분리 집계, 환율 미적용 (Claude가 필요시 변환).

    ⚠️ Pending(감시 대기) 포지션은 제외됨. /stock-daily 스코프는 `list_daily_positions()` 사용.
    """
    uid = settings.stock_user_id
    data = portfolio.compute_current_weights(uid)
    realized = trades.total_realized_by_market(uid)

    return {
        "positions": [_row_safe(p) for p in data["positions"]],
        "cash": {k: float(v) for k, v in data["cash"].items()},
        "kr_total_krw": float(data["kr_total_krw"]),
        "us_total_usd": float(data["us_total_usd"]),
        "realized_pnl": {
            "KRW": float(realized.get("kr", 0)),
            "USD": float(realized.get("us", 0)),
        },
    }


@mcp.tool
def list_daily_positions() -> dict:
    """
    /stock-daily 스코프 — Active + Pending 포지션 일괄 반환 (Close 제외).

    Pending(감시 대기) 포지션은 qty=0이지만 base.md가 있어 daily 생성 대상.
    `get_portfolio()`는 Active만 반환하므로 daily 워크플로우 시작 시 이 툴 사용.

    반환:
      {
        "active": [{code, name, market, qty, avg_price, cost_basis, ...}],
        "pending": [{code, name, market, qty=0, ...}],
        "all_codes": [...],  # daily 생성 대상 코드 일괄
        "counts": {"active": N, "pending": M, "total": N+M}
      }
    """
    uid = settings.stock_user_id
    rows = positions.list_daily_scope(uid)
    active = [_row_safe(r) for r in rows if r["status"] == "Active"]
    pending = [_row_safe(r) for r in rows if r["status"] == "Pending"]
    all_codes = [r["code"] for r in active] + [r["code"] for r in pending]
    return {
        "active": active,
        "pending": pending,
        "all_codes": all_codes,
        "counts": {
            "active": len(active),
            "pending": len(pending),
            "total": len(active) + len(pending),
        },
    }


@mcp.tool
def get_stock_context(code: str) -> dict:
    """
    종목 분석 시작점 — base + 최신 daily + 포지션 + watch levels + 애널 컨센.
    Claude 가 분석·의견 형성 전 첫 호출.
    """
    uid = settings.stock_user_id
    stock_row = stocks.get_stock(code)
    if not stock_row:
        return {"error": f"stock not found: {code}"}

    return {
        "stock": _row_safe(stock_row),
        "base": _row_safe(stock_base.get_base(code)),
        "latest_daily": _row_safe(stock_daily.get_latest(uid, code)),
        "position": _row_safe(positions.get_position(uid, code)),
        "watch_levels": [_row_safe(lv) for lv in watch_levels.list_by_code(uid, code)],
        "analyst_consensus": _row_safe(analyst.get_consensus(code)),
    }


@mcp.tool
def get_applied_weights(code: str, timeframe: str = "swing") -> dict:
    """
    종목 × 타임프레임의 실제 적용 스코어링 가중치.
    override 있으면 그걸, 없으면 global default. source 필드로 출처 구분.
    """
    return score_weights.get_applied(code, timeframe)


@mcp.tool
def list_trades(code: str | None = None, limit: int = 20) -> list[dict]:
    """최근 매매 이력 조회. code 지정 시 종목별."""
    uid = settings.stock_user_id
    rows = trades.list_by_user(uid, code=code, limit=limit)
    return [_row_safe(r) for r in rows]  # type: ignore[misc]


# =====================================================================
# 분석 툴 (deterministic)
# =====================================================================

@mcp.tool
def compute_indicators(code: str, days: int = 400) -> dict:
    """
    최신 OHLCV 스크래핑 → 12개 지표 반환 + 장 상태.
    stock_daily 에 저장은 하지 않음 (refresh_daily 로).
    """
    df = _fetch_ohlcv(code, days=days)
    if df.empty:
        return {"error": f"no OHLCV for {code}"}
    df = df.sort_values("날짜").reset_index(drop=True)
    df_ind = compute_all(df)
    last = df_ind.iloc[-1]

    result: dict[str, Any] = {
        "code": code,
        "date": str(last["날짜"].date()) if hasattr(last["날짜"], "date") else str(last["날짜"]),
        "close": float(last["종가"]),
        "price_context": price_context(df, market="kr"),
    }
    for col in ["SMA5", "SMA20", "SMA60", "SMA120", "SMA200", "RSI14", "ATR14",
                "Stoch_K", "Stoch_D", "ADX14", "MACD", "MACD시그널", "MACD히스토",
                "볼린저_상단", "볼린저_중심", "볼린저_하단", "전환선", "기준선"]:
        if col in last.index:
            v = last[col]
            result[col] = _dec(v) if v is not None else None
    return result


@mcp.tool
def compute_signals(code: str, days: int = 400) -> dict:
    """12개 전략 시그널 평가 + 종합 판정."""
    df = _fetch_ohlcv(code, days=days)
    if df.empty:
        return {"error": f"no OHLCV for {code}"}
    df = df.sort_values("날짜").reset_index(drop=True)
    df_ind = compute_all(df)
    sigs = analyze_all(df_ind)
    return _json_safe({
        "code": code,
        "signals": sigs,
        "summary": summarize(sigs),
    })


@mcp.tool
def check_concentration(code: str, qty: float, price: float) -> dict:
    """
    매매 집행 전 집중도 체크. 25% 룰·섹터 쏠림 등 경고.
    """
    uid = settings.stock_user_id
    data = portfolio.compute_current_weights(uid)

    cost_new = Decimal(str(qty)) * Decimal(str(price))
    target = stocks.get_stock(code)
    if not target:
        return {"error": f"stock not found: {code}"}

    # 단순 버전: Active 기준 총자산 = cost_basis 합 + cash (해당 통화)
    market = target["market"]
    currency = target["currency"]
    cash_amt = data["cash"].get(currency, Decimal(0))
    market_total = data["kr_total_krw"] if market == "kr" else data["us_total_usd"]

    # 이 종목의 기존 비중
    existing_cost = Decimal(0)
    for p in data["positions"]:
        if p["code"] == code:
            existing_cost = p["cost_basis"] or Decimal(0)
            break

    new_cost = existing_cost + cost_new
    new_weight_pct = float(new_cost / market_total * 100) if market_total else 0.0

    violations = []
    notes = []
    if new_weight_pct > 25:
        violations.append(f"25% 단일 상한 초과 (신규 비중 {new_weight_pct:.1f}%)")
    if cost_new > cash_amt:
        notes.append(f"예수금 부족 ({currency} {float(cash_amt)} vs 매수금 {float(cost_new)})")

    return {
        "ok": len(violations) == 0,
        "new_weight_pct": round(new_weight_pct, 2),
        "market_total": float(market_total),
        "cash_available": float(cash_amt),
        "violations": violations,
        "notes": notes,
    }


@mcp.tool
def propose_position_params(code: str, entry_price: float, intent: str = "") -> dict:
    """
    진입 검토 시 파라미터 추천 (초안).
    base.grade, 최신 daily, intent 종합 → style·stop_loss·tags 기본값 제시.
    """
    uid = settings.stock_user_id
    base = stock_base.get_base(code)
    daily = stock_daily.get_latest(uid, code)
    grade = (base or {}).get("grade")

    # 기본 style 결정 (간단 룰)
    if "earnings" in intent.lower() or "실적" in intent:
        suggested_style = "swing"
        horizon = 14
    elif "breakout" in intent.lower() or "돌파" in intent:
        suggested_style = "day-trade"
        horizon = 5
    elif grade in ("Premium", "Standard") and "장기" in intent:
        suggested_style = "long-term"
        horizon = 365
    else:
        suggested_style = "swing"
        horizon = 21

    defaults = score_weights.get_defaults(suggested_style)

    return {
        "code": code,
        "entry_price": entry_price,
        "intent": intent,
        "suggested": {
            "style": suggested_style,
            "horizon_days": horizon,
            "base_grade": grade,
            "default_weights": {k: float(v) for k, v in defaults.items()},
        },
        "base_snapshot": {
            "grade": grade,
            "narrative": (base or {}).get("narrative"),
            "analyst_target_avg": float((base or {}).get("analyst_target_avg") or 0) or None,
        },
        "daily_snapshot": {
            "close": float((daily or {}).get("close") or 0) or None,
            "rsi14": float((daily or {}).get("rsi14") or 0) or None,
            "verdict": (daily or {}).get("verdict"),
        },
        "note": "Claude 가 위 defaults 에 종목 상황 반영해 최종 stop_loss·tags 조정 후 record_trade + update_position_params 호출.",
    }


# =====================================================================
# 쓰기 툴
# =====================================================================

@mcp.tool
def register_stock(
    code: str,
    name: str,
    market: str,                    # 'kr' | 'us'
    industry_code: str,             # 매핑 의무 — NULL 금지 (SKILL.md 룰)
    currency: str | None = None,    # 생략 시 market 으로 추론
    ticker: str | None = None,
    listing_market: str | None = None,
) -> dict:
    """
    신규 종목 stocks 테이블 등록 (record_trade 전에 호출).

    SKILL.md 룰: industry_code NULL 금지 — 신규 등록 시 LLM 이 즉시 매핑 판단해야 함.

    industries 테이블에 해당 코드가 없으면 에러 (base-industry-updater spawn 후 재시도).

    동작:
        - 통화 자동 추론: kr → KRW, us → USD (currency 명시 시 우선)
        - US 의 경우 ticker 없으면 code 와 동일하게 자동 설정
        - ON CONFLICT — 이미 있으면 갱신 (industry_code 누락 보정에도 사용 가능)

    Returns:
        {"status": "ok", "registered": {code, name, market, industry_code, currency, ticker}}
        or
        {"error": "industry_code '...' not found in industries table — base-industry-updater spawn 후 재시도"}
    """
    if currency is None:
        currency = "KRW" if market == "kr" else "USD"
    if ticker is None and market == "us":
        ticker = code

    # industry_code 검증
    ind_row = industries.get_industry(industry_code)
    if not ind_row:
        return {
            "error": (
                f"industry_code '{industry_code}' not found in industries table — "
                f"base-industry-updater sub-agent spawn 으로 신규 산업 등록 후 재시도. "
                f"또는 stocks/{code}/base.md 작성 시 같이 매핑."
            )
        }

    stocks.upsert_stock(
        code=code,
        market=market,
        name=name,
        industry_code=industry_code,
        ticker=ticker,
        listing_market=listing_market,
        currency=currency,
    )

    # 검증 read-back
    saved = stocks.get_stock(code)
    return {"status": "ok", "registered": _row_safe(saved)}


_RULE_CATEGORIES = {
    # 진입 6
    "강매수시그널진입", "신고가돌파매수", "가치신규진입", "VCP_SEPA진입",
    "피라미딩D1안착", "실적D-1선제진입",
    # 청산 6
    "1차목표도달익절", "이벤트익절", "모멘텀꼴찌청산", "피라미딩실패컷",
    "RSI과열청산", "Defensive조기익절",
    # 관리 3
    "집중도25%회수", "ATR손절", "컨센하향청산",
}


@mcp.tool
def record_trade(
    code: str,
    side: str,           # 'buy' | 'sell'
    qty: float,
    price: float,
    executed_at: str,    # ISO datetime
    trigger_note: str = "",
    fees: float = 0,
    rule_category: str | None = None,   # ⭐ 카탈로그 enum (references/rule-catalog.md 14 룰)
) -> dict:
    """
    단건 매매 기록.

    Args:
        rule_category: 적용한 룰 카탈로그 enum (옵셔널이지만 강력 권장).
            진입 5: 강매수시그널진입 / 신고가돌파매수 / 가치신규진입 / VCP_SEPA진입 / 피라미딩D1안착
            청산 6: 1차목표도달익절 / 이벤트익절 / 모멘텀꼴찌청산 / 피라미딩실패컷 / RSI과열청산 / Defensive조기익절
            관리 3: 집중도25%회수 / ATR손절 / 컨센하향청산
            None: 옛 trades 또는 명시 안 한 매매 (회고 분류 어려움)
        trigger_note: 자유 텍스트 — 룰 명시 후 상세 사유/데이터/컨텍스트.

    트리거 자동 처리:
        - positions / realized_pnl 갱신 (recompute_position / compute_realized_pnl)
        - cash_balance 통화별 가감 (issue #7, scripts/10_cash_balance_trigger.sql)

    안전망:
        - stocks 에 code 없으면 → register_stock 안내 에러 (자동 INSERT X)
        - industry_code NULL 이면 → register_stock 으로 매핑 후 재시도 안내
        - rule_category 카탈로그 외 입력 시 명확한 에러 (CHECK constraint 가 강제하지만 사전 차단)
    """
    uid = settings.stock_user_id

    # 안전망 — stocks 존재 + industry_code 매핑 검증
    stock_row = stocks.get_stock(code)
    if stock_row is None:
        return {
            "error": (
                f"Stock '{code}' not registered — "
                f"register_stock(code, name, market, industry_code, ...) 먼저 호출 후 재시도. "
                f"SKILL.md 의 신규 종목 등록 의무 (industry_code 매핑 포함) 참조."
            )
        }
    if stock_row.get("industry_code") is None:
        return {
            "error": (
                f"Stock '{code}' has NULL industry_code — "
                f"register_stock(code='{code}', industry_code='<매핑>', ...) 으로 갱신 후 재시도. "
                f"SKILL.md 의 NULL industry_code 금지 룰."
            )
        }

    # rule_category 사전 검증 (CHECK constraint 더블 가드)
    if rule_category is not None and rule_category not in _RULE_CATEGORIES:
        return {
            "error": (
                f"rule_category '{rule_category}' not in catalog — "
                f"references/rule-catalog.md 의 14 룰 중 1개 또는 None. "
                f"신규 룰 필요 시 카탈로그 확장 후 재시도."
            )
        }

    dt = datetime.fromisoformat(executed_at)
    tid = trades.record_trade(
        user_id=uid, code=code, side=side, qty=qty, price=price,
        executed_at=dt, trigger_note=trigger_note or None, fees=fees,
        rule_category=rule_category,
    )
    # 결과 조회
    row = next((t for t in trades.list_by_user(uid, limit=3) if t["id"] == tid), None)
    pos = positions.get_position(uid, code)
    result = {
        "trade": _row_safe(row),
        "position_after": _row_safe(pos),
    }
    if rule_category is None:
        result["warning"] = (
            "rule_category 미입력 — 회고 작성 시 룰별 분류 어려움. "
            "다음 매매 시 references/rule-catalog.md 의 14 룰 중 1개 명시 권장."
        )
    return result


@mcp.tool
def override_score_weights(
    code: str,
    timeframe: str,
    재무: float,
    산업: float,
    경제: float,
    기술: float,
    밸류에이션: float,
    reason: str,
) -> dict:
    """
    종목별 가중치 override. 합계 1.0 ± 0.01 검증. history 자동 기록.
    """
    score_weights.set_override(
        code=code, timeframe=timeframe,
        weights={"재무": 재무, "산업": 산업, "경제": 경제, "기술": 기술, "밸류에이션": 밸류에이션},
        reason=reason, source="claude",
    )
    return {"ok": True, "applied": score_weights.get_applied(code, timeframe)}


@mcp.tool
def reset_score_weights(code: str, timeframe: str | None = None) -> dict:
    """종목 override 제거 (default 복원)."""
    removed = score_weights.reset_override(code, timeframe)
    return {"ok": True, "removed": removed}


@mcp.tool
def save_daily_report(
    code: str,
    date: str,
    verdict: str,
    content: str,
    *,
    # v7 (2026-05): 결론 정량 컬럼 (G6 결정 — 추론 자연어, 결론 정량)
    size_pct: int | None = None,
    stop_method: str | None = None,
    stop_value: float | None = None,
    override_dimensions: list | None = None,
    key_factors: list | None = None,
    referenced_rules: list | None = None,
) -> dict:
    """
    일일 분석 보고서 저장. date = 'YYYY-MM-DD'.
    verdict CHECK: '강한매수'|'매수우세'|'중립'|'매도우세'|'강한매도'.
    signals JSONB 는 compute_signals 결과를 Claude 가 먼저 확인 후 별도 upsert_signals로.

    v7 신규 결론 정량 인자 (per-stock-analysis 7단계 출력 의무):
      size_pct: LLM 결정 진입 사이즈 (%, NULL 허용)
      stop_method: '%' or 'ATR'
      stop_value: -7 (% 손절) 또는 1.5 (ATR 배수)
      override_dimensions: 활성화된 override 차원 list (예: ["earnings_d7", ...])
      key_factors: 결정 영향 큰 요소 3~5개 (자연어 짧게)
      referenced_rules: 인용한 rule_catalog ID list
    """
    from datetime import date as date_cls

    uid = settings.stock_user_id
    d = date_cls.fromisoformat(date)
    # verdict 빈 문자열 → None 으로 normalize (CHECK constraint 위반 회피)
    v = verdict.strip() if verdict else None
    stock_daily.upsert_content(
        uid, code, d, content, verdict=v or None,
        size_pct=size_pct, stop_method=stop_method, stop_value=stop_value,
        override_dimensions=override_dimensions,
        key_factors=key_factors,
        referenced_rules=referenced_rules,
    )
    return {"ok": True, "code": code, "date": date, "verdict": v or None, "chars": len(content)}


@mcp.tool
def save_portfolio_summary(
    date: str,
    per_stock_summary: list[dict] | None = None,
    risk_flags: list[dict] | None = None,
    action_plan: list[dict] | None = None,
    headline: str | None = None,
    summary_content: str | None = None,
) -> dict:
    """
    포트폴리오 일일 종합 스냅샷 저장 (v11).

    인자:
      date: YYYY-MM-DD
      per_stock_summary: [{code,name,close,change_pct,pnl_pct,verdict,note}, ...]
      risk_flags:        [{type, code?, scope?, level, detail}, ...]
      action_plan:       [{priority,code,action('buy'|'sell'|'hold'),qty,price_hint,trigger,
                           condition,reason,status('pending'|'conditional'|'executed'|'skipped'|'expired'),
                           executed_trade_id,expires_at(ISO)}, ...]
      headline: 한 줄 결론
      summary_content: 자유 서술 본문 (마크다운)

    upsert — 같은 (user, date) 덮어씀.
    """
    from datetime import date as date_cls

    uid = settings.stock_user_id
    d = date_cls.fromisoformat(date)
    portfolio_snapshots.save(
        uid, d,
        per_stock_summary=per_stock_summary,
        risk_flags=risk_flags,
        action_plan=action_plan,
        headline=headline,
        summary_content=summary_content,
    )
    return {
        "ok": True,
        "date": date,
        "action_count": len(action_plan or []),
        "stock_count": len(per_stock_summary or []),
        "risk_count": len(risk_flags or []),
    }


@mcp.tool
def get_portfolio_summary(date: str) -> dict:
    """
    특정 날짜 포트 스냅샷 로드. 없으면 null.

    어제 pending 액션 리마인드 용도. `/stock-daily` 시작 시 yesterday 전달.
    """
    from datetime import date as date_cls

    uid = settings.stock_user_id
    d = date_cls.fromisoformat(date)
    row = portfolio_snapshots.get(uid, d)
    if row is None:
        return {"found": False, "date": date}
    return {"found": True, "snapshot": _row_safe(row)}


@mcp.tool
def reconcile_actions(date: str) -> dict:
    """
    해당 date 의 action_plan 을 trades 와 매칭.

    매칭 규칙:
      - action.code == trade.code AND action.action == trade.side
      - trade.executed_at::date >= snapshot.date
    매칭 성공 시 status='executed' + executed_trade_id 세팅.
    매칭 못 하고 expires_at 이 과거면 status='expired'.

    반환: {updated, total_actions, matched_trade_ids}
    """
    from datetime import date as date_cls

    uid = settings.stock_user_id
    d = date_cls.fromisoformat(date)
    return portfolio_snapshots.reconcile(uid, d)


# =====================================================================
# KIS 실시간 시세 (Phase 3b)
# =====================================================================

@mcp.tool
def kis_current_price(code: str) -> dict:
    """
    KIS API 로 국내 주식 정규장 현재가 조회 (15:30 이후엔 정규장 종가 반환).
    PER/PBR/외국인 보유율 포함. 시간외 단일가가 필요하면 `realtime_price` 사용.
    """
    return kis.fetch_current_price(code)


def _kr_market_state() -> str:
    """KST 기준 장 상태 판정: 'regular' | 'afterhours' | 'closed'."""
    from datetime import datetime, time as dtime
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("Asia/Seoul"))
    if now.weekday() >= 5:
        return "closed"
    t = now.time()
    if dtime(9, 0) <= t <= dtime(15, 30):
        return "regular"
    if dtime(15, 31) <= t <= dtime(18, 10):
        return "afterhours"
    return "closed"


@mcp.tool
def realtime_price(code: str) -> dict:
    """
    국내 주식 현재가 시간대 자동 분기 조회.

    - 정규장(09:00~15:30 KST): KIS API `fetch_current_price`
    - 시간외 단일가(15:31~18:10): Naver `fetch_realtime_price` (시간외 반영)
    - 장 마감/주말/공휴일: Naver (최종 종가 or 시간외 최종)

    반환에 `source` 필드로 어느 경로로 조회됐는지 명시.
    """
    state = _kr_market_state()
    if state == "regular":
        res = kis.fetch_current_price(code)
        res["source"] = "kis_regular"
        res["market_state"] = state
        return res
    # 시간외 or 장외: Naver 실시간 (시간외 자동 반영)
    res = naver.fetch_realtime_price(code)
    res["market_state"] = state
    return res


@mcp.tool
def kis_us_quote(ticker: str, exchange: str = "NAS") -> dict:
    """
    KIS API 로 해외 주식 실시간 현재가. exchange: NAS/NYS/AMS/HKS.
    """
    return kis.fetch_us_quote(ticker, exchange)


@mcp.tool
def kis_intraday(code: str, interval: int = 60) -> list[dict]:
    """
    KIS API 분봉 (1/3/5/10/15/30/60분, 최대 30행).
    """
    df = kis.fetch_minute_ohlcv(code, interval=interval)
    if df.empty:
        return []
    return df.to_dict(orient="records")


# =====================================================================
# 재무 분석 (KR=DART / US=SEC EDGAR)
# =====================================================================

@mcp.tool
def compute_financials(code: str, years: int = 3) -> dict:
    """
    재무제표 → 비율·성장률·재무점수·요약.
    KR (6자리 코드): DART 호출. US (티커): SEC EDGAR XBRL 호출.
    매분기 갱신 (데이터 변경 시만 필요).
    """
    from server.repos import stocks as stocks_repo
    s = stocks_repo.get_stock(code)
    market = (s or {}).get("market") or ("us" if code.isalpha() else "kr")

    if market == "us":
        from server.scrapers import edgar
        try:
            fin = edgar.fetch_financials(code, years=years)
            summary = edgar.summarize_financials(fin)
        except Exception as e:
            return {"error": f"SEC EDGAR 호출 실패: {e}", "market": "us"}
    else:
        try:
            fin = dart.fetch_financials(code, years=years)
            summary = dart.summarize_financials(fin)
        except Exception as e:
            return {"error": f"DART 호출 실패: {e}", "market": "kr"}

    # raw_summary 의 사전계산 값을 ratios 에 직접 매핑 (refresh_base.py 패턴과 동일).
    # compute_financial_ratios 의 raw 키 매핑은 KR/US summary 키와 맞지 않아 None 으로 빠짐.
    ratios: dict = {
        "per": summary.get("PER"),
        "pbr": summary.get("PBR"),
        "eps": summary.get("EPS"),
        "bps": summary.get("BPS"),
        "psr": None,
        "ev_ebitda": None,
        "roe": summary.get("ROE"),
        "roa": summary.get("ROA"),
        "op_margin": summary.get("영업이익률"),
        "net_margin": summary.get("순이익률"),
        "debt_ratio": summary.get("부채비율"),
        "fcf_yield": None,
    }
    growth: dict = {
        "revenue_yoy": summary.get("매출_YoY"),
        "op_profit_yoy": summary.get("영업이익_YoY"),
        "net_profit_yoy": summary.get("순이익_YoY"),
        "revenue_qoq": None,
        "op_profit_qoq": None,
        "eps_yoy": None,
    }
    if summary.get("quarterly"):
        q_growth = compute_growth_rates(summary["quarterly"])
        for k, v in q_growth.items():
            if v is not None:
                growth[k] = v
    score = compute_financial_score(ratios, growth)

    return {
        "code": code,
        "market": market,
        "ratios": ratios,
        "growth": growth,
        "score": score,
        "health_summary": summarize_health(ratios, growth, score),
        "raw_summary": summary,
    }


@mcp.tool
def detect_earnings_surprise_tool(code: str, actual: float, consensus: float) -> dict:
    """
    실적 서프라이즈 판정. (actual - consensus) / consensus × 100.
    magnitude: strong (>10%) / mild / weak.
    """
    return detect_earnings_surprise(actual=actual, consensus=consensus)


# =====================================================================
# 애널리스트 리포트
# =====================================================================

@mcp.tool
def record_analyst_report(
    code: str,
    broker: str,
    published_at: str,
    rating: str,
    target_price: float,
    *,
    previous_target_price: float | None = None,
    rating_change: str | None = None,
    broker_country: str = "kr",
    report_url: str | None = None,
    title: str | None = None,
    summary: str | None = None,
    key_thesis: str | None = None,
    currency: str = "KRW",
) -> dict:
    """
    애널리스트 리포트 저장. URL 중복 자동 skip.
    rating: strong_buy|buy|hold|sell|strong_sell
    rating_change: initiate|upgrade|downgrade|reiterate
    """
    inserted_id = analyst.record_report(
        code=code, broker=broker,
        published_at=datetime.fromisoformat(published_at),
        rating=rating,
        target_price=Decimal(str(target_price)),
        previous_target_price=Decimal(str(previous_target_price)) if previous_target_price else None,
        rating_change=rating_change,
        broker_country=broker_country,
        report_url=report_url,
        title=title,
        summary=summary,
        key_thesis=key_thesis,
        currency=currency,
    )
    return {
        "ok": inserted_id is not None,
        "id": inserted_id,
        "duplicate": inserted_id is None and report_url is not None,
    }


@mcp.tool
def list_analyst_reports(code: str, days: int = 90) -> list[dict]:
    """종목 최근 N일 애널리스트 리포트 목록."""
    rows = analyst.list_recent(code, days=days)
    return [_row_safe(r) for r in rows]  # type: ignore[misc]


@mcp.tool
def get_analyst_consensus(code: str) -> dict | None:
    """
    v_analyst_consensus 뷰 조회. 3개월 평균/최대/최소 목표가, 지배적 rating,
    1개월 평균 vs 이전 1개월 평균 (모멘텀 파악).
    """
    return _row_safe(analyst.get_consensus(code))


# =====================================================================
# 신규 분석 (flow · events · correlation · volatility · consensus)
# =====================================================================

@mcp.tool
def analyze_flow(code: str, window: int = 20) -> dict:
    """
    기관·외국인 최근 window일 수급 분석. 매집/분산 판정 + z-score 이상거래.
    네이버 fetch_investor 데이터 사용.
    """
    try:
        df = naver.fetch_investor(code, pages=max(window // 20 + 1, 2))
    except Exception as e:
        return {"error": f"네이버 조회 실패: {e}"}
    return analyze_investor_flow(df, window=window)


@mcp.tool
def detect_events(code: str) -> dict:
    """
    종목 이벤트 감지:
      - 실적 D-N (DART 기반)
      - 52주 고저 돌파 (네이버 일봉)
      - rating change (analyst_reports 최근 7일)
    """
    uid = settings.stock_user_id
    result: dict = {}

    # 실적
    try:
        ne = dart.fetch_next_earnings_date(code)
        next_date = ne.get("발표예정일") if isinstance(ne, dict) else None
        if next_date:
            from datetime import date as date_cls
            result["earnings"] = earnings_proximity(
                date_cls.fromisoformat(str(next_date))
            )
    except Exception as e:
        result["earnings"] = {"error": str(e)}

    # 52주 돌파
    try:
        df = _fetch_ohlcv(code, days=400).sort_values("날짜").reset_index(drop=True)
        result["price_break"] = detect_52week_break(df)
    except Exception as e:
        result["price_break"] = {"error": str(e)}

    # Rating change
    try:
        reports = analyst.list_recent(code, days=30)
        result["rating_changes"] = detect_rating_changes(reports, days=7)
    except Exception as e:
        result["rating_changes"] = {"error": str(e)}

    return result


@mcp.tool
def portfolio_correlation(days: int = 60) -> dict:
    """
    현재 Active 포지션 종목 간 상관 행렬.
    KR/US 모두 포함. 비중은 cost_basis 기준.
    """
    uid = settings.stock_user_id
    active = positions.list_active(uid)
    if len(active) < 2:
        return {"error": "need at least 2 active positions"}

    import pandas as pd
    prices: dict = {}
    weights: dict = {}
    total_cost = sum(float(p["cost_basis"] or 0) for p in active)
    for p in active:
        code = p["code"]
        market = p["market"]
        try:
            # #19 fix — _fetch_ohlcv 통일 (KR/US 자동 분기 + yfinance fallback for >100일 US)
            df = _fetch_ohlcv(code, days=max(days, 20))
            if df.empty:
                continue
            df = df.sort_values("날짜").reset_index(drop=True)
            close_col = "종가" if "종가" in df.columns else "close"
            prices[code] = pd.Series(df[close_col].values, index=df["날짜"].values)
            weights[code] = float(p["cost_basis"] or 0) / total_cost if total_cost else 1.0 / len(active)
        except Exception as e:
            print(f"[portfolio_correlation] {code} fail: {e}")
            continue

    return diversification_metrics(prices, weights=weights)


@mcp.tool
def analyze_volatility(code: str, days: int = 100) -> dict:
    """
    종목 변동성·drawdown·regime 분류.
    """
    try:
        df = _fetch_ohlcv(code, days=max(days, 20)).sort_values("날짜").reset_index(drop=True)
    except Exception as e:
        return {"error": str(e)}

    rv = realized_volatility(df, window=30)
    pv = parkinson_volatility(df, window=30)
    dd = compute_drawdown(df)
    regime = classify_vol_regime(rv)

    return {
        "code": code,
        "realized_vol_pct": rv,
        "parkinson_vol_pct": pv,
        "regime": regime,
        "drawdown": dd,
    }


@mcp.tool
def analyze_consensus_trend(code: str, days: int = 90) -> dict:
    """
    애널 컨센서스 추이 분석:
      - 목표가 momentum (최근 30일 평균 vs 이전 30일 평균)
      - rating wave (upgrade/downgrade 집계)
    """
    reports = analyst.list_recent(code, days=days)
    return {
        "code": code,
        "target_price_trend": target_price_trend(reports, days_current=30, days_prev=60),
        "rating_wave": rating_wave(reports, days=30),
        "total_reports": len(reports),
    }


@mcp.tool
def detect_portfolio_concentration() -> dict:
    """
    전 포지션 집중도 경고 (시장별 25%+).
    """
    uid = settings.stock_user_id
    active = positions.list_active(uid)
    cash_data = cash.get_all(uid)
    alerts = detect_concentration_alerts(
        [_row_safe(p) for p in active],  # type: ignore[list-item]
        {k: float(v) for k, v in cash_data.items()},
    )
    return {"alerts": alerts, "count": len(alerts)}


# =====================================================================
# Skill 완전 대응 6개 추가 툴
# =====================================================================

@mcp.tool
def compute_score(
    code: str,
    timeframe: str = "스윙",
    *,
    financial_score: int | None = None,
    industry_score: int | None = None,
    economy_score: int | None = None,
    technical_score: int | None = None,
    valuation_score: int | None = None,
) -> dict:
    """
    5차원 종합 등급 산정 (Premium/Standard/Cautious/Defensive).
    timeframe: '단타' | '스윙' | '중장기' | '모멘텀'.

    점수 미지정 시:
      - financial: compute_financials → score
      - industry/economy: industries/economy_base 테이블의 meta 기반
      - technical: 최근 daily verdict → 환산
      - valuation: stock_base.analyst_target_avg vs 현재가
    """
    stock_row = stocks.get_stock(code)
    if not stock_row:
        return {"error": f"stock not found: {code}"}
    market = stock_row["market"]

    fin_dict = {"점수": financial_score if financial_score is not None else 50}
    ind_dict = {"점수": industry_score if industry_score is not None else 50}
    mac_dict = {"점수": economy_score if economy_score is not None else 50}
    tech_dict = {"점수": technical_score} if technical_score is not None else None
    val_dict = {"점수": valuation_score} if valuation_score is not None else None

    # 기본 점수 자동 보강 (DB 기반)
    if financial_score is None:
        base = stock_base.get_base(code)
        if base and base.get("financial_score"):
            fin_dict["점수"] = base["financial_score"]

    if industry_score is None and stock_row.get("industry_code"):
        ind = industries.get_industry(stock_row["industry_code"])
        if ind and ind.get("score"):
            ind_dict["점수"] = ind["score"]

    if economy_score is None:
        econ = economy.get_base(market)
        # economy_base 엔 score 필드 없음 → context 기반 간이 점수
        mac_dict["점수"] = 70  # 디폴트 (실제로는 research로 업데이트됨)

    if technical_score is None:
        uid = settings.stock_user_id
        latest = stock_daily.get_latest(uid, code)
        if latest and latest.get("verdict"):
            mapping = {"강한매수": 85, "매수우세": 70, "중립": 55, "매도우세": 35, "강한매도": 20}
            tech_dict = {"점수": mapping.get(latest["verdict"], 50)}

    result = total_grade(fin_dict, ind_dict, mac_dict, tech_dict, val_dict, timeframe=timeframe)
    return {
        "code": code,
        "timeframe": timeframe,
        "total_score": result["가중총점"],
        "grade": result["등급"],
        "breakdown": {
            "financial": fin_dict["점수"],
            "industry": ind_dict["점수"],
            "economy": mac_dict["점수"],
            "technical": tech_dict["점수"] if tech_dict else None,
            "valuation": val_dict["점수"] if val_dict else None,
        },
        "action_template": result.get("액션_템플릿"),
    }


@mcp.tool
def save_stock_base(
    code: str,
    *,
    total_score: int | None = None,
    financial_score: int | None = None,
    industry_score: int | None = None,
    economy_score: int | None = None,
    grade: str | None = None,
    fair_value_avg: float | None = None,
    analyst_target_avg: float | None = None,
    analyst_target_max: float | None = None,
    analyst_consensus_count: int | None = None,
    per: float | None = None,
    pbr: float | None = None,
    roe: float | None = None,
    op_margin: float | None = None,
    narrative: str | None = None,
    risks: str | None = None,
    scenarios: str | None = None,
    content: str | None = None,
) -> dict:
    """
    research 결과를 stock_base 에 upsert.
    None 인 필드는 기존 값 유지 (COALESCE).
    """
    stock_base.upsert_base(
        code=code,
        total_score=total_score,
        financial_score=financial_score,
        industry_score=industry_score,
        economy_score=economy_score,
        grade=grade,
        fair_value_avg=Decimal(str(fair_value_avg)) if fair_value_avg is not None else None,
        analyst_target_avg=Decimal(str(analyst_target_avg)) if analyst_target_avg is not None else None,
        analyst_target_max=Decimal(str(analyst_target_max)) if analyst_target_max is not None else None,
        analyst_consensus_count=analyst_consensus_count,
        per=Decimal(str(per)) if per is not None else None,
        pbr=Decimal(str(pbr)) if pbr is not None else None,
        roe=Decimal(str(roe)) if roe is not None else None,
        op_margin=Decimal(str(op_margin)) if op_margin is not None else None,
        narrative=narrative, risks=risks, scenarios=scenarios, content=content,
    )
    return {"ok": True, "code": code, "updated": _row_safe(stock_base.get_base(code))}


@mcp.tool
def save_economy_base(
    market: str = "kr",
    *,
    context: dict | None = None,
    content: str | None = None,
    cycle_phase: str | None = None,
    scenario_probs: dict | None = None,
) -> dict:
    """
    economy_base 테이블에 upsert. None 필드는 기존 값 유지 (COALESCE).

    Daily append 패턴:
      1. get via get_economy_base(market) 또는 get_stock_context 유사
      2. content 에 "## 📝 Daily Appended Facts" 섹션 append
      3. save_economy_base(market, content=new_content)

    Research 재작성:
      - 전체 content 덮어쓰기

    v4 (2026-05) 신규 인자:
      - cycle_phase: '확장' | '정점' | '수축' | '저점' (사이클 단계, base inline 절차 v4-b)
      - scenario_probs: {"bull": 0.30, "base": 0.50, "bear": 0.20} (시나리오 트리, v4-a)
    """
    from server.repos import economy
    economy.upsert_base(
        market=market, context=context, content=content,
        cycle_phase=cycle_phase, scenario_probs=scenario_probs,
    )
    return {"ok": True, "market": market, "updated": _row_safe(economy.get_base(market))}


@mcp.tool
def get_economy_base(market: str = "kr") -> dict | None:
    """economy_base 조회 (append 전 현재 content 읽기 용)."""
    from server.repos import economy
    return _row_safe(economy.get_base(market))


@mcp.tool
def save_industry(
    code: str,
    name: str,
    *,
    market: str | None = None,
    name_en: str | None = None,
    parent_code: str | None = None,
    meta: dict | None = None,
    market_specific: dict | None = None,
    score: int | None = None,
    content: str | None = None,
    cycle_phase: str | None = None,
    momentum_rs_3m: float | None = None,
    momentum_rs_6m: float | None = None,
    leader_followers: dict | None = None,
    avg_per: float | None = None,
    avg_pbr: float | None = None,
    avg_roe: float | None = None,
    avg_op_margin: float | None = None,
    vol_baseline_30d: float | None = None,
) -> dict:
    """
    industries 테이블에 upsert. None 필드는 기존 값 유지 (COALESCE).

    Daily append 패턴:
      1. get via get_industry(code) 로 현재 content 로드
      2. "## 📝 Daily Appended Facts" 섹션에 append
      3. save_industry(code, name, content=new_content)

    Research 재작성:
      - 전체 content 덮어쓰기

    v4 (2026-05) 신규 인자:
      - cycle_phase: '도입' | '성장' | '성숙' | '쇠퇴' (산업 사이클 단계, v4-c)
      - momentum_rs_3m / momentum_rs_6m: 산업 ETF 의 KOSPI/SPY 대비 RS (%, v4-d)
      - leader_followers: {"leaders": [...], "followers": [...]} (Top 3 리더 + 팔로워, v4-e)

    v6 (2026-05) 신규 인자 — 산업 표준 메트릭 (종목 financial_grade 본문 판단 근거):
      - avg_per: 산업 평균 PER
      - avg_pbr: 산업 평균 PBR
      - avg_roe: 산업 평균 ROE (%)
      - avg_op_margin: 산업 평균 영업이익률 (%)
      - vol_baseline_30d: 산업 평균 30일 RV (%)
    """
    from server.repos import industries
    industries.upsert(
        code=code, market=market, name=name,
        name_en=name_en, parent_code=parent_code,
        meta=meta, market_specific=market_specific,
        score=score, content=content,
        cycle_phase=cycle_phase,
        momentum_rs_3m=momentum_rs_3m,
        momentum_rs_6m=momentum_rs_6m,
        leader_followers=leader_followers,
        avg_per=avg_per, avg_pbr=avg_pbr,
        avg_roe=avg_roe, avg_op_margin=avg_op_margin,
        vol_baseline_30d=vol_baseline_30d,
    )
    return {"ok": True, "code": code, "updated": _row_safe(industries.get_industry(code))}


@mcp.tool
def get_industry(code: str) -> dict | None:
    """industries 조회 (append 전 현재 content 읽기 용)."""
    from server.repos import industries
    return _row_safe(industries.get_industry(code))


@mcp.tool
def save_weekly_review(
    week_start: str,
    week_end: str,
    *,
    realized_pnl_kr: float | None = None,
    realized_pnl_us: float | None = None,
    unrealized_pnl_kr: float | None = None,
    unrealized_pnl_us: float | None = None,
    trade_count: int | None = None,
    win_rate: dict | None = None,
    rule_evaluations: list | None = None,
    highlights: list | None = None,
    next_week_actions: list | None = None,
    headline: str | None = None,
    content: str | None = None,
    # v7 (2026-05): 결론 정량 컬럼 (G6 결정)
    rule_win_rates: dict | None = None,
    pattern_findings: list | None = None,
    lessons_learned: list | None = None,
    next_week_emphasize: list | None = None,
    next_week_avoid: list | None = None,
    override_freq_30d: dict | None = None,
    # 라운드 2026-05 weekly-review overhaul: 4-Phase 결과
    base_phase0_log: dict | None = None,
    phase3_log: dict | None = None,
    per_stock_review_count: int | None = None,
    base_appendback_count: int | None = None,
    propose_narrative_revision_count: int | None = None,
) -> dict:
    """
    주간 회고 저장 (upsert).

    week_start: 'YYYY-MM-DD' 월요일 (KST)
    week_end:   'YYYY-MM-DD' 금요일 (KST)

    - win_rate: {strategy_name: {tries, wins, pct}}
    - rule_evaluations: [{rule, trade_id, foregone_pnl, smart_or_early, ...}]
    - highlights: [{type: 'insight'|'pattern'|'warning', detail}]
    - next_week_actions: portfolio_summary.action_plan 과 동일 스키마

    v7 신규 결론 정량 인자:
      rule_win_rates: {rule_id: win_rate} — 15 룰 카탈로그 기준
      pattern_findings: [{tag, description, sample_count, win_rate}]
      lessons_learned: [{tag, lesson}]
      next_week_emphasize: 강화 룰 ID list (이번 주 win-rate 높은)
      next_week_avoid: 자제 룰 ID list (이번 주 win-rate < 30%)
      override_freq_30d: {dimension: count} — 30일 override 활성화 빈도

    라운드 2026-05 weekly-review overhaul 신규 인자:
      base_phase0_log: {economy: {...}, industries: [...], stocks: [...], skipped: [...]}
        Phase 0 base 갱신 결과 (cascade economy → industry → stock)
      phase3_log: {appended_facts: [...], proposed_revisions: [...]}
        Phase 3 base append-back / narrative_revision 큐
      per_stock_review_count: weekly_review_per_stock row 수 (Phase 1 결과 카운트)
      base_appendback_count: Phase 3 자동 append 건수
      propose_narrative_revision_count: Phase 3 사용자 큐 적재 건수

    None 인 필드는 기존 값 유지 (COALESCE).
    """
    from datetime import date as date_cls
    from server.repos import weekly_reviews as wr

    ws = date_cls.fromisoformat(week_start)
    we = date_cls.fromisoformat(week_end)

    wr.upsert_review(
        week_start=ws,
        week_end=we,
        realized_pnl_kr=Decimal(str(realized_pnl_kr)) if realized_pnl_kr is not None else None,
        realized_pnl_us=Decimal(str(realized_pnl_us)) if realized_pnl_us is not None else None,
        unrealized_pnl_kr=Decimal(str(unrealized_pnl_kr)) if unrealized_pnl_kr is not None else None,
        unrealized_pnl_us=Decimal(str(unrealized_pnl_us)) if unrealized_pnl_us is not None else None,
        trade_count=trade_count,
        win_rate=win_rate,
        rule_evaluations=rule_evaluations,
        highlights=highlights,
        next_week_actions=next_week_actions,
        headline=headline,
        content=content,
        rule_win_rates=rule_win_rates,
        pattern_findings=pattern_findings,
        lessons_learned=lessons_learned,
        next_week_emphasize=next_week_emphasize,
        next_week_avoid=next_week_avoid,
        override_freq_30d=override_freq_30d,
        base_phase0_log=base_phase0_log,
        phase3_log=phase3_log,
        per_stock_review_count=per_stock_review_count,
        base_appendback_count=base_appendback_count,
        propose_narrative_revision_count=propose_narrative_revision_count,
    )
    return {"ok": True, "week_start": week_start, "week_end": week_end}


@mcp.tool
def get_weekly_review(week_start: str) -> dict | None:
    """주간 회고 조회. week_start = 'YYYY-MM-DD' 월요일."""
    from datetime import date as date_cls
    from server.repos import weekly_reviews as wr

    ws = date_cls.fromisoformat(week_start)
    return _row_safe(wr.get_review(ws))


@mcp.tool
def list_weekly_reviews(limit: int = 12) -> list[dict]:
    """최근 N주 회고 목록 (week_start DESC)."""
    from server.repos import weekly_reviews as wr
    rows = wr.list_reviews(limit=limit)
    return [r for r in (_row_safe(row) for row in rows) if r is not None]


# v7 (2026-05): learned_patterns MCP — 자연어 인사이트 → 정량 메모리 (G6 결정)

@mcp.tool
def get_learned_patterns(status: str | None = None, limit: int = 50) -> list[dict]:
    """learned_patterns 조회 (promotion_status 별 필터). last_seen DESC.

    status: 'observation' | 'rule_candidate' | 'principle' | 'user_principle' | None (전체)
    per-stock-analysis 6단계 LLM 판단에서 user_principle / principle 카테고리 우선 인용.
    """
    from server.repos import learned_patterns
    rows = learned_patterns.list_by_status(status=status, limit=limit)
    return [r for r in (_row_safe(row) for row in rows) if r is not None]


@mcp.tool
def append_learned_pattern(
    tag: str,
    description: str,
    *,
    outcome: str | None = None,
    trade_id: int | None = None,
    related_rule_ids: list[int] | None = None,
) -> dict:
    """패턴 발견 시 호출. 기존 tag 면 occurrences/sample_count/win_rate 누적, 신규면 INSERT.

    weekly_review 작성 시 LLM 이 패턴 인사이트마다 본 함수 호출 의무 (v7 학습 본체).

    outcome: 'win' | 'loss' | 'neutral' (None 이면 sample_count 미증가, 관찰만)
    """
    from server.repos import learned_patterns
    learned_patterns.append(
        tag, description,
        outcome=outcome, trade_id=trade_id,
        related_rule_ids=related_rule_ids,
    )
    return {"ok": True, "tag": tag, "row": _row_safe(learned_patterns.get_by_tag(tag))}


# v8 (2026-05): weekly_strategy MCP — 5번째 모드 (사용자 + LLM 브레인스토밍)

@mcp.tool
def save_weekly_strategy(
    week_start: str,
    *,
    market_outlook: str | None = None,
    focus_themes: list | None = None,
    rules_to_emphasize: list | None = None,
    rules_to_avoid: list | None = None,
    position_targets: dict | None = None,
    risk_caps: dict | None = None,
    notes: str | None = None,
    brainstorm_log: str | None = None,
) -> dict:
    """주간 전략 저장 (upsert). approved_at 자동 NOW().

    week_start: 'YYYY-MM-DD' 월요일 (KST)

    인자:
      market_outlook: 자연어 시장관 (cycle_phase 인용)
      focus_themes: 산업/테마 list (예: ["반도체", "AI인프라"])
      rules_to_emphasize: 강화 룰 ID list (rule_catalog 기준)
      rules_to_avoid: 자제 룰 ID list (지난주 win-rate < 30%)
      position_targets: {신규: [...], 청산: [...], 비중: {kr, us}}
      risk_caps: {single_trade_pct, sector_max, cash_min}
      notes: 사용자 자율 코멘트
      brainstorm_log: LLM 1~3 옵션 제시 + 사용자 검토 대화 로그
    """
    from datetime import date as date_cls
    from server.repos import weekly_strategy as ws

    wd = date_cls.fromisoformat(week_start)
    ws.upsert(
        week_start=wd,
        market_outlook=market_outlook,
        focus_themes=focus_themes,
        rules_to_emphasize=rules_to_emphasize,
        rules_to_avoid=rules_to_avoid,
        position_targets=position_targets,
        risk_caps=risk_caps,
        notes=notes,
        brainstorm_log=brainstorm_log,
    )
    return {"ok": True, "week_start": week_start, "row": _row_safe(ws.get_by_week(wd))}


@mcp.tool
def get_weekly_strategy(week_start: str | None = None) -> dict | None:
    """주간 전략 조회.

    week_start: 'YYYY-MM-DD' 월요일 (KST). None 이면 이번 주 (오늘 기준 월요일).
    미작성 시 직전 작성 row + carry_over=True 플래그 (5단계 brainstorm 절차의 carry-over 정책).
    """
    from datetime import date as date_cls
    from server.repos import weekly_strategy as ws

    if week_start is None:
        result = ws.get_current()
        return _row_safe(result) if result else None

    wd = date_cls.fromisoformat(week_start)
    row = ws.get_by_week(wd)
    if row:
        return {**_row_safe(row), "carry_over": False}
    return None


@mcp.tool
def list_weekly_strategies(weeks: int = 12) -> list[dict]:
    """최근 N주 weekly_strategy 목록 (week_start DESC).

    brainstorm 시 1단계 인풋 — 지난 4~12주 strategies 인용해서 사용자 행동 패턴 추출.
    """
    from server.repos import weekly_strategy as ws
    rows = ws.list_strategies(weeks=weeks)
    return [r for r in (_row_safe(row) for row in rows) if r is not None]


@mcp.tool
def promote_learned_pattern(tag: str, new_status: str) -> dict:
    """promotion_status 갱신. 'observation' → 'rule_candidate' → 'principle' / 'user_principle'.

    user_principle 격상은 사용자가 weekly_strategy 에서 반복 강조한 패턴에 적용.
    principle 격상은 시스템 통계 (occurrences ≥ N + win_rate 임계 이상) 자동 후보 발견 시.
    """
    from server.repos import learned_patterns
    learned_patterns.promote(tag, new_status)
    return {"ok": True, "tag": tag, "row": _row_safe(learned_patterns.get_by_tag(tag))}


@mcp.tool
def get_weekly_context(weeks: int = 4) -> dict:
    """
    Daily 분석 시 활용할 최근 N주 회고 통합 컨텍스트.

    반환:
      - latest_review:  최근 회고 1건 (headline + highlights + pending_actions)
      - rolling_stats:  최근 N주 합산 (룰별 승률, 총 실현, 거래 수)
      - carryover_actions: 만료 안 된 미체결 액션 (전 주 → 이번 주 carry)

    Daily 시작 시 (BLOCKING #8) 1회 호출 → 학습된 룰·승률·미체결 자동 반영.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from server.repos import weekly_reviews as wr

    rows = wr.list_reviews(limit=max(weeks, 1))
    if not rows:
        return {
            "latest_review": None,
            "rolling_stats": {"weeks_count": 0, "rule_win_rates": {}, "total_realized_pnl_kr": 0, "avg_weekly_pnl_kr": 0, "trade_count_total": 0},
            "carryover_actions": [],
        }

    # 최근 1건의 풀 데이터를 다시 읽음 (list_reviews 는 일부 필드만 반환)
    latest_meta = rows[0]
    latest_full = wr.get_review(latest_meta["week_start"])

    pending_actions = []
    carryover = []
    if latest_full:
        for a in (latest_full.get("next_week_actions") or []):
            status = a.get("status", "")
            if status in ("pending", "conditional"):
                # 만료 체크
                exp = a.get("expires_at")
                if exp:
                    try:
                        exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                        if exp_dt > datetime.now(ZoneInfo("UTC")):
                            pending_actions.append(a)
                    except Exception:
                        pending_actions.append(a)
                else:
                    pending_actions.append(a)

    # 롤링 통계 계산
    rule_wins: dict[str, dict] = {}
    total_realized_kr = 0.0
    total_trades = 0
    full_reviews = []

    for meta in rows[:weeks]:
        full = wr.get_review(meta["week_start"])
        if not full:
            continue
        full_reviews.append(full)

        # 실현 PnL 누적
        rk = full.get("realized_pnl_kr")
        if rk is not None:
            total_realized_kr += float(rk)

        # 거래 수
        tc = full.get("trade_count")
        if tc:
            total_trades += int(tc)

        # 룰 승률 누적 — win_rate JSONB 가 {rule: {tries, wins, pct}} 구조
        wr_dict = full.get("win_rate") or {}
        for rule, stats in wr_dict.items():
            if not isinstance(stats, dict):
                continue
            agg = rule_wins.setdefault(rule, {"tries": 0, "wins": 0})
            agg["tries"] += int(stats.get("tries", 0) or 0)
            agg["wins"] += int(stats.get("wins", 0) or 0)

    # 룰별 pct 재계산
    for rule, agg in rule_wins.items():
        agg["pct"] = round(agg["wins"] / agg["tries"] * 100, 1) if agg["tries"] > 0 else 0.0

    # 전 주(2주차 이상) 액션 중 만료 안 된 conditional carryover
    now_utc = datetime.now(ZoneInfo("UTC"))
    for full in full_reviews[1:]:  # 최신 제외
        for a in (full.get("next_week_actions") or []):
            status = a.get("status", "")
            if status not in ("pending", "conditional"):
                continue
            exp = a.get("expires_at")
            if not exp:
                continue
            try:
                exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                if exp_dt > now_utc:
                    carryover.append({**a, "from_week": str(full.get("week_start"))})
            except Exception:
                continue

    return {
        "latest_review": {
            "week_start": str(latest_full.get("week_start")) if latest_full else None,
            "week_end": str(latest_full.get("week_end")) if latest_full else None,
            "headline": latest_full.get("headline") if latest_full else None,
            "highlights": latest_full.get("highlights") if latest_full else [],
            "pending_actions": pending_actions,
        } if latest_full else None,
        "rolling_stats": {
            "weeks_count": len(full_reviews),
            "rule_win_rates": rule_wins,
            "total_realized_pnl_kr": round(total_realized_kr, 2),
            "avg_weekly_pnl_kr": round(total_realized_kr / max(len(full_reviews), 1), 2),
            "trade_count_total": total_trades,
        },
        "carryover_actions": carryover,
    }


@mcp.tool
def rank_momentum(
    codes: list[str] | None = None,
    market: str = "kr",
    lookback_days: int = 252,
) -> list[dict]:
    """
    크로스섹셔널 모멘텀 랭킹. 각 종목 OHLCV → momentum_score → Z-score 정렬.
    codes 미지정 시 해당 market 의 Active 포지션 전부.
    """
    uid = settings.stock_user_id
    if codes is None:
        active = positions.list_active(uid)
        codes = [p["code"] for p in active if p.get("market") == market]

    if not codes:
        return []

    from server.analysis.indicators import compute_all as _compute_all

    rows = []
    for code in codes:
        try:
            # #19 fix — _fetch_ohlcv 통일 (KR/US 자동 분기 + yfinance fallback for >100일 US)
            df = _fetch_ohlcv(code, days=max(lookback_days, 20))
            if df is None or df.empty or len(df) < 60:
                continue
            df = df.sort_values("날짜").reset_index(drop=True)
            df = _compute_all(df)
            result = momentum_score(df)
            rows.append({
                "code": code,
                "score": result.get("점수"),
                "grade": result.get("등급"),
                "detail": {
                    "12_1_return": result.get("세부", {}).get("12_1_수익률", {}).get("값"),
                    "high_52w_proximity": result.get("세부", {}).get("52주고가_근접도", {}).get("값"),
                    "adx": result.get("세부", {}).get("ADX_추세", {}).get("값"),
                },
            })
        except Exception as e:
            rows.append({"code": code, "error": str(e)})

    # Z-score + ranking
    valid = [r for r in rows if isinstance(r.get("score"), (int, float))]
    if len(valid) >= 2:
        import statistics
        scores = [r["score"] for r in valid]
        mean = statistics.mean(scores)
        std = statistics.pstdev(scores) or 1
        for r in valid:
            r["z_score"] = round((r["score"] - mean) / std, 2)
        valid.sort(key=lambda r: r["score"], reverse=True)
        for i, r in enumerate(valid, 1):
            r["rank"] = i

    return rows


@mcp.tool
def detect_market_regime(reference_code: str = "005930") -> dict:
    """
    시장 국면 판정 (bull/bear/sideways/transition).
    기본: 삼성전자(005930) 을 KOSPI 대용으로 사용.
    lookback 300일 OHLCV 기반 4조건 체크 (SMA200/SMA210/SMA20/신고가비율).
    """
    try:
        df = _fetch_ohlcv(reference_code, days=350).sort_values("날짜").reset_index(drop=True)
    except Exception as e:
        return {"error": f"ref OHLCV 실패: {e}"}

    if df.empty or len(df) < 210:
        return {"error": "데이터 부족", "rows": len(df)}

    # kospi_regime 는 df 만 받으면 돌아감
    return {
        "reference": reference_code,
        **kospi_regime(df),
    }


@mcp.tool
def propose_watch_levels(
    code: str,
    entry_price: float,
    tier: str = "Standard",
    atr: float | None = None,
    direction: str = "long",
    persist: bool = False,
) -> dict:
    """
    ATR 기반 watch_levels 자동 제안 (position_planner 래핑).
    atr 미지정 시 최신 daily 에서 조회.
    persist=True 시 watch_levels 테이블에 upsert.

    tier: Premium/Standard/Cautious/Defensive (+ -단타 변형)
    """
    uid = settings.stock_user_id

    # ATR 자동 조회
    if atr is None:
        latest = stock_daily.get_latest(uid, code)
        if latest and latest.get("atr14"):
            atr = float(latest["atr14"])
        else:
            # 실시간 계산
            df = _fetch_ohlcv(code, days=50).sort_values("날짜").reset_index(drop=True)
            if len(df) >= 14:
                from server.analysis.indicators import compute_all as _ca
                df = _ca(df)
                last = df.iloc[-1]
                if "ATR14" in last.index and not pd.isna(last["ATR14"]):
                    atr = float(last["ATR14"])

    if atr is None or atr <= 0:
        return {"error": "ATR 계산 불가"}

    plan = position_planner(entry=int(entry_price), atr=atr, tier=tier, direction=direction)

    if persist and "오류" not in plan:
        # 손절·익절 각각 저장
        if "손절가" in plan:
            watch_levels.upsert(uid, code, "stop_loss", Decimal(str(plan["손절가"])),
                                 note=f"tier={tier} ATR×{plan.get('ATR_배수', {}).get('손절', '?')}")
        for i, stage in enumerate(plan.get("피라미딩_단계", []), 1):
            watch_levels.upsert(uid, code, f"pyramid_{i}",
                                 Decimal(str(stage["가격"])), note=stage.get("트리거", ""))
        if "부분익절" in plan:
            for i, tp in enumerate(plan["부분익절"], 1):
                watch_levels.upsert(uid, code, f"target_{i}",
                                     Decimal(str(tp["가격"])), note=tp.get("비율", ""))

    return {
        "code": code,
        "entry_price": entry_price,
        "tier": tier,
        "atr": atr,
        "plan": plan,
        "persisted": persist,
    }


@mcp.tool
def refresh_daily(code: str, days: int = 400) -> dict:
    """
    단건 종목 일일 스냅샷 즉시 실행.
    KIS 우선 → Naver fallback 으로 OHLCV 수집, 지표 + 시그널 계산 후 stock_daily 저장.
    """
    from server.jobs import daily_snapshot as ds

    result = ds.run(codes=[code], days=days)
    return {
        "code": code,
        "ok": code in result["ok"],
        "failed": code in result["fail"],
    }


# =====================================================================
# 신규 종목 발굴 (Discovery)
# =====================================================================

@mcp.tool
def list_tradable_stocks(
    market: str = "kr",
    min_market_cap_krw: int = 1_000_000_000_000,  # 1조
    sort_by: str = "market_cap",  # 'market_cap' | 'trade_value' | 'volume' | 'change_pct'
    limit: int = 200,
) -> list[dict]:
    """
    상장 종목 마스터 조회 (KRX OpenAPI). 시총 필터 + 정렬.
    신규 발굴 1단계: sort_by='trade_value' 로 유동성 상위 스크리닝.
    - KR: KOSPI + KOSDAQ 전체
    - US: 미지원 (별도 어댑터 필요)
    """
    if market != "kr":
        return [{"error": "US 미지원 — KR 전용"}]
    assert sort_by in ("market_cap", "trade_value", "volume", "change_pct")

    from server.scrapers import krx

    all_stocks = krx.fetch_all_stocks()
    filtered = [
        {
            "code": s["종목코드"],
            "name": s["종목명"],
            "market": s["시장"],
            "market_cap_krw": s["시가총액"],
            "market_cap_jo": round(s["시가총액"] / 1e12, 2),
            "trade_value_krw": s["거래대금"],
            "trade_value_eok": round(s["거래대금"] / 1e8, 1),
            "close": s["종가"],
            "volume": s["거래량"],
            "change_pct": s["등락률"],
        }
        for s in all_stocks
        if s["시가총액"] >= min_market_cap_krw
    ]

    sort_key = {
        "market_cap": "market_cap_krw",
        "trade_value": "trade_value_krw",
        "volume": "volume",
        "change_pct": "change_pct",
    }[sort_by]
    filtered.sort(key=lambda x: x[sort_key], reverse=True)
    return filtered[:limit]


@mcp.tool
def screen_stocks(
    market: str = "kr",
    min_per: float | None = None,
    max_per: float | None = None,
    min_pbr: float | None = None,
    max_pbr: float | None = None,
    min_roe: float | None = None,
    min_op_margin: float | None = None,
    grade_in: list[str] | None = None,
    industry_code: str | None = None,
    limit: int = 30,
) -> list[dict]:
    """
    DB에 리서치된 종목(stock_base) 대상 필터 스크리닝.
    기본 필터: PER, PBR, ROE, 영업이익률, 등급, 산업.

    예:
      screen_stocks(max_per=15, min_roe=15, grade_in=['Premium','Standard'])
    """
    conditions = ["s.market = %s"]
    params: list = [market]
    if min_per is not None:
        conditions.append("sb.per >= %s")
        params.append(min_per)
    if max_per is not None:
        conditions.append("sb.per <= %s AND sb.per IS NOT NULL")
        params.append(max_per)
    if min_pbr is not None:
        conditions.append("sb.pbr >= %s")
        params.append(min_pbr)
    if max_pbr is not None:
        conditions.append("sb.pbr <= %s AND sb.pbr IS NOT NULL")
        params.append(max_pbr)
    if min_roe is not None:
        conditions.append("sb.roe >= %s")
        params.append(min_roe)
    if min_op_margin is not None:
        conditions.append("sb.op_margin >= %s")
        params.append(min_op_margin)
    if grade_in:
        conditions.append("sb.grade = ANY(%s)")
        params.append(grade_in)
    if industry_code:
        conditions.append("s.industry_code = %s")
        params.append(industry_code)

    where = " AND ".join(conditions)
    params.append(limit)

    from server.db import get_conn
    with get_conn() as conn:
        cur = conn.execute(
            f"""
            SELECT s.code, s.name, s.market, s.industry_code,
                   sb.grade, sb.total_score, sb.per, sb.pbr, sb.roe, sb.op_margin,
                   sb.analyst_target_avg
              FROM stocks s JOIN stock_base sb USING(code)
             WHERE {where}
             ORDER BY sb.total_score DESC NULLS LAST, sb.roe DESC NULLS LAST
             LIMIT %s
            """,
            params,
        )
        return [_row_safe(r) for r in cur.fetchall()]  # type: ignore[misc]


@mcp.tool
def rank_momentum_wide(
    market: str = "kr",
    top_n: int = 30,
    min_market_cap_krw: int = 5_000_000_000_000,  # KR: 5조+
    min_market_cap_usd: int = 10_000_000_000,  # US: $10B+
) -> list[dict]:
    """
    전체 시장 시총 상위 종목들의 모멘텀 랭킹 Top-N.

    KR: pykrx → KOSPI+KOSDAQ 전체 → 시총 5조+ → naver 일봉 → momentum_score
    US: S&P 500 ∪ NASDAQ 100 ~530 → 시총 $10B+ → yfinance batch → momentum_score
    실행 시간 30초~1분.
    """
    from server.analysis.indicators import compute_all as _ca

    if market == "us":
        from server.scrapers import us_universe, yfinance_client as yfc

        candidates = us_universe.fetch_top_by_marketcap(
            min_market_cap_usd=min_market_cap_usd,
            limit=top_n * 3,  # 오버샘플링
        )
        if not candidates:
            return []

        tickers = [c["ticker"] for c in candidates]
        ohlcv_map = yfc.fetch_ohlcv_batch(tickers, period="1y")

        rows: list[dict] = []
        for c in candidates:
            t = c["ticker"]
            df = ohlcv_map.get(t)
            if df is None or df.empty or len(df) < 100:
                continue
            try:
                df = df.sort_values("날짜").reset_index(drop=True)
                df = _ca(df)
                score_result = momentum_score(df)
                close = float(df.iloc[-1]["종가"])
                rows.append({
                    "ticker": t,
                    "code": t,  # KR 호환 키
                    "market_cap_b": round(c["market_cap_usd"] / 1e9, 1),
                    "close": close,
                    "momentum_score": score_result.get("점수"),
                    "momentum_grade": score_result.get("등급"),
                })
            except Exception:
                continue

        rows.sort(key=lambda x: x.get("momentum_score") or 0, reverse=True)
        return rows[:top_n]

    # KR (기존)
    if market != "kr":
        return [{"error": f"unsupported market: {market}"}]

    from server.scrapers import krx

    candidates_raw = krx.fetch_all_stocks()
    candidates_kr = [
        s for s in candidates_raw if s["시가총액"] >= min_market_cap_krw
    ]
    candidates_kr.sort(key=lambda x: x["시가총액"], reverse=True)
    candidates_kr = candidates_kr[: min(len(candidates_kr), top_n * 3)]

    rows = []
    for c in candidates_kr:
        code = c["종목코드"]
        try:
            df = _fetch_ohlcv(code, days=300)
            if df is None or df.empty or len(df) < 100:
                continue
            df = df.sort_values("날짜").reset_index(drop=True)
            df = _ca(df)
            score_result = momentum_score(df)
            rows.append({
                "code": code,
                "name": c["종목명"],
                "market_cap_jo": round(c["시가총액"] / 1e12, 2),
                "close": c["종가"],
                "momentum_score": score_result.get("점수"),
                "momentum_grade": score_result.get("등급"),
            })
        except Exception:
            continue

    rows.sort(key=lambda x: x.get("momentum_score") or 0, reverse=True)
    return rows[:top_n]


@mcp.tool
def discover_by_theme(
    keyword: str,
    market: str = "kr",
    limit: int = 20,
) -> list[dict]:
    """
    DB의 stock_base.narrative + industries.content 에서 키워드 매칭.
    예: 'AI', 'HBM', '원전', '지주', '배당'
    """
    from server.db import get_conn
    pattern = f"%{keyword}%"
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT s.code, s.name, s.market, s.industry_code, i.name AS industry_name,
                   sb.grade, sb.total_score, sb.per, sb.roe,
                   CASE
                     WHEN sb.narrative ILIKE %s THEN 'stock'
                     WHEN i.content ILIKE %s THEN 'industry'
                     WHEN s.name ILIKE %s THEN 'name'
                     ELSE 'other'
                   END AS match_source
              FROM stocks s
              LEFT JOIN stock_base sb USING(code)
              LEFT JOIN industries i ON s.industry_code = i.code
             WHERE s.market = %s
               AND (sb.narrative ILIKE %s
                    OR i.content ILIKE %s
                    OR s.name ILIKE %s
                    OR i.name ILIKE %s)
             ORDER BY sb.total_score DESC NULLS LAST
             LIMIT %s
            """,
            (pattern, pattern, pattern, market, pattern, pattern, pattern, pattern, limit),
        )
        return [_row_safe(r) for r in cur.fetchall()]  # type: ignore[misc]


# =====================================================================
# Issue #3 Tier A — 만기 cascade & 분석 묶음 (스킵 불가)
# =====================================================================

@mcp.tool
def refresh_stock_base(codes: list[str] | None = None) -> dict:
    """
    KR 종목 stock_base 의 재무 컬럼 (financial_score / PER / PBR / ROE / op_margin / debt_ratio / 성장률)
    DART 기반 일괄 재계산 + DB 갱신.

    인자:
      codes: KR 종목 코드 리스트. None 시 daily-scope (Active + Pending) 자동.

    반환:
      {"ok": [코드...], "skip": [코드...], "fail": [코드...],
       "details": {code: {ok, financial_score, per, roe, op_margin, ...}}}

    주의:
      - US 종목은 DART 미지원으로 skip.
      - 텍스트 base.md (Narrative / DCF / Comps) 는 갱신 안 함 — `/base-stock` skill 별도.
      - 재무 데이터 변화 없어도 updated_at 갱신됨 → check_base_freshness 의 is_stale 해소.
    """
    from server.jobs.refresh_base import run as _refresh_run
    return _refresh_run(codes=codes, verbose=False)


@mcp.tool
def refresh_kr_consensus(codes: list[str] | None = None, days: int = 90, max_pages: int = 2) -> dict:
    """
    KR 종목 애널 컨센서스를 네이버 리서치에서 수집해 analyst_reports DB 적재.

    인자:
      codes: KR 6자리 코드 리스트. None 시 daily-scope (Active + Pending) 자동.
      days: 발행일 cutoff (오늘 - days 이전 리포트 제외).
      max_pages: 종목별 목록 페이지 수 (1 페이지 ≈ 20건).

    반환:
      {
        "ok": [...], "fail": [...], "skipped_us": [...],
        "details": {code: {fetched: N, inserted: M, latest_dates: [...]}}
      }

    주의:
      - URL 중복 (analyst_reports.report_url UNIQUE) 시 자동 스킵 → 중복 적재 없음.
      - 네이버 페이지 차단 가능성 — 대량 호출 시 rate-limit 주의 (현재 inline sleep 없음).
      - US 종목은 Finnhub 별도 (record_analyst_report 직접 호출 또는 finnhub.fetch_consensus).
    """
    from decimal import Decimal

    from server.repos import analyst, positions, stocks
    from server.scrapers.naver import fetch_research_reports

    if codes is None:
        scope = positions.list_daily_scope(settings.stock_user_id)
        codes = [p["code"] for p in scope if p.get("market") == "kr"]

    out: dict = {"ok": [], "fail": [], "skipped_us": [], "details": {}}
    for code in codes:
        s = stocks.get_stock(code)
        if not s:
            out["fail"].append(code)
            out["details"][code] = {"error": "stock not found"}
            continue
        if s.get("market") != "kr":
            out["skipped_us"].append(code)
            out["details"][code] = {"skipped": "non-KR (use Finnhub)"}
            continue
        try:
            reports = fetch_research_reports(code, max_pages=max_pages, days=days)
        except Exception as e:
            out["fail"].append(code)
            out["details"][code] = {"error": f"scrape: {e}"}
            continue

        inserted = 0
        latest_dates: list[str] = []
        for r in reports:
            try:
                tp = Decimal(str(r["target_price"])) if r.get("target_price") else None
                rid = analyst.record_report(
                    code=code,
                    broker=r.get("broker") or "Unknown",
                    published_at=r["published_at"],
                    broker_country=r.get("broker_country", "kr"),
                    report_url=r.get("report_url"),
                    title=r.get("title"),
                    rating=r.get("rating"),
                    target_price=tp,
                    currency=r.get("currency", "KRW"),
                )
                if rid is not None:
                    inserted += 1
                latest_dates.append(r["published_at"].strftime("%Y-%m-%d"))
            except Exception:
                continue

        out["ok"].append(code)
        out["details"][code] = {
            "fetched": len(reports),
            "inserted": inserted,
            "latest_dates": latest_dates[:5],
        }
    return out


@mcp.tool
def refresh_us_consensus(codes: list[str] | None = None) -> dict:
    """
    US 종목 애널 컨센서스를 Finnhub 에서 수집해 analyst_reports DB 적재.

    Finnhub 무료 plan 은 개별 리포트 메타를 제공하지 않고 집계만 (recommendation_trends + price_target).
    → broker="Finnhub Aggregate" 가상 row 1건으로 적재 (오늘 날짜).
    → report_url 은 unique 보장: finnhub://consensus/{ticker}/{YYYY-MM-DD} (중복 시 skip).

    인자:
      codes: US 티커 리스트. None 시 daily-scope (Active + Pending) 자동.

    반환:
      {
        "ok": [...], "fail": [...], "skipped_kr": [...],
        "details": {ticker: {target_avg, target_high, target_low, total_reports, dominant_rating, inserted}}
      }
    """
    from datetime import datetime
    from decimal import Decimal
    from zoneinfo import ZoneInfo

    from server.repos import analyst, positions, stocks as stocks_repo
    from server.scrapers import finnhub as fh

    KST = ZoneInfo("Asia/Seoul")

    if codes is None:
        scope = positions.list_daily_scope(settings.stock_user_id)
        codes = [p["code"] for p in scope if p.get("market") == "us"]

    out: dict = {"ok": [], "fail": [], "skipped_kr": [], "details": {}}
    today = datetime.now(tz=KST)

    for code in codes:
        s = stocks_repo.get_stock(code)
        if not s:
            out["fail"].append(code)
            out["details"][code] = {"error": "stock not found"}
            continue
        if s.get("market") != "us":
            out["skipped_kr"].append(code)
            out["details"][code] = {"skipped": "non-US (use refresh_kr_consensus)"}
            continue

        try:
            consensus = fh.fetch_consensus(code)
        except Exception as e:
            out["fail"].append(code)
            out["details"][code] = {"error": f"finnhub: {e}"}
            continue

        # dominant rating: Buy / Hold / Sell 중 max → analyst_reports.rating CHECK 매핑
        dist = consensus.get("투자의견_분포") or {}
        rating_map = {"Buy": "buy", "Hold": "hold", "Sell": "sell"}
        dominant = max(rating_map, key=lambda k: dist.get(k, 0)) if dist else None
        rating = rating_map.get(dominant) if dominant and dist.get(dominant, 0) > 0 else None

        target_avg = consensus.get("목표가_평균")
        report_count = consensus.get("리포트수", 0) or 0
        if target_avg is None and report_count == 0:
            out["fail"].append(code)
            out["details"][code] = {"error": "Finnhub coverage 없음 (target + 리포트 모두 비어있음)"}
            continue
        # Finnhub 무료 plan 은 price_target 미제공 가능 — 분포만으로도 적재 가치 있음.
        tp = Decimal(str(target_avg)) if target_avg is not None else None

        try:
            rid = analyst.record_report(
                code=code,
                broker="Finnhub Aggregate",
                broker_country="us",
                published_at=today,
                report_url=f"finnhub://consensus/{code}/{today.strftime('%Y-%m-%d')}",
                title=f"Finnhub Aggregate Consensus ({report_count} reports)",
                rating=rating,
                target_price=tp,
                currency="USD",
                forecasts={
                    "target_high": consensus.get("목표가_최고"),
                    "target_low": consensus.get("목표가_최저"),
                    "target_median": consensus.get("목표가_중간값"),
                    "rating_distribution": dist,
                    "total_reports_all_time": consensus.get("전체_리포트수"),
                },
                summary=f"{dominant or 'Mixed'} 우세 / {consensus.get('리포트수', 0)}건 (3M)",
            )
            inserted = 1 if rid is not None else 0
        except Exception as e:
            out["fail"].append(code)
            out["details"][code] = {"error": f"insert: {e}"}
            continue

        out["ok"].append(code)
        out["details"][code] = {
            "target_avg": target_avg,
            "target_high": consensus.get("목표가_최고"),
            "target_low": consensus.get("목표가_최저"),
            "total_reports": consensus.get("리포트수"),
            "dominant_rating": rating,
            "inserted": inserted,
        }
    return out


@mcp.tool
def check_base_freshness(
    scope: str = "all",
    code: str | None = None,
    auto_refresh: bool = False,
) -> dict:
    """
    Active + Pending 포지션 종목의 base 만기 일괄 판정. LLM이 자연어 비교로 누락하지 않도록
    `is_stale: bool` + `auto_triggers: list[str]` 강제 반환.

    인자:
      scope: 체크 범위 분기. 기본 "all" (기존 호환).
        - "all"      : economy + industries + stocks 모두 (기존 동작)
        - "economy"  : economy KR/US 만 (industries/stocks 빈 리스트)
        - "industry" : industry 만. code 지정 시 해당 1건, 미지정 시 holdings 산업 전체.
        - "stock"    : stock 만. code 지정 시 해당 종목 1건 + 그 종목의 industry_code 1건.
                       code 미지정 시 holdings 종목 전체 + 산업 dedup.
      code: scope ∈ {"industry", "stock"} 일 때만 의미. None이면 holdings 전체 대상.
      auto_refresh: True 시 stale 한 stock_base 를 즉시 refresh_stock_base() 자동 실행.
                    economy / industry 는 텍스트 작성 필요 → auto_triggers 만 반환 (수동 skill 호출).

    호출 예시:
      Phase 2 economy 단독:    check_base_freshness(scope="economy")
      Phase 3 per-stock 단독:  check_base_freshness(scope="stock", code="005930")
      특정 산업 단독:          check_base_freshness(scope="industry", code="G45")
      기존 통합 (default):     check_base_freshness()

    만기 기준 (references/expiration-rules.md):
      - economy/base.md (kr/us)        : 1일
      - industries/{산업}/base.md       : 7일
      - stocks/{종목}/base.md           : 30일

    반환:
      {
        "today": "YYYY-MM-DD",
        "economy":   [{"market", "age_days", "expiry_days", "is_stale", "missing", "trigger"}],
        "industries":[{"code","name","age_days","expiry_days","is_stale","missing","trigger"}],
        "stocks":    [{"code","name","age_days","expiry_days","is_stale","missing","trigger"}],
        "summary": {"total_stale": N, "total_missing": M,
                    "auto_triggers": [...], "needs_refresh": [...], "all_fresh": bool},
        "auto_refresh_log": {  # auto_refresh=True 시만 포함
            "executed": True/False,
            "refreshed_codes": [...],
            "results": {ok, fail, ...},
        }
      }
      scope 가 "all" 외이면 해당 범위 외 키는 빈 리스트(`[]`)로 유지 (LLM 일관성).
    """
    from datetime import date as _date

    valid_scopes = {"all", "economy", "industry", "stock"}
    if scope not in valid_scopes:
        raise ValueError(
            f"invalid scope={scope!r} — must be one of {sorted(valid_scopes)}"
        )

    uid = settings.stock_user_id
    today = _date.today()
    out: dict = {"today": today.isoformat(),
                 "economy": [], "industries": [], "stocks": [], "summary": {}}

    def _age(updated_at) -> int | None:
        if not updated_at:
            return None
        try:
            return (today - updated_at.date()).days
        except Exception:
            return None

    EXP_ECONOMY = 1
    EXP_INDUSTRY = 7
    EXP_STOCK = 30

    do_economy = scope in ("all", "economy")
    do_industry = scope in ("all", "industry")
    do_stock = scope in ("all", "stock")

    # 1) economy bases — scope ∈ {"all", "economy"}
    if do_economy:
        for market in ("kr", "us"):
            row = economy.get_base(market)
            if not row:
                out["economy"].append({
                    "market": market, "age_days": None,
                    "expiry_days": EXP_ECONOMY,
                    "is_stale": True, "missing": True,
                    "trigger": f"/base-economy --{market}",
                })
                continue
            age = _age(row.get("updated_at"))
            is_stale = (age is None) or age >= EXP_ECONOMY
            out["economy"].append({
                "market": market, "age_days": age,
                "expiry_days": EXP_ECONOMY,
                "is_stale": is_stale, "missing": False,
                "trigger": f"/base-economy --{market}" if is_stale else None,
            })

    # 2) industries / stocks — scope 에 따라 holdings 또는 단일 code 분기
    seen_inds: set[str] = set()

    def _append_industry(ind_code: str | None, ind_row: dict | None = None) -> None:
        """ind_row 가 주어지면 추가 query 없이 사용 (#26 perf — batch 경로)."""
        if not ind_code or ind_code in seen_inds:
            return
        seen_inds.add(ind_code)
        ib = ind_row if ind_row is not None else industries.get_industry(ind_code)
        if not ib:
            out["industries"].append({
                "code": ind_code, "name": ind_code,
                "age_days": None, "expiry_days": EXP_INDUSTRY,
                "is_stale": True, "missing": True,
                "trigger": f"/base-industry {ind_code}",
            })
        else:
            age = _age(ib.get("updated_at"))
            is_stale = (age is None) or age >= EXP_INDUSTRY
            out["industries"].append({
                "code": ind_code, "name": ib.get("name") or ind_code,
                "age_days": age, "expiry_days": EXP_INDUSTRY,
                "is_stale": is_stale, "missing": False,
                "trigger": f"/base-industry {ind_code}" if is_stale else None,
            })

    def _append_stock(p_code: str, p_name: str | None, sb_row: dict | None = None) -> None:
        """sb_row 가 주어지면 추가 query 없이 사용 (#26 perf — batch 경로)."""
        name = p_name or p_code
        sb = sb_row if sb_row is not None else stock_base.get_base(p_code)
        if not sb:
            out["stocks"].append({
                "code": p_code, "name": name, "age_days": None,
                "expiry_days": EXP_STOCK,
                "is_stale": True, "missing": True,
                "trigger": f"/base-stock {name}",
            })
        else:
            age = _age(sb.get("updated_at"))
            is_stale = (age is None) or age >= EXP_STOCK
            out["stocks"].append({
                "code": p_code, "name": name, "age_days": age,
                "expiry_days": EXP_STOCK,
                "is_stale": is_stale, "missing": False,
                "trigger": f"/base-stock {name}" if is_stale else None,
            })

    if scope == "stock" and code:
        # 단일 종목 + 그 종목의 산업 1건만 (3 queries OK — small)
        s_row = stocks.get_stock(code)
        name = (s_row.get("name") if s_row else None) or code
        _append_stock(code, name)
        ind_code = s_row.get("industry_code") if s_row else None
        _append_industry(ind_code)
    elif scope == "industry" and code:
        # 단일 산업만
        _append_industry(code)
    elif do_industry or do_stock:
        # holdings 전체 대상 — #26 perf: N+1 → 3 batch queries 로 축소.
        # 이전: positions(1) + stocks.get_stock×N + stock_base.get_base×N + industries.get_industry×M
        # 현재: positions(1) + stocks.list_for_codes(1) + stock_base.list_freshness_for_codes(1)
        #       + industries.list_freshness_for_codes(1) = **4 queries**.
        scope_positions = positions.list_daily_scope(uid)
        holding_codes = [p["code"] for p in scope_positions]

        # Batch fetch — 빈 holdings 면 빈 dict 반환 (no-op)
        stocks_map = stocks.list_for_codes(holding_codes) if (do_industry and holding_codes) else {}
        sb_map = (
            stock_base.list_freshness_for_codes(holding_codes)
            if (do_stock and holding_codes) else {}
        )
        ind_codes_needed: list[str] = []
        if do_industry:
            ind_codes_needed = list({
                s.get("industry_code") for s in stocks_map.values() if s.get("industry_code")
            })
        ind_map = (
            industries.list_freshness_for_codes(ind_codes_needed)
            if ind_codes_needed else {}
        )

        for p in scope_positions:
            p_code = p["code"]
            p_name = p.get("name") or p_code
            if do_stock:
                _append_stock(p_code, p_name, sb_row=sb_map.get(p_code))
            if do_industry:
                s_row = stocks_map.get(p_code) or {}
                ind_code = s_row.get("industry_code")
                _append_industry(ind_code, ind_row=ind_map.get(ind_code) if ind_code else None)

    # 3) Summary
    all_items = out["economy"] + out["industries"] + out["stocks"]
    stale = [x for x in all_items if x.get("is_stale")]
    missing = [x for x in all_items if x.get("missing")]
    triggers = sorted({x["trigger"] for x in stale if x.get("trigger")})

    needs_refresh = []
    for x in stale:
        if x.get("market"):
            needs_refresh.append(f"economy/{x['market']}")
        elif x in out["industries"]:
            needs_refresh.append(f"industries/{x['code']}")
        elif x in out["stocks"]:
            needs_refresh.append(f"stocks/{x['code']}")
    out["summary"] = {
        "total_stale": len(stale),
        "total_missing": len(missing),
        "auto_triggers": triggers,
        "needs_refresh": sorted(set(needs_refresh)),
        "all_fresh": len(stale) == 0,
    }

    # auto_refresh: stale stock_base 즉시 refresh + 결과 재반영
    if auto_refresh:
        stale_kr_stocks = []
        for s in out["stocks"]:
            if not s.get("is_stale"):
                continue
            # KR 종목만 refresh_stock_base 가능 (DART)
            sr = stocks.get_stock(s["code"])
            if sr and sr.get("market") == "kr":
                stale_kr_stocks.append(s["code"])

        log: dict = {"executed": False, "refreshed_codes": [], "results": None,
                     "skipped_economy": [], "skipped_industries": []}

        if stale_kr_stocks:
            from server.jobs.refresh_base import run as _refresh_run
            results = _refresh_run(codes=stale_kr_stocks, verbose=False)
            log["executed"] = True
            log["refreshed_codes"] = stale_kr_stocks
            log["results"] = results

            # 새 updated_at 반영 — stocks 항목 재계산
            for s in out["stocks"]:
                if s["code"] in stale_kr_stocks and s["code"] in results.get("ok", []):
                    sb_new = stock_base.get_base(s["code"])
                    if sb_new:
                        new_age = _age(sb_new.get("updated_at"))
                        s["age_days"] = new_age
                        s["is_stale"] = (new_age is None) or new_age >= EXP_STOCK
                        s["trigger"] = f"/base-stock {s['name']}" if s["is_stale"] else None
                        s["refreshed"] = True

        # economy / industry 는 텍스트 작성 필요 → auto_refresh로 처리 불가
        log["skipped_economy"] = [e["market"] for e in out["economy"] if e.get("is_stale")]
        log["skipped_industries"] = [i["code"] for i in out["industries"] if i.get("is_stale")]

        # summary 재계산
        all_items_after = out["economy"] + out["industries"] + out["stocks"]
        stale_after = [x for x in all_items_after if x.get("is_stale")]
        triggers_after = sorted({x["trigger"] for x in stale_after if x.get("trigger")})
        out["summary"]["total_stale"] = len(stale_after)
        out["summary"]["auto_triggers"] = triggers_after
        out["summary"]["all_fresh"] = len(stale_after) == 0
        out["auto_refresh_log"] = log

    return _json_safe(out)


@mcp.tool
def analyze_position(code: str, include_base: bool = True) -> dict:
    """
    종목별 raw 데이터 분석 일괄 묶음 — LLM이 부분 스킵 못하도록 1회 호출에 강제 포함.

    포함 카테고리 (9개 raw):
      1. context        — get_stock_context (base + position + watch + daily)
      2. realtime       — KIS/Naver 자동 분기 현재가
      3. indicators     — compute_indicators 12지표
      4. signals        — compute_signals 12전략 + summary.종합
      5. financials     — compute_financials raw (ratios + growth + raw_summary, score 제거)
      6. flow           — analyze_flow (KR 기관/외인 z-score)
      7. volatility     — analyze_volatility (regime/DD)
      8. events         — detect_events (52w/실적/등급)
      9. consensus      — get_analyst_consensus + analyze_consensus_trend + reports

    포트 단위 (별도 호출): regime, correlation, concentration, weekly_context, momentum, sensitivity.

    ⚠️ 제거됨 (LLM 본문 판단으로 위임 — per-stock-analysis.md 가이드):
      - scoring (total_score / grade / breakdown) — score anchor 금지
      - cell (12셀 자동 derive) — LLM 본문 판단으로 셀 결정
      - is_stale (만기 자체 판정) — check_base_freshness 단일 진입점
      - financials.score — raw ratios + growth 만 노출

    종목 1건 분석 단일 진입점: references/per-stock-analysis.md (7단계 절차)

    반환:
      {
        "code","name","market",
        "context":{...}, "realtime":{...}, "indicators":{...}, "signals":{...},
        "financials":{...}, "flow":{...}, "volatility":{...}, "events":{...},
        "consensus":{...},
        "errors": {category: error_msg, ...},
        "categories_succeeded": N, "categories_total": 9,
        "coverage_pct": float,
      }
    """
    s_row = stocks.get_stock(code)
    if not s_row:
        return {"error": f"stock not found: {code}"}

    uid = settings.stock_user_id
    market = s_row.get("market", "kr")
    name = s_row.get("name")

    bundle: dict = {"code": code, "name": name, "market": market, "errors": {}}
    success = 0
    # v4 (2026-05): 9 → 12 카테고리 (base + disclosures + insider_trades).
    # include_base=False 시 base 카테고리 제외 (분모 11).
    total = 12 if include_base else 11

    def _ohlcv() -> pd.DataFrame:
        # #19 fix — _fetch_ohlcv 통일 (KR/US 자동 분기 + yfinance fallback for >100일 US)
        return _fetch_ohlcv(code, days=400)

    # 1) context
    try:
        # v4 fix (2026-05): stock_base content 는 카테고리 #12 (base) 에서만 풀 inject.
        # context.base 는 메타만 (stale 여부 / 등급 / 짧은 narrative) — 5,283자 중복 직렬화 제거.
        sb_row = _row_safe(stock_base.get_base(code))
        sb_meta = None
        if sb_row:
            sb_meta = {
                k: sb_row.get(k) for k in (
                    "code", "updated_at", "expires_at",
                    "grade", "total_score", "financial_score",
                    "industry_score", "economy_score",
                    "narrative", "risks", "scenarios",
                    "fair_value_avg", "analyst_target_avg", "analyst_target_max",
                    "analyst_consensus_count",
                    "per", "pbr", "roe", "op_margin",
                ) if k in sb_row
            }
        bundle["context"] = {
            "stock": _row_safe(s_row),
            "base": sb_meta,  # content 제거 — 풀 본문은 bundle["base"]["stock"] 에서 인용
            "latest_daily": _row_safe(stock_daily.get_latest(uid, code)),
            "position": _row_safe(positions.get_position(uid, code)),
            "watch_levels": [_row_safe(lv) for lv in watch_levels.list_by_code(uid, code)],
        }
        success += 1
    except Exception as e:
        bundle["errors"]["context"] = str(e)

    # 2) realtime
    try:
        if market == "kr":
            state = _kr_market_state()
            try:
                rt = kis.fetch_current_price(code) if state == "regular" else naver.fetch_realtime_price(code)
            except Exception:
                rt = naver.fetch_realtime_price(code)
            bundle["realtime"] = {**rt, "market_state": state, "source_market": "kr"}
        else:
            bundle["realtime"] = {**kis.fetch_us_quote(code), "source_market": "us"}
        success += 1
    except Exception as e:
        bundle["errors"]["realtime"] = str(e)

    # OHLCV cache + indicator DataFrame (3, 4, 7, 8 모두 사용)
    df_cache: pd.DataFrame | None = None
    df_ind: pd.DataFrame | None = None
    df_err: str | None = None
    try:
        _df = _ohlcv()
        if _df.empty:
            df_err = "no OHLCV"
        else:
            df_cache = _df.sort_values("날짜").reset_index(drop=True)
            df_ind = compute_all(df_cache)
    except Exception as e:
        df_err = str(e)

    # 3) indicators — 마지막 행만 dict로 추출
    try:
        if df_ind is None:
            bundle["indicators"] = {"error": df_err}
            bundle["errors"]["indicators"] = df_err or "no OHLCV"
        else:
            last = df_ind.iloc[-1]
            ind_result: dict[str, Any] = {
                "code": code,
                "date": str(last["날짜"].date()) if hasattr(last["날짜"], "date") else str(last["날짜"]),
                "close": float(last["종가"]),
                "price_context": price_context(df_cache, market=market),
            }
            for col in ["SMA5", "SMA20", "SMA60", "SMA120", "SMA200",
                        "RSI14", "ATR14", "Stoch_K", "Stoch_D", "ADX14",
                        "MACD", "MACD시그널", "MACD히스토",
                        "볼린저_상단", "볼린저_중심", "볼린저_하단",
                        "전환선", "기준선"]:
                if col in last.index:
                    v = last[col]
                    ind_result[col] = _dec(v) if v is not None else None
            bundle["indicators"] = ind_result
            success += 1
    except Exception as e:
        bundle["errors"]["indicators"] = str(e)

    # 4) signals — analyze_all은 DataFrame(지표 추가된) 받음
    try:
        if df_ind is None:
            bundle["signals"] = {"error": df_err}
            bundle["errors"]["signals"] = df_err or "no OHLCV"
        else:
            sigs = analyze_all(df_ind)
            bundle["signals"] = {"code": code, "signals": sigs, "summary": summarize(sigs)}
            success += 1
    except Exception as e:
        bundle["errors"]["signals"] = str(e)

    # 5) financials (KR=DART / US=SEC EDGAR)
    try:
        if market == "us":
            from server.scrapers import edgar
            fin = edgar.fetch_financials(code, years=3)
            summary = edgar.summarize_financials(fin)
        else:
            fin = dart.fetch_financials(code, years=3)
            summary = dart.summarize_financials(fin)

        # raw_summary 의 사전계산 값 직접 매핑 (compute_financial_ratios raw 키 매핑이 KR/US 모두 None 으로 빠짐)
        ratios = {
            "per": summary.get("PER"), "pbr": summary.get("PBR"),
            "eps": summary.get("EPS"), "bps": summary.get("BPS"),
            "psr": None, "ev_ebitda": None,
            "roe": summary.get("ROE"), "roa": summary.get("ROA"),
            "op_margin": summary.get("영업이익률"),
            "net_margin": summary.get("순이익률"),
            "debt_ratio": summary.get("부채비율"),
            "fcf_yield": None,
        }
        growth = {
            "revenue_yoy": summary.get("매출_YoY"),
            "op_profit_yoy": summary.get("영업이익_YoY"),
            "net_profit_yoy": summary.get("순이익_YoY"),
            "revenue_qoq": None, "op_profit_qoq": None, "eps_yoy": None,
        }
        if summary.get("quarterly"):
            q_growth = compute_growth_rates(summary["quarterly"])
            for k, v in q_growth.items():
                if v is not None:
                    growth[k] = v
        # score 변수는 health_summary 의 인자로 내부 사용. 응답에는 노출 X (per-stock-analysis score anchor 금지 가이드)
        score = compute_financial_score(ratios, growth)
        bundle["financials"] = {
            "code": code, "market": market,
            "ratios": ratios, "growth": growth,
            "health_summary": summarize_health(ratios, growth, score),
            "raw_summary": summary,
        }
        success += 1
    except Exception as e:
        bundle["errors"]["financials"] = str(e)

    # 6) flow (KR 전용)
    if market == "kr":
        try:
            fdf = naver.fetch_investor(code, pages=2)
            bundle["flow"] = analyze_investor_flow(fdf, window=20)
            success += 1
        except Exception as e:
            bundle["errors"]["flow"] = str(e)
    else:
        bundle["flow"] = {"skipped": "US — 13F/options/insider 별도", "market": market}

    # 7) volatility
    try:
        if df_cache is None:
            bundle["volatility"] = {"error": df_err}
            bundle["errors"]["volatility"] = df_err or "no OHLCV"
        else:
            rv = realized_volatility(df_cache, window=30)
            pv = parkinson_volatility(df_cache, window=30)
            dd = compute_drawdown(df_cache)
            bundle["volatility"] = {
                "code": code,
                "realized_vol_pct": rv, "parkinson_vol_pct": pv,
                "regime": classify_vol_regime(rv), "drawdown": dd,
            }
            success += 1
    except Exception as e:
        bundle["errors"]["volatility"] = str(e)

    # 8) events
    try:
        ev: dict = {}
        try:
            from datetime import date as _date_cls
            if market == "us":
                from server.scrapers import finnhub as fh
                ne = fh.fetch_next_earnings_date(code)
            else:
                ne = dart.fetch_next_earnings_date(code)
            next_date = ne.get("차기_예상일") if isinstance(ne, dict) else None
            if next_date:
                ev["earnings"] = earnings_proximity(_date_cls.fromisoformat(str(next_date)))
            else:
                ev["earnings"] = {"info": "차기 실적 일정 없음"}
        except Exception as e:
            ev["earnings"] = {"error": str(e)}
        try:
            ev["price_break"] = detect_52week_break(df_cache) if df_cache is not None else {"error": df_err}
        except Exception as e:
            ev["price_break"] = {"error": str(e)}
        try:
            reports = analyst.list_recent(code, days=30)
            ev["rating_changes"] = detect_rating_changes(reports, days=7)
        except Exception as e:
            ev["rating_changes"] = {"error": str(e)}
        bundle["events"] = ev
        success += 1
    except Exception as e:
        bundle["errors"]["events"] = str(e)

    # 9) consensus
    try:
        cons = analyst.get_consensus(code)
        reports = analyst.list_recent(code, days=90)
        tp_trend = target_price_trend(reports, days_current=30, days_prev=60)
        rw = rating_wave(reports, days=90)
        bundle["consensus"] = {
            "consensus_view": _row_safe(cons),
            "target_price_trend": tp_trend,
            "rating_wave": rw,
            "total_reports": len(reports) if reports else 0,
        }
        if cons or reports:
            success += 1
        else:
            # DB 비어있어도 호출 자체는 성공으로 카운트하되 noted
            bundle["consensus"]["note"] = "DB empty — base.md 컨센 인용 필요"
            success += 1
    except Exception as e:
        bundle["errors"]["consensus"] = str(e)

    # 10) disclosures (v4 신규) — KR=DART / US=EDGAR 14일
    # v9 (라운드 2026-05 사후, #23): 응답 size 가드. 다대량 종목 (8-K 폭증) 대비.
    try:
        if market == "us":
            from server.scrapers import edgar
            disc_df = edgar.fetch_disclosures(code, days=14)
        else:
            disc_df = dart.fetch_disclosures(code, days=14)
        all_disc = (
            disc_df.to_dict(orient="records")
            if disc_df is not None and not disc_df.empty else []
        )
        bundle["disclosures"] = _truncate_rows(all_disc, max_rows=DISCLOSURES_MAX_ROWS)
        success += 1
    except Exception as e:
        bundle["errors"]["disclosures"] = str(e)
        bundle["disclosures"] = {"rows": [], "count": 0, "truncated": False}

    # 11) insider_trades (v4 신규) — KR=DART major_shareholders_exec / US=Finnhub 90일
    # v9 (라운드 2026-05 사후, #23): GS 147KB token 한도 초과 사례 — rows cap + summary 강화.
    try:
        if market == "us":
            from server.scrapers import finnhub as fh
            ins_df = fh.fetch_insider_trading(code, days=90)
        else:
            # KR: 90일 필터링은 raw 응답에 적용 (rcept_dt 기반)
            ins_df = dart.fetch_major_shareholders_exec(code)
            if ins_df is not None and not ins_df.empty and "rcept_dt" in ins_df.columns:
                cutoff = (pd.Timestamp.now() - pd.Timedelta(days=90)).strftime("%Y%m%d")
                ins_df = ins_df[ins_df["rcept_dt"] >= cutoff].copy()
        all_rows = (
            ins_df.to_dict(orient="records")
            if ins_df is not None and not ins_df.empty else []
        )
        # 90일 누적 매수/매도 합계 (US 만 가능 — KR raw 는 별도 매핑 필요)
        net_summary: dict = {"buy_count": 0, "sell_count": 0}
        if market == "us" and all_rows:
            for r in all_rows:
                t = str(r.get("유형") or "").strip()
                if t == "매수":
                    net_summary["buy_count"] += 1
                elif t == "매도":
                    net_summary["sell_count"] += 1
        truncated = _truncate_rows(all_rows, max_rows=INSIDER_MAX_ROWS)
        bundle["insider_trades"] = {
            "rows": truncated["rows"],
            "summary_90d": net_summary,
            "count": truncated["count"],          # 표시 rows 수 (cap 후)
            "total_count": len(all_rows),         # 원본 rows 수 (cap 전)
            "truncated": truncated["truncated"],
        }
        success += 1
    except Exception as e:
        bundle["errors"]["insider_trades"] = str(e)
        bundle["insider_trades"] = {
            "rows": [], "summary_90d": {}, "count": 0, "total_count": 0, "truncated": False,
        }

    # 12) base 본문 3층 inject (v4 신규, include_base=True 시) — economy/industry/stock
    if include_base:
        try:
            from server.repos import economy as economy_repo, industries as ind_repo
            ind_code = (s_row or {}).get("industry_code")
            base_payload = {
                "economy": _row_safe(economy_repo.get_base(market)),
                "industry": _row_safe(ind_repo.get_industry(ind_code)) if ind_code else None,
                "stock": _row_safe(stock_base.get_base(code)),
            }
            bundle["base"] = base_payload
            success += 1
        except Exception as e:
            bundle["errors"]["base"] = str(e)
            bundle["base"] = {}

    # Coverage 임계값 경고 (<80% 시 ⚠️)
    bundle["categories_succeeded"] = success
    bundle["categories_total"] = total
    coverage = round(100 * success / total, 1) if total else 0.0
    bundle["coverage_pct"] = coverage
    bundle["coverage_warning"] = (
        "⚠️ 반쪽 분석 — coverage < 80%, 일부 카테고리 데이터 누락"
        if coverage < 80 else None
    )
    return _json_safe(bundle)


# =====================================================================
# 룰 카탈로그 — 회고 helper
# =====================================================================

@mcp.tool
def list_trades_by_rule(week_start: str, week_end: str | None = None) -> dict:
    """
    특정 주의 trades 를 rule_category 별 그룹으로 반환 — 매주 회고 작성 helper.

    Args:
        week_start: 'YYYY-MM-DD' 월요일 (KST)
        week_end: 'YYYY-MM-DD' 일요일 (생략 시 week_start + 6일)

    Returns:
        {
            "week_start": "...",
            "week_end": "...",
            "by_rule": {
                "신고가돌파매수": [{trade_id, code, side, qty, price, executed_at, trigger_note, ...}, ...],
                "이벤트익절": [...],
                "_no_rule": [...]   # rule_category NULL 인 trades (옛 trades 또는 명시 안 한 매매)
            },
            "summary": {rule: count, ...}
        }

    활용:
        save_weekly_review(win_rate={...}) 작성 시 룰별 trade 보고 win/loss 평가.
    """
    from datetime import date, timedelta
    ws = date.fromisoformat(week_start)
    we = date.fromisoformat(week_end) if week_end else ws + timedelta(days=6)

    from server.db import pool
    from datetime import datetime as dt_cls
    from zoneinfo import ZoneInfo
    kst = ZoneInfo("Asia/Seoul")
    start_dt = dt_cls.combine(ws, dt_cls.min.time(), tzinfo=kst)
    end_dt = dt_cls.combine(we + timedelta(days=1), dt_cls.min.time(), tzinfo=kst)

    by_rule: dict[str, list] = {}
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT t.id, t.code, s.name, t.side, t.qty, t.price, t.executed_at,
                   t.trigger_note, t.fees, t.rule_category, t.realized_pnl
            FROM trades t
            JOIN stocks s ON s.code = t.code
            WHERE t.executed_at >= %s AND t.executed_at < %s
            ORDER BY t.executed_at
            """,
            (start_dt, end_dt),
        )
        for r in cur.fetchall():
            key = r["rule_category"] or "_no_rule"
            by_rule.setdefault(key, []).append(_row_safe(r))

    summary = {k: len(v) for k, v in by_rule.items()}
    return _json_safe({
        "week_start": str(ws),
        "week_end": str(we),
        "by_rule": by_rule,
        "summary": summary,
    })


# =====================================================================
# 백테스트 (시그널 백테스트 — discover 모드 통합)
# =====================================================================

@mcp.tool
def backtest_signals(
    code: str,
    lookback: int = 200,
    hold_days: list[int] | None = None,
) -> dict:
    """
    단일 종목 12 시그널 백테스트 — discover 모드에서 후보 종목 신뢰도 측정용.

    각 시그널 (일목/SEPA/RSI 과매도/그랜빌/평균회귀/볼린저/추세반전/...) 발생 후
    5/10/20일 hold 의 승률·평균수익률 산출. 종목별로 어떤 시그널이 더 신뢰할지 가시화.

    Args:
        code: 종목 코드 (KR 6자리 또는 US 티커, 자동 분기)
        lookback: 백테스트 기간 영업일 (기본 200 ≈ 10개월)
        hold_days: 수익률 추적 기간 리스트 (기본 [5, 10, 20])

    Returns:
        {
            "전략별": {전략명: {"H5": {tries, wins, pct, avg_return}, "H10": {...}, "H20": {...}}},
            "복합시그널": {조합명: 승률},
            "기간": {"시작": "...", "종료": "...", "영업일": int},
        }
        or {"error": "..."}

    활용 (discover-workflow 참조):
        - Top 3~5 추천 시 백테스트 결과 첨부 — LLM 이 종목 선택 시 참고
        - 자동 가중치 조정 X (Phase 1) — 정보 첨부만. 표본 부족 / 과적합 회피.

    제약:
        - 최소 400 영업일 데이터 필요 (지표 안정화 200 + lookback + max_hold)
        - 표본 부족 시 신뢰구간 넓음 — 시그널당 ≥10회 발생 필요
    """
    if hold_days is None:
        hold_days = [5, 10, 20]

    days_needed = lookback + 200 + max(hold_days) + 30  # 안정화 + 백테스트 + hold + 휴일 보정
    df = _fetch_ohlcv(code, days=days_needed)
    if df is None or df.empty:
        return {"error": f"no OHLCV for {code}"}

    from server.analysis.backtest import backtest_stock
    return _json_safe(backtest_stock(df, lookback=lookback, hold_days=hold_days))


# =====================================================================
# rule_catalog MCP (v10) — 매매 룰 single source-of-truth + LLM 노출
# =====================================================================
# 라운드: 2026-05 weekly-review overhaul
# 옛 한글 enum CHECK + INT[] 분산 → rule_catalog 테이블 통일.
# LLM 이 register_rule 으로 새 룰 추가 가능 (학습→격상→카탈로그 자동 확장).

@mcp.tool
def register_rule(
    enum_name: str,
    category: str,
    description: str | None = None,
    display_order: int | None = None,
) -> dict:
    """새 매매 룰 등록 — LLM 이 학습→격상 시 카탈로그 확장.

    Args:
      enum_name: 한글 슬러그 (예: '발굴사용자선택진입'). UNIQUE 강제.
      category: 'entry' | 'exit' | 'manage'
      description: 룰 설명 (LLM 이 회고 시 인용)
      display_order: 사용자 출력 정렬 (None 시 max+1 자동)

    검증:
      - enum_name 중복 차단 / 100자 이하 / 비어있을 수 없음
      - category 3 enum (entry/exit/manage)

    카탈로그 외 매매 패턴 발견 시 (record_trade 의 rule_category 누락 등)
    본 MCP 호출 후 trades.rule_id 사용 — BLOCKING.
    """
    from server.repos import rule_catalog as rc
    try:
        row = rc.register(enum_name, category, description=description, display_order=display_order)
        return {"ok": True, "row": _row_safe(row)}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


@mcp.tool
def list_rule_catalog(category: str | None = None, status: str = "active") -> list[dict]:
    """매매 룰 카탈로그 조회.

    Args:
      category: 'entry' | 'exit' | 'manage' (None = 전체)
      status: 'active' (디폴트) | 'deprecated' | 'all' (None 처리)

    회고 / 매매 작성 시 인용. prepare_weekly_review_* 응답에도 자동 join 됨.
    """
    from server.repos import rule_catalog as rc
    if status == "all" or status is None:
        rows = rc.list_all(category=category)
    elif status == "active":
        rows = rc.list_active(category=category)
    else:
        rows = rc.list_all(category=category, status=status)
    return [_row_safe(r) for r in rows]


@mcp.tool
def get_rule(id_or_enum_name: int | str) -> dict | None:
    """룰 단일 조회 — INT id 또는 한글 enum_name 양쪽 받음 (auto-detect)."""
    from server.repos import rule_catalog as rc
    return _row_safe(rc.get_by_id_or_name(id_or_enum_name))


@mcp.tool
def update_rule(
    rule_id: int,
    description: str | None = None,
    display_order: int | None = None,
) -> dict:
    """룰 메타 갱신 — description / display_order 만. None 인자 미반영."""
    from server.repos import rule_catalog as rc
    try:
        row = rc.update(rule_id, description=description, display_order=display_order)
        return {"ok": True, "row": _row_safe(row)}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


@mcp.tool
def deprecate_rule(rule_id: int, reason: str | None = None) -> dict:
    """룰 폐기 — soft delete (status='deprecated'). 옛 trades 보존 + 신규 사용 차단."""
    from server.repos import rule_catalog as rc
    try:
        row = rc.deprecate(rule_id, reason=reason)
        return {"ok": True, "row": _row_safe(row)}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


# =====================================================================
# weekly_review_per_stock CRUD (v5) — 종목별 회고 영속
# =====================================================================
# 라운드: 2026-05 weekly-review overhaul (Phase 1 결과 영속)

@mcp.tool
def save_weekly_review_per_stock(
    week_start: str,
    week_end: str,
    code: str,
    *,
    trade_evaluations: list | None = None,
    base_snapshot: dict | None = None,
    base_impact: str | None = None,
    base_thesis_aligned: bool | None = None,
    base_refresh_required: bool | None = None,
    base_refreshed_during_review: bool | None = None,
    base_appendback_done: bool | None = None,
    base_narrative_revision_proposed: bool | None = None,
    content: str | None = None,
) -> dict:
    """종목별 주간 회고 저장 (upsert) — Phase 1 결과 영속.

    week_start: 'YYYY-MM-DD' 월요일 / week_end: 'YYYY-MM-DD' 일요일

    - trade_evaluations: [{trade_id, side, sold_at|bought_at, price, current_price,
                           qty, foregone_pnl, delta_pct, smart_or_early}]
    - base_snapshot: {economy: {...}, industry: {...}, stock: {...}}
    - base_impact: 'decisive' | 'supportive' | 'contradictory' | 'neutral'
    - base_thesis_aligned: base.thesis 와 본 주 결과 정합 BOOL
    - base_refresh_required: 만기 임박 또는 narrative 수정 필요
    - base_refreshed_during_review: Phase 0 에서 본 종목 base 갱신했는지
    - base_appendback_done: Phase 3 에서 base.Daily Appended Facts append 했는지
    - base_narrative_revision_proposed: decisive 강화 발견 시 narrative 수정 후보 큐 적재
    - content: 자연어 본문 (200~400자)

    None 인 필드는 기존 값 유지 (COALESCE).
    """
    from datetime import date as date_cls
    from server.repos import weekly_review_per_stock as wrps

    ws = date_cls.fromisoformat(week_start)
    we = date_cls.fromisoformat(week_end)

    try:
        wrps.upsert(
            week_start=ws, week_end=we, code=code,
            trade_evaluations=trade_evaluations,
            base_snapshot=base_snapshot,
            base_impact=base_impact,
            base_thesis_aligned=base_thesis_aligned,
            base_refresh_required=base_refresh_required,
            base_refreshed_during_review=base_refreshed_during_review,
            base_appendback_done=base_appendback_done,
            base_narrative_revision_proposed=base_narrative_revision_proposed,
            content=content,
        )
        return {"ok": True, "week_start": week_start, "code": code}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


@mcp.tool
def get_weekly_review_per_stock(week_start: str, code: str) -> dict | None:
    """종목별 주간 회고 단건 조회. week_start = 'YYYY-MM-DD' 월요일."""
    from datetime import date as date_cls
    from server.repos import weekly_review_per_stock as wrps
    return _row_safe(wrps.get(date_cls.fromisoformat(week_start), code))


@mcp.tool
def list_weekly_review_per_stock(week_start: str) -> list[dict]:
    """한 주의 모든 종목 회고 묶음 조회 — Phase 2 인풋 join 용."""
    from datetime import date as date_cls
    from server.repos import weekly_review_per_stock as wrps
    rows = wrps.list_by_week(date_cls.fromisoformat(week_start))
    return [_row_safe(r) for r in rows]


@mcp.tool
def list_weekly_review_per_stock_by_code(code: str, weeks: int = 12) -> list[dict]:
    """종목별 회고 시계열 — 장기 thesis 추적용 (web UI 가 사용 가능)."""
    from server.repos import weekly_review_per_stock as wrps
    rows = wrps.list_by_code(code, weeks=weeks)
    return [_row_safe(r) for r in rows]


# =====================================================================
# prepare_weekly_review_per_stock (v3) — Phase 1 인풋 묶음
# =====================================================================
# 라운드: 2026-05 weekly-review overhaul
# 종목 1건 회고에 필요한 모든 데이터를 1 호출 묶음으로 반환.
# analyze_position 패턴 평행 — LLM 도구 탐색 0회.

def _classify_smart_or_early(side: str, price: float, current_price: float) -> str:
    """매도가 vs 현재가 비교 → smart / early / marginal 분류.

    sell 거래만 의미 있음 (buy 는 미실현 평가).
    - |Δ| < 1% → smart (정확한 정점/저점)
    - 매도 후 +5% 이상 상승 → early (너무 일찍 팔았음)
    - 매도 후 -5% 이상 하락 → smart (정점 정확 인식)
    - 그 외 → marginal
    """
    if side != "sell" or current_price is None or price is None:
        return "n/a"
    delta_pct = (current_price - price) / price * 100.0
    if abs(delta_pct) < 1.0:
        return "smart"
    if delta_pct > 5.0:
        return "early"
    if delta_pct < -5.0:
        return "smart"
    return "marginal"


def _get_current_price_for_code(code: str, market: str) -> tuple[float | None, str | None]:
    """현재가 조회 — KR realtime_price / US kis_us_quote 자동 라우팅.

    Returns: (price, base_time_iso)
    """
    try:
        if market == "kr":
            from server.scrapers.naver import fetch_realtime_price
            row = fetch_realtime_price(code)
            if row and row.get("price"):
                return (float(row["price"]), row.get("base_time"))
        else:
            from server.scrapers.kis import fetch_us_quote
            row = fetch_us_quote(code)
            if row and row.get("price"):
                return (float(row["price"]), None)
    except Exception:
        pass
    return (None, None)


@mcp.tool
def prepare_weekly_review_per_stock(
    week_start: str,
    week_end: str,
    code: str,
    level: str = "detail",
) -> dict:
    """Phase 1 인풋 묶음 — 종목 1건 회고에 필요한 모든 데이터 1 호출 반환.

    Args:
      week_start: 'YYYY-MM-DD' 월요일
      week_end:   'YYYY-MM-DD' 일요일
      code: 종목 코드
      level: 'summary' | 'detail' (디폴트 detail, summary 면 derived metrics 만)

    Returns: 13 카테고리 묶음 (analyze_position 평행)
      - trades: 본 주 trades + rule_catalog join
      - position_now: 현재 포지션 + style/stop/tags
      - stock_daily_quant_timeseries: 본 주 stock_daily 정량 6 컬럼
      - stock_daily_at_entries: 매매 직전 stock_daily verdict (smart 추적)
      - per_stock_summary_timeseries: portfolio_snapshots.per_stock_summary 본 주
      - watch_levels: pending watch levels
      - position_docs: thesis/action_rules
      - analyst_reports_week: 본 주 published_at
      - events_week: 본 주 events (어닝/신고가 등)
      - base_snapshot: {economy, industry, stock} 회고 시점 메타
      - base_freshness: 만기 임박 여부 (days_to_expire)
      - foregone_pnl_data: 매도 후 현재가 비교 (자동 산출)
      - verdict_distribution: 본 주 verdict 5종 분포
      - override_freq_week: override_dimensions 차원별 활성화 빈도
      - related_learned_patterns: 본 종목 룰 그룹과 매칭 패턴
      - rule_catalog_join: trades.rule_id 등장 룰 메타
    """
    from datetime import date as date_cls
    from server.repos import (
        analyst, learned_patterns, portfolio_snapshots, position_docs,
        positions, rule_catalog as rc, stock_base, stock_daily, stocks,
        trades as trades_repo, watch_levels, economy, industries,
    )

    ws = date_cls.fromisoformat(week_start)
    we = date_cls.fromisoformat(week_end)
    uid = settings.stock_user_id

    # 종목 메타 (market 식별)
    stock_row = stocks.get_stock(code)
    if not stock_row:
        return {"error": f"종목 없음: {code}"}
    market = stock_row.get("market", "kr")
    industry_code = stock_row.get("industry_code")

    # 1) trades + rule_catalog join (본 주만)
    with __import__("server.db", fromlist=["get_conn"]).get_conn() as conn:
        cur = conn.execute(
            """
            SELECT t.id, t.code, t.side, t.qty, t.price, t.executed_at,
                   t.trigger_note, t.realized_pnl, t.fees,
                   t.rule_category, t.rule_id,
                   rc.enum_name, rc.category, rc.description AS rule_description
              FROM trades t
              LEFT JOIN rule_catalog rc ON t.rule_id = rc.id
             WHERE t.user_id = %s AND t.code = %s
               AND (t.executed_at AT TIME ZONE 'Asia/Seoul')::date BETWEEN %s AND %s
             ORDER BY t.executed_at
            """,
            (uid, code, ws, we),
        )
        trades_rows = [_row_safe(r) for r in cur.fetchall()]

    # 2) 현재가 + foregone_pnl + smart_or_early
    current_price, current_price_at = _get_current_price_for_code(code, market)
    foregone_data = []
    for t in trades_rows:
        if not t:
            continue
        sold_price = float(t["price"]) if t.get("price") is not None else None
        qty = float(t["qty"]) if t.get("qty") is not None else None
        side = t.get("side")
        foregone_pnl = None
        delta_pct = None
        smart_or_early = "n/a"
        if current_price and sold_price and qty:
            if side == "sell":
                foregone_pnl = (current_price - sold_price) * qty
                delta_pct = (current_price - sold_price) / sold_price * 100.0
                smart_or_early = _classify_smart_or_early(side, sold_price, current_price)
            elif side == "buy":
                # 미실현 PnL (현재가 - 매수가)
                foregone_pnl = (current_price - sold_price) * qty
                delta_pct = (current_price - sold_price) / sold_price * 100.0
                smart_or_early = "n/a"  # buy 는 분류 안 함
        foregone_data.append({
            "trade_id": t["id"],
            "side": side,
            "executed_at": t.get("executed_at"),  # _row_safe 가 이미 str ISO 로 변환
            "price": sold_price,
            "current_price": current_price,
            "qty": qty,
            "foregone_pnl": foregone_pnl,
            "delta_pct": delta_pct,
            "smart_or_early": smart_or_early,
        })

    # 3) position 현재 상태
    pos = positions.get_position(uid, code) if hasattr(positions, "get_position") else None
    if not pos:
        # fallback — list_daily_positions 등 사용 안 하고 직접 조회
        with __import__("server.db", fromlist=["get_conn"]).get_conn() as conn:
            cur = conn.execute(
                "SELECT * FROM positions WHERE user_id=%s AND code=%s",
                (uid, code),
            )
            pos = cur.fetchone()
    pos_safe = _row_safe(pos) if pos else None

    # 4) stock_daily 정량 시계열 (본 주)
    sd_quant = stock_daily.get_recent_quant(uid, code, ws, we)
    sd_quant_safe = [_row_safe(r) for r in sd_quant]

    # verdict 분포
    verdict_counts: dict[str, int] = {}
    override_counts: dict[str, int] = {}
    for r in sd_quant_safe:
        if r and r.get("verdict"):
            verdict_counts[r["verdict"]] = verdict_counts.get(r["verdict"], 0) + 1
        ods = r.get("override_dimensions") if r else None
        if isinstance(ods, list):
            for d in ods:
                override_counts[str(d)] = override_counts.get(str(d), 0) + 1

    # 5) 매매 직전 stock_daily lookup (각 trade 마다)
    sd_at_entries = []
    for t in trades_rows:
        if not t or not t.get("executed_at"):
            continue
        # _row_safe 가 이미 ISO str 변환 — date 부분만 추출
        ea_str = t["executed_at"]
        try:
            target_date = date_cls.fromisoformat(ea_str.split("T")[0]) if isinstance(ea_str, str) else ea_str.date()
        except Exception:
            continue
        sd_row = stock_daily.get_quant_at_or_before(uid, code, target_date)
        sd_at_entries.append({
            "trade_id": t["id"],
            "executed_at": ea_str,
            "stock_daily": _row_safe(sd_row) if sd_row else None,
        })

    # 6) per_stock_summary 시계열 (portfolio_snapshots 에서 본 종목 추출)
    pss_timeseries = []
    snapshots = portfolio_snapshots.get_range(uid, ws, we)
    for snap in snapshots:
        pss = snap.get("per_stock_summary") or []
        for entry in pss:
            if entry.get("code") == code:
                pss_timeseries.append({
                    "date": snap["date"].isoformat() if hasattr(snap.get("date"), "isoformat") else str(snap.get("date")),
                    "close": entry.get("close"),
                    "change_pct": entry.get("change_pct"),
                    "pnl_pct": entry.get("pnl_pct"),
                    "verdict": entry.get("verdict"),
                    "note": entry.get("note"),
                })
                break

    # 7) watch_levels + position_docs
    wl_rows = []
    pd_row = None
    try:
        wl_rows = [_row_safe(r) for r in watch_levels.list_by_code(uid, code)] if hasattr(watch_levels, "list_by_code") else []
    except Exception:
        wl_rows = []
    try:
        pd_row = _row_safe(position_docs.get(uid, code)) if hasattr(position_docs, "get") else None
    except Exception:
        pd_row = None

    # 8) analyst_reports + events (본 주)
    with __import__("server.db", fromlist=["get_conn"]).get_conn() as conn:
        cur = conn.execute(
            """
            SELECT id, broker, analyst, published_at, rating, rating_change,
                   target_price, previous_target_price, summary, key_thesis
              FROM analyst_reports
             WHERE code = %s
               AND (published_at AT TIME ZONE 'Asia/Seoul')::date BETWEEN %s AND %s
             ORDER BY published_at DESC
            """,
            (code, ws, we),
        )
        ar_rows = [_row_safe(r) for r in cur.fetchall()]

        cur = conn.execute(
            """
            SELECT id, event_type, event_date, payload, processed
              FROM events
             WHERE user_id = %s AND code = %s
               AND COALESCE(event_date, (created_at AT TIME ZONE 'Asia/Seoul')::date)
                   BETWEEN %s AND %s
             ORDER BY COALESCE(event_date, (created_at AT TIME ZONE 'Asia/Seoul')::date) DESC
            """,
            (uid, code, ws, we),
        )
        ev_rows = [_row_safe(r) for r in cur.fetchall()]

    # 9) base_snapshot (회고 시점 base 3종 + freshness)
    eb = economy.get_base(market) if hasattr(economy, "get_base") else None
    ind = industries.get_industry(industry_code) if industry_code and hasattr(industries, "get_industry") else None
    sb = stock_base.get_base(code) if hasattr(stock_base, "get_base") else None

    def _extract_meta(row, content_keys=None, max_chars=200):
        if not row:
            return None
        m = _row_safe(row) or {}
        # content 본문은 200자만
        if "content" in m and m["content"]:
            m["content_excerpt"] = m["content"][:max_chars]
            del m["content"]
        # narrative 도 200자만
        if "narrative" in m and m["narrative"]:
            m["narrative_excerpt"] = m["narrative"][:max_chars]
            del m["narrative"]
        return m

    today = date_cls.today()
    def _freshness(row, expires_default_days=None):
        if not row:
            return {"available": False}
        ua = row.get("updated_at")
        if not ua:
            return {"available": True, "days_since_update": None}
        days_since = (today - ua.date()).days if hasattr(ua, "date") else None
        ea = row.get("expires_at")
        days_to_expire = None
        if ea and hasattr(ea, "date"):
            days_to_expire = (ea.date() - today).days
        return {
            "available": True,
            "days_since_update": days_since,
            "days_to_expire": days_to_expire,
            "expired": (days_to_expire is not None and days_to_expire < 0),
        }

    base_snapshot = {
        "economy": _extract_meta(eb),
        "industry": _extract_meta(ind),
        "stock": _extract_meta(sb),
    }
    base_freshness = {
        "economy": _freshness(eb),
        "industry": _freshness(ind),
        "stock": _freshness(sb),
    }

    # 10) related_learned_patterns (본 종목의 trades.rule_id 매칭)
    rule_ids = [t["rule_id"] for t in trades_rows if t and t.get("rule_id")]
    related_patterns = []
    if rule_ids:
        with __import__("server.db", fromlist=["get_conn"]).get_conn() as conn:
            cur = conn.execute(
                """
                SELECT id, tag, description, occurrences, win_rate, sample_count,
                       promotion_status, related_rule_ids
                  FROM learned_patterns
                 WHERE related_rule_ids && %s::int[]
                """,
                (rule_ids,),
            )
            related_patterns = [_row_safe(r) for r in cur.fetchall()]

    # 11) rule_catalog_join (trades.rule_id 등장 룰)
    rc_rows = rc.list_active()
    rule_catalog_join = [_row_safe(r) for r in rc_rows]

    # === level=summary 면 derived 만 반환 ===
    if level == "summary":
        return _json_safe({
            "code": code,
            "name": stock_row.get("name"),
            "market": market,
            "trade_count": len(trades_rows),
            "current_price": current_price,
            "current_price_at": current_price_at,
            "foregone_pnl_data": foregone_data,
            "verdict_distribution": verdict_counts,
            "override_freq_week": override_counts,
            "base_freshness": base_freshness,
            "related_learned_patterns": related_patterns,
        })

    # === level=detail (디폴트) ===
    return _json_safe({
        "code": code,
        "name": stock_row.get("name"),
        "market": market,
        "industry_code": industry_code,
        "trades": trades_rows,
        "position_now": pos_safe,
        "stock_daily_quant_timeseries": sd_quant_safe,
        "stock_daily_at_entries": sd_at_entries,
        "per_stock_summary_timeseries": pss_timeseries,
        "watch_levels": wl_rows,
        "position_docs": pd_row,
        "analyst_reports_week": ar_rows,
        "events_week": ev_rows,
        "base_snapshot": base_snapshot,
        "base_freshness": base_freshness,
        "current_price": current_price,
        "current_price_at": current_price_at,
        "foregone_pnl_data": foregone_data,
        "verdict_distribution": verdict_counts,
        "override_freq_week": override_counts,
        "related_learned_patterns": related_patterns,
        "rule_catalog_join": rule_catalog_join,
    })


# =====================================================================
# prepare_weekly_review_portfolio (v4) — Phase 2 인풋 묶음
# =====================================================================

@mcp.tool
def prepare_weekly_review_portfolio(
    week_start: str,
    week_end: str,
    level: str = "detail",
) -> dict:
    """Phase 2 인풋 묶음 — 종합 회고에 필요한 모든 데이터 1 호출 반환.

    Args:
      week_start, week_end: 'YYYY-MM-DD'
      level: 'summary' | 'detail'

    Returns: 8 카테고리 묶음
      - per_stock_reviews_join: Phase 1 결과 (weekly_review_per_stock 모든 row)
      - portfolio_timeseries: 본 주 portfolio_snapshots + trends (weights_drift, sector_drift)
      - vs_benchmark: KOSPI/SPX 변화율 + alpha
      - prev_review_followup: 직전 W-1 회고의 next_week_emphasize → 본 주 win_rate
      - prev_strategy_evaluation: weekly_strategy.focus_themes 적중 + rules 효과
      - promote_candidates: sample 5+ 학습 패턴 격상 후보
      - base_thesis_summary: economy / industries (modal) / stock_base 메타
      - rule_catalog_join: 활성 룰 전체
    """
    from datetime import date as date_cls, timedelta
    from server.repos import (
        learned_patterns, portfolio_snapshots, rule_catalog as rc,
        weekly_review_per_stock as wrps, weekly_reviews as wr,
        weekly_strategy as ws_repo, economy, industries, stock_base,
    )

    ws = date_cls.fromisoformat(week_start)
    we = date_cls.fromisoformat(week_end)
    uid = settings.stock_user_id

    # 1) per_stock_reviews_join (Phase 1 결과 자동 join)
    per_stock_rows = wrps.list_by_week(ws)
    per_stock_join = [_row_safe(r) for r in per_stock_rows]

    # 2) portfolio_timeseries
    snapshots = portfolio_snapshots.get_range(uid, ws, we)
    snap_safe = [_row_safe(s) for s in snapshots]
    trends = {}
    if snap_safe:
        first = snap_safe[0]
        last = snap_safe[-1]
        trends["total_krw_start"] = first.get("total_krw")
        trends["total_krw_end"] = last.get("total_krw")
        if first.get("total_krw") and last.get("total_krw"):
            trends["total_krw_chg_pct"] = (last["total_krw"] - first["total_krw"]) / first["total_krw"] * 100.0
        # sector_weights drift
        first_sw = first.get("sector_weights") or {}
        last_sw = last.get("sector_weights") or {}
        drift = {}
        all_sectors = set(first_sw.keys()) | set(last_sw.keys())
        for sector in all_sectors:
            s_pct = float(first_sw.get(sector, 0) or 0)
            e_pct = float(last_sw.get(sector, 0) or 0)
            drift[sector] = round(e_pct - s_pct, 2)
        trends["sector_weights_drift"] = drift
        # action_plan 합산
        total_actions = sum(len(s.get("action_plan") or []) for s in snap_safe)
        executed = sum(
            sum(1 for a in (s.get("action_plan") or []) if a.get("status") == "executed")
            for s in snap_safe
        )
        trends["action_plan_total_count"] = total_actions
        trends["action_plan_executed_count"] = executed
        trends["action_plan_hit_rate"] = (executed / total_actions) if total_actions else None

    # 3) vs_benchmark — KOSPI/SPX (economy_daily 인덱스에서 추출)
    vs_benchmark = {}
    with __import__("server.db", fromlist=["get_conn"]).get_conn() as conn:
        cur = conn.execute(
            """
            SELECT market, date, index_values
              FROM economy_daily
             WHERE date BETWEEN %s AND %s
             ORDER BY date ASC
            """,
            (ws, we),
        )
        ed_rows = cur.fetchall()
    by_market: dict[str, list] = {"kr": [], "us": []}
    for r in ed_rows:
        by_market.setdefault(r["market"], []).append(r)
    for mkt, rows in by_market.items():
        if len(rows) < 2:
            continue
        first = rows[0].get("index_values") or {}
        last = rows[-1].get("index_values") or {}
        idx_key = "kospi" if mkt == "kr" else "spy"
        f = float(first.get(idx_key) or 0)
        l = float(last.get(idx_key) or 0)
        if f > 0:
            vs_benchmark[f"{idx_key}_chg_pct"] = round((l - f) / f * 100.0, 2)
    if trends.get("total_krw_chg_pct") is not None:
        if "kospi_chg_pct" in vs_benchmark:
            vs_benchmark["alpha_kospi"] = round(
                trends["total_krw_chg_pct"] - vs_benchmark["kospi_chg_pct"], 2
            )
    vs_benchmark["portfolio_chg_pct"] = trends.get("total_krw_chg_pct")

    # 4) prev_review_followup (직전 회고)
    prev_ws = ws - timedelta(days=7)
    prev_review = wr.get_review(prev_ws)
    prev_followup = None
    if prev_review:
        prev_followup = {
            "week_start": prev_ws.isoformat(),
            "next_week_emphasize": prev_review.get("next_week_emphasize"),
            "next_week_avoid": prev_review.get("next_week_avoid"),
            "headline": prev_review.get("headline"),
        }
        # 본 주 trades.rule_id 분포로 적용 여부 자동 비교
        with __import__("server.db", fromlist=["get_conn"]).get_conn() as conn:
            cur = conn.execute(
                """
                SELECT rule_id, count(*) AS n
                  FROM trades
                 WHERE user_id = %s
                   AND (executed_at AT TIME ZONE 'Asia/Seoul')::date BETWEEN %s AND %s
                   AND rule_id IS NOT NULL
                 GROUP BY rule_id
                """,
                (uid, ws, we),
            )
            this_week_distribution = {r["rule_id"]: r["n"] for r in cur.fetchall()}
        emphasize = prev_review.get("next_week_emphasize") or []
        avoid = prev_review.get("next_week_avoid") or []
        prev_followup["emphasized_applied"] = [
            {"rule_id": rid, "applied_count": this_week_distribution.get(rid, 0)}
            for rid in emphasize
        ]
        prev_followup["avoided_violations"] = [
            {"rule_id": rid, "violation_count": this_week_distribution.get(rid, 0)}
            for rid in avoid
        ]

    # 5) prev_strategy_evaluation
    prev_strategy = ws_repo.get_by_week(ws)
    prev_strategy_eval = None
    if prev_strategy:
        prev_strategy_eval = {
            "week_start": ws.isoformat(),
            "market_outlook": prev_strategy.get("market_outlook"),
            "focus_themes": prev_strategy.get("focus_themes"),
            "rules_to_emphasize": prev_strategy.get("rules_to_emphasize"),
            "rules_to_avoid": prev_strategy.get("rules_to_avoid"),
            "carry_over": False,
        }
    else:
        # carry-over 직전 strategy
        prev_strategy_eval = {"carry_over": True, "warning": "이번 주 weekly_strategy 미작성"}

    # 6) promote_candidates
    promote = learned_patterns.list_promote_candidates(min_sample=5, min_win_rate=0.6)
    promote_safe = [_row_safe(r) for r in promote]

    # 7) base_thesis_summary
    eb_kr = economy.get_base("kr") if hasattr(economy, "get_base") else None
    eb_us = economy.get_base("us") if hasattr(economy, "get_base") else None
    base_thesis = {
        "economy_kr": _row_safe(eb_kr) if eb_kr else None,
        "economy_us": _row_safe(eb_us) if eb_us else None,
    }
    if base_thesis["economy_kr"]:
        c = base_thesis["economy_kr"].get("content") or ""
        base_thesis["economy_kr"]["content_excerpt"] = c[:200]
        base_thesis["economy_kr"]["content"] = None
    if base_thesis["economy_us"]:
        c = base_thesis["economy_us"].get("content") or ""
        base_thesis["economy_us"]["content_excerpt"] = c[:200]
        base_thesis["economy_us"]["content"] = None

    # 8) rule_catalog_join
    rc_rows = [_row_safe(r) for r in rc.list_active()]

    if level == "summary":
        return _json_safe({
            "week_start": week_start,
            "week_end": week_end,
            "per_stock_review_count": len(per_stock_join),
            "trends": trends,
            "vs_benchmark": vs_benchmark,
            "promote_candidates_count": len(promote_safe),
        })

    return _json_safe({
        "week_start": week_start,
        "week_end": week_end,
        "per_stock_reviews_join": per_stock_join,
        "portfolio_timeseries": {
            "snapshots": snap_safe,
            "trends": trends,
        },
        "vs_benchmark": vs_benchmark,
        "prev_review_followup": prev_followup,
        "prev_strategy_evaluation": prev_strategy_eval,
        "promote_candidates": promote_safe,
        "base_thesis_summary": base_thesis,
        "rule_catalog_join": rc_rows,
    })


# =====================================================================
# Phase 3 base append-back MCP (v6)
# =====================================================================
# 라운드: 2026-05 weekly-review overhaul
# 회고 학습을 base 에 역반영 (학습 사이클 폐쇄).
# ⚠️ main body 재작성 금지 — Daily Appended Facts 섹션 append 만.

DAILY_APPENDED_FACTS_HEADER = "## 📝 Daily Appended Facts"


def _append_to_facts_section(content: str, fact_text: str, today: str, source: str) -> str:
    """base content 의 'Daily Appended Facts' 섹션에 fact_text append.

    섹션 부재 시 신설. 같은 fact_text 가 본 섹션에 이미 있으면 중복 추가 안 함.
    """
    fact_line = f"- [{today}] [{source}] {fact_text}"
    if not content:
        return f"{DAILY_APPENDED_FACTS_HEADER}\n\n{fact_line}\n"
    if DAILY_APPENDED_FACTS_HEADER in content:
        # 중복 체크
        if fact_text in content:
            return content  # idempotent
        # 섹션 끝에 append (헤더 다음 라인부터 끝까지 확장)
        idx = content.rfind(DAILY_APPENDED_FACTS_HEADER)
        # 섹션 헤더 이후 끝까지 가져와서 새 줄 추가
        before = content[:idx]
        section = content[idx:]
        if not section.endswith("\n"):
            section += "\n"
        section += fact_line + "\n"
        return before + section
    # 섹션 부재 — 끝에 신설
    if not content.endswith("\n"):
        content += "\n"
    return content + f"\n{DAILY_APPENDED_FACTS_HEADER}\n\n{fact_line}\n"


@mcp.tool
def append_base_facts(
    target_type: str,
    target_key: str,
    fact_text: str,
    source: str = "weekly_review",
) -> dict:
    """base content 의 'Daily Appended Facts' 섹션에 fact append.

    Args:
      target_type: 'economy' | 'industry' | 'stock'
      target_key:  economy 면 market ('kr'/'us'), industry 면 industry_code, stock 면 종목 code
      fact_text:   회고에서 발견한 사실 한 줄 (예: "W18: SK하닉 1차목표 ₩1.3M 도달 + 신고가")
      source:      'weekly_review' | 'daily' | 'manual' (기본 weekly_review)

    ⚠️ 안전장치:
      - 같은 (target, fact_text) 가 이미 있으면 idempotent (중복 X)
      - main body 재작성 금지 — Daily Appended Facts 섹션만
      - 일일 상한 5건/target (DB content 길이로 추적, 본 라운드 단순 관리)
    """
    from datetime import date as date_cls
    from server.repos import economy, industries, stock_base

    if target_type not in ("economy", "industry", "stock"):
        return {"ok": False, "error": f"invalid target_type: {target_type}"}
    if not fact_text or not fact_text.strip():
        return {"ok": False, "error": "fact_text 비어있을 수 없음"}

    today = date_cls.today().isoformat()

    # 현재 content 조회 + 안전장치 (일일 상한)
    if target_type == "economy":
        row = economy.get_base(target_key)
        if not row:
            return {"ok": False, "error": f"economy_base 없음: {target_key}"}
        current_content = row.get("content") or ""
        # 일일 상한 — 오늘 날짜 라인 5+ 면 차단
        today_count = sum(1 for line in current_content.split("\n") if f"[{today}]" in line)
        if today_count >= 5:
            return {"ok": False, "error": f"일일 상한 초과 (5건/target): economy/{target_key}"}
        new_content = _append_to_facts_section(current_content, fact_text, today, source)
        if new_content == current_content:
            return {"ok": True, "message": "idempotent — 동일 fact 이미 존재", "appended": False}
        economy.upsert_base(market=target_key, content=new_content)

    elif target_type == "industry":
        row = industries.get_industry(target_key)
        if not row:
            return {"ok": False, "error": f"industries 없음: {target_key}"}
        current_content = row.get("content") or ""
        today_count = sum(1 for line in current_content.split("\n") if f"[{today}]" in line)
        if today_count >= 5:
            return {"ok": False, "error": f"일일 상한 초과 (5건/target): industry/{target_key}"}
        new_content = _append_to_facts_section(current_content, fact_text, today, source)
        if new_content == current_content:
            return {"ok": True, "message": "idempotent", "appended": False}
        industries.upsert(
            code=target_key,
            market=row.get("market"),
            name=row.get("name") or target_key,
            content=new_content,
        )

    else:  # stock
        row = stock_base.get_base(target_key)
        if not row:
            return {"ok": False, "error": f"stock_base 없음: {target_key}"}
        current_content = row.get("content") or ""
        today_count = sum(1 for line in current_content.split("\n") if f"[{today}]" in line)
        if today_count >= 5:
            return {"ok": False, "error": f"일일 상한 초과 (5건/target): stock/{target_key}"}
        new_content = _append_to_facts_section(current_content, fact_text, today, source)
        if new_content == current_content:
            return {"ok": True, "message": "idempotent", "appended": False}
        # stock_base.upsert_base 의 content 만 갱신
        stock_base.upsert_base(code=target_key, content=new_content)

    return {
        "ok": True,
        "target_type": target_type,
        "target_key": target_key,
        "fact_text": fact_text,
        "appended": True,
    }


@mcp.tool
def propose_base_narrative_revision(
    target_type: str,
    target_key: str,
    divergence_summary: str,
    evidence_trades: list[int] | None = None,
    week_start: str | None = None,
) -> dict:
    """base.narrative 수정 후보 큐 등록 (자동 적용 X — 사용자 검토).

    Args:
      target_type: 'economy' | 'industry' | 'stock'
      target_key: economy 면 market, industry 면 code, stock 면 code
      divergence_summary: 회고 발견 사실 요약 (예: "us-tech base decisive 시 헤지 30% 이내 룰 신설 후보")
      evidence_trades: 근거 trade_id 리스트
      week_start: 'YYYY-MM-DD' 회고 대상 주 월요일 (KST). None 시 today 기준 이번 주 월요일 추론.
                   지연 회고 안전장치 — 옛 주 회고 시 명시 전달 권장.

    저장 위치:
      해당 주 weekly_reviews.phase3_log.proposed_revisions JSONB 배열.
      get_pending_base_revisions(weeks=4) 로 일일 리마인드 (BLOCKING #14 후보).
    """
    from datetime import date as date_cls, timedelta
    from server.db import get_conn

    if target_type not in ("economy", "industry", "stock"):
        return {"ok": False, "error": f"invalid target_type: {target_type}"}

    today = date_cls.today()
    if week_start is not None:
        try:
            ws_in = date_cls.fromisoformat(week_start)
            if ws_in.weekday() != 0:
                return {"ok": False, "error": f"week_start 는 월요일이어야 함: {week_start} (weekday={ws_in.weekday()})"}
            week_start = ws_in
        except ValueError as e:
            return {"ok": False, "error": f"invalid week_start: {e}"}
    else:
        # 이번 주 월요일 추론 (지연 회고 시 잘못된 주 적재 위험 — 명시 전달 권장)
        week_start = today - timedelta(days=today.weekday())
    uid = settings.stock_user_id

    revision = {
        "target_type": target_type,
        "target_key": target_key,
        "divergence_summary": divergence_summary,
        "evidence_trades": evidence_trades or [],
        "status": "pending_user_review",
        "proposed_at": today.isoformat(),
    }

    with get_conn() as conn:
        cur = conn.execute(
            "SELECT phase3_log FROM weekly_reviews WHERE user_id=%s AND week_start=%s",
            (uid, week_start),
        )
        row = cur.fetchone()
        existing = (row.get("phase3_log") if row else None) or {}
        if not isinstance(existing, dict):
            existing = {}
        revisions = existing.get("proposed_revisions") or []
        # 중복 체크 (같은 target + summary)
        for r in revisions:
            if (r.get("target_type") == target_type
                and r.get("target_key") == target_key
                and r.get("divergence_summary") == divergence_summary):
                return {"ok": True, "message": "idempotent — 동일 revision 이미 큐에 있음"}
        revisions.append(revision)
        existing["proposed_revisions"] = revisions

        # weekly_reviews row 없으면 생성, 있으면 phase3_log 갱신
        if row:
            from psycopg.types.json import Jsonb
            conn.execute(
                "UPDATE weekly_reviews SET phase3_log=%s, updated_at=now() WHERE user_id=%s AND week_start=%s",
                (Jsonb(existing), uid, week_start),
            )
        else:
            from psycopg.types.json import Jsonb
            conn.execute(
                """
                INSERT INTO weekly_reviews (user_id, week_start, week_end, phase3_log)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, week_start) DO UPDATE SET phase3_log = EXCLUDED.phase3_log
                """,
                (uid, week_start, week_start + timedelta(days=6), Jsonb(existing)),
            )

    return {"ok": True, "revision": revision, "queue_size": len(revisions)}


@mcp.tool
def get_pending_base_revisions(weeks: int = 4) -> dict:
    """미처리 base narrative revision 큐 조회.

    Args:
      weeks: 최근 N주 회고에서 적재된 큐 합산 (기본 4)

    Returns: {pending: [...], count}
    daily Phase 1 BLOCKING 에서 count >= 3 시 ⚠️ 알림 가드.
    """
    from datetime import date as date_cls, timedelta
    from server.db import get_conn

    today = date_cls.today()
    cutoff = today - timedelta(weeks=weeks)
    uid = settings.stock_user_id

    pending = []
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT week_start, phase3_log
              FROM weekly_reviews
             WHERE user_id = %s AND week_start >= %s
               AND phase3_log IS NOT NULL
             ORDER BY week_start DESC
            """,
            (uid, cutoff),
        )
        for row in cur.fetchall():
            log = row.get("phase3_log") or {}
            if not isinstance(log, dict):
                continue
            for rev in log.get("proposed_revisions") or []:
                if rev.get("status") == "pending_user_review":
                    rev_copy = dict(rev)
                    rev_copy["week_start"] = row["week_start"].isoformat()
                    pending.append(rev_copy)

    return {"pending": pending, "count": len(pending)}


# =====================================================================
# 헬스체크
# =====================================================================

@mcp.tool
def healthcheck(quick: bool = True) -> dict:
    """
    MCP 도구·스크래퍼·DB·데이터 신선도 일괄 점검.

    Args:
        quick: True 면 발굴 도구 (rank_momentum_wide US 등 ~3분 걸리는 것) 스킵.

    Returns:
        {
          "timestamp": "...",
          "mcp_tools_kr": {도구명: {status, duration_s, preview/error}, ...},
          "mcp_tools_us": {...},
          "mcp_tools_portfolio": {...},
          "mcp_tools_discovery": {...},
          "scrapers": {KIS/DART/Naver/KRX/yfinance/Finnhub/FRED/EDGAR},
          "db_integrity": {stocks_null_industry, cash_balance_KRW, cash_balance_USD,
                           positions_by_status, orphan_positions},
          "data_freshness": {stock_daily_max, per_stock_daily_freshness,
                             economy_base_freshness, stale_stock_base_30d_plus,
                             analyst_reports_max},
          "summary": {카테고리: {ok, fail, total}, ...}
        }

    실행:
        - quick=True (기본, ~30초): KR + US 분석 + 포트 + 스크래퍼 + DB
        - quick=False (~3분+): 발굴 (rank_momentum_wide US 시리얼 fetch) 포함
    """
    from server.jobs.healthcheck import run_healthcheck
    return _json_safe(run_healthcheck(quick=quick))


# =====================================================================
# 정형 매크로 / 공시 / insider — economy/stock base inline 정형 우선 도구
# =====================================================================

@mcp.tool
def get_macro_indicators_us(series_ids: list[str] | None = None) -> dict:
    """FRED 미국 매크로 시계열 한 번에 조회 (economy-inline US 차원).

    series_ids 미지정 시 default 10종: DFF/CPIAUCSL/VIXCLS/T10Y3M/GDP/UNRATE/DGS10/DGS2/DGS3MO/SP500.

    반환: {series_id: {최신값, 날짜, YoY변화}} (raw pd.Series 는 응답에서 제외).
    """
    from server.scrapers import fred
    raw = fred.fetch_macro_indicators(series_ids)
    out: dict = {}
    for sid, payload in raw.items():
        if "error" in payload:
            out[sid] = {"error": payload["error"]}
            continue
        out[sid] = {
            "최신값": payload.get("최신값"),
            "날짜": payload.get("날짜"),
            "YoY변화": payload.get("YoY변화"),
        }
    return _json_safe(out)


@mcp.tool
def get_macro_indicators_kr(stat_codes: list[str] | None = None) -> dict:
    """한국은행 ECOS — KR 매크로 시계열 한 번에 조회 (economy-inline KR 차원).

    stat_codes 미지정 시 default 8종: 기준금리(722Y001) / CPI(901Y009) / 원달러환율(731Y004) /
    M2(101Y004) / 경상수지(301Y013) / 산업생산(901Y033) / 실업률(901Y027) / 외환보유고(732Y001).

    반환: {stat_code: {이름, 최신값, 단위, 날짜, YoY변화, cycle, 출처: "ECOS"}}.
    """
    from server.scrapers import ecos
    return _json_safe(ecos.fetch_kr_macro_indicators(stat_codes))


@mcp.tool
def get_yield_curve() -> dict:
    """UST 수익률 곡선 스냅샷 (3M/2Y/5Y/10Y/30Y + 10Y_3M_spread + 역전여부).

    economy-inline US 차원의 yield curve 섹션 정형 데이터 소스.
    """
    from server.scrapers import fred
    return _json_safe(fred.fetch_yield_curve())


@mcp.tool
def get_fx_rate(pair: str = "DEXKOUS", date: str | None = None) -> dict:
    """FRED 환율 조회. 기본 DEXKOUS = KRW per USD.

    1일 TTL 캐시. economy-inline 환율 차원 정형 소스.
    """
    from server.scrapers import fred
    return _json_safe(fred.fetch_fx_rate(pair=pair, date=date))


@mcp.tool
def get_economic_calendar(
    start: str | None = None,
    end: str | None = None,
    country: str = "US",
) -> list[dict]:
    """Finnhub 경제 캘린더 (이벤트 + 컨센서스 + 실제값).

    start/end 미지정 시 오늘부터 14일치. country 기본 "US".
    economy-inline 의 경제 이벤트 차원 + daily 매크로 권장 검색의 정형 대체.

    반환 row 컬럼: 시각/국가/이벤트/중요도(1~3)/예측/실제/이전.
    """
    from server.scrapers import finnhub as fh
    df = fh.fetch_economic_calendar(start=start, end=end, country=country)
    if df is None or df.empty:
        return []
    return _json_safe(df.to_dict(orient="records"))


@mcp.tool
def compute_industry_metrics(industry_code: str) -> dict:
    """산업 메트릭 자동 산출 (industry-base v6 메트릭 자동화).

    industries.leader_followers.leaders 종목들에 compute_financials + 30일 RV 돌려서
    avg_per / avg_pbr / avg_roe / avg_op_margin / vol_baseline_30d 평균 산출.
    industry-inline 절차에서 LLM 이 수동 산출하던 작업의 정형 MCP 대체.

    반환: {industry_code, name, market, leaders[], avg_per/pbr/roe/op_margin, vol_baseline_30d, computed_at, errors}.
    """
    from server.analysis.industry_metrics import compute_industry_metrics as _impl
    return _json_safe(_impl(industry_code))


@mcp.tool
def get_kr_disclosures(code: str, days: int = 14) -> list[dict]:
    """DART 최근 N일 공시 목록 (KR).

    stock-base 딜레이더 #1(M&A)/#2(관계사)/#5(주주행동주의)/#6(대주주변동) 정형 1차 소스.
    per-stock-analysis 4단계 disclosures 카테고리의 KR 분기.

    반환 row 컬럼: 날짜/공시유형/제목/URL.
    """
    df = dart.fetch_disclosures(code, days=days)
    if df is None or df.empty:
        return []
    return _json_safe(df.to_dict(orient="records"))


@mcp.tool
def get_us_disclosures(ticker: str, days: int = 14) -> list[dict]:
    """SEC EDGAR 최근 N일 공시 목록 (US).

    8-K (M&A·경영진 변동·가이던스) / 10-K·Q / Form 4 (insider) / 13D·G (대량보유) 등.
    stock-base 딜레이더 정형 1차 소스. per-stock-analysis 4단계 disclosures US 분기.

    반환 row 컬럼: 날짜/공시유형/제목/URL.
    """
    from server.scrapers import edgar
    df = edgar.fetch_disclosures(ticker, days=days)
    if df is None or df.empty:
        return []
    return _json_safe(df.to_dict(orient="records"))


@mcp.tool
def get_kr_insider_trades(code: str) -> list[dict]:
    """DART 임원·주요주주 특정증권등 소유상황보고 (KR insider).

    stock-base 딜레이더 #6(대주주변동) 정형 소스. per-stock-analysis insider_trades KR 분기.
    raw 행 그대로 반환 — DART 응답 컬럼 보존.
    """
    df = dart.fetch_major_shareholders_exec(code)
    if df is None or df.empty:
        return []
    return _json_safe(df.to_dict(orient="records"))


@mcp.tool
def get_kr_major_shareholders(code: str) -> list[dict]:
    """DART 대주주 현황 (KR).

    stock-base 딜레이더 #6 보조 소스. 임원 거래(get_kr_insider_trades)와 함께 사용.
    """
    df = dart.fetch_major_shareholders(code)
    if df is None or df.empty:
        return []
    return _json_safe(df.to_dict(orient="records"))


@mcp.tool
def get_us_insider_trades(ticker: str, days: int = 90) -> list[dict]:
    """Finnhub 내부자 매매 (US insider, 본문 파싱 OK).

    stock-base 딜레이더 #5(주주행동주의)/#6(대주주변동) 정형 소스. EDGAR Form 4 stub 보다 본문 파싱 완료.
    per-stock-analysis insider_trades US 분기.

    반환 row 컬럼: 날짜/인물/유형(매수·매도·기타)/주식수/가격/총액/사유.
    """
    from server.scrapers import finnhub as fh
    df = fh.fetch_insider_trading(ticker, days=days)
    if df is None or df.empty:
        return []
    return _json_safe(df.to_dict(orient="records"))


# =====================================================================
# 엔트리포인트
# =====================================================================

def main() -> None:
    open_pool()
    if settings.mcp_remote_enabled:
        # 원격 배포 — streamable-http + Google OAuth 활성화 (인스턴스 생성 시 적용됨)
        mcp.run(
            transport="http",
            host=settings.mcp_host,
            port=settings.mcp_port,
        )
    else:
        # 로컬 — stdio (Claude Code 가 자식 프로세스로 spawn)
        mcp.run()


if __name__ == "__main__":
    main()
