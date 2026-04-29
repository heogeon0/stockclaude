"""
Finnhub 기반 US 주식 어댑터 (60 req/min 무료 티어).

스펙: scrapers/adapter_spec.md (1.1~1.3, 1.6~1.11, 2.1, 2.3, 2.4).

주의:
- Finnhub 무료 티어는 `/stock/candle` (히스토리 OHLCV)을 premium으로 이관함(2024~).
  → 실시간 `/quote`, 펀더멘털, 컨센서스, 캘린더, 13F, insider는 무료 유지.
  → 일봉 OHLCV는 `yfinance_client.fetch_ohlcv_backup()` 사용 권장.
- 본 클라이언트의 `fetch_ohlcv`는 유료 티어 대응용으로 유지하되 402/403 수신 시 None 반환.
"""
from __future__ import annotations

import os
import ssl
import time
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import urllib3
import requests

# macOS + Python 3.14 + corporate proxy 환경 SSL 인증서 체인 충돌 우회.
# regime.py / market_data.py와 동일 패치.
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_orig_request = requests.Session.request
def _patched_request(self, *args, **kwargs):
    kwargs.setdefault('verify', False)
    return _orig_request(self, *args, **kwargs)
requests.Session.request = _patched_request

try:
    import finnhub
except ImportError:
    finnhub = None


_CLIENT_CACHE: Any = None
_LAST_CALL: float = 0.0
_MIN_INTERVAL = 1.05  # 60 req/min = 1초 slot, 여유 0.05초


def _client():
    """Finnhub 클라이언트 싱글톤. API 키 없으면 RuntimeError."""
    global _CLIENT_CACHE
    if _CLIENT_CACHE is not None:
        return _CLIENT_CACHE
    if finnhub is None:
        raise RuntimeError("finnhub-python 미설치. pip install finnhub-python")
    from server.config import settings
    key = settings.finnhub_api_key
    if not key or key.startswith("your_"):
        raise RuntimeError("FINNHUB_API_KEY 미설정. .env 확인 (https://finnhub.io/register 무료)")
    _CLIENT_CACHE = finnhub.Client(api_key=key)
    return _CLIENT_CACHE


def _throttle():
    global _LAST_CALL
    elapsed = time.time() - _LAST_CALL
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _LAST_CALL = time.time()


def _safe_call(func, *args, **kwargs):
    """Rate limit 대응 + 429 backoff. 402/403 (유료 필요)은 None."""
    for attempt in range(3):
        _throttle()
        try:
            return func(*args, **kwargs)
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "rate" in msg:
                time.sleep(2 ** attempt)
                continue
            if "402" in msg or "403" in msg or "premium" in msg:
                return None
            raise
    return None


