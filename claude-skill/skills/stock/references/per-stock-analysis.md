# Per-Stock Analysis — 종목 1건 분석 단일 진입점

> 종목 1건 분석은 모드 (daily / research / discover) 와 무관하게 본 절차 **단일 사용**.
> deterministic 산출 (scoring / cell / is_stale) 은 `analyze_position` 응답에서 제거됨 (v2 슬림화). LLM 본문 판단으로 통일.
> 호출 단위 = 종목 1개. 포트 단위 처리는 `daily-workflow.md` 가 별도 담당.

---

## 진입 가드

- **다른 작업 중 진입 시**: 직전 분석 결과 (다른 종목 / 포트폴리오) 를 본 종목 본문에 인용하지 않음. 깨끗한 상태로 7 단계 처음부터.
- **단일 책임**: 종목 1개의 verdict + 정량 결론 + 보고서 생성·저장. 포트 단위 호출 (regime / correlation / concentration / weekly_context / portfolio_summary) 은 본 절차 밖.
- **압축 금지**: LLM '효율 추구' 본능으로 단계 합치기·생략 금지. 7 단계 모두 통과해야 1건 완료.

---

## 입력 인자

```
code: 종목 코드 (KR 6자리 숫자 or US 1~5자 대문자, 예: "005930", "NVDA")
market: optional — 생략 시 자동 판정 (6자리 숫자 = KR / 1~5자 대문자 = US)
```

---

## 7 단계 절차

### 1단계 — base 신선도 체크
- `check_base_freshness(auto_refresh=True)` 호출
- 응답에서 종목별 stale 여부 확인:
  - `economy[market].is_stale`
  - `industries[]` 중 해당 종목의 industry_code 행
  - `stocks[]` 중 해당 종목 코드 행
- ⚠️ `analyze_position` 자체는 더 이상 is_stale 자동 판정 안 함 (v2-c 후 제거). 본 단계가 단일 진입점.

### 2단계 — stale 갱신 (cascade)
stale 차원에 대해 **cascade 순서 (economy → industry → stock)** 로 inline 절차 실행. 본문 옮기지 않고 절차서 인용:

| 차원 | 절차서 |
|---|---|
| economy stale | `references/base-economy-update-inline.md` |
| industry stale | `references/base-industry-update-inline.md` |
| stock stale | `references/base-stock-update-inline.md` |

각 inline 절차 완료 후 read-back 검증 의무 (`updated_at` 갱신 확인).

> **⛔ 자율 스킵 금지**: '효율 우선' / '시간 절약' / '1일 정도 무시' 같은 LLM 능동 회피 패턴 차단. 사용자 명시 승인 없이는 stale 갱신 스킵 X.

### 3단계 — base 조회 (3층 본문 LLM 컨텍스트 로드)
3 호출로 Top-down 컨텍스트를 LLM 에 명시 로드:

```
get_economy_base(market)             # 시장 매크로 본문 (8 섹션)
get_industry(industry_code)          # 산업 base 본문 (8 섹션)
get_stock_context(code).base         # 종목 base 본문 (9 섹션)
   또는 stock_base.get_base(code)
```

→ 본문 텍스트가 LLM 컨텍스트에 자리잡아야 6단계 LLM 판단에서 Top-down 정합성 / cycle_phase / scenarios 인용 가능.

> **prompt cache 효율**: 같은 daily 안 종목 N개 분석 시 `get_economy_base(market)` 응답은 동일 → 캐시 히트. `get_industry` 도 같은 산업 종목들끼리 캐시. base 본문을 `analyze_position` 응답에 inject 하지 않는 이유.

### 4단계 — analyze_position 조회 (raw 데이터)
`analyze_position(code)` 1회 호출.

응답 카테고리 (v2 슬림화 후):
- context (stock + base + position + watch + latest_daily)
- realtime (현재가 / 장 상태)
- indicators (12 지표 — SMA/RSI/MACD/BB/일목 등)
- signals (12 전략 + summary.종합)
- financials (ratios + growth + raw_summary, **score 제거**)
- flow (KR 기관/외인 z-score)
- volatility (RV / Parkinson / regime / drawdown)
- events (실적 D-N / 52주 돌파 / 등급 변경)
- consensus (컨센 view + 목표가 추세 + rating wave)
- coverage_pct + errors

⚠️ 응답에 **scoring / cell / is_stale 없음**. financials.score 도 strip.

`coverage_pct < 80%` 시 보고서 최상단에 ⚠️ 반쪽 분석 명시.

### 5단계 — WebSearch (당일 뉴스) ⭐
종목별 **1회 호출** — 정량 데이터에 nuance 추가.

| 표준 쿼리 | 다루는 nuance |
|---|---|
| `"YYYY-MM-DD {종목명} 뉴스"` (KR) | 컨센 변경, 임원 거래, 공시, 실적 가이던스 |
| `"{ticker} {date} news earnings"` (US) | analyst 등급 변경, M&A, 가이던스 |

추가 룰: `references/websearch-rules.md` 의 의무 + 5종 추가 조건.

