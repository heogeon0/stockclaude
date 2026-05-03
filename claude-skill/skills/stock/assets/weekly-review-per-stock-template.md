# weekly_review_per_stock 템플릿 — Phase 1 종목별 회고

> 라운드: 2026-05 weekly-review overhaul
> 1 종목 1 row. 8-step 출력. 정량 결론은 save_weekly_review_per_stock 의 9 인자에 영속.

---

## Frontmatter (메타)

```yaml
code: GOOGL
name: Alphabet
market: us
week_start: 2026-04-27
week_end:   2026-05-03
trade_count: 3
realized_pnl: +789.23 USD
current_price: $385.69 (5/3 종가)
base_impact: contradictory
base_thesis_aligned: true
base_refresh_required: false
base_narrative_revision_proposed: true
```

---

## 1. 종목 헤더 + trades 요약

| 종목 | 시장 | 주간 거래 |
|---|---|---|
| GOOGL Alphabet | US | sell × 3 (5+3+3 = 11주, 18주 중 61%) |

**잔여 포지션**: 7주 @$281.84 평단

---

## 2. 매매 평가 (룰별 win/loss + foregone_pnl + smart_or_early)

| trade_id | 매도가 | 현재가 | foregone | delta_pct | 분류 | rule (한글) |
|---|---:|---:|---:|---:|---|---|
| 39 | $345.46 | $385.69 | **+$201.15** | +11.65% | **early** | 집중도25%회수 |
| 42 | $346.00 | $385.69 | **+$119.07** | +11.47% | **early** | 이벤트익절 |
| 43 | $374.71 | $385.69 | **+$32.94** | +2.93% | marginal | 이벤트익절 |

**합산 foregone**: **-$353** (early 매도로 놓친 추가 수익)
**실현 PnL**: +$789, 보유했으면 +$1,142 = -31% 격차

---

## 3. base 영향 분류

`base_impact: contradictory`

```
base_at_review_time:
  industry (us-tech): cycle_phase=성장, momentum_rs_3m=+38, leader_followers={GOOGL: leader}
  stock (GOOGL):     grade=Premium, narrative="AI Search + Cloud 가속, Cloud +63% 비트"

base_thesis_aligned: true (base 자체는 정확)
판단:
  base.thesis = decisive bull (Cloud +63% YoY, Backlog $460B QoQ 2배)
  매매 = 헤지 -8주 (44% 비중), D-1/D-0 단기 RSI 룰
  → 단기 시그널이 base.thesis 압도 = contradictory
```

---

## 4. base 갱신 권장

- `base_refresh_required: false` (stock_base expires_at 6/15, 정상)
- `base_narrative_revision_proposed: true`
  → "us-tech base decisive 강세 시 헤지 사이즈 30% 이내 룰" narrative 수정 제안
  → Phase 3 에서 `propose_base_narrative_revision(stock, GOOGL, ...)` 호출

---

## 5. 학습 패턴 발견 (append_learned_pattern 호출 의무)

```python
append_learned_pattern(
    tag="hedge_size_oversized_in_decisive_base",
    description="base.industry decisive 강세 + base.stock decisive narrative 인 종목의 헤지 매도가 41~44% 사이즈일 때 5거래일 후 +5~12% 추가 상승 발생. 헤지 30% 이내 룰 후보.",
    outcome="loss",  # foregone 관점에서 손실
    trade_id=39,  # 또는 42, 43 — 가장 큰 foregone 인 39 선택
    related_rule_ids=[8, 13],  # 이벤트익절(8) + 집중도25%회수(13)
)
```

**관련 패턴 (related_learned_patterns)**:
- `earnings_d0_partial_pre_sell` (sample 4, win_rate 1.0) — 같은 룰의 다른 측면, sample 5+ 시 격상 후보

---

## 6. 자연어 본문 (200~400자)

### Headline
"GOOGL 4 연속 어닝익절 +$789 실현했지만 헤지 61% 과대 — base contradictory -$353 foregone"

### 본문
4/28~30 GOOGL 매도 3건 모두 base.thesis 와 충돌. Cloud +63% YoY 비트 + Backlog $460B QoQ 2배는 decisive bull thesis 강화 신호인데, D-1/D-0 어닝 헤지 룰 + RSI 84 단기 시그널이 base 를 압도하며 11주 매도 (61% 비중). 5/3 현재 $385.69 보면 -$353 foregone — 보유했으면 +44.7% 추가 가능했음.

핵심 학습: base.industry + base.stock 둘 다 decisive 강세 시에는 단기 헤지 사이즈 30% 이내 룰 신설 필요. "이벤트익절 100% 승률" 표면 통계는 foregone 까지 보면 정정. earnings_d0_partial_pre_sell 패턴 격상은 sample 5+ 도달까지 보류.

---

## 7. 다음 주 종목 액션

```yaml
type: monitor
trigger: '$400 돌파 시 잔여 7주 trailing stop 활성화'
size_hint: '잔여 7주 풀 노출 유지 (헤지 30% 룰 적용 시 최대 2주 추가 익절만 허용)'
horizon: 14d (어닝 후 모멘텀 확인 기간)
```

---

## 8. 저장 (save_weekly_review_per_stock 호출)

```python
save_weekly_review_per_stock(
    week_start="2026-04-27",
    week_end="2026-05-03",
    code="GOOGL",
    trade_evaluations=[
        {"trade_id": 39, "side": "sell", "price": 345.46, "current_price": 385.69,
         "qty": 5, "foregone_pnl": 201.15, "delta_pct": 11.65, "smart_or_early": "early"},
        {"trade_id": 42, ...},
        {"trade_id": 43, ...},
    ],
    base_snapshot={
        "industry": {"code": "us-tech", "cycle_phase": "성장", "momentum_rs_3m": 38},
        "stock": {"grade": "Premium", "narrative_excerpt": "AI Search + Cloud 가속..."},
    },
    base_impact="contradictory",
    base_thesis_aligned=True,
    base_refresh_required=False,
    base_refreshed_during_review=False,  # Phase 0 에서 GOOGL stock_base 갱신 안 했음
    base_appendback_done=False,  # Phase 3 에서 채워짐
    base_narrative_revision_proposed=True,
    content="(위 6 단락 본문)",
)
```
