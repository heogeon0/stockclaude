# Decision Tree — 액션 결정 가이드라인

> **이 문서는 강제 매트릭스가 아닌 권장 가이드라인입니다.** LLM은 매트릭스 권장값을 출발점으로 삼고, 추가 차원 (regime / 이벤트 / 수급 / 패턴) 을 조합해 최종 액션을 결정.

---

## 입력 (analyze_position 결과 기반)

| 변수 | 출처 | 예시 |
|---|---|---|
| **position.status** | `context.position.status` | None / Active / Pending / Close |
| **return_pct** | (현재가 - avg_price) / avg_price × 100 | +20.96% |
| **verdict** | `signals.summary.종합` | 강한매수/매수우세/중립/매도우세/강한매도 |
| **cell** | `cell` (deterministic) | {size, pyramiding, stop_pct, stop_method, fin_tier, vol_tier} |
| **regime** | `detect_market_regime()` (포트 공통) | 강한 상승장 4/4 / 약세 / 횡보 |
| **events** | `events` | earnings_d_n / 52w_breakout / rating_change |
| **flow** | `flow` (KR) | 외인 z / 기관 z / 이상거래 |
| **is_stale** | `is_stale` per-dim | {stock, industry, economy} |

---

## 1. 미보유 / Pending — 진입 결정

### 1-1. Pending (base 있고 진입 대기)

| Verdict | 권장 |
|---|---|
| **강한매수** + cell ≠ 비추 | 진입 (cell.size 사이즈) |
| 매수우세 | 진입 보류, 트리거 (VCP 피봇 / 신고가 돌파 + 거래량) 대기 |
| 중립~매도우세 | 진입 보류 |
| **강한매도** | 진입 후보에서 제외 (Pending 해제 검토) |

**추가 차원 권장**:
- regime 약세장 → 강한매수여도 50% 사이즈
- 외인 z+1.5 매집 + VCP 정석 → 신뢰도 ↑ (cell.size 풀)
- 실적 D-7 이내 → 진입 보류 (이벤트 후 재판정)

### 1-2. 미보유 (base 없음)

⚠️ 신규 진입 신중. base.md 없으면 1차로 `/base-stock` 실행 권장.

---

## 2. Active 보유 — 액션 결정

### 권장 매트릭스 (수익률 × Verdict)

| 수익률 \ Verdict | 강한매수 | 매수우세 | 중립 | 매도우세 | 강한매도 |
|---|---|---|---|---|---|
| **+30%+** | 트레일링 타이트화 | 홀딩 | 부분익절 1/3 | **부분익절 1/2** | **즉시 익절 1/2** |
| **+15~30%** | 홀딩 | 홀딩 | 트레일링 | 부분익절 1/3 | **부분익절 1/2** |
| **+5~15%** | **피라미딩** (cell.pyramiding 단계) | 피라미딩 검토 | 홀딩 | 트레일링 | 부분익절 1/3 |
| **-5~+5%** | 1차 추가 검토 | 홀딩 | 보류 | **본전컷 검토** | **본전컷** |
| **-5~-10%** | 추가 신중 | 홀딩 | 손절 검토 | **즉시 손절** | **즉시 손절** |
| **-10%+** | ❌ 추가 금지 | ❌ 추가 금지 | **즉시 손절** | **즉시 손절** | **즉시 손절** |

⚠️ **변동성-조정 임계값 (권장)**: ±5%/15%/30% 대신 **±1ATR / ±2ATR / ±3ATR** 로 변환 — extreme 변동성 종목은 ±5%가 일상적.

```
ATR-조정 임계값:
- ±1 ATR: 매수우세/매도우세 본전컷·트레일링 zone
- ±2 ATR: 부분익절·피라미딩 zone
- ±3 ATR: 트레일링 타이트화·강한 익절 zone
```

### 매트릭스를 override할 우선 차원

매트릭스 권장값을 다음 차원이 **재정의**할 수 있음 (권장 가중치):

