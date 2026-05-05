# web/src/hooks/ — React Query 훅 룰북

> 깊이 3. **most-local 단일 출처** — 훅 작성·수정 진입 시 본 파일이 SSoT.
> 현재 28개 훅 (`use*.ts`). 신규 훅 추가 시 본 파일의 체크리스트 끝까지.

---

## 1. 절대 룰 — 1훅 = 1엔드포인트 = 1파일

- 파일명·훅명·queryKey root는 모두 일치한다.
  - `usePortfolio.ts` → `usePortfolio` → queryKey `["portfolio", ...]`.
  - `useDailyReports.ts` → `useDailyReports` → queryKey `["dailyReports", ...]`.
- **한 파일에 두 훅 묶지 않는다**. 같은 리소스의 GET / mutation은 같은 파일 OK (예: `usePortfolio` + `useUpdatePortfolio`).
- **다른 리소스를 합치지 않는다**. 한 페이지에서 두 데이터가 필요하면 두 훅 호출.

---

## 2. queryKey 컨벤션

- 형식: `["resource", ...params]`.
- 첫 토큰은 리소스 명사 (camelCase): `["portfolio", status]`, `["dailyReports", { date, code }]`.
- params는 직렬화 가능한 원시값 또는 plain object. 함수·undefined 포함 금지.
- 인자가 바뀌면 React Query가 자동 invalidate — useEffect로 refetch 강제하지 말 것.
- mutation 후 invalidate 시: `queryClient.invalidateQueries({ queryKey: ["resource"] })` (root prefix).

---

## 3. 표준 패턴 (research §5.8 인용)

```ts
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { PortfolioOut } from "@/types/api";

type Status = "active" | "all";

export const usePortfolio = (status: Status = "active") =>
  useQuery({
    queryKey: ["portfolio", status],
    queryFn: () => apiGet<PortfolioOut>("/portfolio", { status }),
  });
```

핵심 4가지:
1. `useQuery` 결과를 **그대로 반환** — 풀어서 `data` / `isLoading` 추출 후 재구성 금지.
2. queryFn 안에서 `apiGet<T>(path, params)` 호출. fetch 직접 사용 금지.
3. 타입 인자 `<PortfolioOut>`은 `@/types/api`에서 import.
4. 인자에 기본값 부여 — 호출부 단순화.

---

## 4. UseQueryResult 반환 룰 (Predictability)

> 글로벌 가이드라인(`~/.claude/CLAUDE.md`)의 Predictability 원칙. 본 폴더 절대 룰.

- 훅은 **항상 `UseQueryResult<T>` 또는 `UseMutationResult`를 그대로 반환**.
- 데이터를 풀어서 `{ portfolio, isLoading, error }` 같은 커스텀 객체로 반환 금지.

### Bad

```ts
// 안티패턴 — 호출부에서 isLoading/error 처리 일관성 깨짐
export const usePortfolio = () => {
  const q = useQuery({ queryKey: ["portfolio"], queryFn: ... });
  return { portfolio: q.data, loading: q.isLoading };
};
```

### Good

```ts
// React Query 표준 결과 그대로 노출
export const usePortfolio = () =>
  useQuery({ queryKey: ["portfolio"], queryFn: ... });
```

---

## 5. mutation 패턴

```ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiPost } from "@/lib/api";

export const useRecordTrade = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TradeIn) => apiPost<TradeOut, TradeIn>("/trades", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["trades"] });
      qc.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
};
```

- mutation 성공 시 영향받는 모든 query를 invalidate. 부분 갱신 X (R5에선 자동 refetch가 안전).
- `onError`는 ApiError 캐치 후 토스트/콘솔. UI에서 추가 분기 가능.

---

## 6. 타입 — `web/src/types/api.ts` 수동 동기화 (§10.5 이슈)

