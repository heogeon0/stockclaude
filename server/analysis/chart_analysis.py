"""
심층 차트 분석 헬퍼 — daily 보고서 자동 강화용.

stock-daily SKILL이 호출하면 '핵심 지표 스냅샷'을 대체 또는 확장.
모든 함수는 compute_all(df) 결과 DataFrame을 입력받음.
"""
from __future__ import annotations

import pandas as pd
import numpy as np


# ============================================================
# 1. 이평선 클러스터 분석
# ============================================================

def sma_cluster(df: pd.DataFrame) -> dict:
    """
    5개 이평선(20/60/120/200 + 현재가)의 수렴/발산 패턴 분석.

    Returns:
        {
            "정배열": bool,
            "클러스터_폭": float (%, 이평 최대-최소 / 종가),
            "이격률": {"SMA20": float, ...},
            "해석": str,
        }
    """
    last = df.iloc[-1]
    price = float(last["종가"])

    smas = {}
    for sma_col in ("SMA5", "SMA20", "SMA60", "SMA120", "SMA200"):
        if sma_col in last.index and not pd.isna(last[sma_col]):
            smas[sma_col] = float(last[sma_col])

    if len(smas) < 3:
        return {"error": "이평선 데이터 부족"}

    vals = list(smas.values())
    정배열 = all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1)) and price > vals[0]
    역배열 = all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1)) and price < vals[0]

    # 장기 이평 4개 클러스터 폭 (SMA20/60/120/200)
    long_smas = [v for k, v in smas.items() if k != "SMA5"]
    cluster_width = (max(long_smas) - min(long_smas)) / price * 100

    # 이격률 (현재가 vs 각 이평)
    이격률 = {k: round((price / v - 1) * 100, 2) for k, v in smas.items()}

    # 해석
    if 정배열 and cluster_width > 5:
        해석 = "정배열 + 확산 (장기 강세 지속 중)"
    elif 정배열 and cluster_width < 2:
        해석 = "정배열 but 이평 수렴 (장기 횡보 후 방금 돌파 — 방향성 취약)"
    elif 역배열:
        해석 = "역배열 (장기 하락 추세)"
    elif cluster_width < 2:
        해석 = "이평 극단 수렴 (변동성 압축 → 돌파 임박)"
    else:
        해석 = "혼조 (추세 불명확)"

    return {
        "정배열": 정배열,
        "역배열": 역배열,
        "클러스터_폭_pct": round(cluster_width, 2),
        "이격률": 이격률,
        "SMA_값": {k: round(v, 2) for k, v in smas.items()},
        "해석": 해석,
    }


# ============================================================
# 2. 기간별 수익률
# ============================================================

def period_returns(df: pd.DataFrame) -> dict:
    """5/10/20/60/120/252일 누적 수익률."""
    out = {}
    periods = {"5일": 5, "10일": 10, "20일": 20, "3개월": 60, "6개월": 120, "12개월": 252}
    for label, days in periods.items():
        if len(df) > days:
            ret = (df.iloc[-1]["종가"] / df.iloc[-days]["종가"] - 1) * 100
            out[label] = round(ret, 2)
        else:
            out[label] = None
    return out


# ============================================================
# 3. RSI/Stoch 최근 추이 (14일)
# ============================================================

