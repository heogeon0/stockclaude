# Portfolio Summary Snapshot — JSON 스키마

> 로드 시점: 포트폴리오 모드 종료 시 `save_portfolio_summary` 호출 직전.

`save_portfolio_summary` 인자에 들어갈 3개 구조화 필드의 표준 스키마.

## per_stock_summary — 종목별 한 줄 요약

종목 하나당 1건:

```json
{
  "code": "005930",
  "name": "삼성전자",
  "close": 224500,
  "change_pct": 3.22,
  "pnl_pct": 15.25,
  "verdict": "강한매수",
  "note": "신고가 돌파 + 거래량 33M"
}
```

| 필드 | 타입 | 비고 |
|---|---|---|
| `code` | str | 종목코드 (KR) 또는 ticker (US) |
| `name` | str | 종목명 |
| `close` | number | 종가 또는 장중 현재가 |
| `change_pct` | number | 전일 종가 대비 % |
| `pnl_pct` | number | 평단 대비 손익 % |
| `verdict` | str | `compute_signals` 종합 판정 (강한매수/매수우세/중립/매도우세/강한매도) |
| `note` | str | 핵심 변화 한 줄 |

## risk_flags — 경고 리스트

종목별 또는 포트 전체 위험 시그널:

```json
{
  "type": "concentration",
  "code": "036570",
  "weight_pct": 24.7,
  "level": "warning",
  "detail": "상한 25% 근접"
}

{
  "type": "overheated",
  "scope": "portfolio",
  "level": "warning",
  "detail": "5종 RSI 75+ 과열 누적"
}
```

| 필드 | 타입 | 비고 |
|---|---|---|
| `type` | str | `concentration` / `overheated` / `volatility_extreme` / `earnings_d-N` / `flow_outflow` / `trigger_active` 등 |
| `code` | str (옵션) | 종목별 경고 시 |
| `scope` | str (옵션) | `portfolio` 시 (전체) |
| `weight_pct` | number (옵션) | concentration 류일 때 |
| `level` | str | `info` / `warning` / `critical` |
| `detail` | str | 사람이 읽는 설명 |

## action_plan — 내일 액션 (필수 — 내일 리마인드 대상)

```json
{
  "priority": 1,
  "code": "005930",
  "name": "삼성전자",
  "action": "buy",
  "qty": 3,
  "price_hint": 225000,
  "trigger": "넥장 or 내일 시가",
  "condition": "갭업 +2% 이상 시 보류",
  "reason": "신고가 돌파 + 거래량 33M",
  "status": "pending",
  "executed_trade_id": null,
  "expires_at": "2026-04-24T15:30:00+09:00"
}
```

| 필드 | 값 | 비고 |
|---|---|---|
| `priority` | int | 1=최우선 |
| `action` | `buy` / `sell` / `hold` | 셋 중 하나 |
| `qty` | number | 주식 수 (구체) |
| `price_hint` | number | 트리거 가격 |
| `trigger` | str | "조건" 한 줄 |
| `condition` | str | 추가 조건 |
| `reason` | str | 근거 |
| `status` | `pending` / `conditional` / `executed` / `skipped` / `expired` | 5개 |
| `executed_trade_id` | int / null | 체결 시 trade ID |
| `expires_at` | ISO datetime | 보통 다음 날 장 마감 시각 |

### 규칙

- 오늘 이미 집행된 건은 `status="executed"` + `executed_trade_id` 세팅
- 내일 집행 예정은 `status="pending"` (무조건 트리거) 또는 `"conditional"` (조건 충족 시만)
- `expires_at`은 보통 **다음 날 장 마감 시각** (놓치면 자동 `expired` 처리)
- 포트폴리오 모드에서만 호출. 단일 종목 모드는 `save_daily_report` 만 사용

## 호출 시그니처 (참고)

```
save_portfolio_summary(
  date=today_YYYY-MM-DD,
  per_stock_summary=[{...}, ...],   # 위 스키마
  risk_flags=[{...}, ...],          # 위 스키마
  action_plan=[{...}, ...],         # 위 스키마
  headline="한 줄 결론",
  summary_content="<마크다운 전체 요약 본문>",
)
```
