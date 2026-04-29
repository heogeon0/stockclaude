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

mcp: FastMCP = FastMCP("stock-manager")


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
    uid = settings.default_user_id
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
    uid = settings.default_user_id
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
    uid = settings.default_user_id
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
    uid = settings.default_user_id
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
    uid = settings.default_user_id
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
    uid = settings.default_user_id
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
    uid = settings.default_user_id

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
def save_daily_report(code: str, date: str, verdict: str, content: str) -> dict:
    """
    일일 분석 보고서 저장. date = 'YYYY-MM-DD'.
    signals JSONB 는 compute_signals 결과를 Claude 가 먼저 확인 후 별도 upsert_signals로.
    """
    from datetime import date as date_cls

    uid = settings.default_user_id
    d = date_cls.fromisoformat(date)
    stock_daily.upsert_content(uid, code, d, content)
    return {"ok": True, "code": code, "date": date, "chars": len(content)}


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

    uid = settings.default_user_id
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

    uid = settings.default_user_id
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

    uid = settings.default_user_id
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
    uid = settings.default_user_id
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
    uid = settings.default_user_id
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
            if market == "kr":
                df = _fetch_ohlcv(code, days=max(days, 20))
            else:
                df = kis.fetch_us_daily(code, days=days)
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
    uid = settings.default_user_id
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
        uid = settings.default_user_id
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
) -> dict:
    """
    economy_base 테이블에 upsert. None 필드는 기존 값 유지 (COALESCE).

    Daily append 패턴:
      1. get via get_economy_base(market) 또는 get_stock_context 유사
      2. content 에 "## 📝 Daily Appended Facts" 섹션 append
      3. save_economy_base(market, content=new_content)

    Research 재작성:
      - 전체 content 덮어쓰기
    """
    from server.repos import economy
    economy.upsert_base(market=market, context=context, content=content)
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
) -> dict:
    """
    industries 테이블에 upsert. None 필드는 기존 값 유지 (COALESCE).

    Daily append 패턴:
      1. get via get_industry(code) 로 현재 content 로드
      2. "## 📝 Daily Appended Facts" 섹션에 append
      3. save_industry(code, name, content=new_content)

    Research 재작성:
      - 전체 content 덮어쓰기
    """
    from server.repos import industries
    industries.upsert(
        code=code, market=market, name=name,
        name_en=name_en, parent_code=parent_code,
        meta=meta, market_specific=market_specific,
        score=score, content=content,
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
) -> dict:
    """
    주간 회고 저장 (upsert).

    week_start: 'YYYY-MM-DD' 월요일 (KST)
    week_end:   'YYYY-MM-DD' 금요일 (KST)

    - win_rate: {strategy_name: {tries, wins, pct}}
    - rule_evaluations: [{rule, trade_id, foregone_pnl, smart_or_early, ...}]
    - highlights: [{type: 'insight'|'pattern'|'warning', detail}]
    - next_week_actions: portfolio_summary.action_plan 과 동일 스키마

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
    uid = settings.default_user_id
    if codes is None:
        active = positions.list_active(uid)
        codes = [p["code"] for p in active if p.get("market") == market]

    if not codes:
        return []

    from server.analysis.indicators import compute_all as _compute_all

    rows = []
    for code in codes:
        try:
            if market == "kr":
                df = _fetch_ohlcv(code, days=max(lookback_days, 20))
            else:
                df = kis.fetch_us_daily(code, days=lookback_days)
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
    uid = settings.default_user_id

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
        scope = positions.list_daily_scope(settings.default_user_id)
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
        scope = positions.list_daily_scope(settings.default_user_id)
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
def check_base_freshness(auto_refresh: bool = False) -> dict:
    """
    Active + Pending 포지션 종목의 base 만기 일괄 판정. LLM이 자연어 비교로 누락하지 않도록
    `is_stale: bool` + `auto_triggers: list[str]` 강제 반환.

    인자:
      auto_refresh: True 시 stale 한 stock_base 를 즉시 refresh_stock_base() 자동 실행.
                    economy / industry 는 텍스트 작성 필요 → auto_triggers 만 반환 (수동 skill 호출).

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
    """
    from datetime import date as _date

    uid = settings.default_user_id
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

    # 1) economy bases
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

    # 2) Daily-scope positions (Active + Pending) → stocks + industries
    scope = positions.list_daily_scope(uid)
    seen_inds: set[str] = set()

    for p in scope:
        code = p["code"]
        name = p.get("name") or code

        sb = stock_base.get_base(code)
        if not sb:
            out["stocks"].append({
                "code": code, "name": name, "age_days": None,
                "expiry_days": EXP_STOCK,
                "is_stale": True, "missing": True,
                "trigger": f"/base-stock {name}",
            })
        else:
            age = _age(sb.get("updated_at"))
            is_stale = (age is None) or age >= EXP_STOCK
            out["stocks"].append({
                "code": code, "name": name, "age_days": age,
                "expiry_days": EXP_STOCK,
                "is_stale": is_stale, "missing": False,
                "trigger": f"/base-stock {name}" if is_stale else None,
            })

        s_row = stocks.get_stock(code)
        ind_code = s_row.get("industry_code") if s_row else None
        if not ind_code or ind_code in seen_inds:
            continue
        seen_inds.add(ind_code)

        ib = industries.get_industry(ind_code)
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


# 변동성×재무 12셀 매트릭스 (~/.claude/skills/stock/references/scoring-weights.md)
_CELL_MATRIX: dict[tuple[str, str], dict] = {
    ("A", "normal"):  {"size": "풀",   "pyramiding": 3, "stop_pct": -10, "stop_method": "%"},
    ("A", "high"):    {"size": "풀",   "pyramiding": 2, "stop_pct":  -8, "stop_method": "%"},
    ("A", "extreme"): {"size": "70%",  "pyramiding": 1, "stop_pct":  -6, "stop_method": "ATR×2"},
    ("B", "normal"):  {"size": "풀",   "pyramiding": 2, "stop_pct":  -8, "stop_method": "%"},
    ("B", "high"):    {"size": "70%",  "pyramiding": 1, "stop_pct":  -7, "stop_method": "%"},
    ("B", "extreme"): {"size": "50%",  "pyramiding": 0, "stop_pct":  -5, "stop_method": "ATR×1.5"},
    ("C", "normal"):  {"size": "70%",  "pyramiding": 1, "stop_pct":  -7, "stop_method": "%"},
    ("C", "high"):    {"size": "50%",  "pyramiding": 1, "stop_pct":  -6, "stop_method": "%"},
    ("C", "extreme"): {"size": "30%",  "pyramiding": 0, "stop_pct":  -5, "stop_method": "ATR×1"},
    ("D", "normal"):  {"size": "50%",  "pyramiding": 0, "stop_pct":  -6, "stop_method": "%"},
    ("D", "high"):    {"size": "30%",  "pyramiding": 0, "stop_pct":  -5, "stop_method": "%"},
    ("D", "extreme"): {"size": "비추",  "pyramiding": 0, "stop_pct":  -5, "stop_method": "비추"},
}


def _derive_cell(financial_score: int | None, vol_regime: str | None) -> dict | None:
    """변동성×재무 12셀 룩업 (deterministic)."""
    if financial_score is None or vol_regime is None:
        return None
    if financial_score >= 80:
        fin_tier = "A"
    elif financial_score >= 60:
        fin_tier = "B"
    elif financial_score >= 40:
        fin_tier = "C"
    else:
        fin_tier = "D"
    vol_tier = vol_regime if vol_regime in ("normal", "high", "extreme") else "high"
    cell = dict(_CELL_MATRIX.get((fin_tier, vol_tier), {}))
    cell["fin_tier"] = fin_tier
    cell["vol_tier"] = vol_tier
    cell["financial_score"] = financial_score
    return cell


@mcp.tool
def analyze_position(code: str) -> dict:
    """
    종목별 16카테고리 분석 일괄 묶음 — LLM이 부분 스킵 못하도록 1회 호출에 강제 포함.

    포함 카테고리 (10개 종목 단위 + 6개 포트 단위는 별도):
      1. context        — get_stock_context (base + position + watch + daily)
      2. realtime       — KIS/Naver 자동 분기 현재가
      3. indicators     — compute_indicators 12지표
      4. signals        — compute_signals 12전략 + chart_analysis (VCP/SEPA)
      5. financials     — compute_financials (KR DART)
      6. flow           — analyze_flow (KR 기관/외인 z-score)
      7. volatility     — analyze_volatility (regime/DD)
      8. events         — detect_events (52w/실적/등급)
      9. scoring        — compute_score breakdown
      10. consensus     — get_analyst_consensus + analyze_consensus_trend + reports

    포트 단위 (별도 호출): regime, correlation, concentration, weekly_context, momentum, sensitivity.

    반환:
      {
        "code","name","market",
        "context":{...}, "realtime":{...}, "indicators":{...}, "signals":{...},
        "financials":{...}, "flow":{...}, "volatility":{...}, "events":{...},
        "scoring":{...}, "consensus":{...},
        "errors": {category: error_msg, ...},
        "categories_succeeded": N, "categories_total": 10,
        "coverage_pct": float,
      }
    """
    s_row = stocks.get_stock(code)
    if not s_row:
        return {"error": f"stock not found: {code}"}

    uid = settings.default_user_id
    market = s_row.get("market", "kr")
    name = s_row.get("name")

    bundle: dict = {"code": code, "name": name, "market": market, "errors": {}}
    success = 0
    total = 10

    def _ohlcv() -> pd.DataFrame:
        if market == "kr":
            return _fetch_ohlcv(code, days=400)
        return kis.fetch_us_daily(code, days=400)

    # 1) context
    try:
        bundle["context"] = {
            "stock": _row_safe(s_row),
            "base": _row_safe(stock_base.get_base(code)),
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
        score = compute_financial_score(ratios, growth)
        bundle["financials"] = {
            "code": code, "market": market,
            "ratios": ratios, "growth": growth, "score": score,
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

    # 9) scoring (compute_score 위임 — 인라인 호출)
    try:
        sb = stock_base.get_base(code)
        if not sb:
            bundle["scoring"] = {"error": "stock_base not found"}
            bundle["errors"]["scoring"] = "stock_base not found"
        else:
            ind = industries.get_industry(s_row.get("industry_code")) if s_row.get("industry_code") else None
            applied = score_weights.get_applied(code, "swing")
            bundle["scoring"] = {
                "code": code,
                "timeframe": "swing",
                "total_score": sb.get("total_score"),
                "grade": sb.get("grade"),
                "breakdown": {
                    "financial": sb.get("financial_score"),
                    "industry": (ind.get("score") if ind else None) or sb.get("industry_score"),
                    "economy": sb.get("economy_score"),
                },
                "weights": applied,
            }
            success += 1
    except Exception as e:
        bundle["errors"]["scoring"] = str(e)

    # 10) consensus
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

    # 11) Auto-derive: cell (변동성×재무 12셀, deterministic)
    # 우선순위: stock_base.financial_score (research 기반, 신뢰도↑)
    #          → compute_financials.score (default 50, 데이터 부족 시 fallback)
    try:
        sb = stock_base.get_base(code)
        fin_score = sb.get("financial_score") if sb else None
        if fin_score is None and isinstance(bundle.get("financials"), dict):
            fin_score = bundle["financials"].get("score")
        vol_regime = None
        if isinstance(bundle.get("volatility"), dict):
            vol_regime = bundle["volatility"].get("regime")
        bundle["cell"] = _derive_cell(fin_score, vol_regime)
    except Exception as e:
        bundle["cell"] = None
        bundle["errors"]["cell"] = str(e)

    # 12) Auto-derive: is_stale per-dim (economy/industry/stock)
    try:
        from datetime import date as _date_cls
        today = _date_cls.today()

        def _stale(updated_at, expiry: int) -> bool:
            if not updated_at:
                return True
            try:
                return (today - updated_at.date()).days >= expiry
            except Exception:
                return True

        sb_row = stock_base.get_base(code)
        ind_code = s_row.get("industry_code")
        ind_row = industries.get_industry(ind_code) if ind_code else None
        econ_row = economy.get_base("kr" if market == "kr" else "us")

        bundle["is_stale"] = {
            "stock": _stale(sb_row.get("updated_at") if sb_row else None, 30),
            "industry": _stale(ind_row.get("updated_at") if ind_row else None, 7) if ind_code else None,
            "economy": _stale(econ_row.get("updated_at") if econ_row else None, 1),
        }
    except Exception as e:
        bundle["errors"]["is_stale"] = str(e)
        bundle["is_stale"] = None

    # 13) Coverage 임계값 경고 (<80% 시 ⚠️)
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
# 엔트리포인트
# =====================================================================

def main() -> None:
    open_pool()
    mcp.run()


if __name__ == "__main__":
    main()
