# server/analysis/ — 순수 계산 레이어

> 깊이 2 — analysis/ 폴더 진입 시 자동 로드.
> 16개 모듈: backtest / chart_analysis / concentration / consensus / correlation / events / financials / flow / indicators / industry_metrics / momentum / regime / scoring / sensitivity / signals / valuation / volatility.

---

## 책임 — 순수 함수 only

- **DB 의존 금지.** `server.db`, `server.repos.*` import 금지. numpy/pandas/표준 라이브러리만 의존.
- 입력은 OHLCV `pandas.DataFrame` 또는 plain `dict`. 출력은 dict/list/scalar.
- 호출 흐름: api/mcp → `repos.*` (DB fetch) → `analysis.*` (계산) → api/mcp (응답 가공). repos 결과를 dict로 받아 analysis 함수에 넘기는 형태.
- DB 접근이 필요해 보이면 STOP — repos에서 fetch한 결과를 인자로 받게 재설계.

---

## OHLCV 한글 컬럼 normalization (§4.2)

- 모든 OHLCV는 한글 컬럼 표준: `날짜 / 시가 / 고가 / 저가 / 종가 / 거래량`.
- 분석 함수는 이 컬럼명을 가정. 영어 컬럼이면 입력 시점에 변환 책임은 scrapers/MCP normalize 단.
- 신규 source 추가 시 한글 normalize layer 의무 (`server/scrapers/CLAUDE.md` 참고).
- 새 분석 함수도 한글 컬럼 가정 — 영어 컬럼명 하드코딩 금지.

---

## 시장별 거래시간 (`indicators.py:17-19`)

- KR: `Asia/Seoul` 09:00–15:30
- US: `America/New_York` 09:30–16:00
- 거래시간 분기·정규장 판정에 이 dict 재사용. 새 시간 상수 중복 정의 금지.

---

## 공시 KST 강제 (`events.py:84,91`)

- `published_at`이 naive datetime이면 `ZoneInfo("Asia/Seoul")` 부착 (KST로 간주).
- timezone-aware datetime은 그대로 유지.
- 신규 시계열 분석에서 datetime 비교 시 동일 패턴 적용. `datetime.now()` 그대로 금지.

---

## 합성 점수 anchor 회피 (§4.7, §6.1) — 매트릭스 폐기

- 라운드 2026-05-stock-daily-overhaul 결정: `analyze_position`에서 `scoring/cell/is_stale` 합성 산출 제거. raw 9 카테고리만 반환.
- 폐기된 룩업: 12셀 매트릭스, decision-tree 5×6, position-action-rules 6대 룰. `references/_archive/`에 보존.
- **재제안 금지 목록** (analysis 신규 작성 시):
  - 종합 점수 산출 (categorical → 단일 score 합성)
  - "셀" 분류 (volatility×financials 같은 2D 매트릭스)
  - is_stale 자동 판정 후 라벨 부착
- `scoring.py`는 raw 카테고리(이동평균/모멘텀/가치/품질 등) 산출까지만. 합성·라벨·임계값 분기는 LLM(Claude)이 본문 판단으로 수행한다.
- 폐기 사유: deterministic 점수가 LLM의 본문 추론을 anchor → 자율 판단 봉쇄.

---

## 산업 표준 메트릭 활용 (§6.1)

- `industries.avg_per / avg_pbr / avg_roe / avg_op_margin / vol_baseline_30d` 컬럼 — 종목 financial_grade 결정 시 산업 평균 대비 본문 판단의 기준.
- `analysis/industry_metrics.py`가 산업 평균 산출 책임. 신규 메트릭 추가 시 이 모듈에.
- `analysis/financials.py / valuation.py`가 종목 메트릭을 산업 평균과 비교. 절대값 임계(예: PER 15 이하면 저평가) 하드코딩 금지 — 산업별로 의미가 다르다.

---

## 출력 컨벤션

- 함수 반환은 dict/list of dict/scalar. JSON-safe 변환 책임은 호출자(MCP는 `_json_safe`, API는 pydantic).
- numpy scalar(`np.float64` 등)·NaN/Inf는 호출자 변환 전제 — 다만 명시적 NaN 의미 없으면 미리 `None` 치환 권장.
- pandas Timestamp는 `.isoformat()`이나 dict 변환 시 자연스럽게 처리되도록.

---

## 모듈별 역할 요약

- `indicators.py` — 이동평균·RSI·MACD·볼린저 등 기본 지표 + 거래시간 dict.
- `signals.py` — 시그널 정의·계산 (rule_catalog 룰 ID와 연동).
- `momentum.py` / `volatility.py` — 모멘텀·변동성 산출.
- `scoring.py` — raw 카테고리 산출 (합성 점수 X — §4.7).
- `financials.py` / `valuation.py` — 재무·밸류에이션. 산업 평균 대비.
- `events.py` — 공시·이벤트 (KST 강제).
- `regime.py` — 시장 레짐 판정.
- `concentration.py` / `flow.py` / `correlation.py` — 포트폴리오 집중도·수급·상관관계.
- `industry_metrics.py` — 산업 평균 산출.
- `backtest.py` / `sensitivity.py` / `chart_analysis.py` / `consensus.py` — 보조 분석.

신규 함수 추가 시 도메인 가장 가까운 모듈에 — 새 영역만 신규 파일.

---

## 신규 analysis 모듈 추가 체크리스트

1. 도메인 단위 1파일 — 기존 16개 중 가장 가까운 곳에 함수 추가, 진짜 새 영역이면 신규 파일.
2. DB import 0건 — `repos.*` / `db` import 금지.
3. 입력 타입 명시 — `pd.DataFrame` (한글 컬럼) 또는 `dict`.
4. 거래시간·timezone 분기는 `indicators.py` 재사용.
5. 합성 점수·셀·라벨 자동 분기 금지 (raw 카테고리까지).
6. 산업 평균 비교는 `industries.avg_*` 컬럼 활용.
7. 호출자에서 JSON-safe 변환 — analysis 내부에서 강제 변환 금지 (정밀도 손실).
