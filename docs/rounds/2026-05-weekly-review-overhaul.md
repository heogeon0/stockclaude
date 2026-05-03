# Round 2026-05 — weekly-review 4-Phase overhaul + rule_catalog 통합

> **요약**: W18 (2026-04-27 ~ 2026-05-03) 회고를 직접 돌리며 발견한 8 함정에 대응한 4-Phase 회고 워크플로우 도입.
> per-stock-analysis (7단계, 라운드 직전) 와 동일한 패턴 (묶음 MCP 1회 + LLM 자연어 + 정량 결론) 을 회고에 평행 적용.
> `weekly_review_per_stock` 테이블 신설 + 묶음 MCP 2종 + base 영향 4분류 + base 역반영 (append-back) +
> rule_catalog DB single source-of-truth (16 active 룰) + LLM register_rule MCP 노출.
>
> 10 버전 (v1~v10) / 137 항목 / W18 풀 시퀀스 통합 검증 통과.

---

## 1. TL;DR (작업 전 → 작업 후)

| 측면 | 작업 전 (W18 회고 직접 운영) | 작업 후 (라운드 적용) |
|---|---|---|
| LLM 도구 호출 | `list_trades_by_rule` + `get_recent_quant` + `get_range` + `get_weekly_strategy` + `get_pending_actions` + `get_economy_base` + `get_industry` + `get_stock_context` × N + `analyst_reports` + ... → **10+ 호출 산발** | **2~5 호출** (`prepare_weekly_review_per_stock` × 9 종목 + `prepare_weekly_review_portfolio` 1회) |
| 매도 후 foregone PnL | 수기 계산 (현재가 vs 매도가 × qty) | **자동 산출** — `prepare_per_stock` 응답의 `foregone_pnl_data` (KR realtime + US kis_us_quote 자동 라우팅) |
| smart vs early 매도 분류 | LLM 정성 판단 | 자동 룰 (\|Δ\|<1% smart, >5% 상승 early, >5% 하락 smart, marginal) |
| base.thesis 와 매매 정합 | LLM 자율 검토 (자주 누락) | **base_impact 4분류** (decisive/supportive/contradictory/neutral) 회고 컬럼 + base_thesis_aligned BOOL |
| portfolio_snapshots 5~7 row 시계열 | **0% 활용** | `portfolio_timeseries.snapshots` + `trends` 자동 derive (총 KRW max/min, weights drift, action plan total) |
| stock_daily v7 정량 6 컬럼 | **0% 활용** | `stock_daily_quant_timeseries` 자동 join — verdict 분포 / override 빈도 derive |
| base 역반영 (회고 발견 → base) | 없음 | Phase 3 — `append_base_facts` (Daily Appended Facts 자동) + `propose_base_narrative_revision` (사용자 큐) |
| rule_catalog | 한글 enum 14개 + CHECK / 분산 (rule_category, rules_to_emphasize INT[], related_rule_ids INT[]) | **DB rule_catalog 테이블 16 active + FK 통일** + register_rule/list/get/update/deprecate MCP 5개 노출 |
| 학습 사이클 | 미폐쇄 (review → ??? → daily) | **닫힌 루프**: review (Phase 2 strategy 평가) → strategy (월요일 brainstorm) → daily → review |

---

## 2. 작업 원인 (W18 회고에서 발견한 8 함정)

### 2.1 배경

전 라운드 (`2026-05-stock-daily-overhaul`) 에서 stock-daily 흐름이 per-stock-analysis 7-step (단일 진입점, 묶음 MCP, 정량 결론) 으로 단순화됨.
그 직후 W18 회고를 직접 돌리며 weekly-review 흐름이 동일한 비대화 함정을 그대로 가지고 있다는 것이 드러남.

### 2.2 발견한 8 함정

