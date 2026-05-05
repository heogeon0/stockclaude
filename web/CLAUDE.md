# web/ — 프론트엔드 일반 가이드

> 깊이 1. 웹 폴더 진입 시 자동 로드. 본 파일은 stockclaude **특화 룰**만 다루고, 가독성·예측가능성·응집도·결합도 4대 원칙은 글로벌 가이드(`~/.claude/CLAUDE.md`)와 `docs/frontend-guideline.md`를 따른다.

---

## 1. 스택

- **Vite + React 18** — 빌드/번들러.
- **Tremor 3** — 디자인 시스템 (차트·카드·테이블). 새 페이지/컴포넌트는 가급적 Tremor 컴포넌트 우선 사용.
- **React Query 5 (`@tanstack/react-query`)** — 서버 상태 관리. 1훅 = 1엔드포인트 (`web/src/hooks/`).
- **react-router-dom 7** — 라우팅. 단, 현재는 `App.tsx` 단일 파일에서 라우팅 정의 (§3 참고).
- **Tailwind** — 유틸리티 CSS.

---

## 2. 환경변수 / API 헬퍼

- API base URL은 `VITE_API_URL` (없으면 `http://localhost:8000`).
- 모든 REST 호출은 `web/src/lib/api.ts`의 **`apiGet` / `apiPost`** 헬퍼 경유. `fetch` 직접 사용 금지.
- 에러는 `ApiError` 클래스로 throw. UI에서 분기 시 `error instanceof ApiError`.

---

## 3. 라우팅 현 구조

- `web/src/routes/`는 의도된 디렉토리 구조였지만, 현재는 `App.tsx`의 `NavLink` + `Outlet`으로 모든 라우팅을 정의한다 (sidebar 5개 메뉴 + skills 1개 참고 메뉴).
- **신규 페이지 추가 절차**:
  1. `web/src/features/<도메인>/Page.tsx`에 페이지 컴포넌트 작성 (또는 `<Domain>Page.tsx`).
  2. `App.tsx`에서 import 후 `NavLink` + Route 등록.
  3. 데이터 훅은 `web/src/hooks/`에 1훅 = 1엔드포인트로 추가.
- routes/ 폴더 활용은 별도 결정 전까지 보류 — 현재는 App.tsx가 단일 라우팅 SSoT.

### 사이드바 메뉴 인벤토리 (App.tsx 발췌)

- `/` 포트폴리오 (end), `/today` 데일리 리포트, `/trades` 매매 기록, `/review` 주간 회고, `/strategy` 전략·로직.
- 참고 그룹: `/skills` 스킬 매뉴얼.

> 사이드바 타이틀이 `stock-manager`로 남아있는 잔재는 외부 식별자 통일 이슈(#11)와 함께 다룬다 — 본 작업에서 코드 수정은 X.

---

## 4. 하위 폴더 안내 (각자 CLAUDE.md 보유)

- `web/src/hooks/` — React Query 훅 28개. queryKey 컨벤션·`apiGet` 패턴·`UseQueryResult` 반환 룰. (깊이 3)
- `web/src/features/` — 도메인별 페이지 + components. features 간 import 금지(격리). (깊이 3)
- `web/src/lib/` — **표시용 only**. 비즈니스 룰은 백엔드 SSoT (rule_catalog). 폐기 매트릭스 잔재 정리 이슈 추적 중. (깊이 3)
- `web/src/types/api.ts` — 백엔드 pydantic 응답을 TS로 **수동 미러링** (자동 생성 미적용 — #15 이슈 추적).

본 web/CLAUDE.md는 폴더 일반 룰만 보유. 디테일은 most-local CLAUDE.md를 따른다 (깊이 역전 금지).

---

## 5. 글로벌 frontend-guideline 참조

- `~/.claude/CLAUDE.md`의 4대 원칙(Readability / Predictability / Cohesion / Coupling)을 따른다.
- 매직 넘버는 명명된 상수로, 복잡한 삼항은 if문/IIFE로, 함수에는 JSDoc 우선.
- React Query 훅은 항상 `UseQueryResult` 반환 (Predictability — `web/src/hooks/CLAUDE.md` 상세).
- 본 파일은 stockclaude 특화 룰만 명시 — 일반 패턴 중복 박지 않음.

---

## 6. 실행 명령

- `cd web && pnpm install` — 의존성 설치.
- `cd web && pnpm dev` — 개발 서버 (Vite).
- `cd web && pnpm build` — 빌드.
- `cd web && pnpm lint` — ESLint.

---

## 7. 도메인 함정 헤드라인 (디테일은 most-local에)

- **통화 미변환**: API에서 환율이 적용되어 내려온다고 가정하지 말 것 — MCP는 unconverted, FastAPI 라우터에서 변환. (server/api/CLAUDE.md)
- **Pending vs Active**: 포트폴리오에 status=`Pending`이 섞여 있을 수 있다 — 화면 표시 시 status 분기 필요.
- **KST 거래일**: 시각 표시는 항상 KST 기준 거래일. UTC 그대로 표기 금지.
- **lib/ 매트릭스 잔재**: `signals12.ts / positionActionRules.ts / baseExpiryRules.ts / volFinMatrix.ts`는 폐기된 v17 매트릭스 잔재 (lib/CLAUDE.md §2 참고).
