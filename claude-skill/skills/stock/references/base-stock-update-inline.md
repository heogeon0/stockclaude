# base-stock-update — inline 절차

> **stale stock_base 발견 또는 신규 종목 진입 시 메인 에이전트가 직접 수행하는 절차.**
> 옛 `agents/base-stock-updater.md` (sub-agent) 폐기 → multi-device 운영 호환을 위해 inline 화.
>
> **단일 책임**: `stock_base` 테이블의 종목 1개 본문 (9 섹션) + 17 인자 + DB 저장 + read-back.
> **언제**: `check_base_freshness` 결과 `stocks[*].is_stale=true` (만기 30일) 또는 `discover` 후 신규 종목 진입 시.
> **누가**: stock skill 메인 LLM. sub-agent spawn 금지.
> **분량**: 본문 ≥ 4KB 권장 (9 섹션 풀 작성).

---

## 입력 인자

```
code: 종목 코드 (KR 6자리 or US 티커)
mode: "new" | "refresh"  # new = 처음 작성, refresh = 만기 갱신
       (생략 시 자동 판단 — get_stock_context 결과로)
```

---

## 0단계 — 의존성 cascade (중요)

> **상위 base 가 stale 면 먼저 inline 처리 후 본 절차 진입.**
> sub-agent 시절엔 "메인이 미리 spawn 했어야 한다" 였지만, inline 화로 책임이 같은 메인에게 통합.

진입 시 점검:
1. `check_base_freshness` 호출
2. **`economy_base` (해당 market) stale → 먼저 `references/base-economy-update-inline.md` 절차 진행 후 복귀**
3. **종목 산업의 `industries` 행 stale → 먼저 `references/base-industry-update-inline.md` 절차 진행 후 복귀**
4. cascade 완료 후 본 절차 (1단계) 진입

진입 가드:
- **다른 작업 중 inline 진입 시**: 직전 분석 결과 (다른 종목/포트폴리오) 를 본문에 인용하지 않음. **깨끗한 상태로 9 섹션을 처음부터 작성**.
- **압축 시도 금지**: LLM '효율 추구' 본능으로 섹션 합치기·생략 금지. base 는 30일 사용되는 정식 문서 — 풀 분량.

---

## 1단계 — 데이터 수집 (MCP 9 호출)

```python
compute_financials(code, years=3)         # DART 3년 (KR) / Finnhub (US)
get_analyst_consensus(code)               # 평균 목표가 + 모멘텀
list_analyst_reports(code, days=90)       # 최근 90일 리포트
analyze_consensus_trend(code, days=90)    # 1M vs 이전 1M
get_stock_context(code)                   # 현재 base + daily + position 번들
backtest_signals(code, lookback=200)      # 12 시그널 종목별 신뢰도 (9번 섹션용)
compute_score(code)                       # 5차원 점수 + 등급 (5단계용)
```

추가 — **딜 레이더 WebSearch 6종**: → `~/.claude/skills/stock/references/deal-radar-checklist.md` 참조 (M&A·경영진 변동·소송·유상증자·자사주·블록딜 6 카테고리).

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

> Reverse → Forward 순서 엄수 (시장 기대치 먼저, 자기 가정 나중).

상세 룰: → `~/.claude/skills/stock/references/valuation-frameworks.md`.

---

## 3단계 — 보고서 작성 (9 섹션)

표준 템플릿: → `~/.claude/skills/stock/assets/base-stock-template.md`.

### 섹션 구조

1. **Narrative** (사업 개요 + 시장 스토리)
2. **거시·산업 맥락 요약** (`economy_base` + `industries` 인용 1단락. cascade 완료 후라 fresh)
3. **재무 분석** (3년 추이 + 이익 질 + 경고 플래그)
4. **Reverse DCF**
5. **Forward DCF** (Bull/Base/Bear + 확률가중)
6. **Comps** (피어 비교)
7. **애널리스트 컨센서스** (평균 목표가 / 모멘텀 / 리포트 톤) — `~/.claude/skills/stock/references/analyst-consensus-tracking.md`
8. **핵심 변수** + **10 Key Points / So What** — `~/.claude/skills/stock/references/narrative-10-key-points.md`
9. **📉 시그널 백테스트** (200일 lookback) — `backtest_signals` 결과 표 작성. 시그널별 발생/승률/평균수익 + 신뢰도 (⭐) + 핵심 인사이트 1~3줄
10. **📝 Daily Appended Facts** (refresh 모드: 통합 후 비움 / new 모드: 빈 섹션으로 시작)

base 영향도 분류: → `~/.claude/skills/stock/references/stock-base-classification.md`.

---

## 4단계 — Daily Appended Facts 통합 (refresh 모드만)

