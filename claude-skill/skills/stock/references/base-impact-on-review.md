# base 영향 4분류 — 회고 전용 룰

> 라운드: 2026-05 weekly-review overhaul
> 회고 Phase 1 의 step 3 에서 base.thesis 와 매매 결과 정합 평가. Phase 3 분기 룰의 인풋.
> 기존 `base-impact-classification.md` (high/medium/review_needed/low) 와 별개 — 회고 전용.

---

## 4분류 정의

### 1. `decisive` — base 가 매매의 결정적 동인

매매가 base.thesis (narrative) 의 핵심 인용으로 결정. 다른 시그널은 부수.

**판단 기준**:
- 진입 시점 stock_daily.key_factors 가 base.narrative 핵심 키워드 인용
- 매매 결과가 base.thesis 와 정합 (decisive bull thesis + 매수 익절 등)

**사례 (W18 SK하이닉스)**:
- base.industry: 반도체 cycle_phase=성장 + RS_3m=+40.5
- base.stock: grade=Premium, narrative="HBM 슈퍼사이클 + 마이크론 갭 7 분기"
- 매매: 4/27 -1주 @₩1,300k +₩214k 익절 (1차 목표)
- → **decisive**: HBM thesis 가 1차 목표 도달의 본질적 동인

**Phase 3 처리**: 자동 `append_base_facts` — "W18: SK하닉 1차목표 ₩1.3M 도달 + 신고가 (반도체 cycle 성장 thesis 부합)"

---

### 2. `supportive` — base 가 부수적 지지

base.thesis 인용했으나 다른 시그널 (RSI / 신고가 / 외인 z) 이 1차 동인.

**판단 기준**:
- key_factors 에 base 메타 + 단기 시그널 둘 다 등장
- 매매 결과 정합 (base 와 어긋나지 않음)

**사례 (W18 NVDA 매도)**:
- base.industry: us-tech 강세 (decisive)
- base.stock: AI Capex thesis (decisive)
- 매매: 4/29 -16.7975주 @$209 → 현재 $198.45 = +$177 회피 (smart)
- 매매 사유: USD 35.79→18.13% critical 회수 + RSI 89 극과열 (단기 시그널 1차)
- → **supportive**: base 는 강세 유지지만 매매 동인은 집중도 룰 + RSI

**Phase 3 처리**: 자동 `append_base_facts` (소극, 짧은 fact 라인)

---

### 3. `contradictory` — 매매가 base.thesis 와 충돌

base 강세인데 매도 / base 약세인데 매수 (thesis-divergence).

**판단 기준**:
- base.thesis 는 강세/decisive 인데 매매 방향이 헤지/축소
- 매매 후 현재가 변동이 base.thesis 와 정합 (early 매도 → 추가 상승 등)

**사례 (W18 GOOGL — 본 라운드 핵심 학습)**:
- base.industry: us-tech 모멘텀 강세 (RS+38)
- base.stock: AI Search + Cloud 가속, narrative 강화 (Cloud +63% 비트)
- 매매: 4/28~30 -3건 매도 (5+3+3주 = 11주, 18주의 61%)
  - foregone_pnl_data: -$201 / -$119 / -$33 = **-$353 합산 early**
  - 실현 +$789, 보유했으면 +$1,142 (-31%)
- 매매 사유: 어닝 D-1 헤지 + RSI 84 극과열 (단기 시그널)
- → **contradictory**: base.thesis decisive 강세인데 단기 RSI 룰이 base 압도. 헤지 사이즈 61% 과대.

**Phase 3 처리**: 사용자 큐 `propose_base_narrative_revision`
- 분석: "us-tech base decisive 강세 시 헤지 사이즈 30% 이내 룰 신설 후보"
- evidence_trades: [39, 42, 43]
- status: pending_user_review → `/base-stock GOOGL` 으로 검토 후 narrative 수정

---

### 4. `neutral` — base 영향 미미

매매가 단기 시그널 위주, base 무관.

**판단 기준**:
- base.thesis 가 매매에 인용되지 않음
- 순수 기술 지표 (RSI 90 / 신고가 / 거래량 1.5x) 만 동인

**사례 (W18 효성중공업)**:
- base.industry: 전력 슈퍼사이클 (long-term thesis)
- 매매: 4/27 -1주 @₩3,930k +₩1,212k 익절 (RSI 90 극과열 + 매도 시그널 5건)
- 매매 후: 5/3 ₩3,952k = 거의 변동 없음 (smart)
- → **neutral**: 단기 정점 컷 룰 / base 사이클은 long-term 으로 무관

**Phase 3 처리**: 무처리

---

## 판단 절차 (Phase 1 step 3)

```
1. base_snapshot 의 economy/industry/stock 메타 인용
   - cycle_phase / scenario_probs / momentum_rs / narrative_excerpt
2. 진입 시점 stock_daily_at_entries 의 key_factors / referenced_rules 조회
3. base_thesis 와 trades.rule_category 의 정합 판단:
   a. base 핵심 키워드 ↔ key_factors 매칭 → decisive
   b. base 일부 인용 + 단기 시그널 1차 → supportive
   c. base ↔ 매매 방향 충돌 → contradictory
   d. base 무관 → neutral
4. base_thesis_aligned BOOL: 본 주 결과가 base.thesis 와 정합 여부 (방향 일치)
5. base_refresh_required BOOL: expires_at < 7d OR contradictory 발견
```

---

## 추가 가이드

- `decisive + base_thesis_aligned=false` → narrative 강도 약화 후보 (Phase 3 사용자 큐)
- `contradictory + base_thesis_aligned=true` → base 정확하지만 매매가 어긋남 → **헤지 사이즈 룰 신설 후보**
- `supportive + smart_or_early=early` → base 보다 단기 룰 비중 과도 → 룰 가중치 재검토
- 4분류 결과는 `weekly_review_per_stock.base_impact` 컬럼에 영속. 종목별 시계열 추적 가능.

---

## 통계 추적 (라운드 후)

장기적으로 종목별 base_impact 분포 (`list_weekly_review_per_stock_by_code(code, weeks=12)`) 가 학습 인사이트:

- 특정 종목이 4주 연속 contradictory → base.narrative 자체가 옛 thesis 일 가능성
- decisive 비율 높은 종목 → thesis-driven 거래 (long-term 전략 유효)
- neutral 비율 높은 종목 → swing/단기 거래 (technical_weight 우선)
