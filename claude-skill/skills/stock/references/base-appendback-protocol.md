# base append-back protocol — Phase 3 절차서

> 라운드: 2026-05 weekly-review overhaul
> 회고 학습을 base 에 역반영하여 학습 사이클 폐쇄.
> `base-patch-protocol.md` 의 daily Append 패턴을 회고 전용으로 확장.

---

## 트리거

Phase 1 결과의 `base_impact` 분류:

| base_impact | append-back 처리 |
|---|---|
| `decisive` | 자동 `append_base_facts` — 사실 한 줄 |
| `supportive` | 자동 `append_base_facts` — 짧은 fact |
| `contradictory` | 사용자 큐 `propose_base_narrative_revision` — narrative 수정 제안 |
| `neutral` | 무처리 |

---

## append_base_facts MCP 호출

### 시그니처

```python
append_base_facts(
    target_type='economy' | 'industry' | 'stock',
    target_key='kr' | 'us' | industry_code | stock_code,
    fact_text: str,                  # 본문 한 줄, 100자 이내 권장
    source='weekly_review',          # 디폴트 (또는 'daily' / 'manual')
)
```

### 동작

1. 현재 base.content 조회 (`get_economy_base` / `get_industry` / stock_base)
2. content 안에 `## 📝 Daily Appended Facts` 섹션 위치:
   - 있으면: 섹션 끝에 라인 append `- [YYYY-MM-DD] [source] {fact_text}`
   - 없으면: content 끝에 신설 + 첫 라인 추가
3. `save_economy_base` / `save_industry` / `save_stock_base` 의 `content` 인자로 저장 (main body 재작성 X)

### ⚠️ 안전장치

- **idempotent**: 같은 (target, fact_text) 조합이 이미 content 안에 있으면 중복 추가 안 함 (return `appended=False, message='idempotent'`)
- **일일 상한**: 같은 target (예: industry/반도체) 에 같은 날짜 5건 이상 발견 시 차단 (return `error: '일일 상한 초과'`)
- **main body 재작성 금지**: narrative / risks / scenarios 등 main 섹션 절대 수정 X
- **fact_text 검증**: 비어있거나 100자 초과 시 거부 (호출 측에서 체크)

### fact_text 작성 가이드

| OK 예시 | NG 예시 |
|---|---|
| "W18: SK하닉 1차목표 ₩1.3M 도달 + 신고가 (반도체 cycle 성장 thesis 부합)" | "이번 주 좋았다" (구체성 부족) |
| "W18: GOOGL Cloud +63% 비트 (AI Cloud thesis 강화)" | "Cloud 좋았음 모두가 알 만한 사실" (이미 base 에 있음) |
| "W18: NVDA RSI 89 + 52w 99% → -16.7975주 회수 (집중도 25% 룰 검증)" | (300자 long-form 분석은 narrative 갱신으로) |

---

## propose_base_narrative_revision MCP 호출

### 시그니처

```python
propose_base_narrative_revision(
    target_type='economy' | 'industry' | 'stock',
    target_key=...,
    divergence_summary: str,      # 회고 발견 사실 요약 (200자 이내)
    evidence_trades=[trade_id, ...],  # 근거 trade 리스트
)
```

### 동작

1. 이번 주 `weekly_reviews.phase3_log.proposed_revisions` JSONB 배열에 적재:
   ```json
   {
     "target_type": "stock",
     "target_key": "GOOGL",
     "divergence_summary": "us-tech base decisive 시 헤지 사이즈 30% 이내 룰 신설 후보",
     "evidence_trades": [39, 42, 43],
     "status": "pending_user_review",
     "proposed_at": "2026-05-03"
   }
   ```
2. weekly_reviews row 가 없으면 자동 생성 (UPSERT)
3. 중복 체크: 같은 (target + summary) 조합 이미 있으면 idempotent

### ⚠️ 자동 적용 X

- LLM 이 base.narrative 직접 수정 절대 금지
- 사용자가 `/base-stock {code}` 로 명시 검토 후 적용 (또는 reject)
- 큐 ≥3 누적 시 daily 보고서에 ⚠️ 알림 (BLOCKING #14 후보)

---

## get_pending_base_revisions — 누적 경고 룰

### 시그니처

```python
get_pending_base_revisions(weeks=4) → {pending: [...], count}
```

### daily 통합

- daily 워크플로우 BLOCKING #14 (검토 후 추가): `count >= 3` 이면 daily 보고서 최상단에 알림
- 알림 형식: `⚠️ pending base revisions: {count}건 — /base-{type} 로 검토 후 적용`
- 사용자가 묵혀두면 학습 사이클 정체 → daily 의 base 인용이 옛 thesis

---

## 절차 흐름 (Phase 3 완료까지)

```
Phase 1 완료 후 (per-stock 회고 9건 저장)
  ↓
phase3_log = {appended_facts: [], proposed_revisions: []}

for each per-stock review:
  if base_impact in (decisive, supportive):
    fact_text = LLM 이 자연어 요약 (본 주 사실 1 줄)
    result = append_base_facts(target_type, target_key, fact_text)
    if result.appended:
      phase3_log.appended_facts.append({...})
  
  elif base_impact == 'contradictory':
    summary = LLM 이 자연어 요약 (divergence + 룰 신설 후보)
    propose_base_narrative_revision(target_type, target_key, summary, evidence_trades)
    phase3_log.proposed_revisions.append({...})

save_weekly_review(...,
    phase3_log=phase3_log,
    base_appendback_count=len(appended_facts),
    propose_narrative_revision_count=len(proposed_revisions),
)
```

---

## 사례 — W18 시뮬레이션

```
Phase 3 자동 append (5건):
  - industry/반도체:    "W18: SK하닉 1차목표 ₩1.3M 도달 (성장 thesis 부합)"
  - industry/금융지주:   "W18: 1Q26 사상최대 + PBR 0.76~0.85 (가치 thesis 강화)"
  - stock_base/NVDA:    "W18: D-22 RSI 89 정점 + 25% 회수 룰 첫 검증"
  - stock_base/효성:     "W18: RSI 90 극과열 컷 +44.6% 익절 (단기 정점)"
  - economy/kr:         "W18: 외인 z+2.36 매집 지속 + KOSPI alpha +1.6%"

Phase 3 사용자 큐 (1건):
  - stock_base/GOOGL:   "us-tech base decisive 강세 시 헤지 사이즈 30% 이내 룰 신설 후보 (evidence: trades 39/42/43)"

phase3_log:
  appended_facts: [5건]
  proposed_revisions: [1건]
base_appendback_count: 5
propose_narrative_revision_count: 1
```

---

## 학습 사이클 폐쇄

```
weekly_review Phase 3
  → base.content 의 Daily Appended Facts 갱신 (자동 5건)
  → 사용자 큐 적재 (1건)
  ↓
사용자 검토 후 /base-stock GOOGL 호출
  → narrative revision 적용 (예: "decisive base 시 헤지 30% 이내" 추가)
  ↓
다음주 weekly_strategy brainstorm 0단계
  → 갱신된 base 인용 + Phase 3 학습 반영
  → focus_themes / rules_to_emphasize 결정에 반영
  ↓
다음주 daily 운영
  → 갱신된 base.narrative 인용 → 같은 실수 반복 X
```
