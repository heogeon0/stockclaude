"""
기술 지표 계산 모음
- 모든 함수는 OHLCV DataFrame을 입력받아 새 컬럼을 추가하거나 Series 반환
- 입력 DataFrame 컬럼: 날짜, 시가, 고가, 저가, 종가, 거래량
"""

from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np


# ============================================================
# 장 상태 및 가격 컨텍스트 (종가 vs 현재가 구분)
# ============================================================

# v10 — 시장별 거래 시간 (KST/ET local time)
MARKET_HOURS = {
    "kr": {"tz": "Asia/Seoul", "open_hm": 900, "close_hm": 1530},
    "us": {"tz": "America/New_York", "open_hm": 930, "close_hm": 1600},
}


def price_context(df: pd.DataFrame, market: str = "kr") -> dict:
    """
    DataFrame의 최근 가격을 장 상태 기준으로 해석.

    - 장중 이고 마지막 row가 오늘 날짜면:
        종가 = 전일 row (전일 종가), 현재가 = 오늘 row (실시간/지연가)
    - 그 외 (장 마감 후, 장 시작 전, 주말/휴장):
        종가 = 마지막 row (실제 확정 종가), 현재가 = None

    Args:
        market: "kr" (기본, Asia/Seoul 09:00~15:30) | "us" (America/New_York 09:30~16:00)

    Returns:
        {
            "장_상태": "장중" | "장마감" | "장시작전" | "휴장",
            "종가": int, "종가_날짜": "YYYY-MM-DD",
            "현재가": int | None, "현재가_날짜": str | None,
            "등락률_현재가기준": float | None (장중일 때만, 전일 종가 대비 %)
        }
    """
    if df.empty:
        return {"장_상태": "데이터없음"}

    hours = MARKET_HOURS.get(market, MARKET_HOURS["kr"])
    tz = ZoneInfo(hours["tz"])
    now = datetime.now(tz)
    today = now.date()
    weekday = now.weekday()  # 0=월 ~ 6=일
    hm = now.hour * 100 + now.minute

    last = df.iloc[-1]
    last_date = last["날짜"].date() if hasattr(last["날짜"], "date") else last["날짜"]

    is_weekday = weekday < 5
    is_market_hours = hours["open_hm"] <= hm < hours["close_hm"]

    # 장중 + 오늘 데이터 있음 → 현재가/종가 분리
    if is_weekday and is_market_hours and last_date == today and len(df) >= 2:
        prev = df.iloc[-2]
        prev_close = int(prev["종가"])
        current = int(last["종가"])
        return {
            "장_상태": "장중",
            "종가": prev_close,
            "종가_날짜": prev["날짜"].strftime("%Y-%m-%d"),
            "현재가": current,
            "현재가_날짜": last["날짜"].strftime("%Y-%m-%d"),
            "등락률_현재가기준": round((current - prev_close) / prev_close * 100, 2),
        }

    # 그 외: 마지막 row가 확정 종가
    if is_weekday and hm >= hours["close_hm"]:
        status = "장마감"
    elif is_weekday and hm < hours["open_hm"]:
        status = "장시작전"
    elif not is_weekday:
        status = "휴장"
    else:
        status = "장중"  # 이론상 fallback

    return {
        "장_상태": status,
        "종가": int(last["종가"]),
        "종가_날짜": last["날짜"].strftime("%Y-%m-%d"),
        "현재가": None,
        "현재가_날짜": None,
        "등락률_현재가기준": None,
    }


# ============================================================
# 이동평균 (Moving Averages)
# ============================================================

def sma(series: pd.Series, period: int) -> pd.Series:
    """단순 이동평균 (Simple Moving Average)."""
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """지수 이동평균 (Exponential Moving Average)."""
    return series.ewm(span=period, adjust=False).mean()


def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    """
    모든 주요 이동평균 추가.
    - SMA: 5, 10, 20, 50, 60, 120, 150, 200일 (그랜빌, 미너비니용)
    - EMA: 10, 13, 20일 (엘더, 미너비니용)
    """
    close = df["종가"]
    for p in [5, 10, 20, 50, 60, 120, 150, 200]:
        df[f"SMA{p}"] = sma(close, p)
    for p in [10, 13, 20]:
        df[f"EMA{p}"] = ema(close, p)
    return df


# ============================================================
# 일목균형표 (Ichimoku Kinko Hyo)
# ============================================================

def ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    """
    일목균형표 5개 라인 추가.
    - 전환선 (Tenkan-sen): 9일 (고가+저가)/2
    - 기준선 (Kijun-sen): 26일 (고가+저가)/2
    - 선행스팬 A: (전환+기준)/2, 26일 앞
    - 선행스팬 B: 52일 (고가+저가)/2, 26일 앞
    - 후행스팬: 종가를 26일 뒤
    """
    high, low, close = df["고가"], df["저가"], df["종가"]

    df["전환선"] = (high.rolling(9).max() + low.rolling(9).min()) / 2
    df["기준선"] = (high.rolling(26).max() + low.rolling(26).min()) / 2
    df["선행스팬A"] = ((df["전환선"] + df["기준선"]) / 2).shift(26)
    df["선행스팬B"] = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    df["후행스팬"] = close.shift(-26)

    return df


# ============================================================
# 볼린저밴드 (Bollinger Bands)
# ============================================================

def bollinger(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.DataFrame:
    """
    볼린저밴드 + 밴드폭(스퀴즈 판단용) 추가.
    - 중심선: 20일 SMA
    - 상/하단: 중심선 ± 2σ
    - 밴드폭 = (상단 - 하단) / 중심선
    """
    close = df["종가"]
    ma = sma(close, period)
    stdev = close.rolling(period).std()

    df["BB중심"] = ma
    df["BB상단"] = ma + std * stdev
    df["BB하단"] = ma - std * stdev
    df["BB폭"] = (df["BB상단"] - df["BB하단"]) / ma

    # 스퀴즈 감지: 최근 6개월(126영업일) 중 밴드폭 최소 수준
    df["BB스퀴즈"] = df["BB폭"] <= df["BB폭"].rolling(126, min_periods=30).quantile(0.1)

    return df


# ============================================================
# MACD
# ============================================================

def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    MACD 계산.
    - MACD선 = EMA(fast) - EMA(slow)
    - 시그널선 = MACD의 EMA(signal)
    - 히스토그램 = MACD - 시그널
    """
    close = df["종가"]
    df["MACD"] = ema(close, fast) - ema(close, slow)
    df["MACD시그널"] = ema(df["MACD"], signal)
    df["MACD히스토"] = df["MACD"] - df["MACD시그널"]
    return df


# ============================================================
# 스토캐스틱 / Williams %R (Triple Screen용 오실레이터)
# ============================================================

def stochastic(df: pd.DataFrame, k: int = 14, d: int = 3) -> pd.DataFrame:
    """스토캐스틱 %K, %D."""
    high, low, close = df["고가"], df["저가"], df["종가"]
    lowest = low.rolling(k).min()
    highest = high.rolling(k).max()
    df["Stoch_K"] = 100 * (close - lowest) / (highest - lowest)
    df["Stoch_D"] = df["Stoch_K"].rolling(d).mean()
    return df


def williams_r(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Williams %R."""
    high, low, close = df["고가"], df["저가"], df["종가"]
    highest = high.rolling(period).max()
    lowest = low.rolling(period).min()
    df[f"WilliamsR{period}"] = -100 * (highest - close) / (highest - lowest)
    return df


# ============================================================
# Force Index (엘더)
# ============================================================

def force_index(df: pd.DataFrame, period: int = 2) -> pd.DataFrame:
    """
    Force Index (엘더).
    FI = (금일 종가 - 전일 종가) × 거래량
    Elder는 2일 EMA를 단기 시그널로 사용.
    """
    raw = (df["종가"] - df["종가"].shift(1)) * df["거래량"]
    df[f"ForceIndex{period}"] = ema(raw, period)
    return df


# ============================================================
# RSI
# ============================================================

def rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """상대강도지수 (Relative Strength Index)."""
    close = df["종가"]
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    df[f"RSI{period}"] = 100 - (100 / (1 + rs))
    return df


# ============================================================
# ATR (Average True Range) — 변동성 기반 손절 산정용
# ============================================================

def atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    ATR — 진짜 레인지 평균.
    True Range = max(H-L, |H-prevC|, |L-prevC|)
    ATR은 TR의 period일 이동평균.
    변동성 기반 손절 산정 시 사용 (예: 진입가 - 2×ATR).
    """
    high, low, close = df["고가"], df["저가"], df["종가"]
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    df[f"ATR{period}"] = true_range.rolling(period).mean()
    df[f"ATR{period}_pct"] = df[f"ATR{period}"] / close * 100  # 종가 대비 ATR 비율
    return df


# ============================================================
# ADX (Average Directional Index) — 추세 강도 판별용
# ============================================================

def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    ADX 계산. +DI, -DI, ADX 3개 컬럼 추가.
    ADX > 25 → 강한 추세, ADX < 20 → 추세 약함/횡보.
    그랜빌 과이격 매도 필터에 사용.
    """
    high, low, close = df["고가"], df["저가"], df["종가"]

    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)

    atr_smooth = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr_smooth)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr_smooth)

    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx_val = dx.rolling(period).mean()

    df[f"+DI{period}"] = plus_di
    df[f"-DI{period}"] = minus_di
    df[f"ADX{period}"] = adx_val
    return df