| # | 함정 | 영향 |
|---|---|---|
| 1 | LLM 산발 10+ MCP 호출 (rule × time-series × base × strategy × pending × ...) | 토큰 누수, 누락 위험, prompt cache 미활용 |
| 2 | portfolio_snapshots 5~7 row 시계열 0% 활용 — 단일 날짜만 조회되는 repo (`get_by_date`) | 주간 추세/drift 인식 불가 |
| 3 | stock_daily v7 정량 6 컬럼 (size_pct/stop_method/.../referenced_rules) 0% 활용 — `get_recent_ohlcv_df` 만 존재 | 결정 추적 본질 누락 |
| 4 | base 3종 (economy/industry/stock) thesis 평가 누락 — 회고 시 base 본문 inject 없음 | thesis 와 매매 결과 정합 평가 X |
| 5 | GOOGL 4/28~30 헤지 매도 3건 — early 매도 후 5/3 가격 상승 → -$353 foregone 손실, 정량 자동 평가 부재 | 사후 LLM 정성으로 "조금 일찍 팔았네" 식 평가만 가능 |
| 6 | 매도 후 foregone PnL (현재가 vs 매도가 × qty) 수기 계산 부담 + KR/US 시장 라우팅 LLM 자율 | 회고 자동화 차단 |
| 7 | base.thesis 와 매매 결과 충돌 시 base 역반영 채널 없음 (회고 발견 → base 적재) | 학습 사이클 미폐쇄 |
| 8 | rule_catalog 분산 (한글 enum CHECK + INT[] 분산) — LLM 이 한글/ID 매핑 매번 추론 | register_rule / 룰 학습→격상 흐름 부재 |

### 2.3 라운드 결정 사항 (사용자 합의)

| # | 갈림길 | 선택 | 이유 |
|---|---|---|---|
| **R1** | 회고 진입점 분산 vs 단일화 | per-stock + portfolio **2개 묶음 MCP** | per-stock-analysis 평행. 종목별 + 종합 의 데이터 결이 다름 (per-stock = trade timeline / portfolio = aggregate timeline) |
| **R2** | base 영향 분류 — 옛 high/medium/review_needed/low (daily용) 재사용 vs 회고 전용 신설 | **회고 전용 4분류 신설** (decisive/supportive/contradictory/neutral) | 회고는 매매 결과 → base.thesis 정합 평가, daily 는 base → 매매 영향 평가. 방향 반대라 분류 의미 다름 |
| **R3** | Phase 0 cascade 정책 — 모든 base 갱신 vs 거래 종목만 | **옵션 A 디폴트** (이번 주 거래 종목만 우선 갱신, --full-cascade 옵트인) | 모든 cascade 시 base 갱신만 30분+ — 회고 시작 차단. 거래 종목 우선 + 사용자 선택 |
| **R4** | Phase 3 base 역반영 — 자동 vs 사용자 큐 | **분기**: high/medium fact 자동 append, review_needed/contradictory 사용자 큐 | 자동 append 가 폭주하지 않도록 안전장치 (idempotent + 5건/target/일 상한) |
| **R5** | rule_catalog 옵션 — 한글 enum CHECK 유지 vs DB 테이블 + MCP 노출 | **옵션 A + LLM MCP 노출** (5 MCP 신설) | LLM 이 매번 한글/ID 매핑 추론 부담 0. 카탈로그 외 패턴 발견 시 register_rule 호출로 학습→격상 자연스러움 |
| **R6** | 학습 사이클 폐쇄 — 자동 promotion 룰 vs 후보만 반환 | **본 라운드 후보만** (`list_promote_candidates`) → Phase 2 LLM 이 사용자에게 격상 제안 | 자동 promotion 은 다음 라운드 후보 — sample 검증 부족 |

---

## 3. 새 워크플로우 (4-Phase)

### 3.1 Phase 구조

