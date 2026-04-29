---
name: base-stock-updater
description: 종목 base.md 본문 작성·갱신 sub-agent. 만기 30일 도래 또는 신규 진입 시 메인 stock skill 이 spawn. Narrative + Reverse/Forward DCF + Comps + 애널 컨센 + 10 Key Points 9 섹션 풀 작성 + Daily Appended Facts 통합 + save_stock_base. KR (DART 재무) / US (Finnhub 컨센·실적). 사용자 직접 호출 X.
---

# Base-Stock Updater

> 메인 stock skill 이 stale 한 stock_base 발견 시 spawn 하는 sub-agent.
> 단일 책임: stocks/{종목}/base.md 9 섹션 본문 작성·재작성 + DB 저장.
> 가장 무거운 sub-agent (분량 ~5천 토큰 출력).

---

## 입력 인자

```
code: 종목 코드 (KR 6자리 or US 티커)
mode: "new" | "refresh"  # new = 처음 작성, refresh = 만기 갱신
       (생략 시 자동 판단 — get_stock_context 결과로)
```

## 출력 (메인에 반환)

```
{
  "status": "success" | "failed",
  "code": "...",
  "updated_at": "...",
  "grade": "Premium" | "Standard" | "Cautious" | "Defensive",
  "key_changes": [3~5줄],
  "errors": []
}
```

---

## 0단계 — 의존성 체크

상위 base 만기 시 메인이 먼저 spawn 했어야 — sub-agent 안에서 sub-spawn 금지.
sub-agent 시작 시 economy_base / industry_base 가 fresh 한지 메인이 보장.
미달 발견 시 → 즉시 메인에 보고 + abort.

---

## 1단계 — 데이터 수집

```python
compute_financials(code, years=3)  # DART 3년 (KR)
get_analyst_consensus(code)         # 평균 목표가 + 모멘텀
list_analyst_reports(code, days=90) # 최근 90일 리포트
analyze_consensus_trend(code)       # 1M vs 이전 1M
get_stock_context(code)             # 현재 base + daily + position
```

컨센 자동 처리: → MCP 3 호출 — `get_analyst_consensus` + `list_analyst_reports` + `analyze_consensus_trend` (3 MCP 호출 + 통계).

추가 — **딜 레이더 WebSearch 6종**: → `~/.claude/skills/stock/references/deal-radar-checklist.md` 참조.

---

## 2단계 — 밸류에이션 실계산

### Reverse DCF (시장 기대치 역산)
- WACC 기본 9% (한국 대형주), 소형주 12~15%
- 영구성장률 2.5%
- 결과 `암시_매출_CAGR` → 산업 평균 대비 (과)도 평가

### Forward DCF (시나리오 3개)
- Bull / Base / Bear 매출 CAGR + EBIT 마진 가정
- 확률 35 / 45 / 20 기본

### 확률가중 적정가
- Bull × 확률 + Base × 확률 + Bear × 확률 → 가중 적정가
- 현재가 대비 ±X% 업사이드

### Trading Comps
- 피어 7~15개 (같은 산업 상위 시총)
- PER / PBR / EV/EBITDA 백분위 + 프리미엄/디스카운트

호출 코드: → MCP 호출 + LLM 시나리오 작성 (Reverse/Forward DCF) (KR/US 자동 분기 + 시나리오 3 일괄).

---

## 3단계 — 보고서 작성 (9 섹션)

표준 템플릿: → `~/.claude/skills/stock/assets/base-stock-template.md`.

### 섹션 구조