# ============================================================
# 지지/저항 레벨 자동 추출
# ============================================================

def support_resistance(df: pd.DataFrame, lookback: int = 60, window: int = 3,
                       num_levels: int = 3, tolerance: float = 0.01) -> dict:
    """
    최근 N일 구간에서 주요 지지/저항 레벨 자동 감지.
    - 지역 고점/저점을 찾아 클러스터링 (비슷한 레벨은 병합)
    - 현재가 기준 위쪽=저항, 아래쪽=지지

    Args:
        lookback: 최근 N일 (기본 60일)
        window: 지역 고/저점 감지 윈도우 (기본 좌우 3일)
        num_levels: 반환할 최대 레벨 수 (기본 3개)
        tolerance: 레벨 병합 허용 오차 (기본 1%)

    Returns:
        {
            "현재가": float,
            "저항": [가격들 — 가까운 순],
            "지지": [가격들 — 가까운 순],
        }
    """
    recent = df.tail(lookback).reset_index(drop=True)
    if len(recent) < window * 2 + 1:
        return {"현재가": None, "저항": [], "지지": []}

    highs = []
    lows = []
    for i in range(window, len(recent) - window):
        if recent["고가"].iloc[i] == recent["고가"].iloc[i-window:i+window+1].max():
            highs.append(float(recent["고가"].iloc[i]))
        if recent["저가"].iloc[i] == recent["저가"].iloc[i-window:i+window+1].min():
            lows.append(float(recent["저가"].iloc[i]))

    def cluster(prices: list[float]) -> list[float]:
        """비슷한 가격 병합 (tolerance 내)."""
        if not prices:
            return []
        sorted_p = sorted(prices)
        clusters = [[sorted_p[0]]]
        for p in sorted_p[1:]:
            if abs(p - clusters[-1][-1]) / clusters[-1][-1] <= tolerance:
                clusters[-1].append(p)
            else:
                clusters.append([p])
        return [sum(c) / len(c) for c in clusters]

    current = float(recent["종가"].iloc[-1])

    resistance_all = [p for p in cluster(highs) if p > current]
    support_all = [p for p in cluster(lows) if p < current]

    resistance = sorted(resistance_all)[:num_levels]  # 가까운 순
    support = sorted(support_all, reverse=True)[:num_levels]  # 가까운 순

    return {
        "현재가": round(current),
        "저항": [round(p) for p in resistance],
        "지지": [round(p) for p in support],
    }


# ============================================================
# 변동성 돌파 (래리 윌리엄스)
# ============================================================

def volatility_breakout(df: pd.DataFrame, k: float = 0.5) -> pd.DataFrame:
    """
    래리 윌리엄스 변동성 돌파 전략 목표가.
    목표가 = 당일 시가 + (전일 고가 - 전일 저가) × k
    """
    prev_range = df["고가"].shift(1) - df["저가"].shift(1)
    df[f"돌파가_k{k}"] = df["시가"] + prev_range * k
    df[f"하락돌파가_k{k}"] = df["시가"] - prev_range * k
    return df


# ============================================================
# 피봇 포인트 (리버모어 + 전통적 피봇)
# ============================================================

def pivot_points(df: pd.DataFrame) -> pd.DataFrame:
    """
    전통적 피봇 포인트 (당일 = 전일 기준).
    P = (H + L + C) / 3
    R1 = 2P - L,  S1 = 2P - H
    R2 = P + (H - L),  S2 = P - (H - L)
    """
    high = df["고가"].shift(1)
    low = df["저가"].shift(1)
    close = df["종가"].shift(1)

    p = (high + low + close) / 3
    df["Pivot"] = p
    df["R1"] = 2 * p - low
    df["S1"] = 2 * p - high
    df["R2"] = p + (high - low)
    df["S2"] = p - (high - low)
    return df


# ============================================================
# 52주 고가/저가 (미너비니)
# ============================================================

def high_low_52week(df: pd.DataFrame) -> pd.DataFrame:
    """52주(252영업일) 고가/저가 및 현재 위치(%)."""
    high_52w = df["고가"].rolling(252, min_periods=50).max()
    low_52w = df["저가"].rolling(252, min_periods=50).min()

    df["52주고가"] = high_52w
    df["52주저가"] = low_52w
    df["고가대비%"] = df["종가"] / high_52w * 100  # 52주 고가 대비 현재 위치
    df["저가대비%"] = df["종가"] / low_52w * 100   # 52주 저가 대비 현재 위치
    return df