def fetch_ohlcv(ticker: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """
    일봉 OHLCV. 무료 티어에서 premium으로 이관돼 402/403 가능 → yfinance fallback 권장.
    """
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    if start is None:
        start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    start_ts = int(pd.Timestamp(start).timestamp())
    end_ts = int(pd.Timestamp(end).timestamp())
    c = _client()
    res = _safe_call(c.stock_candles, ticker, "D", start_ts, end_ts)
    if not res or res.get("s") != "ok":
        return pd.DataFrame()
    df = pd.DataFrame({
        "날짜": pd.to_datetime(res["t"], unit="s"),
        "시가": res["o"],
        "고가": res["h"],
        "저가": res["l"],
        "종가": res["c"],
        "거래량": res["v"],
    }).sort_values("날짜").reset_index(drop=True)
    df.attrs["ticker"] = ticker
    df.attrs["market"] = "us"
    df.attrs["통화"] = "USD"
    df.attrs["tz"] = "America/New_York"
    return df


def fetch_intraday(ticker: str, interval: str = "1", pages: int = 1) -> pd.DataFrame:
    """분봉 OHLCV. interval은 Finnhub resolution('1','5','15','30','60')."""
    end_ts = int(time.time())
    # pages 인자는 KR 호환용. US는 대략 pages*1일 범위로 매핑 (Finnhub 무료는 최근 수일만 허용)
    days_back = max(pages, 1)
    start_ts = end_ts - days_back * 86400
    c = _client()
    res = _safe_call(c.stock_candles, ticker, interval, start_ts, end_ts)
    if not res or res.get("s") != "ok":
        return pd.DataFrame()
    df = pd.DataFrame({
        "시각": pd.to_datetime(res["t"], unit="s", utc=True),
        "시가": res["o"],
        "고가": res["h"],
        "저가": res["l"],
        "종가": res["c"],
        "거래량": res["v"],
    }).sort_values("시각").reset_index(drop=True)
    df.attrs["ticker"] = ticker
    df.attrs["market"] = "us"
    df.attrs["통화"] = "USD"
    return df


def fetch_fundamentals(ticker: str) -> dict:
    """펀더멘털 스냅샷 (/stock/profile2 + /stock/metric)."""
    c = _client()
    profile = _safe_call(c.company_profile2, symbol=ticker) or {}
    metric = _safe_call(c.company_basic_financials, ticker, "all") or {}
    m = metric.get("metric", {}) if isinstance(metric, dict) else {}

    market_cap_m = profile.get("marketCapitalization")  # millions USD
    result = {
        "통화": "USD",
        "시가총액": int(market_cap_m * 1_000_000) if market_cap_m else None,
        "시가총액_M": int(market_cap_m) if market_cap_m else None,
        "시가총액_억": None,
        "PER": m.get("peNormalizedAnnual") or m.get("peInclExtraTTM"),
        "PBR": m.get("pbAnnual") or m.get("pbQuarterly"),
        "EPS": m.get("epsInclExtraItemsAnnual") or m.get("epsAnnual"),
        "BPS": m.get("bookValuePerShareAnnual"),
        "배당수익률": m.get("dividendYieldIndicatedAnnual"),
        "업종": profile.get("finnhubIndustry"),
        "섹터_GICS": profile.get("gsubind"),
        "52주최고": m.get("52WeekHigh"),
        "52주최저": m.get("52WeekLow"),
        "상장주식수": int(profile["shareOutstanding"] * 1_000_000) if profile.get("shareOutstanding") else None,
        "외국인소진율": None,  # US N/A
    }
    return result


def fetch_consensus(ticker: str) -> dict:
    """애널리스트 컨센서스 (/stock/recommendation + /stock/price-target)."""
    c = _client()
    recs = _safe_call(c.recommendation_trends, ticker) or []
    target = _safe_call(c.price_target, ticker) or {}

    # 최근 3개월 투자의견 집계
    cutoff = (datetime.now() - timedelta(days=90))
    recent_recs = [
        r for r in recs
        if r.get("period") and pd.Timestamp(r["period"]) >= cutoff
    ]
    dist = {"Buy": 0, "Hold": 0, "Sell": 0, "기타": 0}
    for r in recent_recs:
        dist["Buy"] += r.get("strongBuy", 0) + r.get("buy", 0)
        dist["Hold"] += r.get("hold", 0)
        dist["Sell"] += r.get("sell", 0) + r.get("strongSell", 0)

    result = {
        "리포트수": sum(dist.values()),
        "전체_리포트수": sum(
            (r.get("strongBuy", 0) + r.get("buy", 0) + r.get("hold", 0)
             + r.get("sell", 0) + r.get("strongSell", 0)) for r in recs
        ),
        "기간": "최근 3개월",
        "목표가_평균": int(target.get("targetMean")) if target.get("targetMean") else None,
        "목표가_중간값": int(target.get("targetMedian")) if target.get("targetMedian") else None,
        "목표가_최고": int(target.get("targetHigh")) if target.get("targetHigh") else None,
        "목표가_최저": int(target.get("targetLow")) if target.get("targetLow") else None,
        "표준편차": None,
        "목표가_분포_폭": (int(target["targetHigh"] - target["targetLow"])
                     if target.get("targetHigh") and target.get("targetLow") else None),
        "투자의견_분포": dist,
        "통화": "USD",
    }
    return result


def fetch_next_earnings_date(ticker: str) -> dict:
    """차기 실적 발표 예정일 (/calendar/earnings)."""
    c = _client()
    today = datetime.now()
    future = (today + timedelta(days=90)).strftime("%Y-%m-%d")
    past = (today - timedelta(days=120)).strftime("%Y-%m-%d")
    cal = _safe_call(c.earnings_calendar, _from=today.strftime("%Y-%m-%d"), to=future, symbol=ticker) or {}
    past_cal = _safe_call(c.earnings_calendar, _from=past, to=today.strftime("%Y-%m-%d"), symbol=ticker) or {}

    upcoming = cal.get("earningsCalendar", []) if isinstance(cal, dict) else []
    historical = past_cal.get("earningsCalendar", []) if isinstance(past_cal, dict) else []

    # Finnhub 응답은 date 내림차순 → 가장 가까운 미래일은 min(date), 가장 최근 과거일은 max(date).
    next_date = min((e["date"] for e in upcoming if e.get("date")), default=None)
    last_date = max((e["date"] for e in historical if e.get("date")), default=None)

    d_remaining = None
    earnings_window = False
    if next_date:
        d_remaining = (pd.Timestamp(next_date) - pd.Timestamp(today.date())).days
        earnings_window = 0 <= d_remaining <= 7

    return {
        "마지막_발표일": last_date,
        "차기_예상일": next_date,
        "D_remaining": d_remaining,
        "earnings_window": earnings_window,
        "근거": f"Finnhub /calendar/earnings (upcoming={len(upcoming)}, historical={len(historical)})",
    }


def fetch_insider_trading(ticker: str, days: int = 90) -> pd.DataFrame:
    """내부자 매매 (/stock/insider-transactions)."""
    c = _client()
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    res = _safe_call(c.stock_insider_transactions, ticker, start, end) or {}
    data = res.get("data", []) if isinstance(res, dict) else []
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    rename = {
        "transactionDate": "날짜",
        "name": "인물",
        "transactionCode": "유형_코드",
        "change": "주식수",
        "transactionPrice": "가격",
    }
    df = df.rename(columns=rename)
    if "날짜" in df.columns:
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df["유형"] = df.get("유형_코드", "").apply(
        lambda c: "매수" if str(c).upper() in ("P", "A") else ("매도" if str(c).upper() in ("S", "D") else "기타")
    ) if "유형_코드" in df.columns else "기타"
    df["총액"] = df.get("가격", 0) * df.get("주식수", 0).abs()
    df["사유"] = df.get("유형_코드")
    return df[[c for c in ["날짜", "인물", "유형", "주식수", "가격", "총액", "사유"] if c in df.columns]]


def fetch_economic_calendar(start: str | None = None, end: str | None = None, country: str = "US") -> pd.DataFrame:
    """경제 캘린더 (/calendar/economic)."""
    c = _client()
    if start is None:
        start = datetime.now().strftime("%Y-%m-%d")
    if end is None:
        end = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    res = _safe_call(c.calendar_economic, _from=start, to=end) or {}
    data = res.get("economicCalendar", []) if isinstance(res, dict) else []
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    if "country" in df.columns:
        df = df[df["country"] == country]
    rename = {
        "time": "시각",
        "country": "국가",
        "event": "이벤트",
        "impact": "중요도",
        "estimate": "예측",
        "actual": "실제",
        "prev": "이전",
    }
    df = df.rename(columns=rename)
    if "시각" in df.columns:
        df["시각"] = pd.to_datetime(df["시각"], utc=True, errors="coerce")
    if "중요도" in df.columns:
        df["중요도"] = df["중요도"].map({"high": 3, "medium": 2, "low": 1}).fillna(1).astype(int)
    return df.reset_index(drop=True)


def fetch_investor_flow_13f(ticker: str, quarters: int = 4) -> pd.DataFrame:
    """기관 보유 (/stock/ownership)."""
    c = _client()
    res = _safe_call(c.ownership, ticker, limit=20) or {}
    data = res.get("ownership", []) if isinstance(res, dict) else []
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    rename = {
        "filingDate": "공시일",
        "name": "기관명",
        "share": "주식수",
        "change": "변화",
        "filingReportDate": "분기말",
    }
    df = df.rename(columns=rename)
    for col in ("공시일", "분기말"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def fetch_short_interest(ticker: str) -> dict:
    """공매도 잔고 (무료 여부 endpoint별 확인 필요)."""
    c = _client()
    res = _safe_call(c.stock_short_interest, ticker) if hasattr(c, "stock_short_interest") else None
    if not res:
        return {"최근_공시일": None, "공매도잔고_주식수": None, "상장주식수_대비_비율": None,
                "Days_to_Cover": None, "이전_공시": [], "통화": "USD",
                "참고": "Finnhub 무료에서 미제공 가능. FINRA 직접 또는 유료 필요."}
    data = res.get("data", []) if isinstance(res, dict) else []
    if not data:
        return {"최근_공시일": None, "공매도잔고_주식수": None, "상장주식수_대비_비율": None,
                "Days_to_Cover": None, "이전_공시": [], "통화": "USD"}
    latest = data[0]
    return {
        "최근_공시일": latest.get("settlementDate"),
        "공매도잔고_주식수": latest.get("shortInterest"),
        "상장주식수_대비_비율": latest.get("shortInterestPercentOfFloat"),
        "Days_to_Cover": latest.get("daysToCover"),
        "이전_공시": data[1:7],
        "통화": "USD",
    }


def fetch_pre_post_market(ticker: str) -> dict:
    """장전/장후 시세 (/quote)."""
    c = _client()
    q = _safe_call(c.quote, ticker) or {}
    return {
        "pre_market": None,  # Finnhub /quote는 regular quote 위주, 확장은 premium
        "regular": {
            "가격": q.get("c"),
            "변동": q.get("d"),
            "변동률": q.get("dp"),
            "고가": q.get("h"),
            "저가": q.get("l"),
            "시가": q.get("o"),
            "전일종가": q.get("pc"),
            "시각": pd.to_datetime(q.get("t"), unit="s", utc=True) if q.get("t") else None,
        } if q else None,
        "post_market": None,
        "통화": "USD",
    }


def fetch_disclosures(ticker: str, days: int = 30) -> pd.DataFrame:
    """SEC filings wrapper (백업). 1차는 edgar_client 사용 권장."""
    c = _client()
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    res = _safe_call(c.filings, symbol=ticker, _from=start, to=end) or []
    if not res:
        return pd.DataFrame()
    df = pd.DataFrame(res)
    rename = {"filedDate": "날짜", "form": "공시유형", "reportUrl": "URL"}
    df = df.rename(columns=rename)
    if "날짜" in df.columns:
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df["제목"] = df.get("공시유형", "")
    return df[[c for c in ["날짜", "공시유형", "제목", "URL"] if c in df.columns]]


if __name__ == "__main__":
    # Smoke test (FINNHUB_API_KEY 필요)
    import sys
    try:
        print("== AAPL pre/post market ==")
        print(fetch_pre_post_market("AAPL"))
        print("== AAPL fundamentals ==")
        print(fetch_fundamentals("AAPL"))
    except RuntimeError as e:
        print(f"smoke test skipped: {e}", file=sys.stderr)
