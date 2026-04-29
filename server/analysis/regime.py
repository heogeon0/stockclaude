"""
시장 국면 판정 — 모멘텀 전략 On/Off 스위치

Core 원칙:
- KOSPI가 10개월 MA 아래 → 모멘텀 매수 전략 무효화 (Mebane Faber)
- V-KOSPI(한국 VIX) 급등 → 공포장, 진입 중단
- 신고가/신저가 Breadth로 시장 폭 건전성 평가
- 섹터별 상대 모멘텀 순위로 로테이션 방향 판단

사용:
    from server.analysis.regime import kospi_regime, sector_regime, breadth_index

    r = kospi_regime()
    if not r['모멘텀_가동']:
        # 방어 모드
        pass
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
import ssl
import pandas as pd
import numpy as np
import urllib3
import requests

# macOS + Python 3.14 + KRX 서버 인증서 체인 충돌 우회.
# pykrx 내부 requests.Session.verify 강제 False (certifi 번들 대신 검증 생략).
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_orig_request = requests.Session.request
def _patched_request(self, *args, **kwargs):
    kwargs.setdefault('verify', False)
    return _orig_request(self, *args, **kwargs)
requests.Session.request = _patched_request


# KOSPI 섹터 인덱스 코드 (KRX 기준)
KOSPI_SECTOR_CODES = {
    "1001": "코스피 전체",
    "1002": "코스피 대형주",
    "1003": "코스피 중형주",
    "1004": "코스피 소형주",
    "1005": "음식료품",
    "1006": "섬유의복",
    "1007": "종이목재",
    "1008": "화학",
    "1009": "의약품",
    "1010": "비금속광물",
    "1011": "철강금속",
    "1012": "기계",
    "1013": "전기전자",
    "1014": "의료정밀",
    "1015": "운수장비",
    "1016": "유통업",
    "1017": "전기가스업",
    "1018": "건설업",
    "1019": "운수창고업",
    "1020": "통신업",
    "1021": "금융업",
    "1024": "서비스업",
    "1026": "제조업",
}


def _fetch_kospi(lookback_days: int = 500) -> pd.DataFrame:
    """KOSPI 지수 시세 조회 (pykrx)."""
    from pykrx import stock as krx
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y%m%d")
    return krx.get_index_ohlcv(start, end, "1001")


def kospi_regime(df: Optional[pd.DataFrame] = None) -> dict:
    """
    KOSPI 기반 시장 국면 판정.

    판정 기준 (4가지):
      1. 200일선 위/아래 (장기 추세)
      2. 10개월선(약 210영업일) 위/아래 (Faber's rule)
      3. 20일 이평 방향 (단기 모멘텀)
      4. 신고가 비율 (60일 내 52주 신고가 터치 일수 / 60)

    종합:
      - 전부 통과 → "강한 상승장" + 모멘텀_가동=True
      - 2~3 통과 → "상승장" + 가동
      - 1 통과 → "횡보/전환기" + 가동 중단 권장
      - 0 통과 → "하락장" + 가동=False
    """
    if df is None:
        try:
            df = _fetch_kospi()
        except Exception as e:
            return {"오류": f"KOSPI 조회 실패: {e}", "모멘텀_가동": True}  # fail-safe: 기존 동작

    if df is None or len(df) < 210:
        return {"오류": "데이터 부족", "모멘텀_가동": True}

    close = df["종가"]
    last = close.iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]
    sma210 = close.rolling(210).mean().iloc[-1]  # 10개월 MA 근사
    sma20 = close.rolling(20).mean().iloc[-1]
    sma20_prev = close.rolling(20).mean().iloc[-21]

    # 신고가 비율 (최근 60일 중 당일 종가가 이전 252일 최고인 날)
    recent = close.iloc[-60:]
    highs = close.rolling(252).max()
    new_high_days = sum(1 for i in range(-60, 0) if close.iloc[i] >= highs.iloc[i])
    new_high_ratio = new_high_days / 60

    checks = {
        "200일선_위": bool(last > sma200),
        "10개월선_위": bool(last > sma210),
        "20일선_상승": bool(sma20 > sma20_prev),
        "신고가_활발": bool(new_high_ratio >= 0.15),
    }
    passed = sum(checks.values())

    if passed == 4:
        state = "강한 상승장"
        momentum_on = True
    elif passed >= 2:
        state = "상승장"
        momentum_on = True
    elif passed == 1:
        state = "전환기"
        momentum_on = False
    else:
        state = "하락장"
        momentum_on = False

    return {
        "국면": state,
        "모멘텀_가동": momentum_on,
        "통과_조건수": f"{passed}/4",
        "체크": checks,
        "세부": {
            "KOSPI_종가": int(last),
            "SMA200": int(sma200),
            "SMA210_10M": int(sma210),
            "신고가_비율_60D": round(new_high_ratio, 3),
        },
        "해석": _interpret_regime(state),
    }


def _interpret_regime(state: str) -> str:
    return {
        "강한 상승장": "모멘텀 전략 적극 가동. 공격적 진입 가능.",
        "상승장": "모멘텀 가동. 단 과매수 종목 신규 진입 주의.",
        "전환기": "신규 모멘텀 매수 중단. 기존 보유 방어 전환. 현금 비중 증가.",
        "하락장": "모멘텀 전략 Off. 현금 or 방어주(필수소비재·유틸리티)로 이동.",
    }.get(state, "")


# ============================================================
# Breadth Index — 시장 폭 건전성
# ============================================================

def breadth_index(codes: list[str], lookback: int = 252) -> dict:
    """
    종목군의 52주 신고가 종목 수 / 52주 신저가 종목 수 비율.

    비율 >2 → 건전한 확산장 (Advance-Decline 긍정)
    비율 1~2 → 중립
    비율 <1 → 상위 소수 종목만 상승, 대부분 하락 → 경고 (2000 닷컴버블 직전 패턴)
    """
    from pykrx import stock as krx

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=400)).strftime("%Y%m%d")

    new_highs = 0
    new_lows = 0
    valid = 0

    for code in codes:
        try:
            df = krx.get_market_ohlcv(start, end, code)
            if df is None or len(df) < lookback:
                continue
            last_close = df["종가"].iloc[-1]
            high_52w = df["고가"].iloc[-lookback:].max()
            low_52w = df["저가"].iloc[-lookback:].min()
            if last_close >= high_52w * 0.97:
                new_highs += 1
            elif last_close <= low_52w * 1.03:
                new_lows += 1
            valid += 1
        except Exception:
            continue

    if valid == 0:
        return {"오류": "데이터 없음"}

    ratio = new_highs / max(new_lows, 1)

    if ratio > 3:
        health = "강한 확산"
        interp = "다수 종목이 신고가 — 건전한 상승장"
    elif ratio > 1:
        health = "중립"
        interp = "선두주만 강세 — 성숙기"
    elif ratio > 0.3:
        health = "약화"
        interp = "폭 좁아짐 — 경계 구간"
    else:
        health = "위축"
        interp = "신저가 우세 — 하락장"

    return {
        "신고가_종목": new_highs,
        "신저가_종목": new_lows,
        "비율": round(ratio, 2),
        "건전성": health,
        "해석": interp,
        "조사_종목수": valid,
    }


# ============================================================
# 섹터 모멘텀 랭킹
# ============================================================

def sector_regime(sector_codes: Optional[dict] = None,
                   lookback_months: int = 6) -> pd.DataFrame:
    """
    KOSPI 섹터별 모멘텀 순위.

    Args:
        sector_codes: {인덱스코드: 섹터명} — 기본값 KOSPI_SECTOR_CODES의 일부
        lookback_months: 수익률 기간 (기본 6개월)

    Returns:
        DataFrame [섹터명, 수익률_3M, 수익률_6M, 수익률_12M, Z_score_6M, 순위]
    """
    from pykrx import stock as krx

    if sector_codes is None:
        # 전체 섹터는 너무 많아 주요 11개만
        sector_codes = {
            "1005": "음식료품", "1008": "화학", "1009": "의약품",
            "1011": "철강금속", "1012": "기계", "1013": "전기전자",
            "1015": "운수장비", "1017": "전기가스업", "1018": "건설업",
            "1020": "통신업", "1021": "금융업",
        }

    end = datetime.now().strftime("%Y%m%d")
    start_12m = (datetime.now() - timedelta(days=400)).strftime("%Y%m%d")

    rows = []
    for code, name in sector_codes.items():
        try:
            df = krx.get_index_ohlcv(start_12m, end, code)
            if df is None or len(df) < 252:
                continue
            close = df["종가"]
            ret_3m = (close.iloc[-1] / close.iloc[-63] - 1) * 100
            ret_6m = (close.iloc[-1] / close.iloc[-126] - 1) * 100
            ret_12m = (close.iloc[-1] / close.iloc[-252] - 1) * 100
            rows.append({
                "섹터": name,
                "코드": code,
                "수익률_3M": round(ret_3m, 1),
                "수익률_6M": round(ret_6m, 1),
                "수익률_12M": round(ret_12m, 1),
            })
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    rdf = pd.DataFrame(rows)
    if len(rdf) >= 2 and rdf["수익률_6M"].std() > 0:
        rdf["Z_6M"] = ((rdf["수익률_6M"] - rdf["수익률_6M"].mean()) / rdf["수익률_6M"].std()).round(2)
    rdf["순위_6M"] = rdf["수익률_6M"].rank(ascending=False, method="min").astype("Int64")
    rdf = rdf.sort_values("순위_6M").reset_index(drop=True)
    return rdf


# ============================================================
# VKOSPI (한국 VIX) — 변동성 지표 (참고용)
# ============================================================

def vkospi_level() -> dict:
    """
    V-KOSPI 현재 수준.
    pykrx.stock.get_index_ohlcv("XXX", "XXX", "...")로 V-KOSPI 코드 조회.
    KRX 공식 V-KOSPI 지수 코드: "5001" (참고: 확인 필요)

    <30 평온 / 30~40 경계 / >40 공포 / >50 패닉
    """
    from pykrx import stock as krx

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

    # V-KOSPI 지수 코드는 거래소 KRX 공식 내부 코드 사용
    # pykrx에서 지원 여부 확인 필요 — 실패 시 None
    try:
        df = krx.get_index_ohlcv(start, end, "5001")
        if df is None or len(df) == 0:
            return {"오류": "V-KOSPI 데이터 미확인"}
        current = float(df["종가"].iloc[-1])
    except Exception as e:
        return {"오류": str(e), "가동": True}

    if current < 20:
        level = "평온"
        action = "정상 가동"
    elif current < 30:
        level = "보통"
        action = "정상"
    elif current < 40:
        level = "경계"
        action = "신규 진입 축소"
    elif current < 50:
        level = "공포"
        action = "신규 진입 중단, 방어"
    else:
        level = "패닉"
        action = "현금화 + 방어주"

    return {"V_KOSPI": round(current, 1), "레벨": level, "권장": action}


# ============================================================
# US 시장 국면 (v10 추가) — 기존 KR 함수 건드리지 않음
# ============================================================

def sp500_regime() -> dict:
    """
    S&P 500 기반 US 시장 국면 판정. KR의 kospi_regime()과 동일 반환 스키마.

    판정 기준 (5가지):
      1. 200일선 위/아래 (장기 추세)
      2. 10개월선(약 210영업일) 위/아래 (Faber's rule)
      3. 20일 이평 방향 (단기 모멘텀)
      4. VIX 레벨 (>30 경계, >40 공포)
      5. Yield curve inversion (10Y-3M < 0 → 리세션 시그널)
    """
    try:
        from scrapers.us.adapter import fetch_benchmark_ohlcv, fetch_macro_indicators, fetch_yield_curve
    except ImportError as e:
        return {"오류": f"US 어댑터 미사용: {e}", "모멘텀_가동": True}

    # S&P 500 ETF SPY (^GSPC보다 더 안정적)
    try:
        df = fetch_benchmark_ohlcv("SPY", start=(datetime.now() - timedelta(days=500)).strftime("%Y-%m-%d"))
    except Exception as e:
        return {"오류": f"SPY 조회 실패: {e}", "모멘텀_가동": True}

    if df is None or df.empty or len(df) < 210:
        return {"오류": "데이터 부족", "모멘텀_가동": True}

    close = df["종가"]
    last = close.iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]
    sma210 = close.rolling(210).mean().iloc[-1]
    sma20 = close.rolling(20).mean().iloc[-1]
    sma20_prev = close.rolling(20).mean().iloc[-21]

    # VIX
    vix_val = None
    try:
        macro = fetch_macro_indicators(["VIXCLS"])
        vix_val = macro.get("VIXCLS", {}).get("최신값")
    except Exception:
        pass

    # Yield curve inversion
    yc = {}
    try:
        yc = fetch_yield_curve()
    except Exception:
        pass
    inversion = yc.get("역전여부", False)

    checks = {
        "200일선_위": bool(last > sma200),
        "10개월선_위": bool(last > sma210),
        "20일선_상승": bool(sma20 > sma20_prev),
        "VIX_평온": bool(vix_val is not None and vix_val < 25),
        "Yield_정상": bool(not inversion),
    }
    passed = sum(checks.values())

    if passed == 5:
        state = "강한 상승장"
        momentum_on = True
    elif passed >= 3:
        state = "상승장"
        momentum_on = True
    elif passed == 2:
        state = "전환기"
        momentum_on = False
    else:
        state = "하락장"
        momentum_on = False

    return {
        "국면": state,
        "모멘텀_가동": momentum_on,
        "통과_조건수": f"{passed}/5",
        "체크": checks,
        "세부": {
            "SPY_종가": round(float(last), 2),
            "SMA200": round(float(sma200), 2),
            "SMA210_10M": round(float(sma210), 2),
            "VIX": round(vix_val, 2) if vix_val is not None else None,
            "Yield_10Y_3M_spread": yc.get("10Y_3M_spread"),
            "Yield_역전": inversion,
        },
        "해석": _interpret_regime(state),
    }


def sector_regime_us(lookback_months: int = 6) -> pd.DataFrame:
    """GICS 11섹터 ETF 모멘텀 순위 (XLK/XLV/XLF/XLY/XLP/XLE/XLI/XLB/XLRE/XLU/XLC)."""
    from scrapers.us.adapter import fetch_benchmark_ohlcv

    sector_etfs = {
        "XLK": "Technology", "XLV": "Healthcare", "XLF": "Financials",
        "XLY": "Consumer Discretionary", "XLP": "Consumer Staples",
        "XLE": "Energy", "XLI": "Industrials", "XLB": "Materials",
        "XLRE": "Real Estate", "XLU": "Utilities", "XLC": "Communication",
    }
    rows = []
    start = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
    for etf, name in sector_etfs.items():
        try:
            df = fetch_benchmark_ohlcv(etf, start=start)
            if df is None or df.empty or len(df) < 252:
                continue
            close = df["종가"]
            rows.append({
                "섹터": name,
                "ETF": etf,
                "수익률_3M": round((close.iloc[-1] / close.iloc[-63] - 1) * 100, 1),
                "수익률_6M": round((close.iloc[-1] / close.iloc[-126] - 1) * 100, 1),
                "수익률_12M": round((close.iloc[-1] / close.iloc[-252] - 1) * 100, 1),
            })
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()
    rdf = pd.DataFrame(rows)
    if len(rdf) >= 2 and rdf["수익률_6M"].std() > 0:
        rdf["Z_6M"] = ((rdf["수익률_6M"] - rdf["수익률_6M"].mean()) / rdf["수익률_6M"].std()).round(2)
    rdf["순위_6M"] = rdf["수익률_6M"].rank(ascending=False, method="min").astype("Int64")
    return rdf.sort_values("순위_6M").reset_index(drop=True)


def breadth_index_us(codes: list[str], lookback: int = 252) -> dict:
    """US 종목군 52주 신고가/신저가 breadth. KR breadth_index와 동일 반환 스키마."""
    from scrapers.us.adapter import fetch_ohlcv

    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")

    new_highs = new_lows = valid = 0
    for ticker in codes:
        try:
            df = fetch_ohlcv(ticker, start=start, end=end)
            if df is None or df.empty or len(df) < lookback:
                continue
            last_close = df["종가"].iloc[-1]
            high_52w = df["고가"].iloc[-lookback:].max()
            low_52w = df["저가"].iloc[-lookback:].min()
            if last_close >= high_52w * 0.97:
                new_highs += 1
            elif last_close <= low_52w * 1.03:
                new_lows += 1
            valid += 1
        except Exception:
            continue

    if valid == 0:
        return {"오류": "데이터 없음"}

    ratio = new_highs / max(new_lows, 1)
    if ratio > 3:
        health, interp = "강한 확산", "다수 종목이 신고가 — 건전한 상승장"
    elif ratio > 1:
        health, interp = "중립", "선두주만 강세 — 성숙기"
    elif ratio > 0.3:
        health, interp = "약화", "폭 좁아짐 — 경계 구간"
    else:
        health, interp = "위축", "신저가 우세 — 하락장"

    return {
        "신고가_종목": new_highs,
        "신저가_종목": new_lows,
        "비율": round(ratio, 2),
        "건전성": health,
        "해석": interp,
        "조사_종목수": valid,
    }


if __name__ == "__main__":
    import json
    print("=== KOSPI 국면 ===")
    print(json.dumps(kospi_regime(), indent=2, ensure_ascii=False))

    print("\n=== 5종목 Breadth ===")
    print(breadth_index(["005930", "000660", "298040", "036570", "000720"]))

    print("\n=== 섹터 모멘텀 ===")
    print(sector_regime().to_string())

    print("\n=== V-KOSPI ===")
    print(vkospi_level())

    print("\n=== S&P 500 국면 ===")
    print(json.dumps(sp500_regime(), indent=2, ensure_ascii=False, default=str))