```
Phase 0 (BLOCKING) — base 신선도 체크 + 옵션 A cascade 갱신
  ↓
Phase 1 — 종목별 8-step (보유/매매 종목 N건 1회씩)
  ├─ 1. prepare_weekly_review_per_stock(week_start, week_end, code)
  ├─ 2. trades + foregone_pnl_data + smart_or_early 자동 분류 검토
  ├─ 3. base_snapshot 인용 (economy/industry/stock 200자 excerpt)
  ├─ 4. base_impact 4분류 LLM 판단 (decisive/supportive/contradictory/neutral)
  ├─ 5. base_thesis_aligned BOOL (thesis 와 매매 정합 여부)
  ├─ 6. base_refresh_required BOOL + base_narrative_revision_proposed BOOL
  ├─ 7. learned_patterns 호출 (발견 패턴 적재)
  └─ 8. save_weekly_review_per_stock(...) — 8 컬럼 + content
  ↓
Phase 2 — 종합 6-section
  ├─ 1. prepare_weekly_review_portfolio(week_start, week_end)
  ├─ 2. portfolio_timeseries.trends + vs_benchmark + per_stock_reviews_join 인용
  ├─ 3. prev_strategy_evaluation (focus_themes 적중 + emphasize/avoid win-rate)
  ├─ 4. promote_candidates (사용자 격상 제안)
  ├─ 5. next_week_emphasize/avoid 작성 (rule_catalog_join 인용)
  └─ 6. save_weekly_review(...) — 5 신규 인자 (base_phase0_log/phase3_log/per_stock_review_count/base_appendback_count/propose_narrative_revision_count)
  ↓
Phase 3 — base 역반영
  ├─ append_base_facts × N (Daily Appended Facts 자동 append, idempotent)
  └─ propose_base_narrative_revision × M (사용자 큐 적재, get_pending_base_revisions 로 daily 리마인드)
```

### 3.2 묶음 MCP 응답 카테고리 (data join 자동)

**`prepare_weekly_review_per_stock(week_start, week_end, code)`**:
- trades (3종 timeline) / position_now / stock_daily_quant_timeseries (정량 6컬럼) / stock_daily_at_entries
- per_stock_summary_timeseries / watch_levels / position_docs
- analyst_reports_week / events_week
- base_snapshot (economy + industry + stock 200자 excerpt + freshness)
- foregone_pnl_data (KR realtime + US kis_us_quote 자동 라우팅 + smart_or_early 자동 분류)
- verdict_distribution / override_freq_week / related_learned_patterns
- **rule_catalog_join** (16 active 룰 ID/enum_name/description 자동 join)

**`prepare_weekly_review_portfolio(week_start, week_end)`**:
- per_stock_reviews_join (Phase 1 결과 N row 자동 join)
- portfolio_timeseries (snapshots 5~7 row + trends derive)
- vs_benchmark (KOSPI/SPX 변화율 vs 포트 — economy_daily 의존, 데이터 없으면 portfolio_chg_pct 만)
- prev_review_followup (W-1 emphasize/avoid 적용 추적)
- prev_strategy_evaluation (focus_themes 적중 + carry_over 처리)
- promote_candidates (sample ≥5 + win_rate ≥0.6 룰 후보)
- base_thesis_summary (보유 종목 modal industries + economy/stock cycle_phase)
- **rule_catalog_join** (전체 활성 룰)

### 3.3 base 영향 4분류 정의

- **decisive**: base 가 매매 결정의 1차 근거. thesis 명시 인용 + 매매 정합 — Phase 3 자동 append
- **supportive**: base 가 보조 근거. thesis 인용했으나 다른 시그널이 1차 — Phase 3 자동 append
- **contradictory**: 매매가 base thesis 와 충돌 (예: 강세 thesis 인데 매도) — Phase 3 사용자 큐 (propose_narrative_revision)
- **neutral**: base 무관 (단기 시그널 위주) — Phase 3 무처리

`base_refresh_required=true` + `contradictory` 인 경우 `propose_base_narrative_revision` 호출 의무 (사용자 큐 적재).

---

## 4. 변경 산출물

### 4.1 DB Migration (5)

