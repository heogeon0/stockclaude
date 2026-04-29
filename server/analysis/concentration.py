"""
포트폴리오 집중도 체크 + 포지션 사이징

기능:
  1. 단일 종목 / 섹터 비중 상한 검증 (매매 집행 전)
  2. Kelly Criterion 기반 적정 진입 금액 (Half-Kelly 기본)
  3. 계좌 리스크 % 기반 Fixed Fractional 사이징
  4. 기존 보유 종목 상관관계 조정 유효 포지션

사용:
    from server.analysis.concentration import check_concentration, kelly_position_size, fixed_risk_sizing

    # 집행 전 체크
    warning = check_concentration('reports/portfolio.md', '000660', new_shares=1, new_price=1224000)

    # 진입 금액 계산
    size = fixed_risk_sizing(entry=1224000, stop=976950, risk_pct=0.02, capital=30_000_000)
"""

from __future__ import annotations
from pathlib import Path
import re
from typing import Optional


# 상한 기본값 (프로 스탠다드)
DEFAULT_SINGLE_STOCK_CAP = 0.25   # 단일 종목 25%
DEFAULT_SECTOR_CAP = 0.40         # 단일 섹터 40%
AGGRESSIVE_SINGLE_CAP = 0.35
AGGRESSIVE_SECTOR_CAP = 0.50


# ============================================================
# 집중도 체크
# ============================================================

def parse_portfolio(md_path: str | Path) -> dict:
    """
    portfolio.md 파싱 → 보유 종목 + 예수금 + 섹터 매핑.

    Returns:
        {
            "보유": [{"종목": str, "코드": str, "주식수": int, "평단": int, "원금": int}, ...],
            "예수금": int,
            "섹터": {"종목": "섹터명", ...},
        }
    """
    text = Path(md_path).read_text(encoding="utf-8")
    result = {"보유": [], "예수금": 0, "섹터": {}}

    # 예수금 추출 (KRW ₩ 기본, USD $ 허용)
    m = re.search(r"예수금:\s*[₩$]?([\d,]+)", text)
    if m:
        result["예수금"] = int(m.group(1).replace(",", ""))

    # 보유 종목 테이블 파싱
    # 패턴: | 종목 | 코드 | 주 | 평단 | 원금 | ...
    # 코드 regex 확장: KR 6자리 (\d{6}) OR US 티커 1~5자 대문자 (\.클래스 접미 허용)
    code_regex = re.compile(r"^(\d{6}|[A-Z]{1,5}(\.[A-Z])?)$")
    table_lines = [l for l in text.split("\n") if l.startswith("|") and not l.startswith("|---")]
    for line in table_lines:
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        # 헤더 스킵
        if cells[0] in ("종목", "코드"):
            continue
        code_match = code_regex.match(cells[1])
        if not code_match:
            continue
        try:
            shares = int(re.sub(r"[^\d]", "", cells[2]))
            # 평단/원금: 소수점 가능 (USD) + 쉼표 제거. int 안 되면 float
            def _num(s):
                cleaned = re.sub(r"[^\d.]", "", s)
                if not cleaned:
                    raise ValueError
                return float(cleaned) if "." in cleaned else int(cleaned)
            avg_price = _num(cells[3])
            principal = _num(cells[4])
            # 시장 판정 (6자리면 KR, 아니면 US)
            market = "kr" if re.match(r"^\d{6}$", cells[1]) else "us"
            # 통화: 평단/원금 셀에 $ 있으면 USD, 아니면 KRW
            has_dollar = "$" in cells[3] or "$" in cells[4]
            currency = "USD" if (has_dollar or market == "us") else "KRW"
            result["보유"].append({
                "종목": cells[0].replace("*", "").strip(),
                "코드": cells[1],
                "주식수": shares,
                "평단": avg_price,
                "원금": principal,
                "시장": market,
                "통화": currency,
            })
        except (ValueError, IndexError):
            continue

    # 섹터 파싱 (## 섹터 분포 섹션)
    sector_match = re.search(r"##\s*섹터 분포(.+?)(?=##|\Z)", text, re.DOTALL)
    if sector_match:
        for line in sector_match.group(1).split("\n"):
            # 예: "- 반도체: SK하이닉스 + 삼성전자 = 30.9%"
            m = re.match(r"^\s*-\s*([^:]+):\s*(.+?)\s*=", line)
            if m:
                sector = m.group(1).strip()
                stocks = [s.strip() for s in m.group(2).split("+")]
                for s in stocks:
                    result["섹터"][s] = sector

    return result


