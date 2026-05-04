# 주간 회고 컨텍스트 활용 룰 (v12.3)

> 로드 시점: BLOCKING 체크 #8 — `get_weekly_context(weeks=4)` 호출 후 결과 분석 시.

`get_weekly_context(weeks=4)` 결과를 daily 의사결정에 **반드시 반영**.

## 1. `latest_review.pending_actions` (이번 주 미체결)

- **자동 reminder**: daily 보고서 상단에 "이번 주 미체결 N건" 박스 의무 출력
- 가격 변동으로 트리거 가능성 변화 시 액션 갱신

예: 효성중 ₩4,200k -1주 pending → 오늘 NXT ₩3,665k 면 +14.6% 잔여 → "도달 가능, 지정가 유지"

## 2. `rolling_stats.rule_win_rates` (4주 누적 승률)

- 신규 매수/피라미딩 시도 전 **해당 룰 승률 체크**
- **승률 < 50% 룰: 자동 추가 검증 단계 부과**
  - 신고가 돌파 매수 33% → "D+1 종가 안착 확인" 룰 강제 적용
  - 평균회귀 매도 60% → 추가 시 거래량 동반 확인 등
- **승률 ≥ 80% 룰**: 신뢰도 높음 — 그대로 집행

## 3. `carryover_actions` (전 주 미체결)

- 만료 안 된 전 주 conditional/pending 액션을 오늘 plan 에 자동 통합
- 동일 종목 신규 액션과 충돌 시 명시적 우선순위 결정 (전 주 vs 이번 주)

## 4. `avg_weekly_pnl_kr` 추세 모니터

- 이번 daily 의 미실현/실현 변화가 최근 4주 평균과 크게 다르면 (±2σ) 경고
- 이상 패턴 감지 시 daily 보고서에 "주간 평균 대비 이상 변화" 노출

## Dependency Audit 강화 — 출력 형식

```markdown
[주간 컨텍스트]
- [x] get_weekly_context(weeks=4) 호출
- 미체결 액션: N건 / 평균 주간 실현: ±₩
- 적용된 룰 강화: {rule: 승률 < 50% → 추가 검증 적용}
```