- `scripts/17_create_weekly_review_per_stock.sql` — `weekly_review_per_stock` 테이블 (PK user_id+week_start+code, 11 컬럼)
- `scripts/18_alter_weekly_reviews_phase_logs.sql` — `weekly_reviews` 5 신규 컬럼 (base_phase0_log/phase3_log/per_stock_review_count/base_appendback_count/propose_narrative_revision_count)
- `scripts/19_alter_weekly_review_indexes.sql` — 4 신규 인덱스 (week_start DESC + code DESC + base_impact + base_refresh_required partial)
- `scripts/20_create_rule_catalog.sql` — `rule_catalog` 테이블 + 16 seed (entry 6 + 실적D-1선제진입 + exit 6 + manage 3)
- `scripts/21_migrate_existing_rule_data.sql` — trades.rule_id INT FK 추가 + 28 row 한글 enum → INT id 자동 변환 + CHECK 제거 + weekly_strategy/learned_patterns FK 추가

### 4.2 Repository (5)

- `server/repos/weekly_review_per_stock.py` 신설 — upsert / get / list_by_week / list_by_code (4 함수)
- `server/repos/portfolio_snapshots.py` — `get_range(week_start, week_end)` 신설 (시계열 5~7 row)
- `server/repos/stock_daily.py` — `get_recent_quant(code, week_start, week_end)` 신설 (정량 6 컬럼 + verdict + signals)
- `server/repos/weekly_reviews.py` — `upsert_review` 5 인자 추가 (base_phase0_log/phase3_log/per_stock_review_count/base_appendback_count/propose_narrative_revision_count)
- `server/repos/learned_patterns.py` — `list_promote_candidates(min_sample=5)` 신설
- `server/repos/rule_catalog.py` 신설 — get_by_id/by_enum_name/by_id_or_name/list_active/list_all/register/update/deprecate (8 함수)

### 4.3 MCP 14 신규