def check_concentration(
    portfolio_md: str | Path,
    code: str,
    stock_name: str,
    new_shares: int,
    new_price: int,
    sector: Optional[str] = None,
    single_cap: float = DEFAULT_SINGLE_STOCK_CAP,
    sector_cap: float = DEFAULT_SECTOR_CAP,
) -> dict:
    """
    매매 집행 전 집중도 검증.

    Args:
        portfolio_md: portfolio.md 경로
        code: 진입/추가할 종목코드
        stock_name: 종목명 (신규 진입 시 필요)
        new_shares: 추가 주식 수 (양수=매수, 음수=매도)
        new_price: 체결가
        sector: 종목 섹터 (신규면 필수, 기존이면 자동 감지)
        single_cap: 단일 종목 상한 비율
        sector_cap: 단일 섹터 상한 비율

    Returns:
        {
            "집행_가능": bool,
            "경고": [str],
            "예상_종목_비중": float,
            "예상_섹터_비중": float,
            "집행_후_총자산": int,
            "세부": dict,
        }
    """
    port = parse_portfolio(portfolio_md)

    # 현재 보유 종목 여부
    existing = next((h for h in port["보유"] if h["코드"] == code), None)
    cash = port["예수금"]

    # 매수 금액 (양수면 cash 감소)
    trade_amount = new_shares * new_price

    if trade_amount > cash and new_shares > 0:
        return {
            "집행_가능": False,
            "경고": [f"예수금 부족 (소요 ₩{trade_amount:,} > 잔고 ₩{cash:,})"],
            "예수금_부족": trade_amount - cash,
        }

    # 집행 후 각 종목 원금
    holdings_after = {h["코드"]: h["원금"] for h in port["보유"]}
    if existing:
        # 평단 재계산
        old_principal = existing["원금"]
        new_principal = old_principal + trade_amount
        holdings_after[code] = new_principal
        stock_name = existing["종목"]
    else:
        holdings_after[code] = trade_amount

    total_principal_after = sum(holdings_after.values())
    cash_after = cash - trade_amount
    total_asset_after = total_principal_after + cash_after

    if total_asset_after <= 0:
        return {"집행_가능": False, "경고": ["자산 계산 오류"]}

    # 종목 비중
    target_weight = holdings_after[code] / total_asset_after

    # 섹터 비중
    sector_map = port["섹터"].copy()
    if sector:
        sector_map[stock_name] = sector
    target_sector = sector_map.get(stock_name, "분류없음")
    sector_principal = sum(
        holdings_after.get(next((h["코드"] for h in port["보유"] if h["종목"] == name), ""), 0)
        for name, sec in sector_map.items() if sec == target_sector
    )
    # 신규 진입이면 목표 종목도 섹터에 포함
    if not existing and sector:
        sector_principal += trade_amount
    sector_weight = sector_principal / total_asset_after

    warnings = []
    if target_weight > single_cap:
        warnings.append(
            f"⚠️ 단일 종목 비중 {target_weight*100:.1f}% > 상한 {single_cap*100:.0f}%"
        )
    if sector_weight > sector_cap:
        warnings.append(
            f"⚠️ {target_sector} 섹터 비중 {sector_weight*100:.1f}% > 상한 {sector_cap*100:.0f}%"
        )

    executable = len(warnings) == 0

    return {
        "집행_가능": executable,
        "경고": warnings,
        "예상_종목_비중_pct": round(target_weight * 100, 1),
        "예상_섹터_비중_pct": round(sector_weight * 100, 1),
        "섹터": target_sector,
        "집행_후_총자산": total_asset_after,
        "집행_후_예수금": cash_after,
        "세부": {
            "매매_금액": trade_amount,
            "종목_원금_후": holdings_after[code],
            "섹터_원금_후": sector_principal,
        },
    }


# ============================================================
# 포지션 사이징 — Kelly Criterion
# ============================================================

