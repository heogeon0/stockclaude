# WebSearch 도메인 화이트리스트 (Tier 1~4 — 단일 출처)

> 라운드 2026-05-daily-workflow-tightening 신설. 모든 reference 가 도메인 목록 인용 시 본 파일 단일 출처 사용.
> 정책 (BLOCKING 횟수·인용 룰·캐시) 은 `websearch-rules.md`. 본 파일은 도메인 enumeration + 단계 × Tier 매트릭스만.
> 신규 사이트 추가 절차는 본 파일 §6 — 라운드 doc 통과 의무.

---

## 1. Tier 1 — 글로벌 매체 (1차 신뢰)

광역 시장·매크로·종목 뉴스의 1차 인용처. FOMC·지정학·실적 가이던스 등.

- `bloomberg.com`
- `reuters.com`
- `ft.com` (Financial Times)
- `wsj.com` (Wall Street Journal)
- `nikkei.com` (Nikkei Asia)
- `cnbc.com`

용도: daily Phase 2 (발언 톤·지정학), daily Phase 3 (per-stock 뉴스), base-stock #3 (경쟁사).

---

## 2. Tier 2 — 공식 기관 (1차 신뢰, 정책 영역)

규제·금리·통계의 1차 발표처. 매체 인용보다 공식 자료 우선.

### US

- `federalreserve.gov` (FOMC 의사록·연설·정책 결정)
- `sec.gov` (10-K / 10-Q / 8-K / proxy / EDGAR)
- `bls.gov` (CPI / PCE / NFP)
- `fred.stlouisfed.org` (시계열 매크로)

### KR

- `bok.or.kr` (한국은행 — 금통위·통화정책)
- `fsc.go.kr` (금융위원회)
- `fss.or.kr` (금융감독원)
- `moef.go.kr` (기획재정부)
- `dart.fss.or.kr` (DART 공시)

### EU

- `ecb.europa.eu` (ECB)
- `europa.eu` (집행위)

용도: daily Phase 2 (정책 결정 원문), base-stock #4 (규제), industry base 부속 (정책 변경).

---

## 3. Tier 3 — 산업 전문 (시장조사·분야별)

산업 평균·점유율·기술 트렌드의 1차 인용처. 정형 자산 거의 없음.

### 시장조사 (범용)

- `gartner.com`
- `idc.com`
- `counterpointresearch.com`
- `statista.com`

### 반도체

- `semianalysis.com`
- `trendforce.com`
- `omdia.com`

### 자동차 / EV

- `insideevs.com`
- `electrek.co`

### AI / SaaS

- `theinformation.com`

용도: base-industry (점유율·기술 트렌드 — BLOCKING 2회).

---

## 4. Tier 4 — KR 매체

KR 종목 뉴스·공시 해석·시장 반응. Tier 1 글로벌 매체가 다루지 않는 KR 로컬 nuance.

- `hankyung.com` (한국경제)
- `mk.co.kr` (매일경제)
- `edaily.co.kr` (이데일리)
- `thebell.co.kr` (더벨 — 자본시장 / IB)
- `mt.co.kr` (머니투데이)

용도: daily Phase 3 (per-stock 뉴스 — KR 종목이면 Tier 1 + 본 Tier 추가).

---

## 5. ⛔ 금지 도메인 (인용 무효)

검색 결과 상위에 보여도 인용 금지. 인용 시 보고서 무효.

### 일반 블로그·커뮤니티

- 네이버 블로그 (`blog.naver.com`)
- 네이버 카페 (`cafe.naver.com`)
- 다음 카페 (`cafe.daum.net`)
- 티스토리 (`*.tistory.com`)
- 브런치 (`brunch.co.kr`)

### SNS

- Reddit (`reddit.com`)
- X / Twitter (`x.com`, `twitter.com`)
- Threads (`threads.net`)
- Facebook (`facebook.com`)
- YouTube 댓글·요약 (`youtube.com`)

### 개인 기고·SEO 사이트

- SeekingAlpha **개인 기고** (`seekingalpha.com/article/...` 단, Premium 애널 리포트는 예외 — 도메인만으로 차단 X. 본문 톤으로 재판단)
- predictabledesigns.com 같은 SEO 양산 사이트
- AI 생성 콘텐츠 (요약 사이트·뉴스 aggregator)

### 위키류

- 위키피디아 (`wikipedia.org`) — 1차 fact 확인용은 OK, 시장 인용은 무효 (시점·tone 부재)
- 나무위키 (`namu.wiki`) — 인용 무효

---

## 6. 단계 × Tier 매트릭스

각 단계가 어느 Tier 를 우선 사용해야 하는지.

```
daily Phase 2 economy (발언 톤·지정학):  Tier 1 + Tier 2
daily Phase 3 per-stock (뉴스):          Tier 1 + Tier 4 (KR 종목이면)
base-industry (점유율·기술 트렌드):       Tier 3 + Tier 1 (전반 동향 보강)
base-stock #3 (경쟁사):                   Tier 1
base-stock #4 (규제):                     Tier 2 공식 우선 + Tier 1 (해석)
```

쿼리 패턴 일반형:
```
site:<tier_a_domain> OR site:<tier_b_domain> {키워드} YYYY-MM[-DD]
```

상세 정책 (BLOCKING 횟수·인용 의무·캐시·결과 quality 가드) → `websearch-rules.md`.

---

## 7. 신규 사이트 추가 절차

본 파일은 라운드 단위로만 갱신. 임의 추가 금지.

1. 신규 사이트 후보 발견 — 어느 단계에서·왜 필요한지·기존 Tier 도메인으로 커버 안 되는 사유 정리.
2. 라운드 doc (`docs/rounds/<YYYY-MM-주제>.md`) 신규 또는 기존에 §"WebSearch 도메인 추가" 섹션 작성.
3. 사용자 검토 + 승인.
4. 본 파일 해당 Tier 에 추가 + Tier 매트릭스 §6 갱신 (필요 시).
5. 변경 reference 가 본 파일 인용하면 자동 반영. websearch-rules.md 캐시 룰·인용 룰은 그대로.

⚠️ Tier 1~4 분류는 라운드 결정 사안. 신규 사이트의 Tier 결정도 라운드 doc 에 명시.

---

## 8. 변경 이력

| 날짜 | 라운드 | 변경 |
|---|---|---|
| 2026-05-04 | 2026-05-daily-workflow-tightening | 신설. Tier 1~4 분류 + 단계 × Tier 매트릭스. 금지 도메인 enumeration. |
