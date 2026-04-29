"""
FRED (Federal Reserve Economic Data) 기반 매크로 어댑터.

스펙: scrapers/adapter_spec.md 3.1~3.3.

- 무료. https://fredaccount.stlouisfed.org/apikeys 즉시 발급.
- 주요 시계열: DFF(Fed funds), CPIAUCSL(CPI), VIXCLS(VIX), T10Y3M(yield curve spread),
  GDP, UNRATE(실업률), DGS10/DGS2/DGS3MO(UST yields), SP500, DEXKOUS(KRW/USD).
"""
from __future__ import annotations

import os
import ssl
import time
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import urllib3

# SSL 우회 (corporate proxy 환경용) — fredapi 내부 requests 포함
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


_CLIENT_CACHE: Any = None
_FX_CACHE: dict[str, tuple[float, dict]] = {}  # pair -> (fetched_at_ts, data)
_FX_TTL = 86400  # 1일


DEFAULT_SERIES = [
    "DFF",       # Federal Funds Rate
    "CPIAUCSL",  # CPI
    "VIXCLS",    # VIX
    "T10Y3M",    # 10Y-3M spread (inversion 지표)
    "GDP",       # 명목 GDP
    "UNRATE",    # 실업률
    "DGS10",     # 10Y UST
    "DGS2",      # 2Y UST
    "DGS3MO",    # 3M UST
    "SP500",     # S&P 500 지수
]


def _client():
    global _CLIENT_CACHE
    if _CLIENT_CACHE is not None:
        return _CLIENT_CACHE
    try:
        from fredapi import Fred
    except ImportError:
        raise RuntimeError("fredapi 미설치. pip install fredapi")
    from server.config import settings
    key = settings.fred_api_key
    if not key or key.startswith("your_"):
        raise RuntimeError(
            "FRED_API_KEY 미설정. .env 확인 "
            "(https://fredaccount.stlouisfed.org/apikeys 무료)"
        )
    _CLIENT_CACHE = Fred(api_key=key)
    return _CLIENT_CACHE


def fetch_macro_indicators(series_ids: list[str] | None = None) -> dict:
    """
    FRED 주요 시계열 한 번에 조회.
    반환: {series_id: {"최신값": float, "날짜": Timestamp, "YoY변화": float | None, "series": pd.Series}}
    """
    if series_ids is None:
        series_ids = DEFAULT_SERIES
    fred = _client()
    result = {}
    for sid in series_ids:
        try:
            s = fred.get_series(sid, observation_start=(datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d"))
        except Exception as e:
            result[sid] = {"error": str(e)}
            continue
        s = s.dropna()
        if s.empty:
            result[sid] = {"error": "no data"}
            continue
        latest_val = float(s.iloc[-1])
        latest_dt = s.index[-1]
        # YoY
        yoy = None
        year_ago = latest_dt - pd.DateOffset(years=1)
        prior = s[s.index <= year_ago]
        if not prior.empty:
            prev_val = float(prior.iloc[-1])
            if prev_val != 0:
                yoy = round((latest_val - prev_val) / abs(prev_val) * 100, 2)
        result[sid] = {
            "최신값": latest_val,
            "날짜": latest_dt,
            "YoY변화": yoy,
            "series": s,
        }
    return result


def fetch_fx_rate(pair: str = "DEXKOUS", date: str | None = None) -> dict:
    """
    환율 조회. 기본 DEXKOUS = KRW per USD (FRED).
    1일 TTL 캐시.
    """
    cache_key = f"{pair}:{date or 'latest'}"
    now = time.time()
    if cache_key in _FX_CACHE:
        cached_at, data = _FX_CACHE[cache_key]
        if now - cached_at < _FX_TTL:
            return data

    fred = _client()
    s = fred.get_series(pair, observation_start=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    s = s.dropna()
    if s.empty:
        result = {"pair": pair, "환율": None, "기준일": None, "source": "FRED", "error": "no data"}
    else:
        if date:
            s = s[s.index <= pd.Timestamp(date)]
        if s.empty:
            result = {"pair": pair, "환율": None, "기준일": None, "source": "FRED"}
        else:
            result = {
                "pair": pair,
                "환율": float(s.iloc[-1]),
                "기준일": s.index[-1].strftime("%Y-%m-%d"),
                "source": "FRED",
            }
    _FX_CACHE[cache_key] = (now, result)
    return result


def fetch_yield_curve() -> dict:
    """UST 수익률 곡선 스냅샷."""
    fred = _client()
    tenors = {"3M": "DGS3MO", "2Y": "DGS2", "5Y": "DGS5", "10Y": "DGS10", "30Y": "DGS30"}
    values = {}
    latest_dt = None
    for label, sid in tenors.items():
        try:
            s = fred.get_series(sid, observation_start=(datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"))
            s = s.dropna()
            if not s.empty:
                values[label] = float(s.iloc[-1])
                if latest_dt is None or s.index[-1] > latest_dt:
                    latest_dt = s.index[-1]
        except Exception:
            values[label] = None
    spread = None
    inversion = False
    if values.get("10Y") is not None and values.get("3M") is not None:
        spread = round(values["10Y"] - values["3M"], 2)
        inversion = spread < 0
    return {
        "기준일": latest_dt.strftime("%Y-%m-%d") if latest_dt is not None else None,
        **values,
        "10Y_3M_spread": spread,
        "역전여부": inversion,
    }


if __name__ == "__main__":
    import sys
    try:
        print("== 환율 DEXKOUS ==")
        print(fetch_fx_rate())
        print("== Yield curve ==")
        print(fetch_yield_curve())
    except RuntimeError as e:
        print(f"smoke test skipped: {e}", file=sys.stderr)
