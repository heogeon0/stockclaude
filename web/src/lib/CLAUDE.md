# web/src/lib/ — 표시용 only · 백엔드 SSoT 규약

> 깊이 3. **most-local 단일 출처** + **불일치 핵심**.
> lib/ 는 프론트가 그릴 때 필요한 **표시 헬퍼만** 두는 곳이다. 비즈니스 룰은 전부 백엔드 SSoT (DB `rule_catalog`, MCP 툴, `server/analysis/*`).

---

## 1. 절대 룰 — 표시(format/decimal/색상) only

- lib/ 에 **들어올 수 있는 것**:
  - 숫자 포맷 (`decimal.ts` — `toNum`, `format*`).
  - 색상 매핑 / Tremor 컬러 토큰 (`constants.ts` — verdict/grade/status별 색).
  - 백엔드 enum의 사람 읽기용 라벨 매핑 (`strategyConstants.ts` 같은 단순 dict).
  - 정적 카탈로그 (예: `analysisModules.ts`, `skillCatalog.ts` — 본문 변경 빈도 낮음, 백엔드 자동 추출 미적용 시점의 수기 인덱스).
- lib/ 에 **들어오면 안 되는 것**:
  - 매매 시그널 계산 (signal weight 합산, verdict 산출).
  - 매수/매도 임계값 분기.
  - base 만기 일수, cascade 갱신 트리거.
  - 룰 win-rate 계산.
  - 매트릭스 룩업 (변동성 × 재무, 수익률 × verdict 등).
- 위 항목은 **모두 백엔드 책임** — `server/analysis/*` (계산) + `server/repos/rule_catalog.py` (룰 SSoT) + MCP 툴 (`compute_signals`, `analyze_position`, ...).

---

## 2. 폐기 매트릭스 잔재 (#14 — 가장 중요)

라운드 2026-05 (`docs/rounds/2026-05-stock-daily-overhaul.md`)에서 다음이 **폐기**됐다:
- v17 12셀 매트릭스 (변동성 × 재무 헬스).
- decision-tree (5×6).
- position-action-rules (6대 룰 + 수익률 × verdict 액션 매트릭스).
- base-*-updater 서브에이전트 (c9e3994에서 inline 처리로 폐기).
- 합성 점수·셀·is_stale (anchor 약화 목적).

backend는 `references/_archive/`로 이동했다. 그러나 프론트엔드 `web/src/lib/`에는 동일 이름의 모듈이 **잔재**로 남아있다 (head 확인 결과):

| 파일 | head 발췌 | 분류 |
|---|---|---|
| `signals12.ts` | `12 기술 시그널 정의 — stock/references/signals-12.md 인용` + `SIGNALS_12: SignalDef[]` (no/name/buyCondition/sellCondition/buyWeight/sellWeight) | **DB rule_catalog 중복 위험** — 룰 weight 포함 |
| `positionActionRules.ts` | `v17 포지션 반영 6대 룰 + 수익률 × verdict 매트릭스` + `POSITION_RULES` + `ACTION_MATRIX` | **폐기 매트릭스 잔재 확정** |
| `baseExpiryRules.ts` | `v17 base 3계층 만기·갱신 규칙` + `BASE_EXPIRY_RULES` (expiryDays/triggers/refreshedBy) | **백엔드 base cascade 룰과 중복 위험** |
| `volFinMatrix.ts` | `v17 핵심 — 변동성 × 재무 헬스 12셀 매트릭스` + `VOLFIN_MATRIX` (size/pyramiding/stopPct/stopMethod) | **12셀 매트릭스 잔재 확정 — 폐기 대상** |

### 사용처

`web/src/features/strategy/components/`의 4개 Section 컴포넌트가 의존:
- `Signals12Section.tsx` ← `signals12.ts`
- `VolFinMatrixSection.tsx` ← `volFinMatrix.ts`
- `PositionActionRulesSection.tsx` ← `positionActionRules.ts`
- `BaseExpirySection.tsx` ← `baseExpiryRules.ts`

