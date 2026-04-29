"""
전략별 백테스트 모듈
- 과거 N일간 매일 시그널을 재생성하고, 시그널 발생 후 수익률 추적
- 전략별 승률/평균수익률/최대손실 산출
- 캐싱: reports/stocks/{종목}/backtest.md에 저장, 7일 이내면 재사용
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
from .indicators import compute_all
from .signals import analyze_all, STRATEGY_WEIGHTS

REPORTS_DIR = Path(__file__).parent.parent / "reports" / "stocks"
CACHE_DAYS = 7  # 캐시 유효 기간


def backtest_stock(df_raw: pd.DataFrame, lookback: int = 200,
                   hold_days: list[int] | None = None) -> dict:
    """
    단일 종목 백테스트.

    Args:
        df_raw: pykrx OHLCV DataFrame (compute_all 전)
        lookback: 백테스트 기간 (최근 N 영업일)
        hold_days: 수익률 추적 기간 리스트 (기본 [5, 10, 20])

    Returns:
        {
            "전략별": {전략명: {hold_days별 승률/평균수익률/횟수}},
            "복합시그널": {조합: 승률},
            "기간": {"시작": str, "종료": str, "영업일": int},
        }
    """
    if hold_days is None:
        hold_days = [5, 10, 20]

    df = compute_all(df_raw.copy())
    max_hold = max(hold_days)

    # 시그널 재생성 가능한 구간: lookback일 전 ~ (끝 - max_hold)일
    total_rows = len(df)
    start_idx = max(total_rows - lookback - max_hold, 200)  # 지표 안정화 200일 필요
    end_idx = total_rows - max_hold  # 수익률 추적 공간 확보

    if start_idx >= end_idx:
        return {"error": "데이터 부족 — 최소 400일 필요"}

    # 전략별 시그널 기록 수집
    records = []

    for i in range(start_idx, end_idx):
        # i번째 날까지의 데이터로 시그널 생성
        df_slice = df.iloc[:i + 1]
        if len(df_slice) < 200:
            continue

        signals = analyze_all(df_slice)
        date = df.index[i]
        entry_price = float(df.iloc[i]["종가"])

        for sig in signals:
            if sig["시그널"] == "관망":
                continue

            # 이후 N일 수익률 계산
            returns = {}
            for hd in hold_days:
                future_idx = i + hd
                if future_idx < total_rows:
                    future_price = float(df.iloc[future_idx]["종가"])
                    if sig["시그널"] == "매수":
                        ret = (future_price - entry_price) / entry_price * 100
                    else:  # 매도
                        ret = (entry_price - future_price) / entry_price * 100
                    returns[f"{hd}일"] = round(ret, 2)

            records.append({
                "날짜": date,
                "전략": sig["전략"],
                "시그널": sig["시그널"],
                "진입가": entry_price,
                **returns,
            })

    if not records:
        return {"error": "시그널 발생 없음"}

    rdf = pd.DataFrame(records)

    # 전략별 집계
    strategy_results = {}
    for strategy in rdf["전략"].unique():
        sdf = rdf[rdf["전략"] == strategy]
        result = {
            "총_시그널": len(sdf),
            "매수": int((sdf["시그널"] == "매수").sum()),
            "매도": int((sdf["시그널"] == "매도").sum()),
        }

        for hd in hold_days:
            col = f"{hd}일"
            if col in sdf.columns:
                valid = sdf[col].dropna()
                if len(valid) > 0:
                    wins = (valid > 0).sum()
                    result[f"{hd}일_승률"] = round(wins / len(valid) * 100, 1)
                    result[f"{hd}일_평균수익"] = round(valid.mean(), 2)
                    result[f"{hd}일_최대수익"] = round(valid.max(), 2)
                    result[f"{hd}일_최대손실"] = round(valid.min(), 2)

        strategy_results[strategy] = result

    # 복합 시그널 분석 (같은 날 매수 2개+ 동시 발생)
    combo_results = {}
    buy_signals = rdf[rdf["시그널"] == "매수"]
    if not buy_signals.empty:
        for date, group in buy_signals.groupby("날짜"):
            if len(group) >= 2:
                combo_key = " + ".join(sorted(group["전략"].tolist()))
                if "5일" in group.columns:
                    avg_ret = group["5일"].mean()
                    if combo_key not in combo_results:
                        combo_results[combo_key] = {"횟수": 0, "수익합": 0, "승": 0}
                    combo_results[combo_key]["횟수"] += 1
                    combo_results[combo_key]["수익합"] += avg_ret
                    if avg_ret > 0:
                        combo_results[combo_key]["승"] += 1

    combo_summary = {}
    for k, v in combo_results.items():
        if v["횟수"] >= 2:  # 2회 이상 발생한 조합만
            combo_summary[k] = {
                "횟수": v["횟수"],
                "승률": round(v["승"] / v["횟수"] * 100, 1),
                "평균수익": round(v["수익합"] / v["횟수"], 2),
            }

    period_start = str(df.index[start_idx])[:10]
    period_end = str(df.index[end_idx])[:10]

    return {
        "전략별": strategy_results,
        "복합시그널": combo_summary,
        "기간": {"시작": period_start, "종료": period_end, "영업일": end_idx - start_idx},
    }


def format_backtest(result: dict, stock_name: str = "") -> str:
    """백테스트 결과를 읽기 좋은 텍스트로 포맷."""
    if "error" in result:
        return f"백테스트 실패: {result['error']}"

    lines = []
    lines.append(f"📊 백테스트 결과 {stock_name} ({result['기간']['시작']} ~ {result['기간']['종료']}, {result['기간']['영업일']}일)")
    lines.append("")

    # 전략별 정렬 (5일 승률 기준)
    strats = result["전략별"]
    sorted_strats = sorted(strats.items(),
                           key=lambda x: x[1].get("5일_승률", 0), reverse=True)

    for name, data in sorted_strats:
        weight = STRATEGY_WEIGHTS.get(name, 1.0)
        count = data['총_시그널']
        reliability = "⚠️ 샘플부족" if count < 5 else ("✅" if count >= 15 else "△ 참고")
        lines.append(f"{'★' if data.get('5일_승률', 0) >= 60 and count >= 5 else '·'} {name} (가중치 {weight}) — {count}회 {reliability}")
        for hd in [5, 10, 20]:
            wr = data.get(f"{hd}일_승률")
            avg = data.get(f"{hd}일_평균수익")
            mx = data.get(f"{hd}일_최대수익")
            mn = data.get(f"{hd}일_최대손실")
            if wr is not None:
                lines.append(f"    {hd}일: 승률 {wr}% | 평균 {avg:+.2f}% | 최대 +{mx:.1f}% / {mn:.1f}%")
        lines.append("")

    # 복합 시그널
    if result["복합시그널"]:
        lines.append("🔗 복합 시그널 (동시 발생 매수)")
        for combo, data in sorted(result["복합시그널"].items(),
                                   key=lambda x: x[1]["승률"], reverse=True):
            lines.append(f"  {combo}: {data['횟수']}회 | 승률 {data['승률']}% | 평균 {data['평균수익']:+.2f}%")

    return "\n".join(lines)


def _cache_path(stock_name: str) -> Path:
    return REPORTS_DIR / stock_name / "backtest.md"


def save_cache(stock_name: str, result: dict) -> Path:
    """백테스트 결과를 md 파일로 캐싱."""
    path = _cache_path(stock_name)
    path.parent.mkdir(parents=True, exist_ok=True)

    content = f"""---
generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
expires: {(datetime.now() + timedelta(days=CACHE_DAYS)).strftime('%Y-%m-%d')}
---

{format_backtest(result, stock_name)}

<!-- raw_json
{json.dumps(result, ensure_ascii=False, default=str)}
-->
"""
    path.write_text(content, encoding="utf-8")
    return path


def load_cache(stock_name: str) -> dict | None:
    """캐시된 백테스트 결과 로드. 만료됐으면 None."""
    path = _cache_path(stock_name)
    if not path.exists():
        return None

    text = path.read_text(encoding="utf-8")

    # 만료 체크
    for line in text.split("\n"):
        if line.startswith("expires:"):
            exp = line.split(":", 1)[1].strip()
            try:
                if datetime.strptime(exp, "%Y-%m-%d") < datetime.now():
                    return None  # 만료
            except ValueError:
                return None

    # JSON 추출
    start = text.find("<!-- raw_json")
    end = text.find("-->", start)
    if start == -1 or end == -1:
        return None

    json_str = text[start + len("<!-- raw_json"):end].strip()
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def get_backtest(stock_name: str, stock_code: str,
                 force: bool = False, lookback: int = 200,
                 earnings_window: bool | None = None,
                 market: str = "kr") -> dict:
    """
    캐시 우선 백테스트. 캐시 유효하면 재사용, 아니면 새로 실행 + 저장.

    Args:
        stock_name: 종목명 (reports/stocks/{종목명}/ 디렉토리명)
        stock_code: 6자리 종목코드
        force: True면 캐시 무시하고 새로 실행
        lookback: 백테스트 기간 (영업일)
        earnings_window: 실적 시즌 (D-7 ~ D+7) 진입 시 True.
                         캐시가 실적 발표 이전 생성이면 강제 재실행해
                         실적 서프라이즈/쇼크 이후 승률 급변을 반영.

    Returns:
        backtest_stock() 결과 dict
    """
    # earnings_window가 None이면 자동 감지 (market별 소스)
    if earnings_window is None:
        try:
            if market == "us":
                from server.scrapers.finnhub import fetch_next_earnings_date  # type: ignore
            else:
                from server.scrapers.dart import fetch_next_earnings_date
            next_e = fetch_next_earnings_date(stock_code)
            earnings_window = next_e.get("earnings_window", False)
        except Exception:
            earnings_window = False

    if earnings_window:
        force = True  # 실적 시즌은 무조건 갱신

    if not force:
        cached = load_cache(stock_name)
        if cached:
            return cached

    if market == "us":
        from server.scrapers import yfinance_client as yfc
        # 2년치 (lookback*2 + 200 ≈ 600일) yfinance period 매핑
        df = yfc.fetch_ohlcv(stock_code, period="2y")
    else:
        from pykrx import stock as pykrx_stock
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=lookback * 2 + 200)).strftime("%Y%m%d")
        df = pykrx_stock.get_market_ohlcv(start, end, stock_code)

    if df.empty or len(df) < 250:
        return {"error": "데이터 부족"}

    result = backtest_stock(df, lookback=lookback)

    if "error" not in result:
        save_cache(stock_name, result)

    return result


if __name__ == "__main__":
    from pykrx import stock

    code = "005930"
    name = "삼성전자"
    result = get_backtest(name, code, force=True, lookback=150)
    print(format_backtest(result, name))
