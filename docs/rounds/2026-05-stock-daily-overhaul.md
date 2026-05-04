# Round 2026-05 — stock-daily 워크플로우 단순화·강화 + 학습 메커니즘 도입

> **요약**: per-stock-analysis 7단계 단일 진입점 신설 + analyze_position 슬림화 +
> 매트릭스 룩업 폐기 (거장 원칙으로 대체) + 정량 결론 + learned_patterns 누적 +
> weekly_strategy 5번째 모드 (사용자+LLM 브레인스토밍) + Procfile 자동 migration.
>
> 8 버전 (v1~v8) / 74 항목 / 100% 완료 + 자동 migration 인프라 추가.

---

## 1. TL;DR (작업 전 → 작업 후)

| 측면 | 작업 전 | 작업 후 |
|---|---|---|
| 종목 1건 분석 진입점 | reference 7~8개 분산 (LLM 자율 종합) | `references/per-stock-analysis.md` **단일 진입점** + 7단계 절차 |
| `analyze_position` 응답 | 16카테고리 / scoring · cell · is_stale 자동 derive | **raw 9 카테고리** (deterministic 합성 점수 제거) |
| economy/industry base 컨텍스트 | LLM 자율 호출 (종종 누락) | Phase 3 에서 `get_economy_base` + `get_industry` **명시 호출 의무** |
| 매매 의사결정 룩업 | scoring-weights 12셀 / decision-tree 5×6 / position-action-rules 6대 룰 (직관적 설계, 검증 X) | `master-principles.md` 거장 10 원칙 (Livermore/Minervini/Buffett/Marks 등) — **추상 방향성, anchor 효과 약함** |
| 종목 보고서 출력 | "📐 Top-down 연결" 섹션 없음 | 보고서 상단에 **경제 → 산업 → 종목 정합성** 의무 |
| 결론 추적 | verdict text 만 | **size_pct / stop_method / stop_value / override_dimensions / key_factors / referenced_rules** 정량 컬럼 |
| 학습 메커니즘 | weekly_review 인프라 있지만 일일 분석 반영 X | `learned_patterns` 자연어 인사이트 정량 누적 + per-stock-analysis 가 인용 의무 |
| 사용자 의지 채널 | 없음 (LLM 자율) | `weekly_strategy` 5번째 모드 — 매주 사용자+LLM 브레인스토밍 |
| 산업 특화 | 없음 (모든 산업 동일 매트릭스) | `industries.avg_per/avg_pbr/avg_roe/avg_op_margin/vol_baseline_30d` — **산업 평균 대비** 본문 판단 |
| DB migration | 수동 `psql` | **Procfile + nixpacks.toml + run_migrations.sh** — git push 시 자동 |

---

## 2. 작업 원인 (왜 이 라운드가 시작됐나)

### 2.1 사용자 인식

`/stock-daily` 흐름이 점진적으로 비대해짐:
- 종목 1건 분석에 reference 7~8개를 LLM 이 의식적으로 호출해야 함
- `analyze_position` 응답에 점수 (`scoring`) / 셀 (`cell`) / 만기 (`is_stale`) 같은 deterministic 산출이 섞여 LLM 의 본문 추론을 anchor 시킴
- 사용자: "구조가 너무 복잡해졌다" → 단순화 + 강화 + 학습 메커니즘 도입

### 2.2 확인된 5가지 한계

| # | 한계 | 영향 |
|---|---|---|
| **A** | 합성 점수의 anchor (economy_score 디폴트 70 / industry_score 정성 / cell 자동 derive) | LLM 이 신뢰도 낮은 점수에 anchor → 본문 판단 생략 |
| **B** | 매트릭스 룩업 표 직관적 설계 / 백테스트 미검증 / 산업 차등 X | 추론 제한, 임계값 boundary 민감 (점수 79 vs 80 이 권장값 갈라짐) |
| **C** | analyze_position 에 economy/industry 본문 자동 inject 안 됨 | Top-down 정합성 종종 누락 |
| **D** | 종목 분석 진입점 분산 (reference 7~8개 자율 종합) | 진입점 단일화 X, 누락 위험 |
| **E** | 학습 메커니즘 부재 (weekly_review 인프라 있지만 룰 win-rate 가 일일 분석에 반영 X / 사용자 의지 채널 X) | 매주 같은 패턴 실수 반복 가능 |

