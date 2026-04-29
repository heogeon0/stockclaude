"""
SEC EDGAR 기반 재무·공시 어댑터.

스펙: scrapers/adapter_spec.md (1.4, 1.5, 1.7, 1.9).

- 무료, API 키 불필요. User-Agent 헤더 필수 (`.env` `SEC_EDGAR_USER_AGENT`).
- Rate limit: 10 req/sec = 100ms 지연.
- XBRL us-gaap 태그 → 한글 키 리매핑.
"""
from __future__ import annotations

import json
import os
import ssl
import time
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import urllib3
import requests

# SSL 우회 (corporate proxy 환경용)
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


_LAST_CALL: float = 0.0
_MIN_INTERVAL = 0.11  # 10 req/sec, 여유 0.01
_TICKER_CIK_CACHE: dict[str, str] | None = None


def _user_agent() -> str:
    from server.config import settings
    ua = (settings.sec_edgar_user_agent or "").strip()
    if not ua or ua.startswith("Your Name"):
        raise RuntimeError(
            "SEC_EDGAR_USER_AGENT 미설정. .env에 '이름 email@example.com' 형식으로 설정 필요. "
            "SEC 정책: https://www.sec.gov/os/accessing-edgar-data"
        )
    return ua


def _throttle():
    global _LAST_CALL
    elapsed = time.time() - _LAST_CALL
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _LAST_CALL = time.time()


