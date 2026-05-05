# Market 라우팅 — KR / US 데이터 소스 표

> 로드 시점: 종목 분석 시작 시 (KR/US 판정 직후).

종목 입력 → market 자동 판정 (LLM 직접 판단 (6자리 숫자 = KR / 1~5자 대문자 = US) — stock-daily 와 공유) → 데이터 소스 분기.

## 데이터 소스 매핑

| 차원 | KR | US |
|---|---|---|
| 재무제표 | `compute_financials(code)` (DART 연결 사업보고서) | `compute_financials(ticker)` (SEC EDGAR XBRL) |
| 펀더멘털 | `realtime_price(code)` 의 PER/PBR/EPS/시총 | `kis_us_quote(ticker)` 또는 `compute_financials.fundamentals` |
| 컨센서스 | `get_analyst_consensus(code)` (네이버 리서치) | `get_analyst_consensus(ticker)` (Finnhub) |
| 공시 | (DART 어댑터) | (SEC EDGAR submissions) |
| 대주주 | (DART 대량보유) | `us.fetch_investor_flow_13f(ticker)` (13F 분기) |
| 실적일 | `detect_events(code).earnings` (DART) | `detect_events(ticker).earnings` (Finnhub) |
| 수급 | `analyze_flow(code, window=10)` (KRX 외인/기관) | 13F + 옵션 P/C ratio + Insider |
| 시장 국면 | `detect_market_regime(reference_code='005930')` (KOSPI 4조건) | `detect_market_regime(reference_code='SPY')` (S&P 4조건) |

## 경로 분기

| 파일 | KR | US |
|---|---|---|
| 종목 base | `reports/stocks/{한글명}/base.md` | `reports/stocks/US/{TICKER}/base.md` |
| 산업 base | `reports/industries/{한글산업}/base.md` | `reports/industries/us/{gics_sector}/base.md` |
| 경제 base | `reports/economy/base.md` | `reports/economy/us-base.md` |
| 종목 daily | `reports/stocks/{한글명}/{YYYY-MM-DD}.md` | `reports/stocks/US/{TICKER}/{YYYY-MM-DD}.md` |

## Valuation 분기

```python
from analysis.valuation import forward_dcf, reverse_dcf, trading_comps

# KR (기본값)
forward_dcf(fin_sum, shares, wacc=0.09, terminal_growth=0.025)

# US
forward_dcf(fin_sum, shares, market='us')
# → WACC 8.5%, risk_free 4.2%, terminal 2.5%, tax_rate 21% 자동 적용
# 또는 override: forward_dcf(..., market='us', wacc=0.09)
```

상세 호출 예: → MCP 호출 + LLM 시나리오 작성 (Reverse/Forward DCF) 참조.

## Scoring 분기

```python
grade_stock(fin_sum, industry_md, economy_md, economy_daily,
            fundamentals=fundamentals, market=market)
# market='us' → VALUATION_THRESHOLDS['us'] 적용 (고 PER Tech 정상 반영)
```

## 산업 매핑

산업 코드는 → `~/.claude/skills/stock/references/industry-sectors.md` 참조 (KR 11 + US GICS 11).

종목 → 산업: `get_stock_context(code).stock.industry_code` 필드.

## 한 종목, 다중 시장 (해당 없음)

KR 종목이 미국 ADR 발행해도 본 시스템은 KR 으로 처리.
US 종목 (NVDA 등) 은 항상 US.
