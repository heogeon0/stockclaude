# Base 만기·자동 재생성 룰

> 로드 시점: stock-daily 0단계 의존성 체크 시.

## 만기 기준 (v17 새 룰)

| Base 종류 | 만기 | 갱신 skill |
|---|---:|---|
| `economy/base.md` (경제) | **1일** | `/base-economy` |
| `industries/{산업}/base.md` (산업) | **7일** | `/base-industry` |
| `stocks/{종목}/base.md` (종목) | **30일** | `/base-stock` |
| `economy/{오늘}.md` (경제 daily) | **0** (매일 생성) | stock-daily 자동 생성 |
| `backtest.md` | research 호출 시 갱신 | `/stock-research` |

## 자동 재생성 룰

| 상태 | 기본 행동 | `--fast` 플래그 시 |
|---|---|---|
| `economy/{오늘}.md` 없음 | ✅ **즉시 자동 생성** (daily 소유, 매일 필수) | 동일 — 스킵 불가 |
| `economy/base.md` 없음/만료 (1일+) | ✅ **자동 `/base-economy` 풀 실행** → 갱신 후 진행 | ⚠️ 경고만, 스킵 |
| `industries/*/base.md` 없음/만료 (7일+) | ✅ **자동 `/base-industry {산업}` 풀 실행** → 갱신 후 진행 | ⚠️ 경고만, 스킵 |
| `stocks/*/base.md` 없음/만료 (30일+) | ✅ **자동 `/base-stock {종목}` 풀 실행** → 생성/갱신 후 진행 | ⚠️ 경고만, 스킵 |
| `backtest.md` 만료 | ✅ `get_backtest(force=False)` 자동 갱신 | 동일 |

## 핵심 원칙

- **skeleton 금지** — 의존성은 "있다/없다" 이분법. 없으면 무조건 풀 갱신
- **사용자 개입 0** — "base 없어요, 어떻게 할까요?" 질문 금지. 그냥 자동 체인
- **병렬 처리** — 여러 의존성 동시 갱신 필요 시 base-* skill 호출 병렬 (subagent)
- **실패 fallback** — 갱신 실패 시 해당 종목만 "기술분석 전용 모드" + 경고 표시
- **투명 보고** — 자동 재생성 내역은 daily 최상단 + Dependency Audit 양쪽 모두 표기

## Auto-regenerated Dependencies 출력 예시

```markdown
### 🔄 Auto-regenerated Dependencies
- stocks/하이닉스/base.md (만료 32일 → `/base-stock 하이닉스` 자동 갱신 완료)
- industries/반도체/base.md (없음 → `/base-industry 반도체` 자동 생성 완료)
- economy/base.md (만료 2일 → `/base-economy` 자동 갱신 완료)
```

## 파일 확인 순서 (1단계 계층 로드)

1. `reports/economy/base.md` — 1일+ 만료면 base-economy 트리거
2. `reports/economy/{오늘}.md` — 없으면 stock-daily가 생성 (`assets/economy-daily-template.md`)
3. `reports/industries/{산업}/base.md` — 7일+ 만료면 base-industry 트리거
4. `reports/stocks/{종목}/position.md` — 없으면 "미보유" 가정
5. `reports/stocks/{종목}/base.md` — 30일+ 만료면 base-stock 트리거
6. `reports/stocks/{종목}/{오늘}.md` — 생성 대상 (`assets/daily-report-template.md`)