### 2.3 우리가 고민한 갈림길 7가지

| # | 갈림길 | 선택 | 이유 |
|---|---|---|---|
| **G1** | 점수/cell 을 LLM 자율 vs 서버 deterministic | 합성 점수/등급/cell 은 anchor → 제거. 단일 통계량 분류 (volatility regime, signals.summary) 는 OK | 점수 신뢰도 낮음 + LLM 추론 제한 차단 |
| **G2** | analyze_position 응답에 base 본문 inject vs 별도 호출 | **별도 호출** | analyze_position 응답 매번 다르면 prompt cache 못 씀. 별도 호출은 deterministic → 캐싱 효율 |
| **G3** | 룩업 테이블 (lookup_case) 신설 vs 기존 references | **신설 X** | sample 부족 (480 cases × 거래 N → case 당 0~4 sample, 통계 무의미) + 차원 폭증 + anchor 위험 |
| **G4** | 매트릭스 룩업 표 유지 vs 폐기 | **폐기 → `_archive`** | anchor 효과 / 검증 안 된 직관적 설계. 거장 원칙으로 대체 |
| **G5** | 매매 원칙 미리 박기 vs 자율 학습 | **검증된 거장 원칙은 출발점**, 사용자 고유 원칙은 weekly_strategy 누적 → learned_patterns 자연 형성 | 원칙 없는 투자 X, 그러나 anchor 위험 줄임 (추상 방향성만, 구체 수치 X) |
| **G6** | 결과를 자연어 vs 정량 | **추론 = 자연어, 결론 = 정량** | 추론은 anchor 없이 자유, 결론은 추적/검증 가능 |
| **G7** | 사용자 의지 자율 작성 vs LLM 협업 | **매주 사용자 + LLM 브레인스토밍** (weekly_strategy 5번째 모드) | 자율 작성은 부담 ↑, 협업이 자연스러움 |

---

## 3. 새 워크플로우

### 3.1 per-stock-analysis 7단계 (단일 진입점)

```
1. base 신선도 체크 (check_base_freshness)
2. stale 갱신 (cascade economy → industry → stock, inline 절차)
3. base 조회 (get_economy_base + get_industry + get_stock_context — 3층 본문 LLM 컨텍스트)
4. analyze_position raw (점수/cell/is_stale 없음)
5. WebSearch (당일 뉴스, LLM 판단 전 의무)
6. LLM 종합 판단 (6 인풋 종합)
7. 출력 + 저장 (verdict + 정량 결론 컬럼 의무)
```

### 3.2 LLM 판단의 6 인풋

```
1. analyze_position raw 데이터
2. economy / industry / stock base 본문 (Top-down)
3. weekly_context (회고 본문 + 룰 win-rate + learned_patterns)
4. master-principles (거장 원칙 10 카테고리)
5. weekly_strategy (이번 주 전략, brainstorm 결과)
6. references 룰 정의 (signals-12, overheat-thresholds, rule-catalog)
```

### 3.3 학습 사이클 (3 단계 닫힌 루프)

```
[월요일] weekly_strategy 브레인스토밍 (사용자 + LLM 협업)
   ↑                                      ↓
[금/주말] weekly_review 회고          [화~금] 일일 운영
  + 정량 결론 + learned_patterns         per-stock-analysis 가
   ←────────────────────────────────  weekly_strategy 인용
```

---

## 4. 변경 산출물

### 4.1 신규 파일 (15)

