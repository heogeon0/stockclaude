# server/scrapers/ — 외부 API 클라이언트 레이어

> 깊이 2 — scrapers/ 폴더 진입 시 자동 로드.
> 10개 파일: dart / ecos / edgar / finnhub / fred / kis / krx / naver / us_universe / yfinance_client.

---

## API 인벤토리

| API | 역할 | 인증 방식 | 함정 |
|---|---|---|---|
| **KIS Open API** | KR/US OHLCV·현재가·intraday·실거래(read-only) | App Key/Secret + 계좌번호 + real/paper 분리 | 토큰 캐시 (`.kis_token.json`), KR 150건 / US 100건 한도 |
| **KRX Open API** | 공매도·시총·종목마스터 | API Key | rate-limit 미상 |
| **DART OpenAPI** | KR 공시·재무제표 | API Key | 회사코드 매핑 (corp_code) 별도 |
| **FRED** | US 거시지표 | API Key | 시리즈 ID 외움 필요 |
| **Finnhub** | US 실적 캘린더·컨센서스 | API Key | freemium tier rate-limit |
| **SEC EDGAR** | US 공시 | **User-Agent (이름+이메일) — 키 아님** | UA 누락 시 즉시 차단 |
| **한국은행 ECOS** | KR 매크로 (기준금리/CPI/환율/M2/경상수지) | API Key (무료, 즉시) | 통계표 코드 외움 필요 |
| **Naver 금융** | KR OHLCV fallback | 무인증 (스크래핑) | HTML 변경 시 깨짐, 차단 위험 |
| **yfinance** | US OHLCV fallback | 무인증 | period 인자만, 임의 일자 X |
| **Anthropic** | (Phase 1 미사용) | API Key | 현재 비활성 |

---

## KIS 토큰 캐시 (`scrapers/kis.py`)

- 토큰 파일: `.kis_token.json` (프로젝트 루트). access_token + 만기 timestamp.
- 갱신 로직 — 만기 임박 시 재발급. 실데이터/모의투자 분리(real/paper) 의무.
- 신규 KIS 호출 추가 시 토큰 캐시 재사용 — 매번 발급 금지(rate-limit 누적).
- 토큰 파일은 `.gitignore` (실 시크릿).

---

## KIS 한도 + fallback 분기 (§4.2)

- KIS는 단일 호출당 KR ≤150일, US ≤100일.
- `server/mcp/server.py:_fetch_ohlcv` (132~182)가 분기 경로:
  - **KR**: ≤150일 → KIS, 초과 → naver 스크래핑
  - **US**: ≤100일 → KIS, 초과 → yfinance period 매핑 (1mo / 3mo / 6mo / 1y / 2y / 5y)
- yfinance는 **임의 일자 인자 불가**. period 문자열만. 일수 → period 매핑 로직 변경 시 검증.
- 신규 OHLCV 경로 추가 시 동일 분기 룰 따름. 직접 `_fetch_ohlcv` 우회 호출 금지.

---

## SEC EDGAR User-Agent 필수

- API Key 아님. **HTTP `User-Agent` 헤더에 이름+이메일** (예: `stockclaude tool heo3793@gmail.com`).
- 누락 시 SEC 측에서 즉시 IP 차단.
- 모든 EDGAR 요청에 UA 헤더 강제 (`scrapers/edgar.py`).
- 신규 클라이언트가 EDGAR 호출하면 동일 UA 의무.

---

## naver 스크래핑 위험 관리

- HTML 파싱 — 네이버가 마크업 변경하면 즉시 깨짐.
- IP 차단 위험 — 과도한 호출 금지. KIS fallback으로만 사용.
- 신규 스크래핑 코드 추가 시 fallback 경로 명시 + 변경 감지 로깅 권장.
- KR 데이터의 1차 source는 KIS — naver는 한도 초과 시만.

---

## yfinance 제약

