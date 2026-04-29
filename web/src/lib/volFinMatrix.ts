/**
 * v17 핵심 — 변동성 × 재무 헬스 12셀 매트릭스.
 * stock/references/scoring-weights.md 인용.
 */

export type FinTier = "A" | "B" | "C" | "D";
export type VolTier = "normal" | "high" | "extreme";

export interface MatrixCell {
  finTier: FinTier;
  volTier: VolTier;
  size: "풀" | "70%" | "50%" | "30%" | "비추";
  pyramiding: number;
  stopPct: number | null;
  stopMethod: string;
  isAvoid: boolean;
}

export const FIN_TIERS: Array<{ tier: FinTier; range: string; meaning: string }> = [
  { tier: "A", range: "80-100", meaning: "흑자 우량 · ROE 15%+ · 부채 적정 · 경고 0" },
  { tier: "B", range: "60-79", meaning: "흑자 보통 · ROE 5-15% · 부채 양호" },
  { tier: "C", range: "40-59", meaning: "소폭 흑자 / 적자 진입기 / 이익질 의심" },
  { tier: "D", range: "<40", meaning: "적자 지속 · 부채 과다 · 경고 다수" },
];

export const VOL_TIERS: Array<{ tier: VolTier; range: string; meaning: string }> = [
  { tier: "normal", range: "<30%", meaning: "안정" },
  { tier: "high", range: "30~50%", meaning: "단기 변동 큼" },
  { tier: "extreme", range: "50%+", meaning: "전구 종목 · 손절 타이트 필수" },
];

export const VOLFIN_MATRIX: MatrixCell[] = [
  { finTier: "A", volTier: "normal", size: "풀", pyramiding: 3, stopPct: -10, stopMethod: "%", isAvoid: false },
  { finTier: "A", volTier: "high", size: "풀", pyramiding: 2, stopPct: -8, stopMethod: "%", isAvoid: false },
  { finTier: "A", volTier: "extreme", size: "70%", pyramiding: 1, stopPct: -6, stopMethod: "ATR×2", isAvoid: false },

  { finTier: "B", volTier: "normal", size: "풀", pyramiding: 2, stopPct: -8, stopMethod: "%", isAvoid: false },
  { finTier: "B", volTier: "high", size: "70%", pyramiding: 1, stopPct: -7, stopMethod: "%", isAvoid: false },
  { finTier: "B", volTier: "extreme", size: "50%", pyramiding: 0, stopPct: -5, stopMethod: "ATR×1.5", isAvoid: false },

  { finTier: "C", volTier: "normal", size: "70%", pyramiding: 1, stopPct: -7, stopMethod: "%", isAvoid: false },
  { finTier: "C", volTier: "high", size: "50%", pyramiding: 1, stopPct: -6, stopMethod: "%", isAvoid: false },
  { finTier: "C", volTier: "extreme", size: "30%", pyramiding: 0, stopPct: -5, stopMethod: "ATR×1", isAvoid: false },

  { finTier: "D", volTier: "normal", size: "50%", pyramiding: 0, stopPct: -6, stopMethod: "%", isAvoid: false },
  { finTier: "D", volTier: "high", size: "30%", pyramiding: 0, stopPct: -5, stopMethod: "%", isAvoid: false },
  { finTier: "D", volTier: "extreme", size: "비추", pyramiding: 0, stopPct: null, stopMethod: "—", isAvoid: true },
];

export const lookupCell = (fin: FinTier, vol: VolTier): MatrixCell | undefined =>
  VOLFIN_MATRIX.find((c) => c.finTier === fin && c.volTier === vol);

export const SIZE_DESCRIPTION = {
  풀: "계획 자금 100% 한 번에 또는 분할 진입",
  "70%": "70% 분할 진입 (1차만, 추가는 트리거 충족 시)",
  "50%": "50% 분할 진입",
  "30%": "30% 진입 — 위험·보상 비율 박함",
  비추: "위험·보상 비율 부적합 — 진입 보류 권장",
} as const;

export const PYRAMIDING_DESCRIPTION = {
  3: "ATR×1 / ATR×2 / ATR×3 돌파 시 추가 매수",
  2: "ATR×1 / ATR×2",
  1: "ATR×1.5 만 추가",
  0: "추가 매수 없음 (1회 진입만)",
} as const;