def oscillator_trend(df: pd.DataFrame, n: int = 14) -> dict:
    """최근 N일 RSI/Stoch 추이 + 턴오버 감지."""
    recent = df.tail(n)
    rsi = recent["RSI14"].dropna()
    stoch_k = recent.get("Stoch_K", pd.Series(dtype=float)).dropna()

    rsi_series = [(pd.to_datetime(d).strftime("%m-%d"), round(float(r), 1))
                  for d, r in zip(recent["날짜"], rsi) if not pd.isna(r)]

    result = {
        "RSI_최근": rsi_series[-5:] if rsi_series else [],
        "RSI_현재": round(float(rsi.iloc[-1]), 2) if len(rsi) else None,
        "RSI_3일전": round(float(rsi.iloc[-4]), 2) if len(rsi) >= 4 else None,
    }

    # 과매수/과매도 구간 일수
    if len(rsi) > 0:
        overbought = (rsi >= 70).sum()
        oversold = (rsi <= 30).sum()
        extreme_ob = (rsi >= 80).sum()
        result["과매수_일수(70+)"] = int(overbought)
        result["극과매수_일수(80+)"] = int(extreme_ob)
        result["과매도_일수(30-)"] = int(oversold)

    # Stoch 턴오버
    if len(stoch_k) >= 2 and "Stoch_D" in recent.columns:
        stoch_d = recent["Stoch_D"].dropna()
        if len(stoch_d) >= 2:
            k_now, d_now = float(stoch_k.iloc[-1]), float(stoch_d.iloc[-1])
            k_prev, d_prev = float(stoch_k.iloc[-2]), float(stoch_d.iloc[-2])
            if k_prev > d_prev and k_now < d_now:
                result["Stoch_신호"] = "데드크로스 (매도 전환)"
            elif k_prev < d_prev and k_now > d_now:
                result["Stoch_신호"] = "골든크로스 (매수 전환)"
            elif k_now < d_now:
                result["Stoch_신호"] = "K<D 하락 추세"
            else:
                result["Stoch_신호"] = "K>D 상승 추세"
            result["Stoch_K"] = round(k_now, 1)
            result["Stoch_D"] = round(d_now, 1)

    return result


# ============================================================
# 4. 캔들 패턴 (최근 5일)
# ============================================================

def candle_patterns(df: pd.DataFrame, n: int = 5) -> list[dict]:
    """최근 N일 캔들 패턴 식별."""
    recent = df.tail(n)
    patterns = []
    for _, row in recent.iterrows():
        o, h, l, c = float(row["시가"]), float(row["고가"]), float(row["저가"]), float(row["종가"])
        body = abs(c - o)
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l
        range_ = h - l if h > l else 1e-9
        body_pct = body / range_
        upper_pct = upper_wick / range_
        lower_pct = lower_wick / range_

        is_bullish = c > o
        pattern = []

        if body_pct < 0.1 and range_ > 0:
            pattern.append("도지 (매수/매도 균형)")
        if upper_pct > 0.5:
            pattern.append(f"윗꼬리 (매도압력 {upper_pct*100:.0f}%)")
        if lower_pct > 0.5:
            pattern.append(f"아랫꼬리 (매수반발 {lower_pct*100:.0f}%)")
        if body_pct > 0.7 and is_bullish:
            pattern.append("장대양봉")
        if body_pct > 0.7 and not is_bullish:
            pattern.append("장대음봉")
        if not pattern:
            pattern.append("평범 " + ("양봉" if is_bullish else "음봉"))

        patterns.append({
            "날짜": pd.to_datetime(row["날짜"]).strftime("%m-%d"),
            "종가": round(c, 2),
            "변동률": round((c / o - 1) * 100, 2) if o else 0,
            "패턴": " + ".join(pattern),
        })
    return patterns


# ============================================================
# 5. 거래량 추세 (15일)
# ============================================================

def volume_trend(df: pd.DataFrame, n: int = 15) -> dict:
    """최근 N일 거래량 추세 + 급증/급감 감지."""
    recent = df.tail(n)
    vols = recent["거래량"].astype(float)
    avg = vols.mean()
    latest = vols.iloc[-1]

    # 추세: 최근 5일 vs 이전 10일
    if len(vols) >= 15:
        recent_5 = vols.tail(5).mean()
        prior_10 = vols.head(10).mean()
        trend_pct = (recent_5 / prior_10 - 1) * 100 if prior_10 else 0
    else:
        trend_pct = 0

    # 급증/급감 일수
    spike = int(((vols / avg) >= 1.5).sum())
    plunge = int(((vols / avg) <= 0.5).sum())

    return {
        "평균거래량": int(avg),
        "최근5일_vs_이전10일": round(trend_pct, 1),
        "급증일수(1.5x+)": spike,
        "급감일수(0.5x-)": plunge,
        "현재비율": round(latest / avg, 2) if avg else 0,
        "해석": (
            "상승 확증 (거래량 증가)" if trend_pct > 20 else
            "매수 에너지 약화 (거래량 감소)" if trend_pct < -20 else
            "중립 (정상 거래량)"
        ),
    }