- period 인자만 사용 (`1d/5d/1mo/3mo/6mo/1y/2y/5y/10y/ytd/max`).
- 임의 시작일/종료일 지정 X. 일수 단위로 정확한 범위가 필요하면 가장 가까운 period 받아서 후처리 슬라이싱.
- 무인증 — rate-limit은 yfinance 측이 알아서. 단 과도하면 yahoo 측 차단.
- US 한도 초과시 fallback. 1차는 KIS.

---

## OHLCV 한글 컬럼 normalize (§4.2)

- 모든 source가 출력 직전에 한글 컬럼으로 변환 의무: `날짜 / 시가 / 고가 / 저가 / 종가 / 거래량`.
- analysis 레이어는 이 컬럼명을 가정 (`server/analysis/CLAUDE.md` 참고).
- 신규 source 추가 시 변환 layer 필수. 영어 컬럼 그대로 흘리면 분석 함수에서 KeyError.

---

## silent fallback 디버깅 (§4.2 함정)

- KIS 실패 → fallback(naver/yfinance) 경로가 silent. 로그 미흡 시 어느 source가 응답했는지 안 보임.
- 신규 코드는 source 식별 로그 명시 권장 (예: `logger.info("ohlcv source=naver", ...)`).
- 디버깅 시 — fallback 분기 함수에 임시 print 추가 후 source 확인.

---

## 인증 정보 — env 우선

- 모든 키/시크릿은 `server/config.py` (pydantic-settings) 경유. 코드에 하드코딩 금지.
- `.env.example`에 새 키 항목 추가 의무 (사용자가 알아챌 수 있도록).
- 토큰 캐시(`.kis_token.json`)는 파일 — 다른 source는 메모리/env로 충분.

---

## rate-limit 처리 패턴

- KIS: 토큰 갱신 + 호출 간 sleep (필요 시). 한도 초과는 fallback로.
- Finnhub freemium: 분당 60 호출 등. 호출 간격 두는 패턴.
- DART/ECOS/FRED: 일별 한도. 캐싱 권장.
- 신규 클라이언트 — rate-limit 문서 확인 후 retry/backoff 명시.

---

## DART corp_code 매핑 (`scrapers/dart.py`)

- DART는 종목코드(KRX) 대신 자체 `corp_code` 사용. 매핑 파일 갱신 필요.
- 신규 KR 종목 등록 시 corp_code 매핑 누락이면 공시 조회 0건. 사용자 입장에선 silent 실패.
- 매핑 캐시 갱신 주기 — 분기/반기 권장. 신규 코드는 갱신 트리거 명시.

---

## FRED·ECOS·Finnhub 시리즈/통계표 코드

- FRED — 시리즈 ID 외움 필요 (예: `FEDFUNDS`, `CPIAUCSL`). 코드에 시리즈 ID 하드코딩 시 주석으로 의미 명시.
- ECOS — 한국은행 통계표 코드 외움 필요. 마찬가지 주석 의무.
- Finnhub — 엔드포인트별 freemium tier 한도 다름. 호출 분당 제한 확인 후 호출.

---

## us_universe.py — US 종목 마스터

- US 종목 인벤토리 (NYSE/NASDAQ). discover 모드에서 사용.
- 갱신 주기·source 명시 (현재 어디서 가져오는지) — 신규 작업 진입 시 확인.

---

## 신규 scraper 추가 체크리스트

1. 새 파일 `scrapers/<source>.py` 또는 기존 모듈 확장.
2. 인증 방식 확인 — API Key / OAuth / User-Agent / 무인증.
3. `server/config.py`에 env 항목 추가 + `.env.example` 갱신.
4. rate-limit 문서 확인 + 호출 간격 처리.
5. OHLCV 반환 시 한글 컬럼 normalize 의무.
6. fallback 위치/조건 명시 (어느 source가 1차, 언제 fallback).
7. silent 실패 방지 — source 식별 로그.
8. 토큰/세션 캐시 필요 시 `.gitignore` 등록.
9. 시리즈 ID·통계표 코드는 코드 주석으로 의미 명시.
10. 매핑 파일 갱신 주기 명시 (예: corp_code 분기마다).
