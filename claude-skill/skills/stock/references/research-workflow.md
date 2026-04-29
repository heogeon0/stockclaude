# Research Workflow — 6차원 정량 분석 절차

> stock skill 의 research 모드 진입 시 따라야 할 워크플로우.
> 6차원 (재무 / 기술 / 수급 / 모멘텀 / 이벤트 / 컨센) 종합 분석.
> daily 모드 / discover 모드가 종목별 호출.

---

## 역할

**공통 정량 분석** 전담:
- 재무 / 기술 / 수급 / 모멘텀 / 이벤트 / 컨센 **6차원** 동시 분석
- KR / US 시장 자동 라우팅
- base 만료 감지 → sub-agent 자동 spawn
- 유의미 발견 → 종목 base 의 `Daily Appended Facts` 섹션에 즉시 patch
- daily / discover 가 액션 결정에 사용할 종합 데이터 반환

**하지 않는 것**:
- 일일 보고서 / 액션 플랜 → daily 모드
- 신규 발굴 / 광역 스크리닝 → discover 모드
- base 본문 작성·갱신 → sub-agent (`agents/base-*-updater`)

---

## MCP 툴 매핑 (6차원 표준)

| 차원 | MCP 툴 |
|---|---|
| 재무 | `compute_financials(code, years=3)` |
| 기술 | `compute_indicators(code)` + `compute_signals(code)` |
| 수급 | `analyze_flow(code, window=10)` (KR) / 13F + 옵션 + Insider (US) |
| 변동성 | `analyze_volatility(code)` (regime 분류) |
| 모멘텀 | `rank_momentum(codes)` / `rank_momentum_wide(market)` |
| 이벤트 | `detect_events(code)` (실적 D-N + 52w + rating) |
| 컨센 | `get_analyst_consensus(code)` + `list_analyst_reports(code, days=90)` + `analyze_consensus_trend(code)` |
| 등급 | `compute_score(code)` (5차원 종합) |
| 컨텍스트 | `get_stock_context(code)` (base + daily + position + watch 번들) |

상세 차원별 해석 룰: → `six-dim-analysis.md` 참조 (research 핵심 룰).

---

## 호출 인터페이스

### 1. 종목 단일 분석 — `/stock-research {종목}`
- 6차원 정량 분석 + 종합 verdict
- base 만료 시 자동 갱신 (sub-agent spawn)
- 유의미 발견 시 종목 base append

### 2. 비교 분석 — `/stock-research {종목A} vs {종목B}`
- 두 종목 6차원 비교 (특히 Comps 측면)

### 3. 부분 분석 — `/stock-research {종목} --dim financial,consensus`
- 특정 차원만 (시간 절약)

### 4. 리밸런싱 모드 — `/stock-research --rebalance`
- 보유 종목 전체 6차원 재평가
- 모멘텀 / 컨센 변동 큰 종목 식별
- 출력: → `~/.claude/skills/stock/assets/rebalance-template.md` 참조

---

## 실행 순서

### 0단계 — 의존성 체크 (필수 선행)

base 만료 시 sub-agent spawn 연쇄:

| 만료/없음 | 행동 |
|---|---|
| `economy_base` 만기 1일+ | `Agent("base-economy-updater", market=...)` spawn |
| `industry_base` 만기 7일+ | `Agent("base-industry-updater", name=...)` spawn |
| `stock_base` 만기 30일+ | `Agent("base-stock-updater", code=...)` spawn |

연쇄 순서: economy → industry → stock (메인 LLM 순차 spawn, sub-agent 안에서 sub-spawn 금지).
각 spawn 종료 후 메인이 DB read-back 으로 검증 (Trust but verify).

### 1단계 — Market 라우팅 + 데이터 수집

종목 입력 → market 자동 판정:
- KR/US 데이터 소스 매핑: → `market-routing.md` 참조
- 시장 판정 코드: → LLM 직접 판단 (6자리 숫자 = KR / 1~5자 대문자 = US)

