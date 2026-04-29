# 거시경제 데일리 — YYYY-MM-DD

> economy/{날짜}.md 자동 생성 템플릿 (stock-daily 0단계 의존성 체크 시).
> 본 파일이 owner. stock-daily/assets/economy-daily-template.md 와 cross-link.

```yaml
---
금리_환경: {base에서 복사}
환율_수혜: {오늘 변화 있으면 덮어쓰기, 없으면 base 복사}
경기_사이클: {base 복사}
유동성: {base 복사}
지정학: {base 복사}
외국인_수급: {fetch_investor 최근 5일 기관/외국인 평균 기반 판정}
VI_수준: {V-KOSPI 확인 가능 시 반영, 없으면 base 복사}
---
```

# 거시경제 데일리 — YYYY-MM-DD

## 시장 지수 (pykrx KOSPI/KOSDAQ)

- KOSPI 종가: X,XXX (±X.X%)
- KOSDAQ 종가: XXX (±X.X%)
- 코스피200 / 코스닥150
- 거래대금 / 거래량 (전일 비)

## 외국인/기관 수급 요약

- 외국인: ±X억주 / ±X조 (당일)
- 기관: ±X억주 / ±X조 (당일)
- 5일 누적 추이

## 주요 이벤트 (WebSearch 당일 뉴스)

- ...

## 종목별 영향 한 줄 (보유 종목 각)

- {종목명}: {경제 변수 → 종목 영향 한 줄}
- ...

## 📌 Economy Base 영향도 판단

> 분류 룰: → `references/economy-base-classification.md` 참조 (4단계 분류).

```
- [high/rates] 연준 6월 인하 전망 약화 (CPI 3.1% 예상 상회) — source: WebSearch
- [medium/fx] 원/달러 1,420원 돌파 — 수출주 수혜 narrative 강화
- [review_needed/geopolitics] 중국 반도체 규제 확대 검토 — 'US-China tension' 재평가
```

→ 즉시 economy base patch (절차: → `~/.claude/skills/stock/references/base-patch-protocol.md` 의 "경제 base patch" 섹션 참조)

→ `/base-economy` 실행 시 main body 전면 재작성 + appended facts 통합 + 섹션 비움
