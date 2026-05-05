# web/src/features/ — 도메인별 페이지 격리 룰

> 깊이 3. **most-local 단일 출처** — 새 페이지·페이지 컴포넌트 추가 시 본 파일 SSoT.
> 현재 6개 features (today / trades / review / portfolio / strategy / skills) = 사이드바 메뉴 + 참고 메뉴.

---

## 1. 절대 룰 — features 격리

- **features 간 import 금지**. `features/today/`가 `features/portfolio/`에서 무언가 import하지 않는다.
- 공유 로직이 필요하면:
  - 데이터: `web/src/hooks/`로 추출 (1훅=1엔드포인트).
  - 표시 헬퍼: `web/src/lib/`로 추출 (단, **표시용 only** — 비즈니스 룰은 백엔드 SSoT, lib/CLAUDE.md 참고).
  - 공통 UI 컴포넌트: 현재 별도 `components/` 루트 폴더 없음 — 필요 시 신설 결정 후 진입.
- 격리가 깨지면 페이지 간 결합도 폭증 → 한 features 변경이 다른 features를 깬다.

---

## 2. 폴더 구조 표준

```
features/<도메인>/
├─ <Domain>Page.tsx       (또는 Page.tsx — 둘 다 허용, 1 features = 1 진입 페이지)
└─ components/
   ├─ <Section>Card.tsx
   └─ <Section>Section.tsx
```

선택적:
- `tabs/` — 페이지 안에 탭이 있을 때 (예: `today/tabs/`).
- `hooks/` — 해당 features 전용 훅이 있을 때만 (재사용 가능하면 상위 `web/src/hooks/`로).

### 현 인벤토리

- `today/TodayPage.tsx` + `components/` + `tabs/`.
- `trades/...Page.tsx` + `components/`.
- `review/...Page.tsx` + `components/`.
- `portfolio/PortfolioPage.tsx` + `components/`.
- `strategy/StrategyPage.tsx` + `components/` (Signals12Section / VolFinMatrixSection / PositionActionRulesSection / BaseExpirySection 등 — lib/ 폐기 잔재 의존, lib/CLAUDE.md §2 참고).
- `skills/...` (참고 메뉴).

---

## 3. Page 컴포넌트 책임

- **데이터 훅 호출 + 레이아웃 + 자식 컴포넌트 조합**까지만.
- 비즈니스 로직, 복잡한 변환, 매매 룰 분기 → **금지**.
- Page가 길어지면 `components/`에 쪼갠다 (Cohesion).

### Good

```tsx
const PortfolioPage = () => {
  const portfolio = usePortfolio();
  const summary = usePortfolioDailySummary();
  if (portfolio.isPending) return <LoadingSkeleton />;
  if (portfolio.error) return <ErrorState error={portfolio.error} />;
  return (
    <div className="space-y-6">
      <PortfolioHeader summary={summary.data} />
      <PortfolioTable rows={portfolio.data?.positions ?? []} />
    </div>
  );
};
```

### Bad

- Page에서 직접 `apiGet` 호출 (훅 우회).
- Page에서 매매 임계값 분기 (룰은 백엔드 SSoT — lib/CLAUDE.md).
- Page에서 다른 features의 컴포넌트 import.

---

## 4. 새 features 추가 체크리스트