- `apiGet<XxxOut>` / `apiPost<XxxOut, XxxIn>`에 사용하는 모든 타입은 **`web/src/types/api.ts`에 정의**.
- 백엔드 `server/schemas/*.py` pydantic 모델과 **수동 동기화** — 자동 생성(openapi-typescript) 미적용 (§10.5 이슈로 추적).
- **신규 훅 추가 시 의무**:
  1. 백엔드 라우터의 `response_model` 확인.
  2. `web/src/types/api.ts`에 대응 TS 타입 추가/갱신.
  3. snake_case 유지 (FastAPI가 그대로 반환).
  4. Optional 필드는 `field?: T | null` 명시.
- 누락 시 silent drift — 컴파일 에러 없이 런타임에 undefined 접근 가능.

---

## 7. 에러 처리

- `apiGet/apiPost`는 응답 비-2xx에서 `ApiError`를 throw (`web/src/lib/api.ts`).
- 훅 사용처에서:
  ```ts
  const { data, error } = usePortfolio();
  if (error instanceof ApiError && error.status === 404) {
    return <EmptyState />;
  }
  ```
- React Query 글로벌 default는 `QueryClient` 설정에 위임 — 훅 단위 retry 옵션 남발 금지.

---

## 8. 신규 훅 추가 체크리스트

- [ ] 1. **엔드포인트 단일성** 확인 — 같은 endpoint 다루는 기존 훅 없는지 grep (`grep -r "apiGet.*<path>" web/src/hooks/`).
- [ ] 2. **파일명** = 훅명 (camelCase, `use` prefix). 1파일 1리소스.
- [ ] 3. **queryKey** = `["resource", ...params]` 컨벤션.
- [ ] 4. **타입** — `web/src/types/api.ts`에 응답 모델 추가/확인 (§10.5 동기화 의무).
- [ ] 5. **반환 형태** — `UseQueryResult` 그대로. 풀어서 반환 금지.
- [ ] 6. **mutation이면 invalidate 대상** 명시.
- [ ] 7. 호출부에서 `data`·`error`·`isPending` 분기 가능한지 점검.

---

## 9. 현 인벤토리 (28개) — 그룹 분류

> 새 훅 추가 시 의미상 가까운 그룹 옆에 배치 (정렬 룰은 없으나 일관성 도움).

- **포트폴리오**: `usePortfolio`, `usePortfolioDailySummary`, `useConcentrationAlerts`.
- **데일리·주간 리포트**: `useDailyReports`, `useDailyReportDates`, `useWeeklyReview`, `useWeeklyReviews`, `useLatestWeeklyReview`, `useWeeklyContext`.
- **거래·백테스트**: `useTrades`, `useRecentTrades`, `useBacktest`.
- **종목·산업·지표**: `useStockBase`, `useIndustries`, `useRegime`.
- **거시 / base**: `useEconomyBase`, `useEconomyDaily`.
- **점수 가중치**: `useScoreWeightsApplied`, `useScoreWeightsDefaults`, `useScoreWeightsOverrides`.
- **스킬 메타**: `useSkills`, `useSkillContent`.

---

## 10. 함정 — 자주 틀리는 것

- **queryKey 누락 인자** — 인자 의존이 있는데 queryKey에 안 넣으면 캐시 충돌. 모든 인자는 queryKey에.
- **fetch 직접 호출** — `apiGet` 우회 시 `ApiError`가 안 나오고 base URL 일관성 깨짐.
- **데이터 풀어 반환** — 호출부에서 React Query 결과 분기 안 됨 (§4 Bad 사례).
- **types/api.ts 갱신 누락** — 응답 변경 시 silent drift. PR 시 `server/schemas/` 변경분과 같이 봐야 함 (§10.5).
- **invalidate 누락** — mutation 후 데이터 stale.

---

## 11. 글로벌 가이드 연결

- 본 파일은 stockclaude 특화 — 일반 React Query 패턴은 글로벌 `~/.claude/CLAUDE.md`와 `docs/frontend-guideline.md` 따름.
- "조기 추상화 지양" — 두 훅이 비슷해도 합치지 말고 두 파일 유지가 원칙(1훅=1엔드포인트).