| 우선 차원 | 영향 | 예시 |
|---|---|---|
| 🔴 **실적 D-3 이내** | 매도 가중치 ↑ | 강한매수여도 D-3 시 부분익절 1/3 |
| 🔴 **외인 z-2 이상매도 + 신고가** | 익절 트리거 | 매수우세 + 신고가 + 외인 분산 → 부분익절 1/3 |
| 🟡 **regime 약세** | 매도 가중치 ↑↑ | 강한매수도 트레일링 타이트화 + 추가 진입 금지 |
| 🟡 **regime 강한 상승장 4/4** | 홀딩 가중치 ↑ | 매도우세도 트레일링만 (부분익절 보류) |
| 🟡 **52w 신고가 돌파 + 거래량 1.5x** | 피라미딩 트리거 | 매수우세 + 신고가 → 피라미딩 cell.pyramiding 단계 |
| 🟡 **VCP 미완성 (수축 진행)** | 진입 보류 | 강한매수도 VCP 미완성이면 피봇 돌파 대기 |
| 🟢 **재무 경고 critical** (이익질·부채) | 익절 가중치 ↑ | 강한매수도 비중 줄이기 (cell 한 단계 down) |
| 🟢 **포트 corr 0.85+ 페어** | 추가 진입 자제 | 신규 매수 시 분산 의무 |

---

## 3. 집행 전 게이트

매트릭스가 buy/pyramiding 결정해도 **다음 게이트 통과해야 집행**:

| 게이트 | MCP 툴 | Pass 조건 |
|---|---|---|
| **25% 룰** | `check_concentration(code, qty, price)` | violations 빈 배열 |
| **예수금** | `get_portfolio()` | cash ≥ 매수 금액 |
| **실적 D-7** | `events.earnings` | D-N > 7 / 또는 사용자 명시 진입 |
| **수급 검증** | `flow` | 매수 시 외인 z > -1.5 / 또는 매도 시 z 조건 무관 |

게이트 실패 시:
- daily 보고서에 ⚠️ 경고 명시
- 사용자 "무시하고 집행" 없으면 자동 매매 금지

---

## 4. Tier별 손절·트레일링 (cell 기반)

cell.stop_method 별 차이:

### `stop_method: "%"`
- 평단 기준 stop_pct 적용
- 단계 손절: 경고선 (stop_pct/2) / 기준선 (stop_pct×0.7) / 손절선 (stop_pct)

### `stop_method: "ATR×N"`
- 평단 - N × ATR 가격이 손절선
- 변동성 종목 (extreme regime) 표준
- 일상 ±5% 변동에 손절 안 맞음

### `stop_method: "비추"` (D 등급 + extreme)
- 신규 진입 비추천
- 이미 보유 시 즉시 정리 검토

---

## 5. 매트릭스 보정 (백테스트 기반)

`weekly_review` 결과로 매트릭스 룰 자체를 보정:

```python
# 예: "신고가 돌파 매수" 룰 win-rate 33% → 매수우세 + 신고가 셀 가중치 ↓
# 매주 weekly_context 결과로 매트릭스 자동 미세 조정 (장기 학습)
```

**현재**: 매트릭스 고정.
**v18+**: `apply_volatility_finance_matrix(code)` MCP 툴 + win-rate 누적으로 셀별 학습.

---

## 6. 단일 종목 처리 의사 코드 (권장 흐름)

```python
def decide_action(data: dict) -> dict:
    """
    data = analyze_position(code) 결과
    return = {action, reason, override_dimensions, gates}
    """
    pos = data['context'].get('position')
    cell = data['cell']
    verdict = data['signals']['summary']['종합']
    events = data.get('events', {})
    flow = data.get('flow', {})

    if pos is None or pos['status'] == 'Pending':
        # 1. Pending — 진입 결정
        action = decide_entry(verdict, cell, regime, events, flow)
    elif pos['status'] == 'Active':
        # 2. Active — 매트릭스 lookup + override
        return_pct = compute_return_pct(pos, data['indicators']['close'])
        action = matrix_lookup(verdict, return_pct)
        action = apply_overrides(action, regime, events, flow, cell)

    # 3. 집행 전 게이트
    gates = check_gates(action, data)
    if not all(gates.values()):
        action['execute'] = False
        action['warnings'] = [k for k, v in gates.items() if not v]

    return action
```

---

## 7. 핵심 원칙

1. **매트릭스는 출발점 — override 차원이 우선**
2. **변동성-조정 임계값 사용 (% → ATR)**
3. **셀은 deterministic, decide는 LLM**
4. **게이트는 deterministic, 사용자 결재 필수**
5. **백테스트 결과로 점진 보정**

---

## 관련 파일
- 변동성×재무 매트릭스: `~/.claude/skills/stock/references/scoring-weights.md`
- 12 시그널: `~/.claude/skills/stock/references/signals-12.md`
- 과열 임계: `~/.claude/skills/stock/references/overheat-thresholds.md`
- 포지션 룰: `~/.claude/skills/stock/references/position-action-rules.md`
- 만기 cascade: `~/.claude/skills/stock/references/expiration-rules.md`