데이터 수집 (MCP 워크플로우):
- 자동화 스크립트: → MCP 9 도구 일괄 호출 (LLM 직접) (`fetch_via_mcp()`)
- 9개 MCP 툴 일괄 호출 (재무 / 컨센 / 리포트 / 추이 / 수급 / 변동성 / 이벤트 / 등급 / 시그널 / 지표 / 컨텍스트)

### 2단계 — 6차원 정량 분석

각 차원별 해석 룰 / 출력 포맷: → `six-dim-analysis.md` 참조.

차원별 보조 파일:
- 모멘텀: → `momentum-6dim-scoring.md` (스코어링)
- 모멘텀 원칙: → `momentum-principles.md` (5대 원칙)
- 모멘텀 필터: → `momentum-filters.md` (진입 / 청산 / Crash 방어)
- 컨센: → `analyst-consensus-tracking.md`

### 3단계 — Valuation 실계산

Valuation 프레임워크: → `valuation-frameworks.md` 참조 (Reverse / Forward DCF / 확률가중 / Comps / SOTP).

호출 코드:
- MCP 호출 + LLM 시나리오 작성 (Reverse/Forward DCF) — KR/US 자동 분기
- MCP 9 도구 일괄 호출 (LLM 직접)

### 4단계 — 딜 레이더 WebSearch (선택)

base 갱신 모드 또는 트리거 발동 시: 6종 WebSearch 카테고리 → `deal-radar-checklist.md` 참조.

### 5단계 — 종합 verdict 산정

6차원 결과 종합:
```
재무 등급: A/B/C/D
기술 verdict: 강한매수 / 매수우세 / 중립 / 매도우세 / 강한매도
수급 신호: 매집 / 분산 / 엇갈림
모멘텀 등급: A+ / A / B / C / D
이벤트 플래그: 실적 D-N / 52w / rating
컨센 신호: 강화 / 약화 / 만장일치 Buy / 분포 폭
변동성 regime: normal / high / extreme
```

→ 종합 판단 (논리)
→ daily / discover 가 받아 액션 플랜 또는 진입 가능성 판단

### 6단계 — 유의미 발견 → 종목 base 즉시 patch

high / medium / review_needed 분류된 fact 는 즉시 종목 base 의 `Daily Appended Facts` 섹션에 append (본문 갱신 X — stale 정책).

- 분류 룰: → `stock-base-classification.md` 참조
- Patch 절차: → `base-patch-protocol.md` 참조

---

## 모멘텀 흡수 (이전 stock-momentum 폐지)

stock-momentum 폐지 → research 의 6차원 중 한 차원 ("모멘텀") 으로 통합.

### 광역 스크리닝
```
rank_momentum_wide(market='kr', top_n=30, min_market_cap_krw=3_000_000_000_000)
→ Top N 출력 (assets/momentum-ranking-template.md)
```

### 종목군 랭킹
```
rank_momentum(codes=['005930', '000660', ...], market='kr')
→ 상대 모멘텀 + Z-score
```

### Dual Momentum
- Absolute: `rank_momentum` 의 12-1 수익률 + benchmark 비교 (LLM 직접 계산)
- Relative: 종목군 내 z-score → Buy / Cash / Bench 결정

### 시장 국면
```
detect_market_regime(reference_code='005930')
→ KOSPI 4조건 + 모멘텀 가동 여부
```

---

## 보조 파일 인덱스

references:
- `six-dim-analysis.md` — 6차원 해석 룰 (research 핵심)
- `market-routing.md` — KR/US 데이터 소스 + valuation 분기
- `valuation-frameworks.md` — Reverse/Forward DCF/확률가중/Comps/SOTP
- `deal-radar-checklist.md` — 6종 WebSearch
- `momentum-6dim-scoring.md` — 모멘텀 6차원 스코어
- `momentum-principles.md` — 5대 원칙
- `momentum-filters.md` — 진입/청산/Crash 방어
- `analyst-consensus-tracking.md` — 컨센 추적

assets:
- `momentum-ranking-template.md` — Top N 출력
- `rebalance-template.md` — 월간 리밸런싱
