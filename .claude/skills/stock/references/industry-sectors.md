# 산업 섹터 매핑

> 로드 시점: 산업 base 작성 시 / 종목 → 산업 매핑 시.

## KR 11 섹터 (코스피 GICS-like)

| 코드 | 섹터 | 핵심 종목 (예) | 관련 산업 base.md 경로 |
|---|---|---|---|
| `반도체` | 반도체 (메모리/파운드리/장비) | 삼성전자, SK하이닉스, 한미반도체 | `reports/industries/반도체/base.md` |
| `전력설비` | 변압기/차단기/송배전 | 효성중공업, HD현대일렉트릭, LS ELECTRIC | `reports/industries/전력설비/base.md` |
| `게임` | PC/모바일 게임, 퍼블리싱 | 엔씨, 크래프톤, 넷마블 | `reports/industries/게임/base.md` |
| `지주` | 컨글로머릿 / 지주 | LG, SK, 삼성물산 | `reports/industries/지주/base.md` |
| `방산` | 항공/지상 방산 | 한화에어로스페이스, KAI, LIG넥스원 | `reports/industries/방산/base.md` |
| `2차전지` | EV / ESS / 소재 | 삼성SDI, LG에너지솔루션, 포스코퓨처엠 | `reports/industries/2차전지/base.md` |
| `조선` | 컨테이너 / LNG / 군함 | HD한국조선해양, 삼성중공업, 한화오션 | `reports/industries/조선/base.md` |
| `건설/EPC` | 건축 / 플랜트 | 현대건설, 대우건설, 삼성E&A | `reports/industries/건설/base.md` |
| `금융` | 은행 / 증권 / 보험 / 카드 | KB금융, 신한지주, 하나금융, 삼성생명 | `reports/industries/금융/base.md` |
| `소비재` | 화장품 / 식품 / 패션 / 담배 | 에이피알, KT&G, 아모레퍼시픽 | `reports/industries/소비재/base.md` |
| `통신` | 통신 / 미디어 | SKT, KT, LG유플러스 | `reports/industries/통신/base.md` |

## US GICS 11 섹터

| GICS 코드 | 섹터 | 핵심 종목 (예) | base.md 경로 |
|---|---|---|---|
| `us-tech` | Information Technology | NVDA, AAPL, MSFT, AVGO | `reports/industries/us/us-tech/base.md` |
| `us-communication` | Communication Services | GOOGL, META, NFLX, DIS | `reports/industries/us/us-communication/base.md` |
| `us-financials` | Financials | JPM, BRK, BAC, GS | `reports/industries/us/us-financials/base.md` |
| `us-healthcare` | Health Care | UNH, JNJ, LLY, PFE | `reports/industries/us/us-healthcare/base.md` |
| `us-consumer-disc` | Consumer Discretionary | AMZN, TSLA, HD, NKE | `reports/industries/us/us-consumer-disc/base.md` |
| `us-consumer-staples` | Consumer Staples | WMT, PG, KO, COST | `reports/industries/us/us-consumer-staples/base.md` |
| `us-industrials` | Industrials | BA, CAT, GE, RTX | `reports/industries/us/us-industrials/base.md` |
| `us-energy` | Energy | XOM, CVX, COP | `reports/industries/us/us-energy/base.md` |
| `us-utilities` | Utilities | NEE, SO, DUK | `reports/industries/us/us-utilities/base.md` |
| `us-real-estate` | Real Estate | PLD, AMT, EQIX | `reports/industries/us/us-real-estate/base.md` |
| `us-materials` | Materials | LIN, APD, FCX | `reports/industries/us/us-materials/base.md` |

## 종목 → 섹터 매핑 룰

stock-daily / research / discover 가 종목 분석 시:

1. `get_stock_context(code)` → `stock.industry_code` 필드 확인
2. industry_code 가 위 표의 코드 중 하나
3. 해당 산업 base.md 자동 로드 (만료 시 base-industry 자동 호출)

## 1 종목, 다중 산업 케이스

지주사 (LG, 삼성물산 등) 또는 복합 기업은 **여러 산업 태그** 가능:

```
LG (003550):
  - 지주 (메인)
  - 2차전지 (LG에너지솔루션 모회사)
  - 통신 (LG유플러스 모회사)
```

stock-daily 의 종목 daily 분석 시 모든 태그 산업 base 를 로드하고 영향도 fact 작성.

## 섹터 코드 추가 / 변경 룰

신규 섹터 발견 시:
1. KR DB 의 `industries` 테이블에 row 추가
2. 본 파일 업데이트
3. 매핑된 종목들의 `stocks.industry_code` 갱신
