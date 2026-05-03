# weekly_review (종합) 템플릿 — Phase 2 portfolio 6-section

> 라운드: 2026-05 weekly-review overhaul
> Phase 1 결과 (weekly_review_per_stock 모든 row) 인용 + 포트 단위 메타.

---

## Frontmatter

```yaml
week_start: 2026-04-27
week_end:   2026-05-03
trade_count: 12
per_stock_review_count: 9
realized_pnl_kr: 1422890
realized_pnl_us: 1015.68
unrealized_pnl_kr: ...
unrealized_pnl_us: ...
base_appendback_count: 5
propose_narrative_revision_count: 1
```

---

## Section 1 — Headline

> "+₩2.92M 실현, win_rate 80%, alpha +1.6% (KOSPI). GOOGL contradictory 가 이번주 핵심 학습 — base decisive 시 헤지 30% 룰 신설 후보."

(1~2줄, 정량 + 핵심 인사이트)

---

## Section 2 — 정량 요약

| 항목 | 값 |
|---|---|
| 실현 PnL | +₩1,422,890 / +$1,015.68 (≈ +₩2.92M) |
| 미실현 PnL | (portfolio_snapshots 끝 - 시작) |
| trade_count | 12 (closed 5 + open 7) |
| closed win_rate | **80%** (4/5) |
| 룰별 100% | RSI과열청산 / 1차목표도달 / 이벤트익절 / 집중도25% (4 카테고리) |

### vs_benchmark

| 지표 | KR | US |
|---|---|---|
| KOSPI / SPX 변화 | +1.2% | +2.5% |
| portfolio | +2.8% | (USD 별도 계산) |
| **alpha** | **+1.6%** | -0.8% |

---

## Section 3 — 룰별 win-rate (rule_catalog 한글 enum 인용)

| rule_id | enum_name | 거래 | win | foregone 평균 |
|---:|---|---:|---:|---:|
| 11 | RSI과열청산 | 1 | 1 | -₩22k (smart) |
| 7 | 1차목표도달익절 | 1 | 1 | +₩6k (smart) |
| 8 | 이벤트익절 | 2 | 2 | -$76 (early 평균) |
| 13 | 집중도25%회수 | 2 | 2 | +$177 / -$201 (mixed) |
| 10 | 피라미딩실패컷 | 1 | 0 | n/a (룰 적중) |

(prepare_weekly_review_portfolio 응답의 rule_catalog_join 자동 인용)

---

## Section 4 — 패턴/예외 인사이트 + 학습 격상 제안

### 발견 패턴 (Phase 1 누적)

- `earnings_d0_partial_pre_sell` — sample 4, win 4 (100%) — **다음주 1건 추가 시 user_principle 격상 후보**
- `pyramiding_d1_settlement_required` — sample 2, win 2 (100%) — 룰 #5 효과 검증
- `low_vol_value_entry_in_overheated_market` — sample 2 (open 보류)
- `usd_concentration_25_auto_trim` — sample 1, win 1 (100%) — 룰 #13 첫 검증
- `hedge_size_oversized_in_decisive_base` — **이번주 신규 GOOGL 발견**, sample 1, foregone -$353

### 학습 격상 제안 (promote_candidates)

- `earnings_d0_partial_pre_sell` (sample 4) → sample 5 도달 시 user_principle 격상 권장
- 기타 격상 후보 없음 (sample 부족)

---

## Section 5 — 이번 주 전략 평가

### prev_strategy_evaluation (weekly_strategy 4/27)

| 인자 | 본 주 결과 |
|---|---|
| `market_outlook="정점 진입 의심"` | KOSPI +1.2% / 외인 z 양호 → 정점 가능성 partial confirmed |
| `focus_themes=["반도체","AI인프라"]` | ✅ 적중 (하닉/NVDA/GOOGL/AVGO 모두 익절·진입) |
| `rules_to_emphasize=[2, 5]` | ID 2 신고가돌파매수 = open / ID 5 피라미딩D1안착 = open (KB +5주) → 미실현 평가 |
| `rules_to_avoid=[8]` | ID 8 이벤트익절 — 자제 의도와 본 주 적용 (2건) 불일치, 전략 의도 재검토 필요 |

