import type { Dim, Timeframe, WeightSource } from "@/types/api";

type TremorColor =
  | "blue"
  | "emerald"
  | "amber"
  | "red"
  | "gray"
  | "violet"
  | "slate"
  | "indigo"
  | "rose";

export const TIMEFRAME_LABEL: Record<Timeframe, string> = {
  "day-trade": "데이트레이드",
  swing: "스윙",
  "long-term": "장기",
  momentum: "모멘텀",
};

export const DIM_LABEL: Record<Dim, string> = {
  재무: "재무",
  산업: "산업",
  경제: "경제",
  기술: "기술",
  밸류에이션: "밸류에이션",
};

export const DIM_DESCRIPTION: Record<Dim, string> = {
  재무: "PER/PBR/ROE/영업이익률·재무 건전성",
  산업: "업종 점수·테마 모멘텀·산업 사이클",
  경제: "거시 환경(금리·환율·시장 국면)",
  기술: "차트 패턴·이동평균·시그널·모멘텀 지표",
  밸류에이션: "Fair Value·애널 컨센서스 대비 적정성",
};

/**
 * KR 4단계 + US 5단계 라벨이 모두 같은 한글 라벨로 들어옴.
 * "강한 상승장 / 상승장 / 전환기 / 하락장" 외에 오류 케이스도 처리.
 */
export const REGIME_COLOR: Record<string, TremorColor> = {
  "강한 상승장": "emerald",
  상승장: "blue",
  전환기: "amber",
  하락장: "red",
  오류: "gray",
};

export const WEIGHT_SOURCE_LABEL: Record<WeightSource, string> = {
  default: "기본값",
  user: "사용자",
  claude: "Claude",
  backtest: "백테스트",
};

export const WEIGHT_SOURCE_COLOR: Record<WeightSource, TremorColor> = {
  default: "slate",
  user: "blue",
  claude: "violet",
  backtest: "emerald",
};

export const TIMEFRAME_OPTIONS: Timeframe[] = [
  "day-trade",
  "swing",
  "long-term",
  "momentum",
];

export const DIM_ORDER: Dim[] = ["재무", "산업", "경제", "기술", "밸류에이션"];