> **⛔ 의무 시점**: LLM 판단 **전**. 저장 후엔 의미 X (보고서에 인용 못 함). 6단계 진입 직전이 마지막 호출 기회.

### 6단계 — LLM 종합 판단
4단계 raw 데이터 + 5단계 뉴스 + 3단계 base 본문 + **회고 학습 + 거장 원칙** 종합.

#### 6단계 인풋 (필수 6개)
```
1. analyze_position raw (4단계 결과)
2. economy / industry / stock base 본문 (3단계)
3. weekly_context (회고 + rule_win_rates + learned_patterns)  ← v7 신규 의무
4. master-principles (거장 원칙 10 카테고리)                   ← v6 신규 의무
5. weekly_strategy (이번 주 전략, brainstorm 결과)             ← v8 신규 의무
6. references 룰 정의 (signals-12, overheat-thresholds, rule-catalog)
```

#### 6-1. 회고 인용 (v7 의무)
```python
get_weekly_context(weeks=4)
   → rule_win_rates: {rule_id: win_rate}
   → 회고 본문 + lessons_learned + pattern_findings 인용

get_learned_patterns(status='user_principle')  # 사용자 고유 원칙
get_learned_patterns(status='principle')       # 시스템 격상 원칙
   → per-stock-analysis 시 우선 인용
```

⚠️ rule_win_rates < 30% 룰은 **자제 권장**, 적용 시 reasoning 명시.

#### 6-1.5. weekly_strategy 인용 (v8 의무)
```python
strategy = get_weekly_strategy()  # None 이면 첫 주
```

판단 시 인용:
- **종목 결정이 이번 주 전략에 정합 / 충돌** 본문 명시 (보고서)
- `rules_to_emphasize` 인용 — 강화 룰이면 매수 가중치 ↑
- `rules_to_avoid` 인용 — 자제 룰이면 적용 시 reasoning 의무
- `risk_caps` 게이트 검증:
  - `single_trade_pct` 한도 — 단일 거래 risk %
  - `sector_max` — 섹터 비중 상한
  - `cash_min` — 최소 현금 비중

⚠️ `carry_over=True` 면 보고서 최상단에 "지난주 전략 사용 중 (이번 주 brainstorm 미작성)" 표기 의무.

#### 6-2. 핵심 판단 흐름

1. **변동성 regime + 재무 grade 로 셀 결정** — `analyze_position.volatility.regime` (서버) + `financials.ratios + growth` 본문 판단 (산업 평균 대비, A/B/C/D, **점수 anchor 금지**)
2. **signals.summary.종합** 으로 verdict 1차 후보 (5종)
3. **master-principles 의 손익 관리 / 추세 / 변동성 / 사이클 / 이벤트 등 카테고리** 인용 → 액션 방향 본문 판단
4. **Top-down 정합성**: 경제 cycle_phase × 산업 cycle_phase × 종목 상태 → 1~2줄 본문 코멘트 (v5 보고서 섹션)
5. **8 override 차원 적용**: 실적 D-7 / 외인 z±2 / regime / 52w / VCP / 재무 critical / 포트 corr / consensus 추세
6. **weekly_strategy 정합성**: rules_to_emphasize / rules_to_avoid / risk_caps 게이트 인용
7. **게이트 검증**: `check_concentration` / 예수금 / 실적 D-7 / 수급 z. 통과 못하면 자동 매매 차단

→ 최종 액션 + 사이즈 + 손절선 + reasoning.

#### 6-3. 회고 인사이트 누적
- 본 종목 분석에서 **새 패턴 발견** 시 `append_learned_pattern(tag, description, ...)` 호출 권장 (또는 weekly_review 작성 시 일괄)
- 보고서 본문에 인용한 learned_patterns / rule_win_rates 명시

---

## 판단 룰 인덱스 (LLM 이 6단계에서 인용)

룰 본문은 옮기지 않음. 필요 시 references 직접 Read.

| 영역 | 파일 |
|---|---|
| ⭐ 검증된 거장 원칙 (10 카테고리, 출발점) | `references/master-principles.md` (v6 신설 — Livermore/Minervini/Buffett/Marks 등) |
| 12 시그널 해석 | `references/signals-12.md` |
| 과열 임계 (RSI / Stoch / 52w 등) | `references/overheat-thresholds.md` |
| 6차원 분석 깊이 (research 모드) | `references/six-dim-analysis.md` 또는 `research-workflow.md` |
| 룰 카탈로그 (record_trade.rule_category 입력) | `references/rule-catalog.md` |
| 옛 매트릭스 (참고용 보존, 인용 X) | `references/_archive/scoring-weights.md`, `decision-tree.md`, `position-action-rules.md` |

### ⚠️ 매트릭스 룩업 폐기 (v6, 2026-05)

scoring-weights / decision-tree / position-action-rules 의 매트릭스 룩업은 **anchor 효과 + 검증 안 된 직관적 설계** 로 폐기됨. 대체:
- 출발점 = `master-principles.md` 의 추상 방향성 (구체 수치 X)
- 케이스별 적용 = LLM 본문 판단 (산업 평균 + 컨텍스트 + Top-down)
- 학습 = weekly_review 의 자연어 인사이트 + rule_catalog win-rate

