# 주간 회고 워크플로우 — 4-Phase 절차서

> 라운드: 2026-05 weekly-review overhaul
> per-stock-analysis 7-step 의 회고 평행 — 종목별 8-step + 종합 6-section + base 양방향 갱신.
> ⛔ Phase 0 BLOCKING — 갱신 전 회고는 만료된 thesis 와 비교 → 결과 신뢰성 0.

---

## 진입

| 자연어 입력 | 슬래시 | 모드 |
|---|---|---|
| "이번 주 회고 / 주간 회고 / 리뷰 / 반성" | `/stock-weekly-review` | weekly-review |

본 절차는 **종목별 회고 (Phase 1) → 종합 (Phase 2) → base 역반영 (Phase 3)** 을 BLOCKING base 갱신 (Phase 0) 후 순차 실행.

---

## ⛔ Phase 0 — base stale 갱신 (BLOCKING)

### 절차

```
1. check_base_freshness(auto_refresh=True)
   → stale 후보: economy/{kr,us}, industries[], stock_base[]
2. 이번주 거래 종목 산업/종목 우선 cascade:
   a. economy_base (1d 만기) → base-economy-update-inline.md
   b. industries (7d 만기, 거래 종목 산업 우선) → base-industry-update-inline.md
   c. stock_base (30d 만기, 거래 종목 우선) → base-stock-update-inline.md
3. 각 갱신 후 DB read-back 검증 (updated_at 갱신 확인)
4. base_phase0_log JSONB 누적:
   {economy: {kr_refreshed_at, us_refreshed_at},
    industries: [{code, refreshed_at}],
    stocks:     [{code, refreshed_at}],
    skipped:    [{target_type, target_key, reason}]}
```

### BLOCKING 가드

- Phase 0 누락 시 회고 출력 최상단에 `⚠️ stale base 와 비교한 회고 — base_thesis_aligned 평가 신뢰도 제한` 명시 의무
- "효율 우선" / "시간 절약" / "stale 이라도 진행" 같은 자율 우회 패턴 차단
- ⚠️ inline 절차 진입 시 sub-agent spawn 금지 — 메인이 직접 절차 따름

### 옵션

- 디폴트: 이번주 거래 종목 산업/종목만 갱신 (옵션 A)
- `--full-cascade` 옵트인: 모든 만기 도래 base 갱신 (옵션 B, 시간 ↑)

---

## Phase 1 — 종목별 회고 (per-stock 8-step, N 종목)

### 진입

```
list_trades_by_rule(week_start)
  → 거래 발생 종목 추출 (예: W18 9 종목)

for each code in 거래 종목:
  prepare_weekly_review_per_stock(week_start, week_end, code)  # 단일 묶음 호출
  → LLM 8-step 자연어 회고
  → save_weekly_review_per_stock(...)
```

### per-stock 8-step

| step | 내용 | 인풋 카테고리 |
|---|---|---|
| 1 | 종목 헤더 + trades 요약 | trades / position_now |
| 2 | 매매 평가 (룰별 win/loss + foregone_pnl + smart_or_early) | foregone_pnl_data / rule_catalog_join |
| 3 | base 영향 4분류 + base_thesis_aligned | base_snapshot / base_freshness |
| 4 | base 갱신 권장 (refresh_required + narrative_revision) | base_freshness (days_to_expire) |
| 5 | 학습 패턴 발견 (append_learned_pattern 호출 의무) | related_learned_patterns / verdict_distribution / override_freq_week |
| 6 | 자연어 본문 (200~400자) — Headline + 본문 | (LLM 종합) |
| 7 | 다음 주 종목 액션 (watch/monitor/earnings_watch/stop_tighten) | (LLM 결정) |
| 8 | save_weekly_review_per_stock 호출 — 9 정량 인자 채움 | (writes) |

### ⛔ 단일 진입점 룰

종목 1건 회고는 **무조건 prepare_weekly_review_per_stock 1 호출 → 8-step → save** 절차 따름. 자율 우회 금지 — 도구 산발 호출 / step 누락 / save 보류 차단.

### foregone_pnl 자동 산출

prepare 응답의 `foregone_pnl_data` 가 자동 분류 제공:
- `smart`: |Δ|<1% (정확한 정점/저점)
- `smart`: 매도 후 -5% 이상 하락 (정점 정확)
- `early`: 매도 후 +5% 이상 상승 (너무 일찍 팔았음)
- `marginal`: 그 외

**이번주 W18 GOOGL 케이스**: 3 sells (foregone +201/+119/+33 = -$353 합산) 모두 자동 분류.

---

## Phase 2 — 종합 회고 (portfolio 6-section, 1건)

### 진입

```
prepare_weekly_review_portfolio(week_start, week_end)  # 단일 묶음 호출
→ LLM 6-section 종합
→ save_weekly_review(...)
```

### portfolio 6-section

