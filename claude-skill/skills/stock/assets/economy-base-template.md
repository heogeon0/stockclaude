# 거시경제 분석 ({KR/US})

> 경제 base.md 표준 템플릿 (6차원 + Daily Appended Facts).
> `reports/economy/base.md` 또는 `reports/economy/us-base.md`. DB `economy_base.content` 본문.

```yaml
---
금리_환경: {동결 / 인상 / 인하}
환율_수혜: {원화강세 / 원화약세 / 중립}
경기_사이클: {확장 / 회복 / 둔화 / 침체}
유동성: {풍부 / 중립 / 부족}
지정학: {안정 / 긴장 / 위기}
외국인_수급: {순유입 / 중립 / 순유출}
VI_수준: {낮음 / 중간 / 높음}
---
```

# 거시경제 분석 ({KR/US})

최종 수정: YYYY-MM-DD
last full review: YYYY-MM-DD
다음 갱신 조건: FOMC / 금통위 / CPI / 환율 임계 / 지정학 이벤트

---

## 1. 금리/유동성

### FOMC (미국)
- 최근 결정: YYYY-MM-DD, X.XX~Y.YY% {동결/인상/인하} (점도표 N-M)
- 다음 회의: YYYY-MM-DD
- 컨센서스: 연내 {N회 인하/인상} 컨센
- 2s10s 스프레드: ±X.X bp (역전 / 정상)
- 10년물: X.XX%

### 한국 (KR)
- 한은 기준금리: X.XX% (X회 연속 동결/인상/인하)
- 10년물: X.XX~Y.YY%
- 다음 금통위: YYYY-MM-DD

---

## 2. 환율/무역

- USD/KRW: X,XXX원 수준 (전월 +X.X%)
- DXY: XX.X
- 반도체 수출: ±X.X% YoY (전월)
- 무역수지: ±X억 달러
- Section 232 / 관세 관련 정책 변화

---

## 3. 경기/지수

### KR
- KOSPI 국면: **{강한 상승장 / 상승장 / 횡보 / 약세 / 강한 약세}** (4조건 통과 N/4)
  - 200일선 위 / 10개월선 위 / 20일선 상승 / 신고가 비율 60D X.X%
- KOSPI 종가: X,XXX
- 외국인: {순매수/매도} 누적 ±X조 (월/주)

### US (해당 시)
- S&P 500 / Nasdaq / Dow
- VIX 지수
- AAII 센티먼트

### 매크로 데이터
- 2026 GDP 전망: ±X.X%
- 산업생산 / 소매판매 / 실업률

---

## 4. 지정학

- **중동**: 휴전 / 분쟁 / 해협 통행 / 유가
- **미중**: 무역 협상 / 관세 / 반도체 규제
- **우크라**: 정세 / 에너지 가격 영향
- **WTI / 금**: $XX, $X,XXX (사상최고 / 최저 / 변동)

---

## 5. 섹터 포지셔닝

| 섹터 | 포지션 | 핵심 narrative |
|---|---|---|
| 반도체/HBM | Overweight / Neutral / Underweight | ... |
| 전력설비/방산 | ... | AI Capex + 지정학 |
| 게임 | ... | 회복 초기 / 판호 |
| 지주 | ... | 밸류업 |
| ... | ... | ... |

---

## 6. 외국인 수급 추이 (선택)

- 4월 누적: ±X조 (코스피)
- 코스닥: ±X조
- 최근 5일 추이: ...

---

## 📝 Daily Appended Facts (since last full review)

> stock-daily 가 매일 append. base-economy 갱신 시 통합 후 비움.
> 분류 룰: → `references/economy-base-classification.md` 참조.

### YYYY-MM-DD
- [high/rates] ...
- [medium/fx] ...
- [review_needed/geopolitics] ...
