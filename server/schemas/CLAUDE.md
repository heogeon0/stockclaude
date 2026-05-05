# server/schemas/ — pydantic 응답 모델

> 깊이 2 — schemas/ 폴더 진입 시 자동 로드.
> 13개 파일: backtest / common / daily_report / economy / industry / portfolio / regime / score_weights / skill / stock / trade / weekly_review.

---

## 책임

- pydantic v2 기반. FastAPI `response_model`로 사용 (`server/api/*.py`가 import).
- 응답 형태의 단일 출처 — 새 응답 필드는 여기에 먼저 정의.
- MCP 툴은 별도 — schemas 미사용. dict 그대로 반환 (단 `_json_safe` 통과).

---

## ⚠️ 수동 동기화 의무 (§10.5)

- `web/src/types/api.ts`가 본 폴더의 pydantic 모델을 **수동 미러링**.
- **필드 추가·이름 변경·타입 변경 시 `web/src/types/api.ts`도 같이 수정 의무**. 빠뜨리면 frontend 빌드 실패 또는 silent drift (런타임 undefined).
- 자동 생성 미적용 — `openapi-typescript` 도입은 §10.5 GitLab 이슈로 추적 중.
- 신규 모델 추가 PR은 같은 PR에서 frontend types도 갱신 (리뷰어가 양쪽 diff 확인).

---

## 명명 규약

- **응답 모델**: `XxxOut` (예: `PortfolioOut`, `DailyReportOut`).
- **요청 모델**: `XxxIn` (예: `RegisterRuleIn`, `RecordTradeIn`).
- 필드명: **snake_case**. FastAPI는 그대로 JSON 응답. frontend는 snake_case 키를 그대로 받음 (camelCase 변환 X).
- 신규 모델도 동일 컨벤션 — camelCase 도입 금지(섞이면 frontend 깨짐).

---

## Optional·기본값

- null 허용 필드는 `Optional[T]` (또는 `T | None`) 명시.
- 기본값 누락은 frontend가 `undefined` 처리하면서 깨질 수 있음.
- pydantic v2에서 `Field(default=None)` 또는 `field: T | None = None` 권장.
- 리스트는 빈 리스트 기본값 (`Field(default_factory=list)`) — `None`보다 frontend 처리 단순.

---

## 공통 모델 — `common.py`

- 페이지네이션·에러·timestamp 등 공통 형태가 있으면 `common.py`에. 도메인 모델에서 import.
- 신규 공통 형태 추가 시 `common.py`에 — 도메인 모델 안에 중복 정의 금지.

---

## FastAPI 통합

- 라우터에서 `response_model=XxxOut` 명시 시 자동 직렬화 + 문서화(/openapi.json).
- response_model 없이 dict 그대로 반환은 가능하지만 OpenAPI 스펙에서 누락 → 신규 엔드포인트는 가급적 명시.
- pydantic 모델 → JSON 변환 시 Decimal/datetime 자동 처리 (pydantic v2가 알아서).

---

## 신규 schemas 추가 체크리스트

1. 도메인 단위 파일 선택 — 13개 중 가장 가까운 곳, 또는 신규 도메인이면 `<domain>.py` 신설.
2. 클래스명 — `XxxOut` (응답) / `XxxIn` (요청).
3. 필드명 snake_case.
4. Optional 명시 + 기본값 부여.
5. **`web/src/types/api.ts` 같이 수정** (§10.5).
6. FastAPI 라우터에 `response_model=` 등록.