| # | MCP | Phase | 설명 |
|---|---|---|---|
| 1 | `prepare_weekly_review_per_stock` | 1 | 10 테이블 join 묶음 — foregone_pnl_data 자동 |
| 2 | `prepare_weekly_review_portfolio` | 2 | 11 테이블 join 묶음 — portfolio_timeseries.trends derive |
| 3 | `save_weekly_review_per_stock` | 1 | 8 컬럼 upsert (base_impact CHECK 적용) |
| 4 | `get_weekly_review_per_stock` | 1 | 단건 조회 |
| 5 | `list_weekly_review_per_stock` | 2 | 한 주 모든 종목 (Phase 2 join 용) |
| 6 | `list_weekly_review_per_stock_by_code` | - | 종목별 시계열 12주 (web UI 후보) |
| 7 | `save_weekly_review` (갱신) | 2 | 5 신규 인자 추가 |
| 8 | `append_base_facts` | 3 | Daily Appended Facts append (idempotent + 5/target/일 상한) |
| 9 | `propose_base_narrative_revision` | 3 | phase3_log.proposed_revisions 큐 적재 |
| 10 | `get_pending_base_revisions` | daily | weeks=4 누적 큐 조회 (daily BLOCKING #14) |
| 11 | `register_rule` | rule_catalog | 한글 enum 검증 + 중복 차단 + display_order auto |
| 12 | `list_rule_catalog` | rule_catalog | category/status 필터, active default |
| 13 | `get_rule` | rule_catalog | id 또는 enum_name auto-detect |
| 14 | `update_rule` | rule_catalog | description/display_order COALESCE |
| 15 | `deprecate_rule` | rule_catalog | soft delete (status='deprecated') |

### 4.4 Skill 파일 (6 신규 + 4 갱신)

**신규**:
- `claude-skill/skills/stock/references/weekly-review-workflow.md` — 4-Phase 절차서 + 14 MCP 인벤토리
- `claude-skill/skills/stock/references/base-impact-on-review.md` — 4분류 + W18 GOOGL contradictory 사례 + Phase 3 분기 룰
- `claude-skill/skills/stock/references/base-appendback-protocol.md` — base-patch-protocol 의 회고 전용 확장
- `claude-skill/skills/stock/assets/weekly-review-per-stock-template.md` — Phase 1 8-step 출력 템플릿
- `claude-skill/skills/stock/assets/weekly-review-portfolio-template.md` — Phase 2 6-section 출력 템플릿
- `claude-skill/commands/stock-weekly-review.md` — wrapper command (slash `/stock-weekly-review`)

**갱신**:
- `claude-skill/skills/stock/SKILL.md` — 호출 인터페이스 5 모드 → 6 모드, 자연어 키워드 표 추가, "rule_catalog single source-of-truth" 룰 명시 (공통 룰 섹션), 매매 체크리스트 갱신
- `claude-skill/skills/stock/references/daily-workflow.md` — BLOCKING 12 → 14 (#14: get_pending_base_revisions, count≥3 시 daily 보고서 최상단 ⚠️ 알림)
- `claude-skill/skills/stock/assets/weekly-review-template.md` — Deprecated 헤더 (히스토리 보존)
- `claude-skill/skills/stock/references/rule-catalog.md` — DB single source-of-truth 명시 + register_rule MCP 절차 (다음 라운드 작업 — 본 라운드는 SKILL.md 매매 체크리스트로 우선 anchor)

---

## 5. W18 통합 검증 결과 (v9)

W18 (week_start=2026-04-27, week_end=2026-05-03) 케이스로 풀 시퀀스 직접 호출 검증.

### 5.1 Phase 0

`check_base_freshness(auto_refresh=False)` — expired 5 (us-tech / us-communication / 게임 / 전력설비 / 지주) + fresh 12. 옵션 A 디폴트 가정 (실제 갱신은 시뮬레이션 — base_phase0_log JSONB 적재).

### 5.2 Phase 1 — 9 종목 회고 저장

| code | trades | foregone_pnl 합 | base_impact | thesis_aligned | refresh | revision |
|---|---|---|---|---|---|---|
| 000660 (SK하이닉스) | 1 | -₩6,000 | decisive | ✓ | - | - |
| 036570 (엔씨) | 1 | +₩34,500 | supportive | ✓ | - | - |
| 086790 (하나금융) | 1 | +₩67,500 | supportive | ✓ | - | - |
| 105560 (KB금융) | 2 | +₩17,600 | supportive | ✓ | - | - |
| 298040 (효성) | 1 | +₩22,000 | decisive | ✓ | - | - |
| AVGO | 1 | +$54.84 | neutral | ✓ | - | - |
| **GOOGL** | **3** | **+$353.16** | **contradictory** | ✓ | **✓** | **✓** |
| GS | 1 | $0.00 | supportive | ✓ | - | - |
| NVDA | 1 | -$177.21 | decisive | ✓ | - | - |

**핵심 검증** — GOOGL 자동 분류:
- foregone_pnl_data 3 trades → 합산 +$353.16 (early 매도 — 매도 후 5/3 까지 11.4%/11.5%/2.9% 상승)
- smart_or_early 룰 자동 적용 — trade 39/42 = `early`, trade 43 = `marginal`
- `base_impact='contradictory'` (us-tech base decisive 강세 thesis 와 헤지 매도 3건 충돌)
- `base_refresh_required=true` + `base_narrative_revision_proposed=true` 자동 적재

### 5.3 Phase 2 — 종합 회고

`prepare_weekly_review_portfolio` 응답:
- `per_stock_reviews_join`: 9 row (Phase 1 저장 후 자동 join)
- `portfolio_timeseries.snapshots`: 5 row, trends auto-derive
- `vs_benchmark`: portfolio_chg_pct 산출 (economy_daily 데이터 부족으로 KOSPI/SPX None)
- `prev_review_followup`: W17 (2026-04-20) 회고 emphasize/avoid 적용 추적
- `prev_strategy_evaluation`: 2026-04-27 weekly_strategy (focus_themes / rules_to_emphasize=[2,5] / avoid=[8])
- `promote_candidates`: 0 (sample 부족 — 다음 라운드 자동 promotion 룰 후보)
- `rule_catalog_join`: 16 active 룰

`save_weekly_review` 5 신규 인자 채움 (id=2 W18 row UPDATE):
- `per_stock_review_count=9 / base_appendback_count=5 / propose_narrative_revision_count=1`
- `base_phase0_log` + `phase3_log` JSONB 적재

**버그 fix** (검증 중 발견): `weekly_reviews.upsert_review` 가 `trade_count` NOT NULL 위반 — 신규 INSERT 인 경우 0 sentinel, ON CONFLICT 시 CASE WHEN 으로 기존 값 보존 (`server/repos/weekly_reviews.py` 갱신).

### 5.4 Phase 3 — base 역반영

`append_base_facts` × 5 (5/5 appended):
1. `industry/반도체` — SK하닉 1차목표 + 신고가 (cycle 성장 thesis 부합)
2. `industry/금융지주` — 1Q26 사상최대 + PBR 0.85 (가치 thesis 강화)
3. `stock/NVDA` — D-22 RSI 89 정점 -16.7975주 회수 (집중도 25% 룰 첫 검증)
4. `stock/298040` — RSI 90 극과열 컷 +44.6% 익절 (단기 정점 정확)
5. `economy/kr` — 외인 z+2.36 매집 + KOSPI alpha +1.6%

**Idempotent 검증**: 동일 fact 재호출 → `appended=False, message=idempotent`

`propose_base_narrative_revision(stock, GOOGL, ..., evidence_trades=[39,42,43])` → `queue_size=1`
`get_pending_base_revisions(weeks=4)` → `count=1, target=stock/GOOGL`

**버그 fix** (검증 중 발견): `append_base_facts` 의 industry 분기에서 `industries.upsert(code, name, content)` 호출이 required `market` 인자 누락 → `industries.upsert(code, market=row['market'], name, content)` 로 수정.

### 5.5 학습 패턴 적재

`append_learned_pattern(tag='hedge_size_oversized_in_decisive_base', outcome='loss', trade_id=39, ...)` →
`learned_patterns.id=7, occurrences=1, win_rate=0.0` (관측 단계, 5+ 누적 시 promote 후보).

### 5.6 v10-h — AVGO register_rule 시나리오

1. AVGO trade.rule_id=NULL (id=41) 확인
2. `register_rule('발굴사용자선택진입_v2', 'entry', '...')` → id=17 신규
3. `list_rule_catalog(category='entry')` → 8 룰 (기존 7 + 신규 1)
4. `UPDATE trades SET rule_id=17 WHERE code='AVGO'`
5. `get_rule('발굴사용자선택진입_v2')` → id=17, status=active
6. `UPDATE trades SET rule_id=6` (기존 발굴사용자선택진입 으로 통합 — id=17 은 검증용 임시)
7. `deprecate_rule(17, reason='검증 완료, id=6 으로 통합')` → status=deprecated
8. `list_rule_catalog(status='active')` 16 (변경 없음) / `list_rule_catalog(status='deprecated')` 1 (id=17)

### 5.7 v10-b 마이그 결과 검증

- `trades` (rule_id IS NULL AND rule_category IS NOT NULL) = 0 (마이그 100%)
- `rule_catalog` (status='active') = 16 (목표)
- `weekly_strategy.rules_to_emphasize=[2,5]` → rule_catalog id=2 신고가돌파매수 + id=5 피라미딩D1안착 매핑 OK
- 잔여 NULL 1건 (trade id=31, 036570 sell 4/20) — 옛 데이터로 rule_category 도 NULL (마이그 대상 외)
- `trades_rule_category_check` 제거 확인 (CHECK 잔재 없음)

---

## 6. 발견 버그 + 후속 fix

| 위치 | 버그 | fix |
|---|---|---|
| `server/repos/weekly_reviews.py:upsert_review` | `trade_count` NOT NULL — INSERT...ON CONFLICT DO UPDATE 시 NULL 전달 시 NotNullViolation (Postgres 가 conflict 전 constraint check) | INSERT 시 `trade_count_insert = trade_count or 0` sentinel + UPDATE branch 는 `CASE WHEN %s::int IS NOT NULL THEN EXCLUDED.trade_count ELSE weekly_reviews.trade_count END` |
| `server/mcp/server.py:append_base_facts` (industry 분기) | `industries.upsert(code, name, content)` — required `market` 인자 누락 | `industries.upsert(code, market=row['market'], name=row.get('name') or target_key, content=...)` |

---

## 7. 운영 반영

### 7.1 자동 migration

전 라운드 (`2026-05-stock-daily-overhaul`) 의 Procfile + nixpacks.toml + run_migrations.sh 인프라 가 본 라운드에도 그대로 적용:
- git push → Railway pre-deploy → `bash scripts/run_migrations.sh` → schema_migrations 테이블 기반 idempotent 적용
- 본 라운드 5 신규 SQL (17~21) 자동 인식

### 7.2 Skill 자동 반영

- `~/.claude/skills/stock/` 가 `claude-skill/skills/stock/` 로 symlink → 신규 references / assets 즉시 반영
- `~/.claude/commands/stock-weekly-review.md` 도 symlink (install-claude-skill.sh 의 `commands/*.md` glob)

---

## 8. 의도적으로 제외된 후속 (다음 라운드 후보)

| # | 항목 | 이유 |
|---|---|---|
| 1 | web UI weekly-review 페이지 | 본 라운드는 백엔드 + skill 단까지. `web/src/` 변경 별도 라운드 |
| 2 | 자동 promotion 룰 (observation→rule_candidate→principle 자동 격상) | 본 라운드는 후보만 반환. sample 검증 부족 + sample 누적 더 필요 |
| 3 | FRED MCP 통합 | vs_benchmark 의 KOSPI/SPX 데이터 부족 — economy_daily refresh 로 우선 보강 가능. 별도 라운드 |
| 4 | full-cascade 모드 (옵션 B) — 모든 base 갱신 후 회고 | 옵션 A 디폴트 운영 시 누락 패턴 관찰 후 도입 결정 |
| 5 | weekly-review 의 종목별 회고 시계열 chart (`list_weekly_review_per_stock_by_code` 활용) | web UI 페이지 같이 |

---

## 9. 본 라운드의 워크플로우 (메타)

본 라운드도 사용자 워크플로우 (`research → plan → modifier → action`) 를 그대로 따름:

1. **research** (`agent/research.md` 끝부분 `[2026-05-03] weekly-review-overhaul`):
   - W18 회고 직접 운영 → 8 함정 분석
   - 각 함정마다 현재 상태 / 변경 영향 / 위험 3 분류
   - 종합 migration 5 / repo 5 / MCP 14 / skill 6 파일 산출 명시

2. **plan** (`agent/plan.md` line 305~):
   - v1~v10 (137 항목) 분해
   - 의존성 / 순서 / W18 검증 + AVGO 시나리오 명시
   - rule_catalog 통합 (R5) 사용자 결정 후 v10 추가

3. **modifier** (사용자 + 메인 Claude 대화):
   - prepare_* MCP 의 rule_catalog_join 카테고리 추가 결정
   - Phase 0 옵션 A 디폴트 결정
   - 4분류 정의 합의

4. **action** (메인 + 본 PM 세션):
   - v1~v8 본체 메인 Claude 작성
   - v9 통합 검증 + v10-h 시나리오 + v7-d/e/f 갱신 + v8-c deprecation + 라운드 문서 + plan.md 정리 — 본 PM 세션
   - 발견 버그 2건 즉시 fix

---

## 10. 결과 요약

- 라운드 시작 → 종료: 1일 (2026-05-03)
- migration 5 / repo 5 / MCP 14 / skill 6 파일 / commands 1
- W18 풀 시퀀스 통합 검증 통과 (Phase 0 → Phase 1 9 종목 → Phase 2 종합 → Phase 3 5+1)
- GOOGL contradictory 자동 분류 + foregone +$353 자동 산출 — 라운드 핵심 가치 검증
- AVGO register_rule 시나리오 통과 — 학습→격상→카탈로그 등록 흐름 검증
- 발견 버그 2건 즉시 fix
- 다음 라운드 후보 5 항목 명시
