"""
일일 스냅샷 배치.

Active 종목 순회하며:
  1. OHLCV 수집 (KIS 우선 → Naver fallback)
  2. compute_all (12 지표)
  3. analyze_all (12 시그널) + summarize (verdict)
  4. stock_daily 에 upsert

실행:
  uv run python -m server.jobs.daily_snapshot
옵션:
  --codes 000660,005930  # 특정 종목만
  --days 400             # 과거 OHLCV 길이
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd

from server.analysis.indicators import compute_all
from server.analysis.signals import analyze_all, summarize


def _sanitize(obj):
    """numpy/pandas 타입 → Python 기본 타입 (JSON-serializable)."""
    if obj is None:
        return None
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return None if np.isnan(v) else v
    if isinstance(obj, float) and np.isnan(obj):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if hasattr(obj, "item"):  # numpy 스칼라 일반
        try:
            return _sanitize(obj.item())
        except (ValueError, TypeError):
            pass
    return obj
from server.config import settings
from server.db import open_pool
from server.repos import positions, stock_daily, stocks
from server.scrapers import kis, naver


def _fetch_kr_ohlcv(code: str, days: int) -> pd.DataFrame:
    """KIS 우선, 실패/부족 시 Naver."""
    try:
        df = kis.fetch_daily_ohlcv(code, days=min(days, 100))
        if df is not None and not df.empty and len(df) >= 60:
            return df
    except Exception as e:
        print(f"  [kis fail] {code}: {e}")
    # Naver fallback (페이지당 10행)
    pages = max(days // 10, 1)
    return naver.fetch_daily(code, pages=pages).sort_values("날짜").reset_index(drop=True)


def _fetch_us_ohlcv(ticker: str, days: int) -> pd.DataFrame:
    """US는 KIS 해외API 사용."""
    try:
        return kis.fetch_us_daily(ticker, days=min(days, 100))
    except Exception as e:
        print(f"  [kis us fail] {ticker}: {e}")
        return pd.DataFrame()


def _to_int_or_none(v) -> int | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _to_num_or_none(v) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _save_latest_bar(user_id, code: str, df: pd.DataFrame) -> date | None:
    """최종 봉의 OHLCV + 지표 + 시그널 저장."""
    if df.empty:
        return None
    df_ind = compute_all(df)
    last = df_ind.iloc[-1]
    last_date = last["날짜"].date() if hasattr(last["날짜"], "date") else last["날짜"]

    # OHLCV upsert
    stock_daily.upsert_ohlcv(
        user_id=user_id, code=code, date=last_date,
        open_=_to_num_or_none(last["시가"]) or 0,
        high=_to_num_or_none(last["고가"]) or 0,
        low=_to_num_or_none(last["저가"]) or 0,
        close=_to_num_or_none(last["종가"]) or 0,
        volume=_to_int_or_none(last["거래량"]) or 0,
    )

    # 지표 매핑 (pandas col name → DB col name)
    ind_map = {
        "rsi14":       _to_num_or_none(last.get("RSI14")),
        "stoch_k":     _to_num_or_none(last.get("Stoch_K")),
        "stoch_d":     _to_num_or_none(last.get("Stoch_D")),
        "adx":         _to_num_or_none(last.get("ADX14")),
        "atr14":       _to_num_or_none(last.get("ATR14")),
        "macd":        _to_num_or_none(last.get("MACD")),
        "macd_signal": _to_num_or_none(last.get("MACD시그널")),
        "macd_hist":   _to_num_or_none(last.get("MACD히스토")),
        "bb_upper":    _to_num_or_none(last.get("볼린저_상단")),
        "bb_middle":   _to_num_or_none(last.get("볼린저_중심")),
        "bb_lower":    _to_num_or_none(last.get("볼린저_하단")),
        "sma5":        _to_num_or_none(last.get("SMA5")),
        "sma20":       _to_num_or_none(last.get("SMA20")),
        "sma60":       _to_num_or_none(last.get("SMA60")),
        "sma120":      _to_num_or_none(last.get("SMA120")),
        "sma200":      _to_num_or_none(last.get("SMA200")),
    }
    ichimoku = {
        "conv":   _to_num_or_none(last.get("전환선")),
        "base":   _to_num_or_none(last.get("기준선")),
        "span_a": _to_num_or_none(last.get("선행스팬A")),
        "span_b": _to_num_or_none(last.get("선행스팬B")),
    }
    stock_daily.upsert_indicators(user_id, code, last_date, ind_map, ichimoku)

    # 시그널 평가
    sigs = analyze_all(df_ind)
    verdict = summarize(sigs).get("종합")
    stock_daily.upsert_signals(user_id, code, last_date, _sanitize(sigs), verdict)

    return last_date


def run(codes: list[str] | None = None, days: int = 400) -> dict:
    uid = settings.stock_user_id
    if codes is None:
        active = positions.list_active(uid)
        codes = [p["code"] for p in active]

    results = {"ok": [], "fail": []}
    for code in codes:
        stock = stocks.get_stock(code)
        if not stock:
            print(f"[skip] {code} not in stocks")
            continue
        market = stock["market"]
        try:
            df = _fetch_kr_ohlcv(code, days) if market == "kr" else _fetch_us_ohlcv(code, days)
            if df.empty:
                print(f"[fail] {code} no data")
                results["fail"].append(code)
                continue
            d = _save_latest_bar(uid, code, df)
            print(f"[ok]   {code:6} {market} rows={len(df):3} last_date={d}")
            results["ok"].append(code)
        except Exception as e:
            print(f"[fail] {code}: {e}")
            results["fail"].append(code)
    return results


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--codes", help="comma-separated code list")
    p.add_argument("--days", type=int, default=400)
    args = p.parse_args()

    open_pool()
    codes = args.codes.split(",") if args.codes else None
    r = run(codes=codes, days=args.days)
    print(f"\n== summary == ok={len(r['ok'])} fail={len(r['fail'])}")
    if r["fail"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