def kelly_position_size(
    win_rate: float,
    win_loss_ratio: float,
    capital: int,
    fraction: float = 0.25,
) -> dict:
    """
    Kelly 기반 진입 금액.

    공식: f* = W - (1-W)/R
    W: 승률 (0~1), R: 이기는 금액 / 지는 금액

    실전 권장: Full Kelly는 변동성 크므로 **Quarter Kelly(25%)** 또는 Half Kelly(50%).
    fraction 인자로 조정.

    Args:
        win_rate: 승률 (0~1)
        win_loss_ratio: 평균 이익 / 평균 손실
        capital: 총 계좌 잔고
        fraction: Kelly 비율 (기본 25% = Quarter Kelly)

    Returns:
        {"Kelly_f": float, "진입_비율": float, "진입_금액": int, "해석": str}
    """
    if win_rate <= 0 or win_rate >= 1 or win_loss_ratio <= 0:
        return {"오류": "입력값 범위 오류", "진입_금액": 0}

    full_kelly = win_rate - (1 - win_rate) / win_loss_ratio
    if full_kelly <= 0:
        return {
            "Kelly_f": round(full_kelly, 3),
            "진입_비율": 0,
            "진입_금액": 0,
            "해석": "음의 기대값 — 진입 금지",
        }

    adjusted_f = full_kelly * fraction
    position = int(capital * adjusted_f)

    return {
        "Kelly_f": round(full_kelly, 3),
        "적용_비율": fraction,
        "진입_비율": round(adjusted_f, 3),
        "진입_금액": position,
        "해석": f"Full Kelly {full_kelly*100:.1f}% × {fraction*100:.0f}% = {adjusted_f*100:.1f}% 진입",
    }


# ============================================================
# Fixed Fractional — 계좌 리스크 % 기반
# ============================================================

def fixed_risk_sizing(
    entry: int,
    stop: int,
    risk_pct: float,
    capital: int,
    direction: str = "long",
) -> dict:
    """
    계좌 리스크 % 기반 주식 수 산정.

    공식:
        최대 손실 허용 = capital × risk_pct
        주당 리스크 = |entry - stop|
        주식 수 = 최대 손실 허용 / 주당 리스크

    예:
        계좌 ₩30M, 리스크 2% = ₩600k 허용
        진입 ₩1,224k, 손절 ₩976k → 주당 리스크 ₩247k
        주식 수 = 600 / 247 = 2.43주 → 2주

    Args:
        entry: 진입가
        stop: 손절가
        risk_pct: 리스크 비율 (0.02 = 2%)
        capital: 계좌 잔고
        direction: "long" (기본) | "short"

    Returns:
        {"최대_손실": int, "주당_리스크": int, "주식수": int, "진입_금액": int, "계좌_비중_pct": float}
    """
    max_loss = int(capital * risk_pct)

    if direction == "long":
        per_share_risk = entry - stop
    else:
        per_share_risk = stop - entry

    if per_share_risk <= 0:
        return {"오류": f"손절가 방향 오류 (entry={entry}, stop={stop}, direction={direction})"}

    shares = max_loss // per_share_risk
    position = shares * entry

    return {
        "최대_손실": max_loss,
        "주당_리스크": int(per_share_risk),
        "주식수": int(shares),
        "진입_금액": int(position),
        "계좌_비중_pct": round(position / capital * 100, 1) if capital else 0,
    }


# ============================================================
# 포지션 플래너 — ATR 기반 동적 피라미딩 가격
# ============================================================

def position_planner(entry: int, atr: float, tier: str = "Standard",
                      direction: str = "long") -> dict:
    """
    등급별 피라미딩/손절 가격 배열.
    고정% 대신 ATR 배수 사용 → 종목 변동성 반영.

    Args:
        entry: 진입가
        atr: ATR14 값
        tier: "Premium" | "Standard" | "Cautious" | "Defensive"
              | "Premium-단타" | "Standard-단타" | "Cautious-단타" | "Defensive-단타"
        direction: "long" | "short"

    Returns:
        {
            "손절가": int,
            "피라미딩_단계": [{"단계": 1, "가격": int, "비율": str, "트리거": str}, ...],
            "부분익절": [{"가격": int, "비율": str}, ...],
            "ATR_배수": dict (참조용),
        }
    """
    atr = float(atr)
    if atr <= 0:
        return {"오류": "ATR 값 오류"}

    # ATR 배수 정의 (등급별)
    mult = {
        # 스윙
        "Premium":     {"손절": 4.0, "1단계": 1.0, "2단계": 2.0, "3단계": 3.0, "익절": 5.0},
        "Standard":    {"손절": 3.0, "1단계": 1.0, "2단계": 2.0, "익절": 4.0},
        "Cautious":    {"손절": 2.0, "1단계": 1.5, "익절": 3.0},
        "Defensive":   {"손절": 1.5, "익절": 2.5},
        # 단타 (기술 스윙)
        "Premium-단타":   {"손절": 1.5, "1단계": 0.5, "2단계": 1.0, "3단계": 1.5, "4단계": 2.0, "익절": 3.0},
        "Standard-단타":  {"손절": 2.0, "1단계": 0.8, "2단계": 1.5, "3단계": 2.2, "익절": 3.0},
        "Cautious-단타":  {"손절": 1.5, "1단계": 1.0, "2단계": 1.8, "익절": 2.5},
        "Defensive-단타": {"손절": 1.0, "1단계": 1.0, "익절": 2.0},
    }

    m = mult.get(tier)
    if m is None:
        return {"오류": f"알 수 없는 등급: {tier}"}

    sign = 1 if direction == "long" else -1

    stop = int(entry - sign * atr * m["손절"])

    stages = []
    stage_n = 1
    while f"{stage_n}단계" in m:
        price = int(entry + sign * atr * m[f"{stage_n}단계"])
        stages.append({
            "단계": stage_n,
            "가격": price,
            "트리거": f"ATR×{m[f'{stage_n}단계']} ({'상승' if sign>0 else '하락'})",
        })
        stage_n += 1

    take_profit_price = int(entry + sign * atr * m["익절"])

    return {
        "진입가": entry,
        "손절가": stop,
        "손절_손실폭": round((entry - stop) / entry * 100, 1) if direction == "long" else round((stop - entry) / entry * 100, 1),
        "피라미딩_단계": stages,
        "1차_익절가": take_profit_price,
        "1차_익절_이익폭": round((take_profit_price - entry) / entry * 100, 1),
        "ATR": int(atr),
        "ATR_pct": round(atr / entry * 100, 2),
    }


