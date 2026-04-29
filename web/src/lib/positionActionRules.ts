/**
 * v17 포지션 반영 6대 룰 + 수익률 × verdict 매트릭스.
 * stock/references/position-action-rules.md 인용.
 */

export interface PositionRule {
  no: number;
  title: string;
  body: string;
}

export const POSITION_RULES: PositionRule[] = [
  {
    no: 1,
    title: "수익률 계산 (자동)",
    body: "수익률 = (현재가 - 평단가) / 평단가 × 100. compute_indicators(code).price_context + get_portfolio.positions[code].avg_price 기반.",
  },
  {
    no: 2,
    title: "보유 + 매도 시그널 다수 → 이익 실현 / 손절 검토",
    body: "verdict = 매도우세/강한매도 → 수익률 +10% 이상이면 부분 익절 (셀의 피라미딩 단계 = 익절 단계). -5%~+5% 손익분기. -5% 이하 손절 검토.",
  },
  {
    no: 3,
    title: "보유 + 매수 시그널 다수 → 피라미딩 검토 (조건부)",
    body: "verdict = 강한매수/매수우세 + 비중 < 25% + 셀 피라미딩 단계 > 0 + check_concentration 통과 → 피라미딩. 25% 룰 위반 시 자동 차단.",
  },
  {
    no: 4,
    title: "미보유 + 매수 시그널 다수 → 신규 진입 + 재무 확증",
    body: "verdict = 강한매수/매수우세 + 셀 ≠ 비추 → 셀의 size 적용. base.md 작성 또는 컨센 확인 필수.",
  },
  {
    no: 5,
    title: "손절선 -3% 이내 → 최상단 ⚠️ 경고",
    body: "abs((현재가 - 손절가) / 현재가 × 100) < 3% → daily 보고서 최상단 경고 박스. \"즉시 결정 필요\".",
  },
  {
    no: 6,
    title: "평단 ±2% → 손익분기 구간",
    body: "abs(수익률) < 2% → \"손익분기 — 트레일링 스탑 점검\". 추가 매수/매도 모두 신중.",
  },
];

export type ReturnBucket = "+30%+" | "+15~30%" | "+5~15%" | "-5~+5%" | "-5~-10%" | "-10%+";
export type VerdictTone = "buy" | "neutral" | "sell";

export interface ActionMatrixCell {
  bucket: ReturnBucket;
  buy: string;
  neutral: string;
  sell: string;
}

export const ACTION_MATRIX: ActionMatrixCell[] = [
  { bucket: "+30%+", buy: "트레일링 스탑 타이트화", neutral: "부분 익절 (1/3)", sell: "즉시 부분 익절 (1/2)" },
  { bucket: "+15~30%", buy: "홀딩", neutral: "트레일링 스탑", sell: "부분 익절 (1/3)" },
  { bucket: "+5~15%", buy: "피라미딩 검토", neutral: "홀딩", sell: "트레일링 스탑 점검" },
  { bucket: "-5~+5%", buy: "1차 진입 검토", neutral: "손익분기 — 결정 보류", sell: "본전컷 검토" },
  { bucket: "-5~-10%", buy: "추가 진입 신중", neutral: "손절 검토", sell: "즉시 손절" },
  { bucket: "-10%+", buy: "❌ 추가 매수 금지", neutral: "즉시 손절", sell: "즉시 손절" },
];

export interface StopStage {
  stage: "경고선" | "기준선" | "손절선";
  ratio: string;
  action: string;
  example: string;
  atrExample: string;
}

export const STOP_STAGES: StopStage[] = [
  { stage: "경고선", ratio: "셀 손절폭 × 50%", action: "관망", example: "A급 normal (-10%) → -5%", atrExample: "extreme → ATR×1" },
  { stage: "기준선", ratio: "셀 손절폭 × 75%", action: "1/3 매도", example: "A급 normal → -7.5%", atrExample: "extreme → ATR×1.5" },
  { stage: "손절선", ratio: "셀 손절폭 × 100%", action: "잔여 전량", example: "A급 normal → -10%", atrExample: "extreme → ATR×2" },
];

export const SPLIT_PROFIT_RULE = [
  "1차 목표 도달 → 1/3 매도",
  "2차 목표 도달 → 추가 1/3 매도",
  "3차 목표 또는 트레일링 스탑까지 → 잔여 1/3 보유",
];

export const SPLIT_PROFIT_REASON =
  "W17 회고 \"효성 4/23 익절 후 +₩330k 추가 상승 놓침\" 사례. 변동성×재무 셀의 피라미딩 단계 = 익절 단계 (대칭).";

export const PRE_EXECUTION_CHECKLIST = [
  "check_concentration → 25% 룰 통과",
  "예수금 충분 (currency 기준)",
  "실적 D-7 이내면 손절선 타이트화",
  "최근 외인/기관 수급 톤 (analyze_flow)",
  "동일 섹터 보유 총합 (portfolio_correlation)",
  "W17 회고 룰 (rule_win_rates) — 승률 < 50% 룰은 추가 검증",
  "변동성×재무 셀 사이즈 적용",
  "집행 후 record_trade 호출 (positions 자동 재계산)",
  "필요 시 propose_watch_levels(persist=True) 로 감시 레벨 자동 생성",
];
