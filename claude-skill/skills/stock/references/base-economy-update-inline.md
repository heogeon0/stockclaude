# base-economy-update — inline 절차

> **stale economy_base 발견 시 메인 에이전트가 직접 수행하는 절차.**
> 옛 `agents/base-economy-updater.md` (sub-agent) 폐기 → multi-device (mobile/Desktop/iOS Custom Connector) 운영 호환을 위해 inline 화.
>
> **단일 책임**: `economy_base` 행 (KR 또는 US) 본문 재작성 + 메타 7키 + DB 저장 + read-back.
> **언제**: `check_base_freshness` 결과 `economy.is_stale=true` 또는 사용자 `/base-economy --kr|--us` 호출 시.
> **누가**: stock skill 메인 LLM. sub-agent spawn 금지.

---

## 입력 인자

```
market: "kr" | "us"
```

## 0단계 — 의존성 / 진입 가드

- **다른 작업 중 inline 진입 시**: 직전 분석 결과 (다른 종목/포트폴리오 등) 를 economy 본문에 인용하지 않음. **깨끗한 상태로 8 섹션을 처음부터 작성**.
- **WebSearch 횟수 제한**: 4회 이내 (FOMC/한은, CPI/PCE, 외인 수급, 환율). 압축 시도 금지.
- 본 절차 진행 중 daily/research 본문에 매크로 결과를 추가 inline 작성하지 말 것 (저장 후 daily 가 `get_economy_base` 로 다시 읽음).

---

## 1단계 — 데이터 수집

| 차원 | 소스 | 핵심 메트릭 |
|---|---|---|
| 금리 | FRED (미국) / 한은 / WebSearch | FOMC, 한은 기준금리, 2s10s, 10년물 |
| 환율 | FRED / WebSearch | USD/KRW, DXY, 주요 통화 |
| 경기 | `detect_market_regime` + WebSearch | 코스피 국면 4조건, GDP, 수출 |
| 지정학 | WebSearch | 중동 / 미중 / 우크라 / 제재 / 무역 |
| 섹터 | 산업 base 종합 (`get_industry`) | Overweight / Neutral / Underweight |
| 외국인 수급 | KRX / WebSearch | 월/주 누적, 최근 5일 추이 |

WebSearch 표준 쿼리 (필요 분만):
```
"YYYY-MM-DD FOMC 결정 금리"
"YYYY-MM-DD CPI 발표 컨센서스"
"YYYY-MM-DD 외국인 코스피 순매수"
"YYYY-MM-DD 한은 금통위"
```

---

## 2단계 — 본문 재작성 (8 섹션)

표준 템플릿: → `~/.claude/skills/stock/assets/economy-base-template.md` (있다면) 참조. 없으면 아래 구조 그대로.

base 본문 구조:
1. **Frontmatter** (메타데이터 7키 — 4단계 참조)
2. 금리/유동성
3. 환율/무역
4. 경기/지수
5. 지정학
6. 섹터 포지셔닝
7. (옵션) 외국인 수급 추이
8. **📝 Daily Appended Facts (since last full review)** — 통합 후 비움

---

## 3단계 — Daily Appended Facts 통합

기존 `📝 Daily Appended Facts` 섹션 처리:

1. 분류 별 (high / medium / review_needed) 묶기
2. **high** → 본문 해당 섹션 반영
   - 금리 정책 변화 → 금리 섹션 갱신
   - 환율 레짐 전환 → 환율 섹션 갱신
3. **medium** → 추세 / 누적 변화 반영
4. **review_needed** → 섹터 포지셔닝 재검토 명시
5. 통합 후 섹션 비움 + last full review 날짜 갱신

영향도 분류 룰: → `~/.claude/skills/stock/references/economy-base-classification.md`.

---

## 4단계 — 메타 7키 + 저장

`save_economy_base(market, content, context)` 의 `context` 7키:

```python
context = {
    '금리_환경': '동결' | '인상' | '인하',
    '환율_수혜': '원화강세' | '원화약세' | '중립',
    '경기_사이클': '확장' | '회복' | '둔화' | '침체',
    '유동성': '풍부' | '중립' | '부족',
    '지정학': '안정' | '긴장' | '위기',
    '외국인_수급': '순유입' | '중립' | '순유출',
    'VI_수준': '낮음' | '중간' | '높음',
}
```

호출:
```python
save_economy_base(
    market=...,           # "kr" | "us"
    content=<8 섹션 본문>, # frontmatter 포함
    context=<7키>,
)
```

---

## 5단계 — Read-back 검증 (Trust but verify)

저장 직후:
```python
result = get_economy_base(market=...)
assert result['updated_at'] > <save 호출 직전 시각>
```

`updated_at` 이 갱신 안 되었거나 본문이 누락이면 **즉시 사용자 보고 + 재시도**.

---

## (옵션) economy daily 자동 생성

`reports/economy/{YYYY-MM-DD}.md` 가 없으면 별도 생성 가능:
- 템플릿: `~/.claude/skills/stock/assets/economy-daily-template.md`
- 4 섹션: 시장 지수 / 외국인 수급 / 주요 이벤트 / 종목별 영향
- 마지막 `📌 Economy Base 영향도 판단` 섹션

> 본 절차의 핵심 결과물은 `economy_base` (DB) 임. daily 파일은 부속.

---

## 작성 원칙

- 모든 숫자는 출처 + 시점 명시 (예: "FOMC 3/18: 3.50~3.75% 동결")
- `[실제]` / `[추정]` / `[가정]` 태깅
- WebSearch 결과 인용은 출처 URL 또는 매체 명시
- 매일 갱신 — 캐시 재사용 금지

---

## ✅ 완료 체크리스트

- [ ] 8 섹션 (Frontmatter 포함) 모두 작성
- [ ] 메타 7키 모두 채움 (None/공백 금지)
- [ ] `save_economy_base(market, content, context)` 호출 성공
- [ ] `get_economy_base(market)` read-back 으로 `updated_at` 갱신 확인
- [ ] Daily Appended Facts 비움 + last full review 날짜 갱신

## 완료 시 메인이 정리할 것

작업 후 메인이 1~3줄로 핵심 변경 요약 (사용자에게 보고 또는 daily 본문 인용용):
```
✅ economy_base[market=kr] 갱신 (updated_at=YYYY-MM-DDTHH:MM)
주요 변경:
  - FOMC 동결 (3.50~3.75% 유지) — Daily Appended Facts → 본문 통합
  - USD/KRW 1,420 → 1,395 (원화강세 전환) — 환율_수혜 메타 변경
  - 외국인 4월 누적 +2.3조원 순유입 → 섹터 포지셔닝 반도체 OW
```

실패 시:
```
❌ economy_base[market=kr] 갱신 실패
원인: <구체 에러>
재시도 권장: <조치>
```

---

> **inline 진입 시 주의 (재강조)**: 메인이 다른 작업 (daily/research/discover) 중에 본 절차로 진입하더라도, 직전 작업의 결과를 economy 본문에 끌어오지 않는다. 깨끗한 상태로 8 섹션을 처음부터 작성한다. **섹션 압축·생략 금지** — `economy_base` 는 1일 동안 daily/research/discover 가 참조하는 정식 문서다 (LLM 의 '효율 추구' 본능을 의식적으로 차단할 것).