# ============================================================
# 6. 볼린저 밴드 + 스퀴즈
# ============================================================

def bollinger_analysis(df: pd.DataFrame) -> dict:
    """볼린저 밴드 위치 + 스퀴즈 감지."""
    last = df.iloc[-1]
    upper = last.get("BB_Upper")
    mid = last.get("BB_Mid")
    lower = last.get("BB_Lower")
    price = float(last["종가"])

    if not all(v is not None and not pd.isna(v) and v > 0 for v in (upper, mid, lower)):
        return {"error": "볼린저 데이터 부족"}

    upper, mid, lower = float(upper), float(mid), float(lower)
    band_width = (upper - lower) / mid * 100  # 대역폭

    # 위치
    if price > upper:
        position = "상단 이탈 (극과열)"
    elif price > mid:
        position = f"상단대 (중심선 +{(price/mid - 1)*100:.1f}%)"
    elif price < lower:
        position = "하단 이탈 (극과매도)"
    else:
        position = f"하단대 (중심선 {(price/mid - 1)*100:.1f}%)"

    # 스퀴즈: 과거 60일 평균 대비 band_width
    prior_bw = ((df["BB_Upper"] - df["BB_Lower"]) / df["BB_Mid"] * 100).tail(60).mean()
    squeeze = band_width < prior_bw * 0.7 if prior_bw else False

    return {
        "상단": round(upper, 2),
        "중심": round(mid, 2),
        "하단": round(lower, 2),
        "대역폭_pct": round(band_width, 2),
        "위치": position,
        "스퀴즈": squeeze,
        "스퀴즈_해석": "변동성 극축소 → 돌파 임박" if squeeze else "정상 변동성",
    }


# ============================================================
# 7. MACD 히스토그램 추세
# ============================================================

def macd_trend(df: pd.DataFrame, n: int = 10) -> dict:
    """최근 N일 MACD 히스토그램 변화."""
    col = "MACD히스토" if "MACD히스토" in df.columns else ("MACD_Hist" if "MACD_Hist" in df.columns else None)
    if col is None:
        return {"error": "MACD 데이터 없음"}
    hist = df[col].tail(n).dropna()
    if len(hist) < 3:
        return {"error": "MACD 데이터 부족"}

    recent = float(hist.iloc[-1])
    prev = float(hist.iloc[-2])
    trend = hist.diff().tail(5).mean()

    # 0축 돌파 감지
    zero_cross_up = any((hist.iloc[i-1] < 0 and hist.iloc[i] >= 0) for i in range(1, len(hist)))
    zero_cross_down = any((hist.iloc[i-1] > 0 and hist.iloc[i] <= 0) for i in range(1, len(hist)))

    return {
        "현재_히스토": round(recent, 2),
        "1일전_히스토": round(prev, 2),
        "5일_평균변화": round(float(trend), 2) if not pd.isna(trend) else 0,
        "0축_상향돌파_최근10일": zero_cross_up,
        "0축_하향돌파_최근10일": zero_cross_down,
        "해석": (
            "강한 상승 모멘텀 (히스토 증가 + 양수)" if recent > 0 and trend > 0 else
            "상승 약화 (양수 but 감소)" if recent > 0 and trend < 0 else
            "강한 하락 모멘텀" if recent < 0 and trend < 0 else
            "하락 약화 (음수 but 증가)" if recent < 0 and trend > 0 else "중립"
        ),
    }


# ============================================================
# 8. 저항 시도 횟수 카운트
# ============================================================

