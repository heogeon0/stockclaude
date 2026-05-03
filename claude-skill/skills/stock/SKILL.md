---
name: stock
description: 개인 주식 포트폴리오 운영·분석 통합 skill (KR + US). 일일 운영(daily) / 신규 발굴(discover) / 6차원 정량 분석(research) / base 자동 갱신(inline) 모든 모드 통합. 매매 추천·피라미딩·손절·집중도·실적임박·컨센·재무·모멘텀·52주돌파·수급 분석. 사용자가 주식·매매·종목·포트·투자·분석·발굴·매도·매수·익절·손절·차트·시그널·재무·실적·컨센·DCF 같은 단어를 언급하면 반드시 이 skill 사용. v6 매트릭스 폐기 후 거장 원칙(master-principles 10 카테고리) + 산업 평균 대비 본문 판단. stockclaude MCP 서버(89 툴 인벤토리, v1 +9 라운드 2026-05) + PostgreSQL 백엔드 + 4개 KR/US 슬래시 명령(stock-daily/discover/research/base-*).
---

# Stock — 통합 주식 운영 skill

> **단일 진입점**으로 모든 주식 운영 처리.
> 모드별 워크플로우는 `references/{daily,discover,research}-workflow.md` 분리.
> base 본문 작성은 `references/base-*-update-inline.md` 절차로 메인이 inline 처리 (mobile/Desktop/iOS 호환).
> 데이터·계산은 `stockclaude` MCP (89 툴 인벤토리) + PostgreSQL.

---

## 호출 인터페이스 (6 모드)

| 슬래시 | wrapper 위치 | 모드 | 워크플로우 |
|---|---|---|---|
| `/stock-daily` | `~/.claude/commands/stock-daily.md` | daily — 보유+Pending 종목 일일 운영 | `references/daily-workflow.md` |
| `/stock-discover` | `~/.claude/commands/stock-discover.md` | discover — 신규 종목 발굴 | `references/discover-workflow.md` |
| `/stock-research` | `~/.claude/commands/stock-research.md` | research — 6차원 정량 분석 | `references/research-workflow.md` |
| **`/stock-weekly-strategy`** | `~/.claude/commands/stock-weekly-strategy.md` | **weekly-strategy** — 사용자+LLM 브레인스토밍 (v8 신설) | `references/weekly-strategy-brainstorm.md` |
| **`/stock-weekly-review`** | `~/.claude/commands/stock-weekly-review.md` | **weekly-review** — 4-Phase 종목별+종합+base 역반영 (라운드 2026-05 신설) | `references/weekly-review-workflow.md` |
| `/base-economy` `/base-industry` `/base-stock` | `~/.claude/commands/base-*.md` | base 갱신 (수동 호출) | `references/base-*-update-inline.md` 절차 inline 실행 |

각 wrapper 가 stock skill 의 해당 모드로 진입. 컨텍스트는 항상 stock skill 단일.

### 자연어 입력 시 모드 추측 (사용자가 슬래시 안 쓸 때)

사용자가 슬래시 명시 없이 자연어로 입력하면 의도 분석 후 적절한 모드로 진입:

| 입력 패턴 | 모드 | 예시 |
|---|---|---|
| "내 포트 / 어제 매매 / 보유 종목 현황 / 매매 추천 / 익절·손절·피라미딩" | **daily** | "내 포트 어때?", "오늘 뭐 사야 돼?", "삼성전자 매도할까?" |
| "신규 종목 / 발굴 / 추천 / 모멘텀 상위 / 어떤 종목이 좋아 / 테마" | **discover** | "요즘 좋은 종목 추천해줘", "AI 관련 신규 종목 찾아줘" |
| "분석 / 6차원 / 재무 / 컨센 / DCF / 모멘텀 / `{종목명}` 어때 / 비교" | **research** | "삼성SDI 분석해줘", "엔비디아 컨센 어떻게 변했어?" |
| "base 갱신 / 만기 / 재작성 / Narrative / 펀더멘털 풀 분석" | **base 갱신 inline** | "삼성전자 base 갱신해줘" → 메인이 `references/base-stock-update-inline.md` 절차 직접 수행 |
| "거시 / 금리 / 환율 / FOMC / 외국인 수급" | **base-economy inline** | "오늘 거시 어때?" → 메인이 `references/base-economy-update-inline.md` 절차 직접 수행 |
| "이번 주 전략 / 주간 전략 / 월요일 전략 / 시장관 / 브레인스토밍" | **weekly-strategy** (v8) | "이번 주 어떻게 갈까?" → `references/weekly-strategy-brainstorm.md` 5단계 절차 진입 |
| "이번 주 회고 / 주간 회고 / 리뷰 / 반성 / 회고하자 / 이번 주 평가" | **weekly-review** (라운드 2026-05) | "이번 주 회고해보자" → `references/weekly-review-workflow.md` 4-Phase 절차 진입 |

