# 애널 컨센 추적 룰

> 로드 시점: 컨센 데이터 fetch 후 base 의 "애널리스트 컨센서스" 섹션 작성 시.

## 5가지 핵심 메트릭

### 1. 평균 / 최고 / 최저 / 표준편차

```
- 평균 목표가: ₩XXX,XXX
- 최고 / 최저: ₩XXX,XXX (○○증권) / ₩XXX,XXX
- 표준편차: ₩XX,XXX (분포 폭 X%)
- → 표준편차 > 평균의 20% 시 "애널 의견 분포 폭 큼" 경고
```

### 2. 1M 평균 vs 이전 1M (모멘텀)

`analyze_consensus_trend(code, days=90)` 결과:

```
- 최근 1M 평균 목표가: ₩XXX,XXX
- 이전 1M 평균 목표가: ₩XXX,XXX
- 변화율: ±X.X%
- 해석: 상향(>+5%) / 보합(±5%) / 하향(<-5%)
```

### 3. Buy / Hold / Sell 비율

```
- 총 N건 (최근 3개월 M건)
- Buy XX% / Hold XX% / Sell XX%
- 만장일치 Buy (Hold+Sell <10%) 시 "강한 매수 컨센"
```

### 4. 최근 7일 신규 리포트 톤

```
- ○○증권 (4/16): "이제부터 본 게임" TP ₩XXX 매수
- △△투자증권 (4/13): "반등의 서막" TP ₩XXX
- ...
```

리포트당:
- 작성일 / 증권사 / 핵심 헤드라인 / 목표가 / 투자의견

### 5. 컨센 vs 현재가 업사이드

```
- 현재가 ₩XXX,XXX vs 평균 TP ₩XXX,XXX → +XX.X% 업사이드
- 현재가 vs 최고 TP → +XX.X%
- 현재가 vs 최저 TP → ±XX.X%
```

## 갱신 트리거 룰 (base 재작성 자동 호출)

다음 조건 충족 시 base-stock 자동 호출 (만기 30일 무관):

| 트리거 | 조건 |
|---|---|
| **컨센 평균 ±15% 조정** | 3사 이상 동시 ±15% 변동 시 |
| **신규 리포트 ≥3건 (1주일 내)** | `list_analyst_reports(code, days=7)` count ≥ 3 |
| **만장일치 Buy 비율 변화** | Buy 비율 ±10%p 이상 변동 |
| **모멘텀 반전** | 1M vs 이전 1M ±10%+ 반전 (상향 → 하향 또는 그 반대) |
| **가장 보수적 / 공격적 의견 출현** | 새 최고/최저 TP 진입 (기존 ±20% 초과) |

## Daily 시 활용 룰

stock-daily 의 종목별 분석에서:

- **컨센 ±15%+ 변동** 감지 시 → daily 보고서 `📌 Base 영향도 판단` 에 `[high/consensus]` 로 기록
- **신규 리포트 ≥3건** 감지 시 → daily 보고서 `📌 Base 영향도 판단` 에 `[high/research_coverage]` 로 기록
- 상기 둘 다 누적 → base-stock 갱신 트리거 발동

## 캐시 정책

- 컨센 데이터는 **매번 fetch** (캐시 재사용 금지)
- 이유: 새 리포트 / 목표가 조정이 시간당 발생 가능
- `get_analyst_consensus(code)` / `list_analyst_reports(code)` / `analyze_consensus_trend(code)` 모두 호출 시점에 갱신

## 실행 코드

자동화 스크립트: → MCP 3 호출 — `get_analyst_consensus` + `list_analyst_reports` + `analyze_consensus_trend` 참조 (3개 MCP 호출 시퀀스 + 통계 계산).

## 출력 포맷 (base 의 "애널리스트 컨센서스" 섹션)

```markdown
## 애널리스트 컨센서스 [실제, ○○ 리서치 N건 집계 YYYY-MM-DD]

### 📌 전체 N건 요약
- 목표가 평균: ₩XXX,XXX
- 중간값: ₩XXX,XXX
- 최고/최저: ₩XXX (○○증권) / ₩XXX
- 표준편차: ₩XX,XXX (분포 폭 X%)
- 투자의견: Buy XX / Hold XX / Sell XX
- 최근 3개월 M건 (집중 커버리지)
- 1M vs 이전 1M: ±X% (상향/보합/하향)

### 최근 리포트 톤 (3개월 내)
- ○○증권 (4/16): "이제부터 본 게임" TP ₩XXX 매수
- △△투자증권 (4/13): "반등의 서막" TP ₩XXX
- ...

### 컨센 vs 현재가
- 현재가 ₩XXX vs 평균 TP ₩XXX → +XX.X% 업사이드
```