def resistance_tests(df: pd.DataFrame, tolerance_pct: float = 1.5, lookback: int = 60) -> dict:
    """최근 N일 고가 근처 터치 횟수 (돌파 실패 카운트)."""
    recent = df.tail(lookback)
    high_52w = float(df["고가"].tail(252).max()) if len(df) >= 252 else float(recent["고가"].max())
    recent_high = float(recent["고가"].max())

    # 기준: 최근 60일 고가의 tolerance_pct% 이내 터치한 날 개수
    threshold = recent_high * (1 - tolerance_pct / 100)
    touches = int((recent["고가"] >= threshold).sum())

    # 52주 고가 돌파 여부
    current = float(df.iloc[-1]["종가"])
    near_52w = (current / high_52w - 1) * 100

    return {
        "최근60일_고가": round(recent_high, 2),
        "52주_고가": round(high_52w, 2),
        "52주근접도_pct": round(near_52w, 2),
        "고가_터치_횟수(60일)": touches,
        "해석": (
            "52주 신고가 돌파 성공 ✅" if current > high_52w else
            f"최근 {touches}회 고가 터치 → 저항 {touches}회 실패" if touches >= 3 else
            "정상 변동"
        ),
    }


# ============================================================
# 9. 주봉 정합성 (멀티 타임프레임)
# ============================================================

def weekly_alignment(df: pd.DataFrame) -> dict:
    """일봉 + 주봉 추세 정합성 확인."""
    if len(df) < 50:
        return {"error": "데이터 부족"}

    # 주봉 resample
    df_w = df.copy()
    df_w["날짜"] = pd.to_datetime(df_w["날짜"])
    df_w = df_w.set_index("날짜")
    weekly = df_w["종가"].resample("W").last().dropna()
    if len(weekly) < 20:
        return {"error": "주봉 데이터 부족"}

    wk_sma10 = weekly.rolling(10).mean().iloc[-1]
    wk_sma20 = weekly.rolling(20).mean().iloc[-1]
    wk_last = weekly.iloc[-1]

    wk_trend = "상승" if wk_last > wk_sma10 > wk_sma20 else ("하락" if wk_last < wk_sma10 < wk_sma20 else "횡보")

    # 일봉 추세
    daily_last = float(df.iloc[-1]["종가"])
    daily_sma20 = float(df.iloc[-1].get("SMA20", 0))
    daily_sma60 = float(df.iloc[-1].get("SMA60", 0))
    daily_trend = "상승" if daily_last > daily_sma20 > daily_sma60 else ("하락" if daily_last < daily_sma20 < daily_sma60 else "횡보")

    return {
        "일봉_추세": daily_trend,
        "주봉_추세": wk_trend,
        "정합성": wk_trend == daily_trend,
        "해석": (
            "다중 시계 상승 정합 (강력 매수)" if wk_trend == "상승" and daily_trend == "상승" else
            "다중 시계 하락 정합 (강력 매도)" if wk_trend == "하락" and daily_trend == "하락" else
            "일봉/주봉 엇갈림 (단기 조정 or 반등 초입)"
        ),
    }


# ============================================================
# 통합 호출
# ============================================================

def chart_snapshot(df: pd.DataFrame) -> dict:
    """daily 보고서용 통합 차트 분석 스냅샷."""
    return {
        "이평선_클러스터": sma_cluster(df),
        "기간별_수익률": period_returns(df),
        "RSI_Stoch_추이": oscillator_trend(df),
        "캔들_패턴_최근5일": candle_patterns(df, 5),
        "거래량_추세": volume_trend(df, 15),
        "볼린저": bollinger_analysis(df),
        "MACD_추세": macd_trend(df),
        "저항_시도": resistance_tests(df),
        "주봉_정합": weekly_alignment(df),
    }


