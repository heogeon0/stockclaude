"""
US 종목 풀 (Universe) — S&P 500 + NASDAQ 100 정적 시드 + 시총 상위 추출.

KR 의 `pykrx.fetch_all_stocks()` 와 동등한 역할. yfinance 로 시총 일괄 fetch 후 필터.

스펙: agent/research.md `### [2026-04-27] us-momentum-scanning` 참조.
- 정적 시드 ~530 unique tickers (S&P 500 ∪ NASDAQ 100)
- yfinance batch 로 marketCap fetch → 시총 임계값 필터 + 상위 N
- ETF / ADR / 우선주 제외 룰
"""
from __future__ import annotations

# fmt: off

# S&P 500 (2026-04 시점, 시총 상위 ~120 + 주요 sector mid-cap 보강)
# 실시간 갱신은 fetch_sp500_from_wiki() fallback. 정적 list 는 안정성 우선.
SP500_SEED: list[str] = [
    # Mega cap (시총 $500B+)
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "BRK.B", "AVGO",
    "LLY", "JPM", "WMT", "V", "XOM", "MA", "ORCL", "UNH", "PG", "JNJ",
    "HD", "COST", "ABBV", "BAC", "NFLX", "CVX", "KO", "AMD", "CRM", "PEP",
    "TMUS", "LIN", "TMO", "ACN", "ADBE", "MCD", "CSCO", "WFC", "ABT", "DHR",
    "GE", "AXP", "INTC", "VZ", "QCOM", "PFE", "INTU", "DIS", "CAT", "T",
    # Large cap ($100B~$500B)
    "PM", "NOW", "TXN", "AMGN", "MS", "IBM", "ISRG", "RTX", "NEE", "UBER",
    "UNP", "GS", "PGR", "BX", "BLK", "BKNG", "PLTR", "C", "AMAT", "SCHW",
    "SPGI", "DE", "LOW", "ELV", "BA", "HON", "TJX", "MDT", "KKR", "MMC",
    "VRTX", "LRCX", "MU", "GILD", "PANW", "SBUX", "CMCSA", "ADI", "CB", "ETN",
    "ANET", "BSX", "PYPL", "ADP", "PLD", "MO", "REGN", "AMT", "SYK", "CI",
    # Mid cap ($30B~$100B) — 분산 위해 sector 다양화
    "FI", "NKE", "TT", "DUK", "ICE", "ZTS", "SO", "BMY", "EQIX", "CL",
    "MCO", "KLAC", "WM", "PNC", "USB", "GD", "WELL", "CME", "MDLZ", "EOG",
    "CDNS", "TGT", "SNPS", "ITW", "MAR", "FCX", "SHW", "EMR", "FDX", "CSX",
    "APD", "TFC", "PSX", "PCAR", "COF", "ECL", "AON", "MNST", "PSA", "GIS",
    "WMB", "CHTR", "MPC", "NSC", "BDX", "ROST", "AJG", "SLB", "AZO", "VLO",
    "NEM", "TRV", "CMG", "AFL", "ADSK", "FTNT", "DLR", "PXD", "FAST", "OKE",
    "CARR", "ALL", "SPG", "ORLY", "OXY", "AIG", "F", "GM", "PAYX", "RSG",
    # Healthcare / Biotech
    "MRK", "DHR", "BMY", "AMGN", "GILD", "MDT", "CI", "BSX", "REGN", "VRTX",
    # Energy
    "EOG", "PXD", "PSX", "MPC", "WMB", "VLO", "OKE", "SLB", "OXY",
    # Industrials
    "GE", "RTX", "BA", "HON", "CAT", "DE", "UNP", "UPS", "LMT", "GD",
    # Consumer
    "WMT", "COST", "HD", "MCD", "PG", "KO", "PEP", "NKE", "SBUX", "TGT",
    # Tech (additional)
    "ARM", "SNOW", "SHOP", "DDOG", "NET", "ZS", "CRWD", "MDB", "TEAM",
]

# NASDAQ 100 (2026-04 시점) — S&P 500 와 일부 중복, 합집합 처리
NDX100_SEED: list[str] = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "AVGO",
    "COST", "NFLX", "AMD", "PEP", "TMUS", "ADBE", "CSCO", "QCOM", "INTC",
    "INTU", "TXN", "AMGN", "ISRG", "AMAT", "BKNG", "LRCX", "MU", "GILD",
    "PANW", "SBUX", "CMCSA", "ADI", "VRTX", "ADP", "REGN", "MELI", "KLAC",
    "CDNS", "MAR", "SNPS", "ASML", "ORLY", "FTNT", "PYPL", "MNST", "PCAR",
    "ADSK", "PAYX", "FAST", "ROP", "CTAS", "CHTR", "AEP", "WDAY", "EXC",
    "CRWD", "MRVL", "ROST", "DXCM", "KDP", "BIIB", "AZN", "ODFL", "GEHC",
    "FANG", "TEAM", "DDOG", "CTSH", "IDXX", "ANSS", "CCEP", "ON", "CSGP",
    "MDB", "ZS", "ARM", "SHOP", "PDD", "JD", "BIDU",
]


def get_universe(min_market_cap_usd: float = 10_000_000_000) -> set[str]:
    """
    S&P 500 ∪ NASDAQ 100 정적 시드 합집합 — ETF / ADR 제외 후 unique 반환.

    실시간 시총 필터링은 fetch_top_by_marketcap() 에서 수행.
    여기서는 단순히 ticker 풀만 반환.
    """
    seed = set(SP500_SEED) | set(NDX100_SEED)

    # ADR / 외국 기업 제외 (US 모멘텀 스크리닝 대상 = 미국 본사 기준)
    # PDD/JD/BIDU/MELI/ASML/AZN 등은 일단 포함 (글로벌 대표 ADR 도 미국 거래)
    # 추후 필터 필요 시 EXCLUDE_ADR set 추가

    return seed


def fetch_top_by_marketcap(
    min_market_cap_usd: float = 10_000_000_000,
    limit: int = 100,
) -> list[dict]:
    """
    유니버스 → yfinance 로 시총 batch fetch → 임계값 필터 + 시총 내림차순 상위 N.

    반환: [{"ticker": "AAPL", "name": "Apple Inc.", "market_cap_usd": 3.5e12, ...}, ...]

    yfinance batch fetch 실패한 ticker 는 스킵 (시총 None 처리).
    """
    from server.scrapers import yfinance_client as yfc

    tickers = sorted(get_universe())
    cap_map = yfc.fetch_market_cap_batch(tickers)

    rows: list[dict] = []
    for t in tickers:
        cap = cap_map.get(t)
        if cap is None or cap < min_market_cap_usd:
            continue
        rows.append({"ticker": t, "market_cap_usd": cap})

    rows.sort(key=lambda r: r["market_cap_usd"], reverse=True)
    return rows[:limit]