def _get(url: str, params: dict | None = None) -> Any:
    _throttle()
    headers = {"User-Agent": _user_agent(), "Accept": "application/json"}
    r = requests.get(url, headers=headers, params=params, timeout=15, verify=False)
    if r.status_code == 429:
        time.sleep(11)  # EDGAR blocks ~10 min, but 11s soft retry
        r = requests.get(url, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def _ticker_to_cik(ticker: str) -> str:
    """SEC 공개 ticker→CIK 매핑. 1회 캐시."""
    global _TICKER_CIK_CACHE
    if _TICKER_CIK_CACHE is None:
        data = _get("https://www.sec.gov/files/company_tickers.json")
        _TICKER_CIK_CACHE = {
            v["ticker"].upper(): str(v["cik_str"]).zfill(10)
            for v in data.values()
        }
    cik = _TICKER_CIK_CACHE.get(ticker.upper())
    if not cik:
        raise ValueError(f"ticker '{ticker}' CIK 매핑 실패 (SEC 등록 종목 아닐 수 있음)")
    return cik


# us-gaap 태그 → 한글 키 후보 (복수 candidate 중 첫 non-null 채택)
TAG_MAP = {
    "매출": ["Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax",
           "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "매출총이익": ["GrossProfit"],
    "영업이익": ["OperatingIncomeLoss"],
    "순이익": ["NetIncomeLoss", "ProfitLoss"],
    "영업CF": ["NetCashProvidedByUsedInOperatingActivities"],
    "투자CF": ["NetCashProvidedByUsedInInvestingActivities"],
    "재무CF": ["NetCashProvidedByUsedInFinancingActivities"],
    "Capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "자산": ["Assets"],
    "부채": ["Liabilities"],
    "자본": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "현금성자산": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "이자비용": ["InterestExpense"],
}


def _pick_annual_value(facts: dict, tag_candidates: list[str], year: int) -> float | None:
    """companyfacts JSON에서 특정 연도 FY 10-K(annual) USD 값 추출."""
    units = None
    for tag in tag_candidates:
        entry = facts.get("facts", {}).get("us-gaap", {}).get(tag)
        if not entry:
            continue
        units = entry.get("units", {}).get("USD")
        if units:
            break
    if not units:
        return None
    # fy == year, fp == FY, form == 10-K 또는 10-K/A 우선. 없으면 Q4 합산은 생략
    candidates = [u for u in units if u.get("fy") == year and u.get("fp") == "FY"]
    if not candidates:
        return None
    # 가장 최근 filed(end 날짜 큰 것) 채택
    candidates.sort(key=lambda u: u.get("end", ""), reverse=True)
    val = candidates[0].get("val")
    return float(val) if val is not None else None


def fetch_financials(ticker: str, years: int = 5) -> dict:
    """
    재무제표 N년치 (XBRL 기반).

    반환: scrapers/adapter_spec.md 1.4 스키마.
    """
    cik = _ticker_to_cik(ticker)
    facts = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
    entity_name = facts.get("entityName", ticker)

    # 연도 범위 — 현재 연도부터 거슬러
    end_year = datetime.now().year
    year_list = list(range(end_year - years, end_year + 1))

    years_data = []
    for y in year_list:
        row = {"연도": y, "분기": "FY"}
        for key, tags in TAG_MAP.items():
            row[key] = _pick_annual_value(facts, tags, y)
        # Capex는 US-GAAP에서 양수로 보고되지만 현금유출이라 부호 통일 (DART와 동일 — 양수 처리)
        if row.get("Capex"):
            row["Capex"] = abs(row["Capex"])
        # FCF = 영업CF - Capex
        if row.get("영업CF") is not None and row.get("Capex") is not None:
            row["FCF"] = row["영업CF"] - row["Capex"]
        else:
            row["FCF"] = None
        # 수익성·안정성·성장성 계산 (DART 포맷 호환)
        if row.get("매출") and row.get("매출총이익") is not None:
            row["매출총이익률"] = round(row["매출총이익"] / row["매출"] * 100, 2)
        else:
            row["매출총이익률"] = None
        if row.get("매출") and row.get("영업이익") is not None:
            row["영업이익률"] = round(row["영업이익"] / row["매출"] * 100, 2)
        else:
            row["영업이익률"] = None
        if row.get("매출") and row.get("순이익") is not None:
            row["순이익률"] = round(row["순이익"] / row["매출"] * 100, 2)
        else:
            row["순이익률"] = None
        if row.get("자본") and row.get("순이익") is not None:
            row["ROE"] = round(row["순이익"] / row["자본"] * 100, 2)
        else:
            row["ROE"] = None
        if row.get("자산") and row.get("순이익") is not None:
            row["ROA"] = round(row["순이익"] / row["자산"] * 100, 2)
        else:
            row["ROA"] = None
        if row.get("자본") and row.get("부채") is not None:
            row["부채비율"] = round(row["부채"] / row["자본"] * 100, 2)
        else:
            row["부채비율"] = None
        row["유동비율"] = None  # 유동자산/유동부채 태그는 별도 (AssetsCurrent/LiabilitiesCurrent) — Phase 2 확장
        if row.get("자산") and row.get("자본") is not None:
            row["자기자본비율"] = round(row["자본"] / row["자산"] * 100, 2)
        else:
            row["자기자본비율"] = None
        if row.get("영업이익") is not None and row.get("이자비용") and row["이자비용"] > 0:
            row["이자보상배율"] = round(row["영업이익"] / row["이자비용"], 2)
        else:
            row["이자보상배율"] = None
        # 순이익/영업이익 배율 — 일회성 이익 경고용
        if row.get("순이익") and row.get("영업이익") and row["영업이익"] > 0:
            row["순이익_영업이익_배율"] = round(row["순이익"] / row["영업이익"], 2)
        else:
            row["순이익_영업이익_배율"] = None
        years_data.append(row)

    # YoY 성장률
    for i in range(1, len(years_data)):
        prev, curr = years_data[i - 1], years_data[i]
        for key in ("매출", "영업이익", "순이익", "FCF"):
            if prev.get(key) and curr.get(key) is not None and prev[key] != 0:
                curr[f"{key}_YoY"] = round((curr[key] - prev[key]) / abs(prev[key]) * 100, 2)
            else:
                curr[f"{key}_YoY"] = None
    # 첫 해는 YoY 없음
    if years_data:
        for key in ("매출", "영업이익", "순이익", "FCF"):
            years_data[0][f"{key}_YoY"] = None

    # None 핵심 지표가 전부인 행 제거 (해당 연도 미리포팅)
    years_data = [y for y in years_data if y.get("매출") or y.get("순이익")]

    return {
        "종목명": entity_name,
        "ticker": ticker,
        "통화": "USD",
        "연도별": years_data,
    }


def summarize_financials(fin: dict) -> dict:
    """
    DART summarize_financials와 동일 스키마 반환 (US 버전 — _M 필드 사용).

    scoring.score_financial()이 market 무관하게 호출 가능해야 함.
    """
    years = fin.get("연도별", [])
    if not years:
        return {"error": "재무 데이터 없음", "통화": "USD"}

    latest = years[-1]
    summary = {
        "최근연도": latest["연도"],
        "통화": "USD",
        # 규모 (millions USD)
        "매출_억": None,  # KR 전용 키
        "매출_M": round(latest["매출"] / 1e6) if latest.get("매출") else None,
        "영업이익_억": None,
        "영업이익_M": round(latest["영업이익"] / 1e6) if latest.get("영업이익") else None,
        "순이익_억": None,
        "순이익_M": round(latest["순이익"] / 1e6) if latest.get("순이익") else None,
        "영업CF_억": None,
        "영업CF_M": round(latest["영업CF"] / 1e6) if latest.get("영업CF") else None,
        "FCF_억": None,
        "FCF_M": round(latest["FCF"] / 1e6) if latest.get("FCF") else None,
        "Capex_억": None,
        "Capex_M": round(latest["Capex"] / 1e6) if latest.get("Capex") else None,
        "현금_억": None,
        "현금_M": round(latest["현금성자산"] / 1e6) if latest.get("현금성자산") else None,
        # 공통 비율
        "매출총이익률": latest.get("매출총이익률"),
        "영업이익률": latest.get("영업이익률"),
        "순이익률": latest.get("순이익률"),
        "ROE": latest.get("ROE"),
        "ROA": latest.get("ROA"),
        "부채비율": latest.get("부채비율"),
        "유동비율": latest.get("유동비율"),
        "자기자본비율": latest.get("자기자본비율"),
        "이자보상배율": latest.get("이자보상배율"),
        "매출_YoY": latest.get("매출_YoY"),
        "영업이익_YoY": latest.get("영업이익_YoY"),
        "순이익_YoY": latest.get("순이익_YoY"),
        "FCF_YoY": latest.get("FCF_YoY"),
    }

    # 경고 (DART와 동일 임계값)
    warnings = []
    ratio = latest.get("순이익_영업이익_배율")
    if ratio and ratio > 2:
        warnings.append(f"순이익이 영업이익의 {ratio}배 — 일회성 이익 의심. CF 확인 필요")
    if latest.get("영업이익률") is not None and latest["영업이익률"] < 5:
        warnings.append(f"영업이익률 {latest['영업이익률']}% — 수익성 취약")
    if latest.get("부채비율") is not None and latest["부채비율"] > 200:
        warnings.append(f"부채비율 {latest['부채비율']}% — 재무 레버리지 과도")
    if latest.get("이자보상배율") is not None and latest["이자보상배율"] < 3:
        warnings.append(f"이자보상배율 {latest['이자보상배율']} — 이자 감당 부담")
    if latest.get("영업CF") is not None and latest.get("순이익") and latest["영업CF"] < latest["순이익"] * 0.5:
        warnings.append("영업CF가 순이익의 50% 미만 — 이익 질 낮음")

    summary["경고"] = warnings
    return summary


def fetch_disclosures(ticker: str, days: int = 30) -> pd.DataFrame:
    """최근 N일 공시 목록 (10-K/10-Q/8-K/Form 4/13D/G 등)."""
    cik = _ticker_to_cik(ticker)
    data = _get(f"https://data.sec.gov/submissions/CIK{cik}.json")
    recent = data.get("filings", {}).get("recent", {})
    if not recent:
        return pd.DataFrame()

    df = pd.DataFrame({
        "날짜": pd.to_datetime(recent.get("filingDate", []), errors="coerce"),
        "공시유형": recent.get("form", []),
        "제목": recent.get("primaryDocDescription", recent.get("primaryDocument", [])),
        "accession": recent.get("accessionNumber", []),
    })
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    df = df[df["날짜"] >= cutoff].copy()
    # URL 구성
    df["URL"] = df["accession"].apply(
        lambda a: f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{a.replace('-', '')}/" if a else ""
    )
    return df[["날짜", "공시유형", "제목", "URL"]].reset_index(drop=True)


def fetch_insider_trading(ticker: str, days: int = 90) -> pd.DataFrame:
    """Form 4 목록 (상세 매매 정보는 각 Form 4 원문 파싱 필요 — Phase 2 확장)."""
    disc = fetch_disclosures(ticker, days=days)
    if disc.empty:
        return pd.DataFrame()
    form4 = disc[disc["공시유형"].isin(["4", "4/A"])].copy()
    form4["인물"] = None  # 원문 파싱 전까지 미확정
    form4["유형"] = None
    form4["주식수"] = None
    form4["가격"] = None
    form4["총액"] = None
    form4["사유"] = "Form 4 원문 파싱 필요 (Phase 2)"
    return form4[["날짜", "인물", "유형", "주식수", "가격", "총액", "사유", "URL"]].reset_index(drop=True)


if __name__ == "__main__":
    import sys
    try:
        print("== AAPL CIK ==")
        print(_ticker_to_cik("AAPL"))
        print("== AAPL disclosures (7d) ==")
        print(fetch_disclosures("AAPL", days=7).head())
    except RuntimeError as e:
        print(f"smoke test skipped: {e}", file=sys.stderr)
