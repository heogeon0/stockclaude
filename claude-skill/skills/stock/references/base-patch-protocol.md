# Base Patch 프로토콜 (Daily Appended Facts)

> 로드 시점: 종목/산업/경제 base에 유의미한 fact를 append할 때.
> 분류 룰은 → `references/base-impact-classification.md` 참조.

## 핵심 원칙

- **Daily는 base의 main body를 절대 건드리지 않음** — 하단 `Daily Appended Facts` 섹션에만 append
- **Research/base-* skill만 main body 재작성 권한** — 실행 시 (1) main body 재작성 (2) appended facts 통합 (3) 섹션 비움 (4) last full review 날짜 갱신
- **즉시 patch (실시간)** — daily 보고서 작성과 동시에 base에 append. 지연 처리 금지

## 종목 base patch (3-step)

```
1. get_stock_context(code) → 현재 base content 읽기
2. content 의 "## 📝 Daily Appended Facts" 섹션에 오늘 날짜 하위로 append
   - 섹션이 있으면 오늘 날짜 헤더 추가
   - 섹션이 없으면 맨 아래에 섹션 생성 후 append
3. save_stock_base(code, content=new_content) 저장
```

## 산업 base patch (3-step)

```
감지된 각 산업 태그마다:
1. get_industry(code=산업코드) → 현재 content 읽기
2. "## 📝 Daily Appended Facts" 섹션에 오늘 날짜 하위로 append
3. save_industry(code=산업코드, name=산업명, content=new_content) 저장
```

산업 태그 규칙:
- 한 종목 daily에 여러 산업 언급 가능 (지주사는 여러 섹터)
- 섹터 표기는 `industries` 테이블의 code/name 기준

## 경제 base patch (3-step)

```
1. get_economy_base(market="kr") → 현재 content 읽기
2. content 의 "## 📝 Daily Appended Facts" 섹션에 오늘 날짜 하위로 append
3. save_economy_base(market="kr", content=new_content) 저장
```

## base.md 표준 레이아웃

```markdown
# {종목명} Base (last full review: 2026-04-01)

## 1. Narrative (base-stock 소유)
...

## 2. Reverse DCF / Comps / ... (base-stock 소유)
...

---
<!-- 아래는 daily 영역. base-stock 은 실행 시 통합 후 비움 -->

## 📝 Daily Appended Facts (since last full review)

### 2026-04-22
- [high/earnings] ...

### 2026-04-24
- [high/disclosure] ...
```

## 역할 분리

- **stock-daily**: 하단 `Daily Appended Facts` 섹션에만 append. Main body 절대 건드리지 않음
- **base-stock / base-industry / base-economy**: 실행 시 main body 재작성 + appended facts 통합 + 섹션 비움 + last full review 날짜 갱신

## 누적 경고 룰

- review_needed 플래그 **3개+ 누적** 시 daily 최상단 "🟡 base 재검토 권장 — `/base-stock {종목}` 권장" 경고 박스 필수
- 축적 기간이 60일+ (base 오래됨) 이면 자동 재생성 트리거 (`references/expiration-rules.md`와 연동)