| 파일 | 역할 |
|---|---|
| `.claude/skills/stock/references/per-stock-analysis.md` | 종목 1건 분석 단일 진입점 (7단계 + 판단 룰 인덱스) |
| `.claude/skills/stock/references/master-principles.md` | 거장 트레이딩 원칙 10 카테고리 (Livermore/Minervini/Buffett/Marks 등) |
| `.claude/skills/stock/references/weekly-strategy-brainstorm.md` | 5단계 brainstorm 절차 (0단계 BLOCKING 신선도 체크 포함) |
| `.claude/commands/stock-weekly-strategy.md` | 5번째 모드 wrapper command |
| `.claude/skills/stock/assets/weekly-review-template.md` | 주간 회고 5섹션 템플릿 (정량 + 자연어) |
| `.claude/skills/stock/references/_archive/scoring-weights.md` | 폐기된 12셀 매트릭스 (참고용) |
| `.claude/skills/stock/references/_archive/decision-tree.md` | 폐기된 5×6 매트릭스 |
| `.claude/skills/stock/references/_archive/position-action-rules.md` | 폐기된 6대 룰 |
| `server/repos/learned_patterns.py` | 자연어 인사이트 → 정량 메모리 |
| `server/repos/weekly_strategy.py` | 5번째 모드 repo (carry-over 로직 포함) |
| `scripts/13_alter_base_phase_momentum.sql` | economy/industries 사이클 + 모멘텀 컬럼 |
| `scripts/14_alter_industries_baseline.sql` | 산업 표준 메트릭 (avg_per/pbr/roe/op_margin/vol_baseline) |
| `scripts/15_alter_daily_review_quant_and_patterns.sql` | stock_daily/weekly_reviews 정량 컬럼 + learned_patterns 신규 |
| `scripts/16_create_weekly_strategy.sql` | weekly_strategy 신규 테이블 |
| `scripts/run_migrations.sh` | 자동 migration 실행기 (schema_migrations 추적) |
| `Procfile` | Railway release-phase: bash scripts/run_migrations.sh |
| `nixpacks.toml` | postgresql-client 의존 추가 |

### 4.2 수정 파일 (10)

| 파일 | 핵심 변경 |
|---|---|
| `.claude/skills/stock/SKILL.md` | "종목 1건 분석 단일 진입점" 섹션 신설, 매트릭스 인용 → master-principles, 5 모드 표 |
| `.claude/skills/stock/references/daily-workflow.md` | Phase 3 단순화 (per-stock-analysis 인용), Phase 4/5 갱신, BLOCKING 표 #11~13 갱신 |
| `.claude/skills/stock/references/base-economy-update-inline.md` | 시나리오 트리 + 사이클 단계 섹션 추가, 새 인자 (cycle_phase / scenario_probs) |
| `.claude/skills/stock/references/base-industry-update-inline.md` | 사이클 단계 + RS + 리더/팔로워 + 산업 표준 메트릭 5종 추가 |
| `.claude/skills/stock/assets/daily-report-template.md` | "📐 Top-down 연결" + "📊 결론 메타" 섹션 신설 |
| `db/schema.sql` | industries 9 컬럼 / economy_base 2 컬럼 / stock_daily 6 컬럼 추가 |
| `server/mcp/server.py` | analyze_position 슬림화 (scoring/cell/is_stale 제거, total 9), save_economy_base / save_industry / save_daily_report / save_weekly_review 시그니처 갱신, 신규 MCP 6종 (learned_patterns 3 + weekly_strategy 3) |
| `server/repos/economy.py` | upsert_base 에 cycle_phase / scenario_probs 인자 |
| `server/repos/industries.py` | upsert 에 cycle_phase / momentum_rs_3m/6m / leader_followers / avg_per/pbr/roe/op_margin / vol_baseline_30d 인자 (9개 추가) |
| `server/repos/stock_daily.py` | upsert_content 에 정량 결론 6 인자 |
| `server/repos/weekly_reviews.py` | upsert_review 에 정량 결론 6 인자 |

### 4.3 제거 / 이동

- `references/scoring-weights.md` / `decision-tree.md` / `position-action-rules.md` → `references/_archive/`
- `analyze_position` 의 `_CELL_MATRIX` + `_derive_cell` 헬퍼 함수 (사용처 0)

---

## 5. 검증 결과 (로컬 도커 DB)