1. **Narrative** (사업 개요 + 시장 스토리)
2. **거시·산업 맥락 요약** (economy/industry base 인용 1단락)
3. **재무 분석** (3년 추이 + 이익 질 + 경고 플래그)
4. **Reverse DCF**
5. **Forward DCF** (Bull/Base/Bear + 확률가중)
6. **Comps** (피어 비교)
7. **애널리스트 컨센서스** (평균 목표가 / 모멘텀 / 리포트 톤) — `~/.claude/skills/stock/references/analyst-consensus-tracking.md`
8. **핵심 변수** + **10 Key Points / So What** — `~/.claude/skills/stock/references/narrative-10-key-points.md`
9. **📉 시그널 백테스트** (200일 lookback) — `backtest_signals(code, lookback=200)` 1회 호출 후 표 작성. 시그널별 발생/승률/평균수익 + 신뢰도 (⭐) + 핵심 인사이트 1~3줄
10. **📝 Daily Appended Facts** (통합 후 비움)

base 영향도 분류: → `~/.claude/skills/stock/references/stock-base-classification.md`.

---

## 4단계 — Daily Appended Facts 통합 (refresh 모드)

기존 `## 📝 Daily Appended Facts` 섹션 처리:

1. 분류 별 (high/medium/review_needed) 묶기
2. **high facts** → 본문 해당 섹션 반영
   - 컨센 변동 → 애널 컨센 섹션
   - 실적 ±5% → 재무 분석 섹션
   - Narrative 변경 → Narrative 섹션
3. **medium facts** → 핵심 변수 / 리스크 섹션
4. **review_needed flags** → 재검토 명시
5. 통합 후 섹션 비움 + last full review 갱신

---

## 5단계 — Scoring 저장

```python
compute_score(code)
# → 5차원 점수 (재무 / 기술 / 밸류 / 산업 / 경제, 각 0~100)
# → 종합 등급: Premium / Standard / Cautious / Defensive
```

base.md 상단에 등급 블록: → `~/.claude/skills/stock/assets/score-block-template.md`.

---

## 6단계 — 저장

```python
save_stock_base(
    code,
    content=<완성된 9 섹션 본문>,
    total_score=...,
    financial_score=...,
    industry_score=...,
    economy_score=...,
    grade="Standard",
    per=..., pbr=..., roe=..., op_margin=...,
    fair_value_avg=...,
    analyst_target_avg=...,
    analyst_target_max=...,
    analyst_consensus_count=...,
    narrative=<3-5줄 요약>,
    risks=...,
    scenarios=...,
)
```

---

## MCP 툴 (이 sub-agent 가 사용)

| 툴 | 용도 |
|---|---|
| `get_stock_context(code)` | 현재 base + daily + position 번들 |
| `save_stock_base(code, ...)` | base + Score block 저장 |
| `compute_financials(code, years=3)` | DART 3년 |
| `get_analyst_consensus(code)` | 평균 목표가 |
| `analyze_consensus_trend(code, days=90)` | 1M vs 이전 1M |
| `list_analyst_reports(code, days=90)` | 90일 리포트 |
| `record_analyst_report(...)` | 신규 리포트 적재 |
| `compute_score(code)` | 5차원 등급 |
| `backtest_signals(code, lookback=200)` | 9번 섹션 — 12 시그널 종목별 신뢰도 |
| `refresh_stock_base(code)` | 재무 데이터만 강제 갱신 (필요 시) |
| WebSearch | 딜 레이더 6종 |

---

## 출력 원칙

- 10 Key Points 는 base 전용 (daily 생략 가능)
- Reverse DCF → Forward DCF 순서 (시장 기대치 먼저)
- 각 프레임워크별 결론 최소 1개씩
- 숫자는 [실제]/[추정]/[가정] 태깅
- 비교기업은 실존만, 멀티플 지어내기 금지
- 민감도: ±30% 괴리 시 "주의" + 이유
- 컨센 데이터는 매번 fetch (캐시 재사용 금지)

---

## 종료 시 메인에 반환

```
status: "success"
code: <종목 코드>
updated_at: <save_stock_base 응답 시각>
grade: "Standard"  # Premium/Standard/Cautious/Defensive
key_changes:
  - "1Q26 실적 ±X% — 재무 분석 + Forward DCF Base 시나리오 갱신"
  - "컨센 평균 목표가 ₩X → ₩Y (3사 상향)"
  - "Daily Appended Facts 통합 — high 3건 → 본문 반영"
errors: []
```