### 산업 평균 대비 본문 판단 가이드 (v6-k)

financial_grade (A/B/C/D) 결정 시 **절대값 anchor 금지**, **산업 평균 대비** 본문 판단:

```
industries 테이블의 표준 메트릭 인용 (v6-f 컬럼):
- avg_per / avg_pbr / avg_roe / avg_op_margin / vol_baseline_30d

LLM 본문 판단:
- 종목 PER vs 산업 avg_per → 할인/프리미엄 여부
- 종목 ROE vs 산업 avg_roe → 우열
- 종목 변동성 vs 산업 vol_baseline_30d → regime 보정
→ A/B/C/D 종합 grade 결정 (점수 anchor X, 본문)
```

### ⚠️ score 사용 가이드

`stock_base.financial_score` / `compute_financials.score` / `compute_score.total_score` 는:
- discover / screen 의 빠른 1차 필터용
- 종목 1건 분석에서는 본문 (ratios + growth + 산업·경제 컨텍스트) 보고 **LLM 판단 우선**
- 점수에 anchor 되지 말 것 — 점수 자체에 정성 / 디폴트 / 임의 가중합 섞여있음

---

### 7단계 — 출력 + 저장

#### 보고서 작성
`assets/daily-report-template.md` 사용. 의무 섹션:

- **📐 Top-down 연결** (v5 신설) — 경제 regime → 산업 phase → 종목 상태 1~2줄
- **한 줄 결론** — verdict 5종 + 핵심 사유 1~2줄
- **📊 결론 메타** (v7 신설) — 정량 결론 필드 (size_pct/stop/override/key_factors/referenced_rules)
- **데이터 태깅** — `[실제]` / `[추정]` / `[가정]` (SKILL.md 룰)

#### 저장 (정량 결론 의무)
```python
save_daily_report(
    code=...,
    date=today,
    verdict="강한매수" | "매수우세" | "중립" | "매도우세" | "강한매도",  # 필수
    content=<보고서 본문>,
    # v7 (2026-05): 결론 정량 컬럼 — 추론 자연어 / 결론 정량 (G6)
    size_pct=70,                              # LLM 결정 사이즈 %
    stop_method="%",                          # "%" or "ATR"
    stop_value=-7,                            # % 또는 ATR 배수
    override_dimensions=["earnings_d7", "consensus_upward"],
    key_factors=[
        {"factor": "산업 RS +18.5% (성장 phase)", "weight": "+"},
        {"factor": "실적 D-6 (이벤트 리스크)", "weight": "-"},
        {"factor": "외인 z+2.3 (강한 매수)", "weight": "+"},
    ],
    referenced_rules=[2, 5],                  # rule_catalog ID list
)
```

⚠️ verdict 인자 None / 공백 금지 (DB verdict 컬럼 NULL 화).
⚠️ 결론 메타 누락 시 weekly_review 의 정량 통계 부정확.

#### Read-back 검증 (Trust but verify)
- `stock_daily.get_by_date(uid, code, today)` 로 해당 종목 row 존재 + 정량 컬럼 확인
- 미달 시 즉시 재호출

---

## 출력 의무 (요약)

| 의무 | 위치 |
|---|---|
| 📐 Top-down 연결 1~2줄 | 보고서 상단 (v5 섹션) |
| 한 줄 결론 + verdict | 보고서 끝 |
| 데이터 태깅 ([실제]/[추정]/[가정]) | 모든 숫자 |
| WebSearch 출처 / 시점 | 인용 시 |
| coverage_pct < 80% 시 ⚠️ 반쪽 분석 | 보고서 상단 |

---

## 이 절차의 외부 (호출자 책임)

다음은 본 절차 **밖** — `daily-workflow.md` 가 별도 처리:

| 처리 | 범위 / 위치 |
|---|---|
| `list_daily_positions()` | Phase 0 (포트 1회) |
| `detect_market_regime()` | Phase 2 (포트 1회) |
| `WebSearch` 매크로 | Phase 2 (포트 1회) |
| `economy/{date}.md` 자동 생성 | Phase 2 |
| `get_portfolio_summary` / `reconcile_actions` / `list_trades` | Phase 1 (포트 1회) |
| `get_weekly_context(weeks=4)` | Phase 1 (포트 1회) |
| `portfolio_correlation` | Phase 6 (포트 1회) |
| `detect_portfolio_concentration` | Phase 6 (포트 1회) |
| `save_portfolio_summary` | Phase 7 (포트 1회) |

→ 종목 1건 절차는 **본 파일**, 시장/포트 단위는 `daily-workflow.md`. 책임 분리.

---

## 호출 위치 (모드별)

| 모드 | 호출 시점 | 종목 수 |
|---|---|---|
| **daily** | Phase 3 — Active + Pending 종목 순회 | 5~15 |
| **research** | 6차원 정량 분석 진입 시 | 1 |
| **discover** | 신규 발굴 후 Top 후보 분석 | 1~5 |

세 모드 모두 종목 1건 분석은 본 절차 단일 사용. SKILL.md 가 강제 인용 (v3-a).