# ============================================================
# VCP 패턴 (미너비니)
# ============================================================

def detect_vcp(df: pd.DataFrame, lookback: int = 60, min_contractions: int = 2) -> dict:
    """
    VCP (Volatility Contraction Pattern) 감지.
    - 최근 N일 구간에서 수축(pullback) 횟수와 각 수축률 계산
    - 수축률이 점점 작아지고 거래량이 감소하면 VCP 후보

    Returns:
        {
            "is_vcp": bool,
            "contractions": [수축률 리스트],
            "volume_trend": "감소" / "증가",
            "피봇": 최근 고점
        }
    """
    recent = df.tail(lookback).reset_index(drop=True)
    if len(recent) < 20:
        return {"is_vcp": False, "reason": "데이터 부족"}

    # 지역 고점/저점 감지 (5일 윈도우)
    highs = recent["고가"]
    lows = recent["저가"]

    contractions = []
    last_high_idx = 0
    for i in range(5, len(recent) - 5):
        if highs.iloc[i] == highs.iloc[max(0, i-5):i+6].max():
            # 지역 고점 발견
            if last_high_idx > 0:
                peak = highs.iloc[last_high_idx]
                trough = lows.iloc[last_high_idx:i].min()
                pullback = (peak - trough) / peak * 100
                if pullback > 2:  # 2% 이상 수축만 카운트
                    contractions.append(round(pullback, 2))
            last_high_idx = i

    # 거래량 추세 (최근 20일 vs 이전 20일)
    if len(recent) >= 40:
        recent_vol = recent["거래량"].tail(20).mean()
        prev_vol = recent["거래량"].iloc[-40:-20].mean()
        volume_trend = "감소" if recent_vol < prev_vol else "증가"
    else:
        volume_trend = "불명"

    # VCP 조건: 수축이 실질적으로 작아지고(단조감소 + 마지막이 첫 수축의 70% 이하), 거래량 감소.
    # 미너비니 원칙상 각 수축이 직전보다 명확히 작아야 하므로 단순 "≥"가 아닌 "실질 감소"를 요구.
    is_decreasing = False
    if len(contractions) >= min_contractions:
        strictly_down = all(contractions[i] > contractions[i+1] * 0.95 for i in range(len(contractions)-1))
        meaningful_shrink = contractions[-1] <= contractions[0] * 0.7
        is_decreasing = strictly_down and meaningful_shrink

    return {
        "is_vcp": is_decreasing and volume_trend == "감소",
        "contractions": contractions,
        "volume_trend": volume_trend,
        "피봇": float(highs.max()) if not highs.empty else None,
    }


# ============================================================
# 거래량 지표
# ============================================================

def volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """거래량 평균 및 비율."""
    df["거래량20MA"] = sma(df["거래량"], 20)
    df["거래량비율"] = df["거래량"] / df["거래량20MA"]  # 1.5 이상이면 평균 대비 50% 증가
    return df


# ============================================================
# 통합 함수 — 모든 지표 한번에 계산
# ============================================================

def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """
    OHLCV DataFrame에 모든 기술지표 추가.

    Args:
        df: columns = [날짜, 시가, 고가, 저가, 종가, 거래량]

    Returns:
        모든 지표가 추가된 DataFrame
    """
    df = df.copy()
    df = add_moving_averages(df)
    df = ichimoku(df)
    df = bollinger(df)
    df = macd(df)
    df = stochastic(df)
    df = williams_r(df)
    df = force_index(df)
    df = rsi(df)
    df = atr(df)
    df = adx(df)
    df = volatility_breakout(df, k=0.5)
    df = pivot_points(df)
    df = high_low_52week(df)
    df = volume_indicators(df)
    return df


if __name__ == "__main__":
    from pykrx import stock
    from datetime import datetime, timedelta

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=500)).strftime("%Y%m%d")
    df = stock.get_market_ohlcv(start, end, "005930")
    df = df.reset_index()
    df.columns = ["날짜", "시가", "고가", "저가", "종가", "거래량", "등락률"]

    result = compute_all(df)
    print("=== 최근 5일 주요 지표 ===")
    cols = ["날짜", "종가", "SMA20", "SMA60", "전환선", "기준선", "BB상단", "BB하단",
            "MACD", "RSI14", "Stoch_K", "52주고가", "거래량비율"]
    print(result[cols].tail(5).to_string())

    print("\n=== VCP 감지 ===")
    print(detect_vcp(df))