→ strategy 페이지가 폐기된 매트릭스를 사용자에게 노출 중. 정합성 깨짐.

### 룰 (즉시 적용)

- **신규 코드 추가 금지** — 본 4개 파일 또는 동일 패턴(매트릭스 룩업·룰 weight·만기일수)을 **lib/ 에 새로 넣지 말 것**.
- **수정 시 우선 #14 이슈 확인** — 폐기 vs 보존 결정 미정. 변경 전에 이슈 코멘트 또는 사용자 확인.
- **새 features 페이지에서 import 금지** — 잔재가 더 퍼지지 않게.
- **삭제·대체는 #14 이슈로 추적** — 본 작업에선 코드 수정 X (룰만 박음).

---

## 3. 백엔드 SSoT 매핑 — "여기 대신 어디?"

| 폐기 잔재 (lib/) | 백엔드 SSoT |
|---|---|
| `signals12.ts` 룰 weight | DB `rule_catalog` 테이블 + `register_rule` MCP 툴 (server/repos/rule_catalog.py) |
| `signals12.ts` 시그널 계산 | `compute_signals` MCP 툴 (server/mcp/server.py) + `server/analysis/signals.py` |
| `positionActionRules.ts` ACTION_MATRIX | 폐기 — 매트릭스 룩업 자체가 사라짐. 대안은 `analyze_position`의 raw 9 카테고리 + master-principles |
| `baseExpiryRules.ts` BASE_EXPIRY_RULES | `check_base_freshness` MCP 툴 + `references/base-{economy,industry,stock}-update-inline.md` |
| `volFinMatrix.ts` VOLFIN_MATRIX | 폐기 — 12셀 매트릭스 자체가 사라짐. 대안은 `propose_position_params` (변동성·재무 raw 입력 → 정성 추천) |

→ 화면에 표시가 필요하면 위 백엔드 엔드포인트를 호출해 **데이터를 받아서 표시**하는 방식으로 전환 (lib/ 정적 dict 대신).

---

## 4. 허용되는 lib/ 모듈 — 사례

- **`decimal.ts`** ✅ — `toNum`, KRW/USD `Intl.NumberFormat`. 표시 전용 명시 (head 코멘트). 유지.
- **`api.ts`** ✅ — `apiGet/apiPost` 헬퍼 + `ApiError`. 통신 인프라.
- **`constants.ts`** ✅ — Tremor 색상 매핑 (verdict/grade/status → blue/emerald/amber/red/...). 표시용.
- **`strategyConstants.ts`** ✅ — `TIMEFRAME_LABEL` 등 enum 라벨. 표시용 (단, weight·임계값 들어가면 §1 위반).
- **`analysisModules.ts`** ⚠️ — `server/analysis/*` 16개 모듈의 수기 카탈로그 (head: "docstring 자동 추출은 v16+ 보류"). 백엔드 자동화 도입 시 폐기 검토.
- **`skillCatalog.ts`** ⚠️ — skill 인벤토리 정적 카탈로그 (head: "1 hub + 6 active + 1 deprecated"). 백엔드 자동 노출 도입 시 폐기 검토.

→ ✅ 표시용 / ⚠️ 잠정 허용(미래 백엔드화 후 정리).

---

## 5. 신규 lib/ 모듈 추가 체크리스트

- [ ] 1. **백엔드에 같은 로직 있는지 grep** — `server/analysis/`, `server/repos/`, `server/mcp/server.py`에서 검색.
- [ ] 2. **있으면** — 백엔드 호출(MCP 또는 REST)로 대체. lib/ 추가 X.
- [ ] 3. **없으면 분류**:
  - 표시 헬퍼 (format/색상/라벨 매핑) → OK, 추가.
  - 비즈니스 룰 (계산·임계값·매트릭스) → **STOP**. 백엔드에 먼저 추가 후 호출.