| Ver | 검증 | 결과 |
|---|---|---|
| v2 | analyze_position 응답에 scoring/cell/is_stale 제거 | ✅ |
| v2 | financials.score strip (DART 키 부재로 financials error, 무관) | ✅ 코드 검증 |
| v2 | coverage 분모 9 (8/9 = 88.9%) | ✅ |
| v4 | economy_base.cycle_phase / scenario_probs 컬럼 | ✅ NULL 정상 |
| v4/v6 | industries 9 컬럼 (cycle_phase / momentum_rs_3m/6m / leader_followers / avg_*) | ✅ NULL 정상 |
| v7 | save_daily_report 새 인자 6종 → DB read-back | ✅ verdict/size_pct/stop_method/stop_value/override_dimensions/key_factors/referenced_rules |
| v7 | learned_patterns MCP — append/list/promote | ✅ occurrences=1 / win_rate=1.0 자동 누적 / status='rule_candidate' 격상 |
| v8 | weekly_strategy MCP — save/get | ✅ focus_themes / risk_caps jsonb 직렬화 |
| 인프라 | Python 7 파일 syntax | ✅ |

---

## 6. 운영 반영 — git push 시 자동 흐름

```
git push
   ↓
Railway 감지 → Nixpacks 빌드 (nixpacks.toml: postgresql-client 설치)
   ↓
release phase: bash scripts/run_migrations.sh
   ├─ schema_migrations 추적 테이블 보장
   ├─ scripts/[0-9]*.sql 정렬 순회
   ├─ 미적용 파일만 psql 실행 + 추적 기록
   └─ release 실패 시 web 시작 X (안전)
   ↓
web 시작 (Nixpacks 자동 감지)
   ↓
claude.ai 의 stockclaude MCP 가 새 도구/시그니처 자동 인식
```

### 멱등 보장 (이중 안전장치)
- 모든 sql 파일 자체 `IF NOT EXISTS` 패턴
- `schema_migrations` 테이블이 적용 이력 추적 (이중 안전)

### 첫 배포 시 (Railway 운영 DB 의 schema_migrations 비어있음)
- 03~16 모두 idempotent 라 매 ALTER 가 NO-OP 또는 실제 적용
- 첫 release 후 schema_migrations 에 기록 → 다음부턴 skip

---

## 7. 의도적으로 제외된 후속 (별도 라운드)

- `compute_score.economy_score` 디폴트 70 deprecate (영향 범위 큼) → **GitHub Issue #5**
- 매트릭스 자동 학습 / 보정 (sample 부족, v18+ 인프라 후)
- FRED MCP 통합 등 인프라 (Issue #5)
- web UI 의 weekly_strategy / learned_patterns 표시 페이지 (백엔드만 본 라운드 범위)
- 첫 배포 후 4주 / 12주 시점 회고 — learned_patterns 누적량 / rule_win_rates 트렌드 평가

---

## 8. 본 라운드의 워크플로우 (메타)

이 라운드 자체는 다음 협업 흐름으로 진행됨:

```
1. research (서브에이전트) — agent/research.md 갱신
2. plan (서브에이전트) — agent/plan.md 8 버전 분해
3. modifier (메인) — 사용자와 7개 갈림길 의사결정 + plan 수정
4. action (/action 슬래시) — v1~v8 순차 실행, 항목당 체크박스 갱신
5. 검증 (Python 직접 호출) — 로컬 도커 DB 로 v2/v4/v6/v7/v8 검증
6. 인프라 보강 — Procfile + run_migrations.sh + nixpacks.toml (자동 migration)
7. 라운드 문서화 (본 파일) + git push
```

**총 작업 시간**: 단일 세션 내 완료. plan 합의에 대화 비중 ~70%, 코드 작성/검증 비중 ~30%.

**다음 라운드 사용자 가이드**:
- 첫 운영 daily 시 `references/per-stock-analysis.md` 7단계 따르기
- 월요일 `/stock-weekly-strategy` 로 brainstorm 진입
- 매주 weekly_review 작성 시 `learned_patterns` 누적
- 4주~12주 후 누적된 learned_patterns 의 promotion_status 갱신 (observation → rule_candidate → user_principle)
