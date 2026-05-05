# 테마별 자주 쓰는 키워드

> 로드 시점: `discover_by_theme(keyword)` 호출 시.

## 테마 매핑

| 테마 | 키워드 |
|---|---|
| **반도체** | "HBM", "AI 칩", "파운드리", "DRAM", "NAND" |
| **2차전지** | "전기차", "양극재", "음극재", "전해액", "ESS" |
| **바이오** | "신약", "항체", "CDMO", "ADC", "백신" |
| **전력·인프라** | "AI 전력", "변압기", "원전", "데이터센터", "송배전" |
| **소비재** | "K뷰티", "K푸드", "엔터", "콘텐츠" |
| **지주·배당** | "지주", "배당", "자사주", "밸류업" |
| **방산** | "방산", "항공우주", "미사일", "수출" |
| **조선** | "LNG선", "컨테이너", "친환경", "군함" |
| **AI 인프라** | "GPU", "서버", "PCB", "패키징", "광학" |
| **자동차** | "전기차 EV", "자율주행", "수소", "ADAS" |

## 호출 예시

```python
discover_by_theme(keyword="AI 전력", market="kr")
# → DB의 stock_base.narrative + industries.content 에서 키워드 매칭
```

## 키워드 결합

복합 테마는 OR 검색:
```python
# AI + 전력 인프라
keywords = ["AI 전력", "변압기", "데이터센터"]
results = []
for k in keywords:
    results.extend(discover_by_theme(keyword=k))
# 중복 제거 + 동일 종목 카운트 ≥ 2 우선
```

## 시즌별 추가 키워드

| 시즌 | 키워드 |
|---|---|
| 1Q (실적 시즌) | "1Q26 실적", "어닝 서프라이즈" |
| 4Q (배당 시즌) | "배당기준일", "결산 배당" |
| 11~12월 (북클로징) | "북 클로징", "양도세" |
| 5~6월 (정책) | "FOMC 인하", "금통위" |

## US 테마 키워드

| 테마 | 키워드 |
|---|---|
| **AI Capex** | "AI infrastructure", "data center", "GPU" |
| **Semiconductor** | "HBM", "advanced packaging", "TSMC" |
| **Cloud** | "AWS", "Azure", "GCP", "hyperscaler" |
| **Drug** | "GLP-1", "obesity", "Alzheimer" |
| **EV** | "Tesla", "Rivian", "battery" |
