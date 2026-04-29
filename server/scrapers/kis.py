"""
한국투자증권 Open API — READ-ONLY 시세·공시·펀더멘털.

⚠️ 이 모듈은 READ-ONLY 입니다. 매매 주문·취소·계좌 조회는 절대 구현하지 않습니다.
   유저가 증권사 앱에서 직접 매매하고, 기록은 record_trade 툴로 수동.

스펙: https://apiportal.koreainvestment.com
인증: OAuth2 (access token 24h 유효, 파일 캐시)

제공 함수:
  - fetch_current_price(code)        : 실시간 현재가 (국내)
  - fetch_daily_ohlcv(code, days)    : 일봉 (최대 100건)
  - fetch_period_ohlcv(code, ...)    : 기간별 (일·주·월)
  - fetch_minute_ohlcv(code, tf)     : 분봉
  - fetch_investor_flow(code, days)  : 투자자별 매매동향
  - fetch_us_quote(ticker)           : 해외 현재가
  - fetch_us_daily(ticker, days)     : 해외 일봉
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from server.config import settings

# ---------------------------------------------------------------------
# Base URLs (real vs paper)
# ---------------------------------------------------------------------
BASE_URL_REAL = "https://openapi.koreainvestment.com:9443"
BASE_URL_PAPER = "https://openapivts.koreainvestment.com:29443"
TOKEN_CACHE = Path(__file__).parent.parent.parent / ".kis_token.json"


def _base_url() -> str:
    return BASE_URL_PAPER if settings.kis_env == "paper" else BASE_URL_REAL


# ---------------------------------------------------------------------
# Token (24h 유효, 파일 캐시)
# ---------------------------------------------------------------------
def _load_cached_token() -> str | None:
    if not TOKEN_CACHE.exists():
        return None
    try:
        data = json.loads(TOKEN_CACHE.read_text())
        if data.get("expires_at", 0) > time.time() + 60:  # 60초 여유
            return data["access_token"]
    except Exception:
        pass
    return None


def _save_token(token: str, ttl: int) -> None:
    TOKEN_CACHE.write_text(json.dumps({
        "access_token": token,
        "expires_at": time.time() + ttl,
    }))


def _issue_token() -> str:
    if not settings.kis_app_key or not settings.kis_app_secret:
        raise RuntimeError("KIS_APP_KEY / KIS_APP_SECRET 이 .env 에 없음")
    r = httpx.post(
        f"{_base_url()}/oauth2/tokenP",
        json={
            "grant_type": "client_credentials",
            "appkey": settings.kis_app_key,
            "appsecret": settings.kis_app_secret,
        },
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    token = data["access_token"]
    _save_token(token, int(data.get("expires_in", 86400)))
    return token


def _get_token() -> str:
    return _load_cached_token() or _issue_token()


# ---------------------------------------------------------------------
# 공통 요청 헬퍼
# ---------------------------------------------------------------------
def _request(
    endpoint: str,
    *,
    tr_id: str,
    params: dict[str, Any] | None = None,
    custtype: str = "P",   # P(개인) / B(법인)
) -> dict:
    token = _get_token()
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": settings.kis_app_key or "",
        "appsecret": settings.kis_app_secret or "",
        "tr_id": tr_id,
        "custtype": custtype,
    }
    r = httpx.get(f"{_base_url()}{endpoint}", headers=headers, params=params or {}, timeout=20)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------
# 국내 주식 (KR)
# ---------------------------------------------------------------------
def fetch_current_price(code: str) -> dict:
    """
    국내 주식 현재가. 실시간 값.

    Returns: {
      code, price, change, change_pct, volume, high, low, open,
      high_52w, low_52w, per, eps, pbr, market_cap, ...
    }
    """
    data = _request(
        "/uapi/domestic-stock/v1/quotations/inquire-price",
        tr_id="FHKST01010100",
        params={"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code},
    )
    out = data.get("output", {})

    def f(key: str) -> float | None:
        v = out.get(key)
        try:
            return float(v) if v not in (None, "", "0", "0.00") else None
        except ValueError:
            return None

    def i(key: str) -> int | None:
        v = out.get(key)
        try:
            return int(v) if v not in (None, "") else None
        except ValueError:
            return None

    return {
        "code": code,
        "price": i("stck_prpr"),                  # 현재가
        "change": i("prdy_vrss"),                 # 전일 대비
        "change_pct": f("prdy_ctrt"),             # 전일 대비율
        "open": i("stck_oprc"),
        "high": i("stck_hgpr"),
        "low": i("stck_lwpr"),
        "volume": i("acml_vol"),                  # 누적 거래량
        "trade_value": i("acml_tr_pbmn"),         # 누적 거래대금
        "high_52w": i("stck_mxpr"),
        "low_52w": i("stck_llam"),
        "per": f("per"),
        "pbr": f("pbr"),
        "eps": f("eps"),
        "bps": f("bps"),
        "market_cap": i("hts_avls"),              # 억원 단위
        "foreign_holding_pct": f("hts_frgn_ehrt"),
        "base_date": out.get("stck_prpr_bas_dt") or str(date.today()),
    }


def fetch_period_ohlcv(
    code: str,
    period: str = "D",   # D(일), W(주), M(월), Y(년)
    adjusted: bool = True,
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    """
    기간별 OHLCV. 최대 100건 (분할 조회 기능은 추후).
    """
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=150))
    data = _request(
        "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
        tr_id="FHKST03010100",
        params={
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": code,
            "fid_input_date_1": start.strftime("%Y%m%d"),
            "fid_input_date_2": end.strftime("%Y%m%d"),
            "fid_period_div_code": period,
            "fid_org_adj_prc": "0" if adjusted else "1",
        },
    )
    rows = data.get("output2", []) or []
    if not rows:
        return pd.DataFrame()

    records = []
    for r in rows:
        if not r.get("stck_bsop_date"):
            continue
        records.append({
            "날짜": pd.to_datetime(r["stck_bsop_date"], format="%Y%m%d"),
            "시가": int(r.get("stck_oprc") or 0) or None,
            "고가": int(r.get("stck_hgpr") or 0) or None,
            "저가": int(r.get("stck_lwpr") or 0) or None,
            "종가": int(r.get("stck_clpr") or 0) or None,
            "거래량": int(r.get("acml_vol") or 0) or None,
            "거래대금": int(r.get("acml_tr_pbmn") or 0) or None,
        })
    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values("날짜").reset_index(drop=True)
    return df


def fetch_daily_ohlcv(code: str, days: int = 100) -> pd.DataFrame:
    """최근 N일 일봉 (period='D' 래퍼)."""
    end = date.today()
    start = end - timedelta(days=max(days + 30, days))  # 주말 보정
    return fetch_period_ohlcv(code, "D", True, start, end).tail(days).reset_index(drop=True)


def fetch_minute_ohlcv(code: str, interval: int = 60) -> pd.DataFrame:
    """
    분봉 조회 (1/3/5/10/15/30/60 분).
    KIS API 는 당일 데이터 30건만 반환 (과거 분봉은 별도 API 필요).
    """
    assert interval in (1, 3, 5, 10, 15, 30, 60), "invalid interval"
    data = _request(
        "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
        tr_id="FHKST03010200",
        params={
            "fid_etc_cls_code": "",
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": code,
            "fid_input_hour_1": f"{interval:02d}0000",
            "fid_pw_data_incu_yn": "Y",
        },
    )
    rows = data.get("output2", []) or []
    records = []
    for r in rows:
        if not r.get("stck_bsop_date"):
            continue
        records.append({
            "날짜": r["stck_bsop_date"],
            "시각": r.get("stck_cntg_hour"),
            "시가": int(r.get("stck_oprc") or 0) or None,
            "고가": int(r.get("stck_hgpr") or 0) or None,
            "저가": int(r.get("stck_lwpr") or 0) or None,
            "종가": int(r.get("stck_prpr") or 0) or None,
            "거래량": int(r.get("cntg_vol") or 0) or None,
        })
    return pd.DataFrame(records)


def fetch_investor_flow(code: str) -> dict:
    """
    투자자별 매매동향 (당일). 기관/외국인/개인 + 프로그램매매.
    """
    data = _request(
        "/uapi/domestic-stock/v1/quotations/inquire-investor",
        tr_id="FHKST01010900",
        params={"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code},
    )
    rows = data.get("output", []) or []
    return {"code": code, "rows": rows}


# ---------------------------------------------------------------------
# 해외 주식 (US)
# ---------------------------------------------------------------------
def fetch_us_quote(ticker: str, exchange: str = "NAS") -> dict:
    """
    해외주식 현재가. exchange: NAS(나스닥) / NYS(NYSE) / AMS(AMEX) / HKS(홍콩).
    """
    data = _request(
        "/uapi/overseas-price/v1/quotations/price",
        tr_id="HHDFS00000300",
        params={"AUTH": "", "EXCD": exchange, "SYMB": ticker},
    )
    out = data.get("output", {})
    def f(k: str) -> float | None:
        v = out.get(k)
        try:
            return float(v) if v not in (None, "") else None
        except ValueError:
            return None

    return {
        "ticker": ticker,
        "exchange": exchange,
        "price": f("last"),
        "open": f("open"),
        "high": f("high"),
        "low": f("low"),
        "prev_close": f("base"),
        "change_pct": f("rate"),
        "volume": int(float(out.get("tvol") or 0)) or None,
        "high_52w": f("h52p"),
        "low_52w": f("l52p"),
        "per": f("perx"),
        "pbr": f("pbrx"),
        "eps": f("epsx"),
    }


def fetch_us_daily(ticker: str, days: int = 100, exchange: str = "NAS") -> pd.DataFrame:
    """해외 일봉 (최근 N일, 최대 100)."""
    end = date.today()
    start = end - timedelta(days=max(days + 60, days))  # 주말·휴장 보정
    data = _request(
        "/uapi/overseas-price/v1/quotations/dailyprice",
        tr_id="HHDFS76240000",
        params={
            "AUTH": "",
            "EXCD": exchange,
            "SYMB": ticker,
            "GUBN": "0",           # 0=일
            "BYMD": end.strftime("%Y%m%d"),
            "MODP": "1",           # 수정주가
        },
    )
    rows = data.get("output2", []) or []
    records = []
    for r in rows:
        if not r.get("xymd"):
            continue
        records.append({
            "날짜": pd.to_datetime(r["xymd"], format="%Y%m%d"),
            "시가": float(r.get("open") or 0) or None,
            "고가": float(r.get("high") or 0) or None,
            "저가": float(r.get("low") or 0) or None,
            "종가": float(r.get("clos") or 0) or None,
            "거래량": int(float(r.get("tvol") or 0)) or None,
        })
    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values("날짜").reset_index(drop=True)
    return df.tail(days).reset_index(drop=True)
