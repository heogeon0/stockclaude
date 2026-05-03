# 주간 회고 — Week of YYYY-MM-DD

> ⚠️ **Deprecated (라운드 2026-05 weekly-review overhaul)** — 본 템플릿은 단일 파일 5섹션 구조로,
> 4-Phase (Phase 0 base 갱신 / Phase 1 종목별 / Phase 2 종합 / Phase 3 base 역반영) 신 워크플로우 미지원.
> 새 템플릿은 2개로 분할:
> - `assets/weekly-review-per-stock-template.md` — Phase 1 종목별 8-step 출력
> - `assets/weekly-review-portfolio-template.md` — Phase 2 종합 6-section 출력
>
> 절차서: `references/weekly-review-workflow.md` (4-Phase). slash: `/stock-weekly-review`.
> 본 파일은 v7 라운드 산출물 — **참고/히스토리 보존 목적만** 유지 (신규 회고 작성 시 위 2 파일 인용).

---

> 템플릿. weekly_review 작성 시 복사 후 채움.
> **추론은 자연어, 결론은 정량** (G6 원칙). 4 섹션 모두 작성 의무.

---

## 1. 주간 trades 요약 + 룰별 outcome

> rule_catalog 의 15 룰 기준 그룹화. `list_trades_by_rule(week_start)` 결과 인용.

| 룰 ID | 룰명 | 거래 수 | win | loss | win_rate | 평균 수익률 |
|---|---|---:|---:|---:|---:|---:|
| 1 | 강매수시그널진입 | N | N | N | NN.N% | +/-N.N% |
| 2 | 신고가돌파매수 | N | N | N | NN.N% | +/-N.N% |
| ... | ... | ... | ... | ... | ... | ... |

**save_weekly_review 인자**: `rule_win_rates = {rule_id: win_rate, ...}`

---

## 2. 패턴 발견 인사이트 (자연어 자유)

> 정량 표로 안 잡히는 nuance. LLM 자율 작성. 발견 패턴마다 `append_learned_pattern` 호출 의무.

### 패턴 1: {tag — 영문 식별자, 예: "earnings_d3_strict_stop"}
- **상황 설명**: 실적 D-3 이내 + 외인 z+2 동반 시...
- **거래 수 / 결과**: N건 / win N : loss N
- **인사이트**: "...같은 셀 + earnings 임박은 부분익절 강화 후보"
- **trade_id 인용**: [123, 145]
- **outcome 누적**: append_learned_pattern("earnings_d3_strict_stop", "...", outcome="win", trade_id=123)

### 패턴 2: ...

**save_weekly_review 인자**: `pattern_findings = [{tag, description, sample_count, win_rate}, ...]`

---

## 3. 핵심 교훈 (lessons_learned)

> 본 주의 전체 학습. 자연어 + 태그.

- **{tag}**: 자연어 교훈 한 줄. (예: "vol=high + 실적 D-7 → 손절 -5% 타이트화 효과적")
- ...

**save_weekly_review 인자**: `lessons_learned = [{tag, lesson}, ...]`

---

## 4. 다음 주 적용 가이드

### 강화할 룰 (next_week_emphasize)
- 룰 ID N: {룰명} — 이번 주 win_rate NN% (강화 가치)
- ...

### 자제할 룰 (next_week_avoid)
- 룰 ID N: {룰명} — 이번 주 win_rate NN% (< 30%, 자제)
- ...

### override 차원 빈도 (override_freq_30d)
- earnings_d7: N회 활성화 (월간)
- consensus_upward: N회
- ...

**save_weekly_review 인자**:
- `next_week_emphasize = [rule_id, ...]`
- `next_week_avoid = [rule_id, ...]`
- `override_freq_30d = {dimension: count}`

---

## 5. 이번 주 전략 평가 (v8 신설)

> weekly_strategy (월요일 brainstorm) 와 실적 비교. 다음 brainstorm 의 인풋.

### focus_themes 적중 / 실패
- {테마 1}: ✅ 적중 (+N.N%) / ❌ 실패 (-N.N%) / ⏸️ 중립
- {테마 2}: ...

### rules_to_emphasize 의 win-rate
- {강화 룰}: 이번 주 win_rate NN% (예측 부합 / 부족)
- ...

### rules_to_avoid 자제 효과
- {자제 룰}: 자제로 손실 N건 회피 / 또는 자제했으나 무관함
- ...

### 다음 주 시사점
- 자연어 한 줄 — 다음 월요일 brainstorm 에 반영할 view

---

## 자유 서술 본문 (content)

> 위 5 섹션의 자연어 종합. headline 한 줄 + 본문 마크다운.

### Headline
"이번 주 {핵심 사건} — {결과 한 줄}"

### 본문
{여러 단락의 자연어 회고}

---

## 호출 흐름

```python
# 매주 금요일 / 주말
list_trades_by_rule(week_start, week_end)
   → 표 작성 → rule_win_rates 산출

# 패턴마다
for pattern in 발견_패턴들:
    append_learned_pattern(tag, description, outcome, trade_id)

# 최종 저장
save_weekly_review(
    week_start, week_end,
    rule_win_rates=...,
    pattern_findings=...,
    lessons_learned=...,
    next_week_emphasize=...,
    next_week_avoid=...,
    override_freq_30d=...,
    headline=..., content=...,
)
```

학습 사이클 닫기: 다음 월요일 weekly_strategy brainstorm 이 본 review 의 lessons_learned + pattern_findings + next_week_* 인용.