**복합 요청** (예: "포트 점검하고 신규도 찾아줘") → daily 먼저, 끝난 뒤 discover 진입.
**모호 시** → 사용자에게 한 번 확인 ("daily 모드로 진입할까요?").
**호출 후** → 결과 보고 시 모드 + 진입 사유 한 줄 명시 (예: "daily 모드 — 보유 종목 점검 의도").

---

## 프로젝트 핵심 사실

- **데이터·계산은 MCP**: `stockclaude` MCP 서버가 **89 툴 인벤토리** 제공 (`~/Desktop/Project/stockclaude/`)
- **PostgreSQL 백엔드**: 포지션·거래·지표·시그널·애널·스코어링 가중치 모두 DB
- **MCP 단일 의존**: 모든 데이터는 MCP 호출로 조회. **markdown 파일 직접 Read 금지** (DB source of truth)
- **너의 역할 = 해석·판단·서술**. 숫자는 MCP, 의미 부여는 references 룰
- **사용자 기대치**: 월스트리트 IB 시니어 분석가 품질. 질문하지 말고 실행

---

## ⛔ 종목 1건 분석 단일 진입점 (5단계, v6 단순화)

> 종목 1건 분석은 모드 (daily / research / discover) 와 무관하게 **`references/per-stock-analysis.md` 의 5단계 절차를 무조건 따른다**.
>
> v6 (2026-05) 단순화: 7단계 → 5단계. base 조회 + WebSearch 의무 단계 폐기. `analyze_position` 이 base 본문 inject + disclosures + insider 통합.
> WebSearch 는 LLM 자율 — `websearch-rules.md` 가이드 참조.

절차 요약 (상세는 `references/per-stock-analysis.md`):
1. **stale 조회** (`check_base_freshness`)
2. **stale 갱신** (cascade economy → industry → stock, 발견 시만)
3. **종목 분석** — `analyze_position(code, include_base=True)` 1 MCP (12 카테고리 — base 본문 3층 + disclosures + insider + 정량 raw)
4. **LLM 종합 판단** (필요시 자율 WebSearch)
5. **출력 + 저장** (`save_daily_report`, verdict 5종)

모드별 호출 위치:

| 모드 | 호출 시점 | 종목 수 |
|---|---|---|
| daily | Phase 3 — Active + Pending 순회 | 5~15 |
| research | 6차원 분석 진입 | 1 |
| discover | Top 후보 분석 | 1~5 |

⚠️ 포트 단위 처리 (`detect_market_regime` / `portfolio_correlation` / `detect_portfolio_concentration` / `get_weekly_context` / `save_portfolio_summary`) 는 본 절차 밖 — `daily-workflow.md` 가 별도 처리.

---

## 공통 룰 (모든 모드 적용)

### ⭐ 거장 트레이딩 원칙 (v6 신설, 2026-05)

매트릭스 룩업 (옛 v17 의 12셀 / 5×6 / 6대 룰) 은 **anchor 효과 + 검증 안 된 직관적 설계** 로 폐기됨 (`references/_archive/` 보존). 대체:

