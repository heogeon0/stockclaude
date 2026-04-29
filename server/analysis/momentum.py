"""
모멘텀 분석 — 종목별 점수 + 상대 랭킹 + Dual Momentum 시그널

6차원 모멘텀 스코어 (0~100점):
  1. 12-1 수익률 (Jegadeesh-Titman)          — 최대 25
  2. 52주 고가 근접도 (George-Hwang)          — 최대 20
  3. ADX 추세 강도                            — 최대 15
  4. Sharpe 조정 수익률 (변동성 조정)         — 최대 15
  5. MA 정렬 점수 (완전 정배열 만점)           — 최대 15
  6. 거래량 동반 (최근 20일 vs 60일)           — 최대 10

사용:
    from server.analysis.momentum import momentum_score, cross_sectional_ranking

    df = compute_all(get_market_ohlcv(...))
    score = momentum_score(df)  # {'점수': 78, '세부': {...}}

    codes = ['005930', '000660', ...]
    ranking = cross_sectional_ranking(codes, lookback=252)
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import numpy as np


DEFAULT_WEIGHTS = {
    "12_1_수익률": 0.25,
    "52주고가_근접도": 0.20,
    "ADX_추세": 0.15,
    "Sharpe_조정": 0.15,
    "MA_정렬": 0.15,
    "거래량_동반": 0.10,
}


def _momentum_12_1(df: pd.DataFrame) -> tuple[float, float]:
    """
    Jegadeesh-Titman 12-1 모멘텀.
    = 12개월 전 ~ 1개월 전 종가 수익률 (가장 최근 1개월 제외)
    최근 1개월은 평균회귀 편향 있어 제외.

    Returns: (점수 0~25, 원값 수익률 pct)
    """
    if len(df) < 252:
        # 데이터 부족 — 가용 기간으로 fallback
        if len(df) < 42:
            return 0, 0
        start = df.iloc[0]["종가"]
        end = df.iloc[-21]["종가"]
    else:
        start = df.iloc[-252]["종가"]
        end = df.iloc[-21]["종가"]

    ret = (end / start - 1) * 100
    # 점수: -20%=0, 0%=10, 30%=20, 60%+=25
    if ret >= 60:
        pts = 25
    elif ret >= 30:
        pts = 20 + (ret - 30) / 30 * 5
    elif ret >= 0:
        pts = 10 + ret / 30 * 10
    elif ret >= -20:
        pts = 10 + ret / 20 * 10  # -20%=0점
    else:
        pts = 0
    return round(max(0, pts), 1), round(ret, 1)


def _high_52w_proximity(df: pd.DataFrame) -> tuple[float, float]:
    """
    52주 고가 근접도 (George-Hwang).
    고가 대비 -5%~0%=만점, -20%=10점, -40%+=0점

    Returns: (점수 0~20, 이격 pct)
    """
    last = df.iloc[-1]
    high_52w = last.get("52주고가", 0)
    if not high_52w or pd.isna(high_52w):
        return 0, 0
    proximity = last["종가"] / high_52w - 1  # 음수 (-0.05 = 5% 아래)
    proximity_pct = proximity * 100

    if proximity_pct >= -2:
        pts = 20
    elif proximity_pct >= -10:
        pts = 20 + (proximity_pct + 2) / 8 * -10  # -2%=20, -10%=10
    elif proximity_pct >= -30:
        pts = 10 + (proximity_pct + 10) / 20 * -10
    else:
        pts = 0
    return round(max(0, pts), 1), round(proximity_pct, 1)


def _adx_strength(df: pd.DataFrame) -> tuple[float, float]:
    """
    ADX 추세 강도.
    ADX<15=0, 15~25=7, 25~35=12, 35+=15

    Returns: (점수 0~15, ADX 원값)
    """
    last = df.iloc[-1]
    adx = last.get("ADX14")
    plus_di = last.get("+DI14", 0)
    minus_di = last.get("-DI14", 0)

    if adx is None or pd.isna(adx):
        return 0, 0

    # 상승 추세에만 점수 (+DI > -DI)
    if plus_di <= minus_di:
        # 하락 추세에서는 모멘텀 점수 깎음
        return 0, round(adx, 1)

    if adx >= 35:
        pts = 15
    elif adx >= 25:
        pts = 10 + (adx - 25) / 10 * 5
    elif adx >= 15:
        pts = 5 + (adx - 15) / 10 * 5
    else:
        pts = 0
    return round(max(0, pts), 1), round(adx, 1)


def _sharpe_adjusted(df: pd.DataFrame, lookback: int = 126) -> tuple[float, float]:
    """
    리스크 조정 수익률 (연율화 Sharpe-like).
    (기간 수익률 / 기간 연율 표준편차)
    >2.0=15, 1.0=10, 0=5, 음수=0

    Returns: (점수 0~15, Sharpe 값)
    """
    if len(df) < lookback + 1:
        return 0, 0
    recent = df.iloc[-lookback:]
    returns = recent["종가"].pct_change().dropna()
    if len(returns) < 30 or returns.std() == 0:
        return 0, 0

    period_return = (recent.iloc[-1]["종가"] / recent.iloc[0]["종가"] - 1)
    annualized_vol = returns.std() * np.sqrt(252)
    sharpe = period_return * (252 / lookback) / annualized_vol  # 연율화

    if sharpe >= 2.0:
        pts = 15
    elif sharpe >= 1.0:
        pts = 10 + (sharpe - 1.0) * 5
    elif sharpe >= 0:
        pts = 5 + sharpe * 5
    else:
        pts = max(0, 5 + sharpe * 5)
    return round(max(0, pts), 1), round(sharpe, 2)


def _ma_alignment(df: pd.DataFrame) -> tuple[float, str]:
    """
    이평선 완전 정배열 점수.
    5 > 20 > 60 > 120 > 200 모두 충족 = 15점
    부분 충족은 충족 수에 비례.

    Returns: (점수 0~15, 상태)
    """
    last = df.iloc[-1]
    mas = [last.get(f"SMA{p}") for p in [5, 20, 60, 120, 200]]
    if any(pd.isna(m) or m is None for m in mas):
        return 0, "데이터 부족"

    price = last["종가"]
    conditions = [
        price > mas[0],      # 가격 > 5MA
        mas[0] > mas[1],     # 5 > 20
        mas[1] > mas[2],     # 20 > 60
        mas[2] > mas[3],     # 60 > 120
        mas[3] > mas[4],     # 120 > 200
    ]
    met = sum(conditions)
    pts = met / 5 * 15

    if met == 5:
        status = "완전 정배열"
    elif met >= 3:
        status = "부분 정배열"
    elif met <= 1:
        status = "역배열"
    else:
        status = "혼조"

    return round(pts, 1), status


def _volume_confirmation(df: pd.DataFrame) -> tuple[float, float]:
    """
    거래량 동반 확인.
    최근 20일 평균 / 60일 평균 비율.
    >1.3=10, 1.0~1.3=7, 0.7~1.0=3, <0.7=0

    Returns: (점수 0~10, 비율)
    """
    if len(df) < 60:
        return 0, 0
    recent_20 = df["거래량"].iloc[-20:].mean()
    prior_60 = df["거래량"].iloc[-60:-20].mean()
    if prior_60 == 0:
        return 0, 0
    ratio = recent_20 / prior_60

    if ratio >= 1.3:
        pts = 10
    elif ratio >= 1.0:
        pts = 7 + (ratio - 1.0) / 0.3 * 3
    elif ratio >= 0.7:
        pts = 3 + (ratio - 0.7) / 0.3 * 4
    else:
        pts = max(0, ratio / 0.7 * 3)
    return round(max(0, pts), 1), round(ratio, 2)


def momentum_score(df: pd.DataFrame, weights: Optional[dict] = None) -> dict:
    """
    compute_all()된 DataFrame 받아 6차원 모멘텀 점수 반환.

    Args:
        df: compute_all() 결과 DataFrame (52주고가/ADX/이평선 등 필수)
        weights: 6차원 가중치 (None이면 DEFAULT_WEIGHTS 사용)

    Returns:
        {"점수": 0~100, "세부": {차원별 (점수, 원값/상태)}, "등급": str, "해석": str}
    """
    w = weights or DEFAULT_WEIGHTS

    pts_12_1, val_12_1 = _momentum_12_1(df)
    pts_high, val_high = _high_52w_proximity(df)
    pts_adx, val_adx = _adx_strength(df)
    pts_sharpe, val_sharpe = _sharpe_adjusted(df)
    pts_ma, status_ma = _ma_alignment(df)
    pts_vol, val_vol = _volume_confirmation(df)

    total = round(pts_12_1 + pts_high + pts_adx + pts_sharpe + pts_ma + pts_vol, 1)

    if total >= 80:
        grade = "A+"
        interp = "강한 모멘텀 — Top 10% 후보"
    elif total >= 65:
        grade = "A"
        interp = "견조한 모멘텀 — 유지/진입 고려"
    elif total >= 50:
        grade = "B"
        interp = "중립 모멘텀 — 추가 확인 필요"
    elif total >= 35:
        grade = "C"
        interp = "약한 모멘텀 — 매수 대기"
    else:
        grade = "D"
        interp = "모멘텀 부재 — 회피"

    return {
        "점수": total,
        "등급": grade,
        "해석": interp,
        "세부": {
            "12_1_수익률": {"점수": pts_12_1, "값": f"{val_12_1}%"},
            "52주고가_근접도": {"점수": pts_high, "값": f"{val_high}%"},
            "ADX_추세": {"점수": pts_adx, "값": val_adx},
            "Sharpe_조정": {"점수": pts_sharpe, "값": val_sharpe},
            "MA_정렬": {"점수": pts_ma, "상태": status_ma},
            "거래량_동반": {"점수": pts_vol, "비율": val_vol},
        },
    }


# ============================================================
# Cross-sectional (상대) 랭킹
# ============================================================

def cross_sectional_ranking(codes: list[str], lookback: int = 252,
                             lookback_days: int = 400, market: str = "kr") -> pd.DataFrame:
    """
    종목군 전체 모멘텀 Z-score 순위.

    Args:
        codes: 6자리 종목코드 리스트
        lookback: 모멘텀 산정 기간 (영업일)
        lookback_days: pykrx에서 가져올 일수 (지표 안정화 여유 포함)

    Returns:
        DataFrame [종목코드, 점수, Z_score, 순위, 등급, ...]
    """
    from .indicators import compute_all

    if market == "us":
        from scrapers.us.adapter import fetch_ohlcv as _us_fetch
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        def _fetch(c): return _us_fetch(c, start, end)
    else:
        from pykrx import stock as krx
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y%m%d")
        def _fetch(c): return krx.get_market_ohlcv(start, end, c)

    rows = []
    for code in codes:
        try:
            df = _fetch(code)
            if df is None or len(df) < 60:
                continue
            df = compute_all(df)
            result = momentum_score(df)
            rows.append({
                "종목코드": code,
                "점수": result["점수"],
                "등급": result["등급"],
                "12_1_수익률": result["세부"]["12_1_수익률"]["값"],
                "52주고가_근접도": result["세부"]["52주고가_근접도"]["값"],
                "ADX": result["세부"]["ADX_추세"]["값"],
            })
        except Exception as e:
            rows.append({"종목코드": code, "오류": str(e)})

    if not rows:
        return pd.DataFrame()

    rdf = pd.DataFrame(rows)
    if "점수" in rdf.columns:
        valid = rdf.dropna(subset=["점수"])
        if len(valid) >= 2 and valid["점수"].std() > 0:
            rdf["Z_score"] = (rdf["점수"] - valid["점수"].mean()) / valid["점수"].std()
            rdf["Z_score"] = rdf["Z_score"].round(2)
        else:
            rdf["Z_score"] = 0
        rdf["순위"] = rdf["점수"].rank(ascending=False, method="min").astype("Int64")
        rdf = rdf.sort_values("점수", ascending=False).reset_index(drop=True)

    return rdf


# ============================================================
# Dual Momentum (Gary Antonacci)
# ============================================================

def dual_momentum_signal(df: pd.DataFrame, benchmark_df: pd.DataFrame,
                         risk_free_annual: float = 0.035) -> dict:
    """
    Dual Momentum: 절대(자기 12M > 무위험) + 상대(벤치마크 초과) 조합.

    Args:
        df: 종목 OHLCV (compute_all 불필요, 종가만 사용)
        benchmark_df: KOSPI 지수 OHLCV (동일 기간)
        risk_free_annual: 연 무위험 수익률 (기본 3.5% — 한국 3년 국채)

    Returns:
        {
            "시그널": "Buy" | "Cash",
            "절대_모멘텀": bool, "절대_수익률_12M": float,
            "상대_모멘텀": bool, "벤치마크_초과_12M": float,
            "해석": str,
        }
    """
    if len(df) < 252 or len(benchmark_df) < 252:
        return {"오류": "12개월 데이터 부족", "시그널": "Cash"}

    stock_ret = df.iloc[-1]["종가"] / df.iloc[-252]["종가"] - 1
    bench_ret = benchmark_df.iloc[-1]["종가"] / benchmark_df.iloc[-252]["종가"] - 1

    absolute_momentum = stock_ret > risk_free_annual
    relative_momentum = stock_ret > bench_ret

    if absolute_momentum and relative_momentum:
        signal = "Buy"
        interp = f"절대(+{stock_ret*100:.1f}%) + 상대(벤치 대비 +{(stock_ret-bench_ret)*100:.1f}%p) 모두 양수"
    elif absolute_momentum:
        signal = "Cash"
        interp = f"절대는 양수이나 벤치마크 하회 — 다른 종목 찾기"
    elif relative_momentum:
        signal = "Cash"
        interp = f"벤치 상회하나 자체 수익률이 무위험 이하 — 하락장 신호"
    else:
        signal = "Cash"
        interp = "절대/상대 모두 약세 — 현금 보유"

    return {
        "시그널": signal,
        "절대_모멘텀": absolute_momentum,
        "절대_수익률_12M": round(stock_ret * 100, 1),
        "상대_모멘텀": relative_momentum,
        "벤치마크_초과_12M": round((stock_ret - bench_ret) * 100, 1),
        "무위험_수익률": round(risk_free_annual * 100, 1),
        "해석": interp,
    }


# ============================================================
# Momentum Decay — 모멘텀 시작 시점부터 경과일
# ============================================================

def momentum_decay(df: pd.DataFrame, lookback: int = 252) -> dict:
    """
    현재 상승 모멘텀이 시작된 시점부터의 경과일 + 피로도 판정.

    방법: SMA60 돌파 시점을 모멘텀 시작으로 간주.
    180일 초과 → 피로 경계.

    Returns:
        {"모멘텀_시작일": str, "경과일": int, "피로도": str, "해석": str}
    """
    if len(df) < lookback:
        return {"오류": "데이터 부족"}

    # SMA60 위에서 일관되게 유지된 최장 구간
    above_ma = df["종가"] > df["SMA60"]
    if not above_ma.iloc[-1]:
        return {"경과일": 0, "피로도": "모멘텀 부재", "해석": "현재 SMA60 아래"}

    # 마지막에 SMA60 아래였던 시점 찾기
    for i in range(len(df) - 2, max(0, len(df) - lookback), -1):
        if not above_ma.iloc[i]:
            start_idx = i + 1
            break
    else:
        start_idx = len(df) - lookback

    start_date = df.index[start_idx]
    elapsed = len(df) - 1 - start_idx

    if elapsed < 30:
        fatigue = "초기"
        interp = "모멘텀 초입 — 진입 적기"
    elif elapsed < 90:
        fatigue = "중기"
        interp = "건강한 모멘텀 지속 중"
    elif elapsed < 180:
        fatigue = "후기"
        interp = "모멘텀 성숙 — 신규 진입 신중"
    else:
        fatigue = "경계"
        interp = f"{elapsed}일째 지속 — 소멸 임박 가능성 (>180일 통계적 피크)"

    return {
        "모멘텀_시작일": str(start_date)[:10] if hasattr(start_date, '__str__') else str(start_date),
        "경과일": elapsed,
        "피로도": fatigue,
        "해석": interp,
    }


if __name__ == "__main__":
    import json
    from pykrx import stock as krx
    from indicators import compute_all

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=400)).strftime("%Y%m%d")

    # 단일 종목 스코어
    df = krx.get_market_ohlcv(start, end, "005930")
    df = compute_all(df)
    result = momentum_score(df)
    print("=== 삼성전자 모멘텀 ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 5종목 상대 랭킹
    codes = ["005930", "000660", "298040", "036570", "000720"]
    print("\n=== 5종목 상대 랭킹 ===")
    ranking = cross_sectional_ranking(codes, lookback=252)
    print(ranking.to_string())

    # Dual Momentum
    kospi = krx.get_index_ohlcv(start, end, "1001")
    kospi = kospi.rename(columns={col: col for col in kospi.columns})
    dual = dual_momentum_signal(df, kospi)
    print("\n=== 삼성전자 Dual Momentum ===")
    print(json.dumps(dual, indent=2, ensure_ascii=False))

    # Decay
    print("\n=== 모멘텀 피로도 ===")
    print(momentum_decay(df))
