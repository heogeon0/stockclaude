/**
 * 12 기술 시그널 정의 — stock/references/signals-12.md 인용.
 * compute_signals(code).signals 의 12 전략 + verdict 산정 룰.
 */

export interface SignalDef {
  no: number;
  name: string;
  buyCondition: string;
  sellCondition: string;
  buyWeight: number | null;
  sellWeight: number | null;
}

export const SIGNALS_12: SignalDef[] = [
  {
    no: 1,
    name: "일목균형표",
    buyCondition: "삼역호전 (구름 위 + 전환선>기준선 + 후행스팬 위)",
    sellCondition: "삼역호전 깨짐",
    buyWeight: 2,
    sellWeight: 2,
  },
  {
    no: 2,
    name: "래리윌리엄스",
    buyCondition: "변동성 돌파 (전일 고가 + α × 고저폭)",
    sellCondition: "—",
    buyWeight: 1.5,
    sellWeight: null,
  },
  {
    no: 3,
    name: "미너비니 SEPA",
    buyCondition: "트렌드 템플릿 4조건 + VCP 패턴 감지",
    sellCondition: "정배열 깨짐",
    buyWeight: 1.5,
    sellWeight: 1,
  },
  {
    no: 4,
    name: "리버모어 피봇",
    buyCondition: "3주 신고가 돌파 + 거래량 동반",
    sellCondition: "—",
    buyWeight: 1.5,
    sellWeight: null,
  },
  {
    no: 5,
    name: "TripleScreen (Elder)",
    buyCondition: "추세↑ + Stoch 매수 + MACD↑",
    sellCondition: "추세↓ + 과매수",
    buyWeight: 1,
    sellWeight: 1.5,
  },
  {
    no: 6,
    name: "볼린저",
    buyCondition: "상단 돌파 + 거래량",
    sellCondition: "하단 이탈 + 거래량",
    buyWeight: 1,
    sellWeight: 1,
  },
  {
    no: 7,
    name: "그랜빌 SMA20",
    buyCondition: "SMA20 매수8 패턴",
    sellCondition: "과이격 30%+",
    buyWeight: null,
    sellWeight: 1,
  },
  {
    no: 8,
    name: "그랜빌 SMA60",
    buyCondition: "SMA60 매수8 패턴",
    sellCondition: "과이격 40%+",
    buyWeight: null,
    sellWeight: 1,
  },
  {
    no: 9,
    name: "그랜빌 SMA120",
    buyCondition: "SMA120 매수8 패턴",
    sellCondition: "과이격 60%+",
    buyWeight: null,
    sellWeight: 1,
  },
  {
    no: 10,
    name: "RSI 과열",
    buyCondition: "RSI < 30 (과매도)",
    sellCondition: "RSI > 80 (극과매수)",
    buyWeight: null,
    sellWeight: 1.5,
  },
  {
    no: 11,
    name: "평균회귀",
    buyCondition: "20MA 이탈 후 회복",
    sellCondition: "20MA 이격 30%+ + 거래량 약화",
    buyWeight: null,
    sellWeight: 1,
  },
  {
    no: 12,
    name: "추세반전",
    buyCondition: "MACD 골든크로스",
    sellCondition: "MACD 데드크로스",
    buyWeight: 1,
    sellWeight: 1,
  },
];

export interface VerdictRule {
  verdict: "강한매수" | "매수우세" | "중립" | "매도우세" | "강한매도";
  buyCondition: string;
  sellCondition: string;
  color: "emerald" | "blue" | "gray" | "amber" | "red";
}

export const VERDICT_RULES: VerdictRule[] = [
  { verdict: "강한매수", buyCondition: "≥ 3.5", sellCondition: "0", color: "emerald" },
  { verdict: "매수우세", buyCondition: "> 매도, ≤ 1.5", sellCondition: "< 매수", color: "blue" },
  { verdict: "중립", buyCondition: "≈ 매도", sellCondition: "≈ 매수", color: "gray" },
  { verdict: "매도우세", buyCondition: "< 매도", sellCondition: "> 매수, ≥ 1.5", color: "amber" },
  { verdict: "강한매도", buyCondition: "0", sellCondition: "≥ 3.5", color: "red" },
];

export const VCP_NOTE =
  "VCP 정석 = `is_vcp: true` + `contractions: [22, 9]` (수축률) + `volume_trend: '감소'` + 피봇 돌파 + 거래량 폭증. 미너비니 진입 시그널 핵심.";

export const SIGNAL_USAGE_RULES = [
  "**보유 종목**: 강한매수/매수우세 + 비중 < 25% → 피라미딩 검토 (변동성×재무 셀 룩업)",
  "**보유 종목**: 중립 → 홀딩, 트레일링 스탑 점검",
  "**보유 종목**: 매도우세/강한매도 → 부분/전량 청산 검토",
  "**신규 진입**: 강한매수 → 진입 가능 (셀 사이즈 적용)",
  "**신규 진입**: 매수우세 → 1차 진입 (잔여는 추가 트리거 대기)",
  "**신규 진입**: 중립/매도우세/강한매도 → ❌ 진입 비추",
  "단일 시그널 의존 금지 — 종합 verdict 우선. RSI 90+ 같은 극단치만 단독 매도 가능.",
];