→ **`references/master-principles.md`** — 검증된 거장 (Livermore / Minervini / O'Neil / Weinstein / Buffett / Marks / PTJ / Lynch) 의 10 카테고리 추상 방향성. 구체 수치 X. LLM 본문 판단의 출발점.

10 카테고리:
1. 손익 관리 (Cut losses, let winners run)
2. 추세 추종 (The trend is your friend)
3. 변동성 관리
4. 사이클 인식 (Stage Analysis)
5. 재무 우량 + 모멘텀 (SEPA / CAN SLIM)
6. 이벤트 리스크
7. Top-down (시장 → 산업 → 종목)
8. 인내와 규율 (Wait for fat pitches)
9. 분산 vs 집중
10. 회고와 학습

### 12 기술 시그널

`compute_signals(code).signals` 12 전략 + 종합 verdict 산정:

→ **`references/signals-12.md`**.

### 과열 경고 임계

RSI / Stoch / 52주 고가 이격 / ADX / 20MA 이격 / 변동성 / 거래량:

→ **`references/overheat-thresholds.md`**.

### 산업 평균 대비 본문 판단 (v6 신설)

종목 financial_grade (A/B/C/D) 결정 시 **절대값 anchor 금지**, **산업 평균 대비** 본문 판단:
- `industries.avg_per` / `avg_pbr` / `avg_roe` / `avg_op_margin` / `vol_baseline_30d` 인용
- 종목 PER/ROE 가 산업 평균 대비 할인/프리미엄 여부로 grade 결정

### ⛔ rule_catalog single source-of-truth (라운드 2026-05)

- **DB `rule_catalog` 테이블이 매매 룰의 single source-of-truth** (16 active 룰, 참고 md: `references/rule-catalog.md`)
- `prepare_weekly_review_per_stock` / `prepare_weekly_review_portfolio` MCP 응답의 **`rule_catalog_join` 카테고리 인용 의무** — LLM 이 ID/한글명 매핑 추론하지 말고 응답값 그대로 사용
- **카탈로그 외 매매 패턴 발견 시 `register_rule(enum_name, category, description)` MCP 호출 후 진행** (BLOCKING — `record_trade` 직전에 처리)
- `trades.rule_id` 명시 (옛 한글 enum `trades.rule_category` 는 옛 데이터 호환용 — 라운드 2026-05 마이그 후 신규 매매는 `rule_id` FK 만 사용)
- 룰 폐기는 `deprecate_rule(rule_id, reason)` (soft delete: `status='deprecated'`)

### KR/US 시장 자동 라우팅

종목명/티커로 market 식별:
- KR: 6자리 숫자 / 한글명
- US: 1~5자 대문자 (`AAPL`, `NVDA`, `BRK.B`)

상세 매핑: → `references/market-routing.md`.
판정: LLM 이 입력 형태로 직접 판단 (6자리 숫자 = KR / 1~5자 대문자 = US).

---

## base 자동 갱신 (inline)

base 본문 작성·갱신은 **메인 LLM 이 inline 으로 처리** — multi-device (Mac/iOS/Desktop/웹) 환경에서 동일 동작 보장. (옛 sub-agent 격리 폐기 — 2026-04-30. mobile/Desktop/iOS Custom Connector 가 sub-agent 미지원이라 base 가 매일 stale 화되는 문제 해소.)

### 만기 표

| Base | 만기 | inline 절차 |
|---|---|---|
| economy | 1일 | `references/base-economy-update-inline.md` (입력: market="kr"\|"us") |
| industry | 7일 | `references/base-industry-update-inline.md` (입력: name="반도체"\|"us-tech") |
| stock | 30일 | `references/base-stock-update-inline.md` (입력: code="005930"\|"NVDA") |

### 자동 갱신 정책

각 모드 (daily/discover/research) 진입 시:
1. `check_base_freshness(auto_refresh=True)` MCP 호출 — KR stock_base 데이터는 자동 refresh, 본문 텍스트가 필요한 base 는 `auto_triggers` 반환
2. `is_stale: true` 인 base 마다 즉시 해당 inline 절차 진입 (위 만기 표 참조)
3. **cascade 순서**: economy → industry → stock (메인이 순차 처리)
4. **inline 절차 진입 시 sub-spawn 금지** — 메인이 직접 절차 따름. cascade 의존성도 메인 책임.

### 결과 검증 (Trust but verify)

inline 절차 완료 후 메인이 즉시:
- `get_economy_base(market)` / `get_industry(code)` / `get_stock_context(code).base` 호출
- DB 의 `updated_at` 이 갱신 시작 시각 이후인지 확인
- 미달 시 사용자 보고 + 1회 재시도 (그래도 실패 시 사용자 개입)

이유: inline 절차 결과를 "완료" 라고 자가 보고만 하고 실제 DB 저장 누락 가능성 차단. 무인 운영 신뢰성 핵심.

### stale 룰 — base 본문 vs Daily Appended Facts

- **만기 (stale) 도래** → 본문 재작성 (메인이 inline 절차 따름)
- **트리거 (컨센±15%/실적±10%/신고가/공시 등)** → 본문 갱신 X. **`Daily Appended Facts` 섹션에 append 만** (사용자 정책: 4/28)
- 4/28 메모리 룰 `feedback_stale_auto_call.md` 정합

---

## 데이터 태깅 · 할루시네이션 방어

### 태그 규칙

- **[실제]** — MCP 조회값·DART/SEC 확정치
- **[추정]** — MCP 데이터 + 내 계산
- **[가정]** — 시나리오용 설정값 (변경 가능 명시)

### "모른다" 선언 의무

- base 없는 종목: MCP 조회 결과 없으면 추정 절대 금지, "base 미작성" 명시
- 애널 컨센 없음: `get_analyst_consensus` → None 이면 "애널 커버 없음"
- 재무 비공개: `compute_financials` 실패 시 "DART/SEC 재무 접근 불가, 미공시 가능"
- 비교기업: 실존 + DB 검증된 종목만 멘션

---

## 매매 집행 전 체크리스트 (모든 모드 공통)

매수 / 피라미딩 / 매도 결정 직전 체크:

```
[ ] check_concentration → 25% 룰 통과
[ ] 예수금 충분 (currency 기준 — KRW / USD 분리)
[ ] 실적 D-7 이내면 손절선 타이트화
[ ] 최근 외인/기관 수급 톤 (analyze_flow)
[ ] 동일 섹터 보유 총합 (portfolio_correlation)
[ ] 회고 룰 — get_weekly_context.rolling_stats.rule_win_rates 확인
    • 적용할 rule_category 의 누적 승률 < 50% → D+1 안착 룰 또는 추가 검증 강제
    • < 30% → 4주 누적 폐지 후보 (사용자 검토 권장)
[ ] 변동성 + 재무 grade LLM 본문 판단 → master-principles 의 변동성 관리 / 재무 우량 원칙 적용
[ ] ⭐ record_trade 시 rule_id 명시 — DB rule_catalog 인용 (참고: references/rule-catalog.md)
    • DB rule_catalog 테이블이 single source-of-truth (16 active 룰, 라운드 2026-05)
    • 카탈로그 외 매매 패턴 발견 시 register_rule MCP 호출 후 진행 (BLOCKING)
    • rule_category 한글 enum 은 옛 데이터 호환용 (신규 매매는 rule_id 명시)
[ ] 집행 후 trades AFTER trigger 가 positions / cash_balance / realized_pnl 자동 재계산
[ ] 필요 시 propose_watch_levels(persist=True) 로 감시 레벨 자동 생성
```

상세 원칙: → `references/master-principles.md` (옛 position-action-rules 는 `_archive/` 에 보존).

---

## ⛔ 종목 신규 등록 시 industry_code 매핑 의무

신규 종목을 stocks 테이블에 INSERT 하는 모든 진입점에서 LLM 이 즉시 industry_code 를 판단해서 같이 입력. **NULL 상태로 stocks INSERT 절대 금지**.

### 진입점

- `record_trade` — 처음 매매 종목이면 stocks row 자동 생성됨
- Pending 포지션 추가 — 감시 종목 등록 시
- `save_stock_base` — base 저장 시 stocks row 신규/갱신

### 매핑 절차

1. **종목명/티커로 산업 판단** — 사업 영역, 섹터, 매출 구성
   - 예: 하나금융지주 → `금융지주`, 삼성SDI → `2차전지`, 이수페타시스 → `AI-PCB`, NVDA → `us-tech`, GOOGL → `us-communication`

2. **industries 테이블 존재 확인**
   - `get_industry(code)` → 있으면 매핑
   - 없으면 → 메인이 `references/base-industry-update-inline.md` 절차로 직접 작성 후 매핑

3. **stocks.industry_code UPDATE**
   - INSERT 시점에 같이 입력하거나, 누락됐으면 즉시 UPDATE

4. **매핑 검증** (analyze_position 의 is_stale 자동 derive 제거 — v2)
   - `check_base_freshness()` 결과의 `industries[]` 에 해당 종목 산업이 보이지 않으면 매핑 누락 신호
   - 또는 `get_industry(industry_code)` 직접 호출 후 None 이면 매핑 누락 / industry_code 미등록

### 산업 코드 컨벤션

- KR: 한글 슬러그 (`반도체`, `게임`, `전력설비`, `지주`, `금융지주`, `2차전지`, `AI-PCB`)
- US: `us-{gics_sector_slug}` (`us-tech`, `us-communication`)

### 누락 발생 시

- 발견 즉시 처리 (다음 daily 까지 미루지 않음)
- 같은 종목 base.md 의 "섹터" 메타와 일관성 검증

---

## 모드별 워크플로우 (상세는 references/)

### daily 모드 → `references/daily-workflow.md`

**일일 운영** — 보유(Active) + 감시(Pending) 종목 일일 보고서 + 포트폴리오 종합.

핵심:
- ⛔ BLOCKING 11개 — Phase 0~1 진입 전 필수 (v6 단순화 + WebSearch 자율, 라운드 2026-05)
- v6 7-Phase Pipeline (Phase 0~7, per-stock 5단계 정합)
- `analyze_position(code, include_base=True)` 1 MCP 로 12 카테고리 묶음 반환 (base 본문 3층 + disclosures + insider + 정량 raw)
- KR/US 하이브리드 통화별 분리

### discover 모드 → `references/discover-workflow.md`

**신규 종목 발굴** — 광역 모멘텀 → 좁은 분석 → Top 3~5.

핵심:
- 광역 모멘텀이 메인, `screen_stocks`/`discover_by_theme` 는 부산물
- KR (~2,500 종목) / US (S&P500 ∪ NDX100 ~530)
- 변동성×재무 매트릭스 셀로 진입 사이즈 결정

### research 모드 → `references/research-workflow.md`

**6차원 정량 분석** — 재무/기술/수급/모멘텀/이벤트/컨센.

핵심:
- daily / discover 의 종목별 상세 분석 호출
- base 만료 시 메인 inline 처리 (위 cascade)
- 유의미 발견 → 종목 base 의 `Daily Appended Facts` append

---

## MCP 89 툴 인벤토리 (v1 라운드 2026-05 — 전수 재계산)

### 📊 조회 (7)
`get_portfolio`, `get_portfolio_summary`, `get_stock_context`, `get_applied_weights`, `list_trades`, `list_tradable_stocks`, `list_daily_positions`

### 📈 기술·시그널 (8)
`compute_indicators`, `compute_signals`, `refresh_daily`,
`detect_market_regime`, `analyze_volatility`, `rank_momentum`, `rank_momentum_wide`,
`backtest_signals` (단일 종목 12 시그널 5/10/20일 hold 승률 측정)

### 💰 재무·애널 (8)
`compute_financials`, `detect_earnings_surprise_tool`,
`record_analyst_report`, `list_analyst_reports`, `get_analyst_consensus`, `analyze_consensus_trend`,
`refresh_kr_consensus`, `refresh_us_consensus`

### 🔬 리스크·이벤트 (5)
`check_concentration`, `detect_portfolio_concentration`,
`detect_events`, `analyze_flow`, `portfolio_correlation`

### 🎯 진입 설계 (3)
`propose_position_params`, `propose_watch_levels`, `compute_score`

### 🔍 실시간 시세 (4)
`kis_current_price`, `kis_us_quote`, `kis_intraday`, `realtime_price`

### 📦 종목 분석 단일 진입점 (1)
`analyze_position` — 12 카테고리 묶음 (base 본문 3층 + disclosures + insider + context + realtime + indicators + signals + financials + flow + volatility + events + consensus). per-stock-analysis 5단계의 3단계 = 1 MCP 정신.

### 📝 쓰기 (10)
`record_trade` (cash_balance 자동 갱신 — issue #7 trigger), `register_stock` (신규 종목 등록 — industry_code 매핑 의무),
`save_daily_report`, `save_portfolio_summary`,
`save_stock_base`, `save_industry`, `save_economy_base`,
`override_score_weights`, `reset_score_weights`, `refresh_stock_base`

### 🌐 발굴 (2)
`screen_stocks`, `discover_by_theme`

### 🔧 base 운영 (6)
`get_economy_base`, `get_industry`, `check_base_freshness`,
`append_base_facts` (Daily Appended Facts append),
`propose_base_narrative_revision` (회고 phase 3 narrative 충돌 시 큐 적재),
`get_pending_base_revisions` (BLOCKING #11 daily 진입 시 알림용)

### 📊 산업 메트릭 (1) ⭐ v1 신규 (2026-05)
`compute_industry_metrics` — leader_followers 기반 avg_per/avg_pbr/avg_roe/avg_op_margin/vol_baseline_30d 자동 산출. industry-inline v6 메트릭 자동화.

### 🌍 정형 매크로 (5) ⭐ v1 신규 (2026-05)
`get_macro_indicators_us` (FRED 시계열 — DFF/CPI/UNRATE/DGS10/SP500 등),
`get_macro_indicators_kr` (한국은행 ECOS — 기준금리/CPI/M2/경상수지/실업률/외환보유고/산업생산 8 default stat_code),
`get_yield_curve` (UST 3M~30Y + 10Y_3M_spread + 역전여부),
`get_fx_rate` (FRED DEXKOUS 기본, 1일 TTL),
`get_economic_calendar` (Finnhub 경제 캘린더 + 컨센서스)

### 📰 공시 + insider (5) ⭐ v1 신규 (2026-05)
`get_kr_disclosures` (DART 14일), `get_us_disclosures` (EDGAR 14일),
`get_kr_insider_trades` (DART 임원·주요주주 거래), `get_kr_major_shareholders` (DART 대주주 현황),
`get_us_insider_trades` (Finnhub 90일, 본문 파싱 OK)

### 📅 주간 회고·전략 (14)
- 종합 회고 (5): `save_weekly_review`, `get_weekly_review`, `list_weekly_reviews`, `get_weekly_context`, `reconcile_actions`
- 종목별 회고 (6, 라운드 2026-05): `save_weekly_review_per_stock`, `get_weekly_review_per_stock`, `list_weekly_review_per_stock`, `list_weekly_review_per_stock_by_code`, `prepare_weekly_review_per_stock`, `prepare_weekly_review_portfolio`
- 주간 전략 (3): `save_weekly_strategy`, `get_weekly_strategy`, `list_weekly_strategies`

### 🧠 학습 패턴 (3)
`append_learned_pattern`, `get_learned_patterns`, `promote_learned_pattern`

### 📚 룰 카탈로그 (6, 라운드 2026-05 — DB single source-of-truth)
`list_trades_by_rule` (주간 회고 helper. trades 를 rule_id 별 그룹 반환),
`list_rule_catalog`, `register_rule`, `update_rule`, `deprecate_rule`, `get_rule`
→ `references/rule-catalog.md` 참고 (DB rule_catalog 테이블이 정의처).

### 🩺 운영 (1)
`healthcheck` — 전체 도구 + 8 스크래퍼 + DB 정합 + 신선도 일괄 점검 (quick=True 기본 ~30s)

---

## 수치 표기 규칙

- 주식수: **X주** (절반·1/3 금지)
- 금액: "5주 × ₩267,500 = ₩1,337,500"
- 수익: "+2.52% = +₩184,016"
- US 분수주 허용: 26.7975주

---

## 출력 원칙

- 마크다운 자유, 테이블 가독성 우선
- 장 상태 필수 표기
- 투자의견 반드시 3관점 (중장기/단기/포지션)
- 각 시그널 진입가/손절가 명시
- 집행 전 집중도 체크 결과 인용
- **한 줄 결론 필수** — 각 보고서 끝에
- 모든 숫자 [실제]/[추정]/[가정] 태깅
- WebSearch 결과 출처 + 시점 명시
- 컨센 데이터는 매번 fetch (캐시 재사용 금지)

---

## 메타 정보

### 프로젝트 경로

```
~/Desktop/Project/stockclaude/          ← MCP 서버 (FastAPI + PG + 67 tools 인벤토리)
  .mcp.json                                ← Claude Code 자동 등록
  server/
    api/, scrapers/, analysis/, repos/, jobs/, mcp/
  db/schema.sql                            ← 19개 테이블 + 트리거

~/.claude/skills/stock/                    ← 본 skill (단일 통합)
  ├── SKILL.md (이 파일)
  ├── references/  (36개 파일 — base-*-update-inline 3개 + weekly-* 3개 + rule-catalog 등 포함, _archive/ 별도)
  └── assets/      (15 templates — weekly-review 3개 포함)
  (agents/ 폐지 — 2026-04-30, base-*-update-inline.md 로 통합)
  (scripts/ 폐지 — 모든 분석·계산은 MCP 단일 의존)

~/.claude/commands/                        ← wrapper 6개 (호환 슬래시)
  stock-daily.md, stock-discover.md, stock-research.md,
  base-economy.md, base-industry.md, base-stock.md

~/.claude/_archive_skills_2026-04-28/      ← 마이그레이션 백업 (롤백용)
```

### 서버 기동 (필요 시)

```bash
cd ~/Desktop/Project/stockclaude
docker compose up -d                       # PG + Adminer
uv run uvicorn server.main:app --reload    # FastAPI (선택)
```

MCP 서버는 `.mcp.json` 으로 Claude Code 가 자동 기동.

### 배치 job

```bash
uv run python -m server.jobs.daily_snapshot    # 매일 장 마감 후
uv run python -m server.jobs.refresh_base      # 분기별 재무 갱신
```

---

## 보조 파일 인덱스

### references/ (36개, _archive/ 별도 3개)

**공통 룰** (모든 모드 적용):
- `master-principles.md` — 거장 트레이딩 원칙 10 카테고리 ⭐ (v6 신설, 옛 매트릭스 대체)
- `signals-12.md` — 12 기술 시그널 정의
- `overheat-thresholds.md` — 과열 경고 임계
- ~~`position-action-rules.md`~~ → `_archive/` 로 이동 (v6, 매트릭스 anchor 폐기)
- `market-routing.md` — KR/US 데이터 소스 분기

**모드별 워크플로우**:
- `daily-workflow.md` — daily 모드 (BLOCKING 11 + Phase 0~7, v6 단순화)
- `discover-workflow.md` — discover 모드 (광역 모멘텀 → Top 3~5)
- `research-workflow.md` — research 모드 (6차원 verdict)

**daily 보조**:
- ~~`decision-tree.md`~~ → `_archive/` 로 이동 (v6). Phase 5 액션 결정은 master-principles + LLM 본문 판단
- `expiration-rules.md` — base 만기·자동 재생성
- `base-impact-classification.md` — 4분류 (high/medium/review/low)
- `base-patch-protocol.md` — Daily Appended Facts append 절차
- `websearch-rules.md` — WebSearch 단위별 LLM 자율 가이드 (v7 — BLOCKING 폐지, 종목/economy/industry/stock 단위별 권장 강도 표)
- `weekly-context-rules.md` — 4가지 활용 룰
- `snapshot-schema.md` — `save_portfolio_summary` JSON 스키마

**research 보조**:
- `six-dim-analysis.md` — 6차원 해석 룰
- `valuation-frameworks.md` — Reverse/Forward DCF/확률가중/Comps/SOTP
- `momentum-6dim-scoring.md` — 모멘텀 스코어링
- `momentum-principles.md` — 5대 원칙
- `momentum-filters.md` — 진입/청산/Crash 방어
- `deal-radar-checklist.md` — 6종 WebSearch
- `analyst-consensus-tracking.md` — 컨센 추적

**discover 보조**:
- `discover-filters.md` — 1/2/3단계 필터 + 매트릭스 적용
- `theme-keywords.md` — 테마별 키워드 (10+ 카테고리)

**base inline 절차** (메인이 따라하는 절차서):
- `base-economy-update-inline.md` — 거시 base 갱신 inline (1일 만기, 8 섹션 + 메타 7키)
- `base-industry-update-inline.md` — 산업 base 갱신 inline (7일 만기, 8 섹션 + 메타 5키 + score)
- `base-stock-update-inline.md` — 종목 base 갱신 inline (30일 만기, 9 섹션 + 17 인자)

**base 부속 룰**:
- `economy-base-classification.md` — 경제 base 영향도 4분류
- `industry-base-classification.md` — 산업 base 영향도 4분류
- `industry-sectors.md` — KR 11 + US GICS 11 매핑
- `stock-base-classification.md` — 종목 base 영향도 4분류
- `narrative-10-key-points.md` — 10 Key Points 작성

### agents/ — 폐지 (2026-04-30)

옛 `base-economy-updater` / `base-industry-updater` / `base-stock-updater` 3 sub-agent 는 multi-device 운영 호환을 위해 inline 절차로 통합됨. `references/base-*-update-inline.md` 3 파일 참조.

### scripts/ — 폐지 (MCP 단일 의존)

기존 9개 script (detect_market / concentration_check / fetch_consensus / valuation_call 등) 모두 MCP 도구로 대체됨. 시장 판정·집중도·컨센 fetch·DCF 호출은 LLM 이 MCP 직접 호출 (위 89 툴 인벤토리 참조). multi-step orchestration (discover Pending 등록 등) 도 LLM 이 MCP 시퀀스로 직접 처리.

### assets/ (12 templates)

- `daily-report-template.md` — 종목 daily 본문
- `portfolio-summary-template.md` — 포트폴리오 종합 요약
- `position-template.md` — 보유 종목 position.md (변동성×재무 등급 포함)
- `dependency-audit-template.md` — Audit 출력 + ⚠️ 반쪽 daily
- `economy-daily-template.md` — economy/{날짜}.md 자동 생성
- `economy-base-template.md` — 경제 base.md 표준 (6차원)
- `industry-base-template.md` — 산업 base.md 표준 (5차원)
- `base-stock-template.md` — 종목 base.md 표준 (9 섹션)
- `score-block-template.md` — 등급 블록 표준
- `momentum-ranking-template.md` — Top N 출력
- `rebalance-template.md` — 월간 리밸런싱
- `discover-output-template.md` — 발굴 결과 표준 출력

---

## 지침 요약

1. **MCP 먼저** — 숫자·데이터는 항상 MCP 호출, 암기/추정 금지
2. **거장 원칙 우선** — `references/master-principles.md` 의 10 카테고리 추상 방향성. 케이스별 수치는 LLM 본문 판단 (산업 평균 대비)
2.5. **추론은 자연어, 결론은 정량** (v7) — 보고서 본문은 자연어 reasoning (anchor 없음), 저장 시 정량 컬럼 (verdict/size_pct/stop/override_dimensions/key_factors/referenced_rules) 의무. 추적/검증 가능한 학습 누적의 본체
3. **base 만기 → 메인 inline 처리** — `references/base-*-update-inline.md` 절차 따름. cascade 지휘 + DB read-back 검증 메인 책임
4. **6차원 분석** — daily / discover 모두 research 차원 활용
5. **point of truth: 보조 파일** — 같은 룰 여러 곳 복제 금지, references 정의처에서만
6. **태깅 의무** — [실제]/[추정]/[가정], 불확실은 명시
7. **집중도 우선** — 매수 제안 전 `check_concentration` 반드시
8. **자동화 활용** — `record_trade` 후 positions/realized_pnl 은 DB 트리거가 처리
9. **industry_code 매핑 의무** — NULL 금지
10. **모드 라우팅** — 사용자 입력에 따라 daily / discover / research / base-* inline 진입