# ============================================================
# 상관관계 조정 (간단 버전)
# ============================================================

def correlation_adjustment(holdings: list[dict], new_code: str,
                            correlation_map: Optional[dict] = None) -> dict:
    """
    기존 보유 종목과의 상관관계 고려 유효 포지션 계산.

    간단 모델: 동일 섹터면 상관계수 0.7, 다른 섹터 0.2로 가정.
    실제 계산은 로그수익률 피어슨 상관 필요하나, 여기선 근사.

    Args:
        holdings: parse_portfolio()['보유']
        new_code: 새로 추가할 종목코드
        correlation_map: {(code1, code2): corr} 미리 계산된 상관계수 (선택)

    Returns:
        {"실효_종목수": float, "다각화_점수": str, "권장": str}
    """
    if not holdings:
        return {"실효_종목수": 1, "다각화_점수": "신규 진입"}

    # 가장 단순한 근사: 섹터 매핑 필요. 여기선 종목 수만 기준 다각화
    n = len(holdings) + (0 if any(h["코드"] == new_code for h in holdings) else 1)

    # 실효 종목수 (독립성 가정시 n, 완전 상관시 1)
    # 평균 상관 0.4 가정 → 실효 = 1 / (1/n × (1 + (n-1)×0.4))
    avg_corr = 0.4
    effective_n = n / (1 + (n - 1) * avg_corr)

    if effective_n >= 5:
        score = "양호"
        rec = "다각화 충분"
    elif effective_n >= 3:
        score = "보통"
        rec = "섹터 분산 고려"
    else:
        score = "집중"
        rec = "과집중 주의 — 다른 섹터 종목 추가 권장"

    return {
        "보유_종목수": n,
        "실효_종목수": round(effective_n, 1),
        "다각화_점수": score,
        "권장": rec,
    }


if __name__ == "__main__":
    import json

    pm = Path.home() / ".claude/skills/stock/reports/portfolio.md"
    if pm.exists():
        port = parse_portfolio(pm)
        print("=== 포트폴리오 파싱 ===")
        print(json.dumps(port, indent=2, ensure_ascii=False, default=str))

        print("\n=== 집중도 체크: SK하이닉스 1주 더 매수 @ ₩1,224,000 ===")
        check = check_concentration(pm, "000660", "SK하이닉스", 1, 1224000, sector="반도체")
        print(json.dumps(check, indent=2, ensure_ascii=False))

    print("\n=== Kelly 포지션 사이징 (승률 55%, 손익비 2) ===")
    print(kelly_position_size(0.55, 2.0, 30_000_000))

    print("\n=== Fixed Risk (진입 ₩1,224k, 손절 ₩976k, 2%) ===")
    print(fixed_risk_sizing(1224000, 976950, 0.02, 30_000_000))

    print("\n=== 상관관계 (보유 5 + 신규 1) ===")
    sample_holdings = [{"코드": "005930"}, {"코드": "000660"}, {"코드": "298040"}, {"코드": "036570"}, {"코드": "000720"}]
    print(correlation_adjustment(sample_holdings, "035420"))