기존 `## 📝 Daily Appended Facts` 섹션 처리:

1. 분류 별 (high / medium / review_needed) 묶기
2. **high facts** → 본문 해당 섹션 반영
   - 컨센 변동 → 애널 컨센 섹션
   - 실적 ±5% → 재무 분석 섹션
   - Narrative 변경 → Narrative 섹션
3. **medium facts** → 핵심 변수 / 리스크 섹션
4. **review_needed flags** → 재검토 명시
5. 통합 후 섹션 비움 + last full review 갱신

---

## 5단계 — Scoring + 등급

```python
compute_score(code)
# → 5차원 점수 (재무 / 기술 / 밸류 / 산업 / 경제, 각 0~100)
# → 종합 등급: Premium / Standard / Cautious / Defensive
```

base.md 상단에 등급 블록: → `~/.claude/skills/stock/assets/score-block-template.md` (있다면).

---

## 6단계 — 저장 (17 인자, code 제외)

```python
save_stock_base(
    code=...,
    # 점수 4개 (compute_score 결과)
    total_score=..., financial_score=..., industry_score=..., economy_score=...,
    # 등급 1개
    grade="Standard",  # "Premium" | "Standard" | "Cautious" | "Defensive"
    # 컨센 4개
    fair_value_avg=..., analyst_target_avg=..., analyst_target_max=..., analyst_consensus_count=...,
    # 재무 비율 4개
    per=..., pbr=..., roe=..., op_margin=...,
    # 텍스트 4개
    narrative=<3-5줄 요약>,
    risks=<리스크 요약>,
    scenarios=<Bull/Base/Bear 1줄 each>,
    content=<완성된 9 섹션 본문 — 4KB 이상 권장>,
)
```

`None` 인 필드는 DB 의 기존 값 유지 (COALESCE) — 신규 작성 (`new`) 시엔 모두 채우고, refresh 시엔 변동분만 명시 가능. **단 본 절차는 풀 갱신 전제 — 17 인자 모두 채우기 권장**.

---

## 7단계 — Read-back 검증

저장 직후:
```python
ctx = get_stock_context(code=...)
assert ctx['stock_base']['updated_at'] > <save 호출 직전 시각>
assert len(ctx['stock_base']['content'] or '') >= 4000  # 4KB
```

본문 길이 4KB 미달 시 9 섹션 중 누락 의심 → 재작성.

---

## 작성 원칙

- 10 Key Points 는 base 전용 (daily 생략 가능)
- Reverse DCF → Forward DCF 순서 (시장 기대치 먼저)
- 각 프레임워크별 결론 최소 1개씩
- 숫자는 [실제]/[추정]/[가정] 태깅
- 비교기업은 실존만, 멀티플 지어내기 금지
- 민감도: ±30% 괴리 시 "주의" + 이유
- 컨센 데이터는 매번 fetch (캐시 재사용 금지)

---

## ✅ 완료 체크리스트

- [ ] 0단계 cascade 완료 (economy/industry fresh 보장)
- [ ] 9 섹션 모두 작성 + Daily Facts 통합/초기화
- [ ] 17 인자 (code 제외) 모두 채움 — 점수 4 / 등급 1 / 컨센 4 / 재무 4 / 텍스트 4
- [ ] `save_stock_base(...)` 호출 성공
- [ ] `get_stock_context(code)` read-back — `updated_at` 갱신 확인
- [ ] 본문 길이 ≥ 4KB (9 섹션 풀 분량 보장)

## 완료 시 메인이 정리할 것

```
✅ stock_base[code=005930] 갱신 (updated_at=YYYY-MM-DDTHH:MM, grade=Premium)
주요 변경:
  - 1Q26 실적 ±X% — 재무 분석 + Forward DCF Base 시나리오 갱신
  - 컨센 평균 목표가 ₩X → ₩Y (3사 상향)
  - Daily Appended Facts 통합 — high 3건 → 본문 반영
```

실패 시:
```
❌ stock_base[code=005930] 갱신 실패
원인: <구체 에러>
재시도 권장: <조치>
```

---

> **inline 진입 시 주의 (재강조)**: 메인이 다른 작업 (daily/research/discover) 중에 본 절차로 진입하더라도, 직전 작업의 결과 (다른 종목 분석·포트폴리오 컨텍스트 등) 를 본 종목 base 본문에 끌어오지 않는다. 깨끗한 상태로 9 섹션을 처음부터 작성한다. **섹션 압축·생략 금지** — `stock_base` 는 30일 동안 daily/discover/research 가 참조하는 정식 문서다 (LLM 의 '효율 추구' 본능을 의식적으로 차단할 것).