- [ ] 4. **head에 표시용 명시** — `/** 표시 전용 헬퍼. 비즈니스 룰은 백엔드 SSoT. */` 같은 주석.
- [ ] 5. **사용처 점검** — features/* 페이지 1곳에서만 쓰면 features 폴더 안에 두는 것도 고려 (Cohesion).

---

## 6. 함정 — 자주 틀리는 것

- **"표시인 줄 알았는데 룰" 혼동** — verdict label 매핑(표시) vs verdict 산출 가중치(룰). 가중치/임계값/일수가 들어가면 룰이다.
- **백엔드 응답을 lib/에서 후처리** — 환율 변환·합산은 백엔드(API 단)에서 끝낸다 (§4.3). lib/는 받은 값 표시만.
- **자동 동기화 가정** — `analysisModules.ts` 같은 정적 카탈로그가 백엔드와 자동 동기화된다고 가정 X. 수기다.
- **`signals12.ts`를 신규 페이지에서 import** — 잔재가 더 퍼짐. 신규는 백엔드 호출로.
- **매트릭스 부활 욕구** — `analyze_position`이 raw 카테고리만 반환하는 게 의도. 프론트에서 다시 매트릭스로 합치지 말 것 (§4.7 anchor 회피).

---

## 7. 백엔드 분업 원칙 인용 (db/schema.sql:11)

> "서버 = deterministic, Claude = reasoning"

프론트엔드 lib/는 양쪽 어디에도 비즈니스 룰을 가져선 안 된다. 정량 계산은 서버, 의미 부여는 LLM, **표시는 프론트** — 3계층 명확히.

---

## 8. 좋은/나쁜 예시

### Good — 표시 헬퍼

```ts
// web/src/lib/decimal.ts (현존, 유지)
export const toNum = (v: string | number | null | undefined): number => {
  if (v === null || v === undefined) return 0;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
};
// 표시 전용. 백엔드 Pydantic Decimal → JSON string 직렬화 받음.
```

### Bad — 비즈니스 룰 카피

```ts
// 안티패턴 — 이런 패턴이 lib/에 등장하면 #14 위반
export const POSITION_RULES = [
  { no: 2, body: "verdict=매도우세 + 수익률 +10% 이상이면 부분 익절" },
  // ... 임계값·매트릭스가 frontend에 박힘 → 백엔드 룰 변경 시 silent drift
];
```

→ 위 패턴은 백엔드 `rule_catalog` + `analyze_position` 응답으로 대체. 프론트는 응답을 받아서 표시만.

---

## 9. 이슈 추적

- **GitHub Issue #14 — `chore(web/src/lib): 폐기 매트릭스 잔재 정리 (signals12/positionActionRules/baseExpiryRules/volFinMatrix)`** (발행 완료).
  - 본문 3섹션:
    1. 발견된 룰 — "lib/는 표시(format/decimal/색상)만. 비즈니스 룰은 백엔드 SSoT."
    2. 어긋난 위치 — `signals12.ts / positionActionRules.ts / baseExpiryRules.ts / volFinMatrix.ts` (head 확인: 4개 모두 v17 매트릭스/룩업 기반, 백엔드는 라운드 2026-05에서 폐기). 사용처: `features/strategy/components/{Signals12Section,VolFinMatrixSection,PositionActionRulesSection,BaseExpirySection}.tsx`.
    3. 권장 수정 방향 — (a) 4개 파일 분류: 표시 헬퍼 vs 폐기 비즈니스 로직 (head 기준 4개 모두 후자) (b) 잔재면 삭제 + 사용처(strategy 페이지) 백엔드 호출로 대체 (`compute_signals` / `propose_position_params` / `check_base_freshness` 등) (c) 표시용 보존이면 head 주석으로 명시 (d) `signals12.ts`는 단순 enum/labels로 축소(weight 제거)하면 표시용으로 살릴 여지 있음, 룰 weight 유지면 백엔드 rule_catalog로 이전.
- 라벨: `claude-md-audit`, `tech-debt`.