### prev_review_followup (W17)

- W17 의 next_week_emphasize 가 본 주 trades 와 어떻게 매칭되었는지 (자동 derived)

---

## Section 6 — 다음 주 적용 가이드

### next_week_emphasize (강화 룰)

- `7` 1차목표도달익절 (이번주 100%)
- `8` 이벤트익절 (4 연속 100%, 단 GOOGL contradictory 발견 → 헤지 사이즈 룰 같이 적용)
- `13` 집중도25%회수 (USD 25% 룰 첫 검증, 자동 트리거 효과 확인)
- `5` 피라미딩D1안착 (룰 강화 효과 검증, KB금융 사례)

### next_week_avoid (자제)

- 없음. 단 **신고가/돌파 피라미딩 D+1 미확인 진입 자제** (룰 5 강화로 대체).

### override_freq_30d

| dimension | count |
|---|---:|
| earnings_d7 | 4 |
| consensus_upward | 2 |
| usd_concentration_25 | 1 |
| low_vol_value_hedge | 2 |
| rsi_overheat_50 | 4 |
| pyramiding_d1_settlement | 2 |

### next_week_actions (action_plan 스키마)

- 006400 삼성SDI: VCP 피봇 돌파 + 거래량 → B-high 70%
- 007660 이수페타시스: AI-PCB 신고가 + D+1 안착 → C-mid 50%
- 086790 하나금융: 피봇 ₩133.7k 돌파 → +5~10주
- NVDA 5/20 D-22 → D-7 진입 시 부분익절 (이벤트익절 룰)

---

## Phase 0 / Phase 3 결과 (메타)

### base_phase0_log (Phase 0 갱신 결과)

```json
{
  "economy": {"kr_refreshed_at": "2026-05-03T08:30:00Z", "us_refreshed_at": null},
  "industries": [
    {"code": "반도체", "refreshed_at": "..."},
    {"code": "금융지주", "refreshed_at": "..."},
    {"code": "us-tech", "refreshed_at": "..."}
  ],
  "stocks": [{"code": "036570", "refreshed_at": "..."}],  // 엔씨 28d 만기
  "skipped": []
}
```

### phase3_log (Phase 3 append-back)

```json
{
  "appended_facts": [
    {"target_type": "industry", "target_key": "반도체", "fact_text": "W18: SK하닉 1차목표 ₩1.3M 도달..."},
    ... (5건)
  ],
  "proposed_revisions": [
    {"target_type": "stock", "target_key": "GOOGL",
     "divergence_summary": "us-tech base decisive 강세 시 헤지 사이즈 30% 이내 룰 신설 후보",
     "evidence_trades": [39, 42, 43],
     "status": "pending_user_review"}
  ]
}
```

→ daily 다음번 BLOCKING #14 에서 `pending revisions: 1건` 알림 표시

---

## save_weekly_review 호출

```python
save_weekly_review(
    week_start="2026-04-27",
    week_end="2026-05-03",
    realized_pnl_kr=1422890.0,
    realized_pnl_us=1015.68,
    trade_count=12,
    win_rate={"closed_total": {"tries": 5, "wins": 4, "pct": 80}, ...},
    rule_win_rates={"7": 1.0, "8": 1.0, "10": 0.0, "11": 1.0, "13": 1.0},
    pattern_findings=[{tag, sample, win_rate}, ...],
    lessons_learned=[{tag, lesson}, ...],
    next_week_emphasize=[7, 8, 13, 5],
    next_week_avoid=[],
    override_freq_30d={...},
    headline="...",
    content="(위 6 섹션 본문)",
    base_phase0_log={...},
    phase3_log={...},
    per_stock_review_count=9,
    base_appendback_count=5,
    propose_narrative_revision_count=1,
)
```