| section | 내용 | 인풋 카테고리 |
|---|---|---|
| 1 | 헤드라인 (week + 핵심 결론) | (LLM) |
| 2 | 정량 요약 (총 PnL + win_rate + trade_count + vs_benchmark) | portfolio_timeseries / vs_benchmark / per_stock_reviews_join |
| 3 | 룰별 win-rate (rule_catalog 한글 enum_name 인용) | rule_catalog_join / per_stock_reviews_join |
| 4 | 패턴/예외 인사이트 + 학습 격상 제안 | promote_candidates / per_stock_reviews_join |
| 5 | 이번 주 전략 평가 (focus_themes 적중 + rules 효과 + carry_over) | prev_strategy_evaluation |
| 6 | 다음 주 적용 가이드 (next_week_emphasize/avoid + Phase 3 결과 + pending revision 큐) | prev_review_followup |

### save_weekly_review 인자 (정량 + Phase 결과)

```
- 정량 6: rule_win_rates, pattern_findings, lessons_learned,
          next_week_emphasize, next_week_avoid, override_freq_30d
- Phase 결과 5: base_phase0_log, phase3_log, per_stock_review_count,
                base_appendback_count, propose_narrative_revision_count
```

---

## Phase 3 — base append-back (학습 → base 역반영)

### 분기 룰

Phase 1 결과의 `base_impact` 분류에 따라 자동/수동 분기:

| base_impact | 처리 |
|---|---|
| `decisive` | **자동** `append_base_facts` — base.md 의 "📝 Daily Appended Facts" 섹션에 사실 한 줄 추가 |
| `supportive` | **자동** `append_base_facts` (소극) |
| `contradictory` | **사용자 큐** `propose_base_narrative_revision` — narrative 수정 후보 적재 |
| `neutral` | **무처리** (단기 시그널 위주, base 영향 미미) |

### ⚠️ 안전장치

- 같은 (target, fact_text) 같은 날 중복 append 방지 (idempotent)
- 일일 상한 5건/target (DB content 길이 추적)
- main body 재작성 금지 — `Daily Appended Facts` 섹션만
- narrative 수정은 **자동 적용 X** — `/base-stock {code}` 로 사용자 명시 검토

### 누적 경고

`get_pending_base_revisions(weeks=4)` 큐 ≥3 시 daily 보고서 최상단에 ⚠️ 알림. 사용자가 묵혀두면 학습 사이클 정체.

---

## 출력 형식

Phase 1 9 종목 표 + Phase 2 6 section + Phase 3 자동 append 5건 + 사용자 큐 1건 = 전체 통합 출력. 상세는 `assets/weekly-review-per-stock-template.md` + `assets/weekly-review-portfolio-template.md`.

---

## 학습 사이클 폐쇄

```
weekly_strategy (월요일 brainstorm)
   → daily (BLOCKING 매일 인용)
   → trades 누적
   → weekly_review Phase 1~2 (전략 평가)
   → Phase 3 base append-back (학습 → base)
   → 다음 weekly_strategy (본 회고 lessons_learned 인용)
```

**Phase 3 가 없으면 학습이 base 에 도달 안 함 — 다음주 daily 가 옛 thesis 인용 → 같은 실수 반복.**

---

## 신설 MCP 인벤토리 (라운드 본 라운드)

| MCP | Phase | 용도 |
|---|---|---|
| `prepare_weekly_review_per_stock(week, code)` | 1 | 종목 1건 인풋 묶음 (15 카테고리) |
| `prepare_weekly_review_portfolio(week)` | 2 | 종합 인풋 묶음 (8 카테고리) |
| `save_weekly_review_per_stock(...)` | 1 | 종목 회고 저장 (upsert) |
| `get_weekly_review_per_stock(week, code)` | 1 | 단건 조회 |
| `list_weekly_review_per_stock(week)` | 2 | 한 주 묶음 조회 |
| `list_weekly_review_per_stock_by_code(code, weeks)` | — | 종목별 시계열 (web UI 용) |
| `save_weekly_review(...)` | 2 | 5 인자 추가 (Phase 0/3 로그) |
| `append_base_facts(target_type, target_key, fact_text)` | 3 | Daily Appended Facts append |
| `propose_base_narrative_revision(...)` | 3 | 사용자 큐 적재 |
| `get_pending_base_revisions(weeks)` | — | 미처리 큐 조회 (daily 알림) |
| `register_rule(enum_name, category, ...)` | — | 카탈로그 외 룰 발견 시 등록 (BLOCKING) |
| `list_rule_catalog / get_rule / update_rule / deprecate_rule` | — | rule_catalog CRUD |

---

## 참고 문서

- `references/per-stock-analysis.md` — 8-step 모델 (daily 평행)
- `references/base-impact-on-review.md` — 4분류 정의 + W18 GOOGL contradictory 사례
- `references/base-appendback-protocol.md` — Phase 3 절차서 (base-patch-protocol 의 회고 확장)
- `references/base-economy-update-inline.md` / `base-industry-update-inline.md` / `base-stock-update-inline.md` — Phase 0 갱신 절차
- `references/rule-catalog.md` — DB rule_catalog single source-of-truth (참고 문서)
- `assets/weekly-review-per-stock-template.md` — Phase 1 출력 템플릿
- `assets/weekly-review-portfolio-template.md` — Phase 2 출력 템플릿