def format_snapshot_md(snapshot: dict) -> str:
    """차트 스냅샷을 마크다운 섹션으로 포맷."""
    out = []

    # 1. 이평선 클러스터
    sc = snapshot.get("이평선_클러스터", {})
    if "error" not in sc:
        out.append("## 🧭 이평선 클러스터")
        out.append(f"- **{sc.get('해석')}**")
        out.append(f"- 정배열: {'✅' if sc.get('정배열') else '❌'}, 클러스터 폭 {sc.get('클러스터_폭_pct')}%")
        for k, v in sc.get("이격률", {}).items():
            sma_v = sc.get("SMA_값", {}).get(k)
            out.append(f"  - {k} ${sma_v} (현재가 대비 {v:+.2f}%)")
        out.append("")

    # 2. 기간별 수익률
    pr = snapshot.get("기간별_수익률", {})
    out.append("## 📊 기간별 수익률")
    for label, v in pr.items():
        if v is not None:
            emoji = "🟢" if v > 0 else "🔴" if v < 0 else "⚪"
            out.append(f"- {label}: {emoji} {v:+.2f}%")
    out.append("")

    # 3. RSI/Stoch
    ot = snapshot.get("RSI_Stoch_추이", {})
    out.append("## 📈 오실레이터 추이 (RSI/Stoch)")
    out.append(f"- RSI14 현재: **{ot.get('RSI_현재')}** (3일전 {ot.get('RSI_3일전')})")
    out.append(f"- 극과매수(80+) 일수: {ot.get('극과매수_일수(80+)', 0)}/14")
    out.append(f"- Stoch K/D: {ot.get('Stoch_K')} / {ot.get('Stoch_D')} — {ot.get('Stoch_신호', 'N/A')}")
    if ot.get("RSI_최근"):
        last5 = ", ".join(f"{d}:{v}" for d, v in ot["RSI_최근"])
        out.append(f"- 최근 5일 RSI: {last5}")
    out.append("")

    # 4. 캔들 패턴
    cp = snapshot.get("캔들_패턴_최근5일", [])
    if cp:
        out.append("## 🕯️ 최근 5일 캔들 패턴")
        for c in cp:
            out.append(f"- {c['날짜']} ${c['종가']} ({c['변동률']:+.2f}%): {c['패턴']}")
        out.append("")

    # 5. 거래량 추세
    vt = snapshot.get("거래량_추세", {})
    out.append("## 📊 거래량 추세 (15일)")
    out.append(f"- **{vt.get('해석')}**")
    out.append(f"- 최근5일 vs 이전10일: {vt.get('최근5일_vs_이전10일')}%")
    out.append(f"- 현재 비율: {vt.get('현재비율')}x, 급증 {vt.get('급증일수(1.5x+)')}일 / 급감 {vt.get('급감일수(0.5x-)')}일")
    out.append("")

    # 6. 볼린저
    bb = snapshot.get("볼린저", {})
    if "error" not in bb:
        out.append("## 📏 볼린저 밴드")
        out.append(f"- 위치: {bb.get('위치')}")
        out.append(f"- 상단 ${bb.get('상단')} / 중심 ${bb.get('중심')} / 하단 ${bb.get('하단')}")
        out.append(f"- 대역폭: {bb.get('대역폭_pct')}% — {'🔔 ' + bb.get('스퀴즈_해석') if bb.get('스퀴즈') else bb.get('스퀴즈_해석')}")
        out.append("")

    # 7. MACD
    mt = snapshot.get("MACD_추세", {})
    if "error" not in mt:
        out.append("## 🎯 MACD 히스토그램")
        out.append(f"- **{mt.get('해석')}**")
        out.append(f"- 현재 {mt.get('현재_히스토')} / 1일전 {mt.get('1일전_히스토')} / 5일 평균변화 {mt.get('5일_평균변화')}")
        if mt.get("0축_상향돌파_최근10일"):
            out.append("- ⬆ 최근 10일 내 0축 상향 돌파 (모멘텀 전환)")
        if mt.get("0축_하향돌파_최근10일"):
            out.append("- ⬇ 최근 10일 내 0축 하향 돌파 (모멘텀 약화)")
        out.append("")

    # 8. 저항
    rt = snapshot.get("저항_시도", {})
    out.append("## 🏔️ 52주 고가 / 저항")
    out.append(f"- **{rt.get('해석')}**")
    out.append(f"- 52주 고가: ${rt.get('52주_고가')} (근접도 {rt.get('52주근접도_pct')}%)")
    out.append(f"- 최근 60일 고가: ${rt.get('최근60일_고가')} (터치 {rt.get('고가_터치_횟수(60일)')}회)")
    out.append("")

    # 9. 주봉 정합
    wa = snapshot.get("주봉_정합", {})
    if "error" not in wa:
        out.append("## 🔀 멀티 타임프레임")
        out.append(f"- **{wa.get('해석')}**")
        out.append(f"- 일봉 {wa.get('일봉_추세')} / 주봉 {wa.get('주봉_추세')} / 정합성 {'✅' if wa.get('정합성') else '❌'}")
        out.append("")

    return "\n".join(out)