- [ ] 1. **폴더 생성**: `web/src/features/<domain>/`.
- [ ] 2. **Page.tsx 또는 `<Domain>Page.tsx` 작성** — 데이터 훅 + 레이아웃만.
- [ ] 3. **데이터 훅** — `web/src/hooks/use<Resource>.ts` 추가 (해당 폴더 CLAUDE.md 룰 준수). 백엔드 라우터가 없으면 `server/api/`에 먼저 추가.
- [ ] 4. **타입** — `web/src/types/api.ts`에 응답 모델 추가 (#15 수동 동기화 의무).
- [ ] 5. **App.tsx 라우트 등록** — `NAV_ITEMS`에 추가 + Route element 연결 (§3 routing 룰은 web/CLAUDE.md).
- [ ] 6. **components/** — 처음엔 비워두고, Page가 길어질 때 점진 분리.
- [ ] 7. **격리 점검** — 다른 features의 컴포넌트를 import하지 않는지.

---

## 5. 디자인 시스템 — Tremor 우선

- 차트(LineChart, BarChart, AreaChart 등), 카드(Card, Metric, Badge), 테이블(Table, TableRow, TableCell)은 **Tremor 우선**.
- Tailwind raw로 같은 컴포넌트 재구현 금지 (Cohesion 깨짐).
- Tremor 색상 팔레트(blue/emerald/amber/red/...)도 일관 사용. 색상 매핑은 `web/src/lib/constants.ts` 참고 (표시용 헬퍼).

---

## 6. 글로벌 frontend-guideline 4원칙 적용 포인트

> 글로벌 가이드(`~/.claude/CLAUDE.md`, `docs/frontend-guideline.md`)와 충돌 시 글로벌이 우선. 본 절은 features/ 특화 적용.

### 6.1 Readability
- 매직 넘버 금지 — 임계값/색상은 명명된 상수로 (`features/<domain>/components/constants.ts` 또는 `lib/constants.ts`).
- 복잡한 삼항 연산자 → if문 또는 IIFE.
- 함수에 JSDoc.

### 6.2 Predictability
- 페이지/컴포넌트 props 타입 명시. inferred any 금지.
- React Query 훅 결과는 `UseQueryResult` 그대로 사용 (hooks/CLAUDE.md §4).

### 6.3 Cohesion
- 한 도메인 = 한 features. 도메인 간 분리는 폴더 경계로.
- 관련 상수·타입·헬퍼는 `features/<domain>/components/` 안에 둔다 (지역화 우선, 조기 추상화 X).

### 6.4 Coupling
- Props Drilling 발견 시 Component Composition으로 해결 (children/slot 패턴).
- features 간 결합 ZERO — 격리 룰 (§1).
- 상태는 필요한 최소 범위 (focused hooks). 페이지 전체 상태 store 신설은 신중.

---

## 7. 함정 — 자주 틀리는 것

- **다른 features import** — 가장 흔한 실수. 같은 카드를 두 페이지에서 쓰고 싶으면 둘 중 하나가 ownership 갖거나 상위로 추출.
- **Page에 비즈니스 로직** — 매매 시그널 계산, base 만기 분기 등은 백엔드. 표시 분기만 허용.
- **페이지 안에서 fetch 직접 호출** — 훅 우회 시 캐시·에러 일관성 깨짐.
- **lib/의 폐기 매트릭스 직접 참조** — `Signals12Section / VolFinMatrixSection / PositionActionRulesSection / BaseExpirySection`은 폐기된 매트릭스를 시각화. 신규 페이지에서 같은 패턴 추가 금지 (lib/CLAUDE.md §2).
- **NavLink 등록 누락** — features 폴더만 만들고 App.tsx 누락 → 화면에 안 보임.

---

## 8. 폐기 인지 — strategy/ 페이지 잔재

- `strategy/components/Signals12Section.tsx`, `VolFinMatrixSection.tsx`, `PositionActionRulesSection.tsx`, `BaseExpirySection.tsx`는 라운드 2026-05에서 폐기된 v17 매트릭스/12셀/포지션 액션 룰을 시각화한다.
- 이 컴포넌트들은 `web/src/lib/{signals12,volFinMatrix,positionActionRules,baseExpiryRules}.ts`에 의존 — 모두 #14 이슈로 정리 대상.
- **신규 페이지/섹션은 같은 패턴 추가 금지**. 매트릭스 룩업 UI는 백엔드 rule_catalog 조회로 대체.
- 잔재 정리는 #14 이슈 결정 후 — 현 시점에선 새 의존 추가만 금지.

---

## 9. 데이터 흐름 표준 (페이지 진입 → 렌더 → mutation)

```
사용자 페이지 진입
  → react-router가 features/<domain>/<Domain>Page.tsx 마운트
  → Page가 web/src/hooks/use<Resource>() 호출
  → React Query가 캐시 확인 → 없으면 apiGet 발사 (web/src/lib/api.ts)
  → FastAPI 라우터 (server/api/<resource>.py) 응답 (envelope: web/src/types/api.ts 미러링)
  → Page가 isPending/error/data 분기 → 자식 components/ 렌더
  → 사용자 액션 (예: trade 기록) → mutation 훅 → onSuccess invalidateQueries → 자동 refetch
```

- 위 어디에도 features 간 import 없음. 공유는 hooks/lib/types 경유만.
- mutation 후 invalidate 누락 시 화면 stale — hooks/CLAUDE.md §5.

---

## 10. 글로벌 가이드 연결

- 본 파일은 stockclaude 특화 룰만. 일반 React/Tailwind 패턴은 글로벌 가이드를 따른다.
- "조기 추상화 지양" — 비슷한 컴포넌트가 둘이라도 features 간 공유는 신중. 중복 코드가 features 격리보다 가벼울 수 있다.
- features 경계가 결합도 방어선. 격리 룰이 흔들리면 페이지 단위 변경 영향 반경이 폭증한다.
