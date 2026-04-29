/**
 * 분석 모듈 정적 카탈로그 — server/analysis/*.py 16개.
 * docstring 자동 추출은 v16+ 보류, 현재는 수기 정리.
 */

export type ModuleTag = "technical" | "fundamental" | "portfolio" | "macro";

export interface AnalysisModule {
  id: string;
  name_ko: string;
  name_en: string;
  summary: string;
  description: string;
  inputs: string[];
  outputs: string[];
  mcp_tools: string[];
  db_tables: string[];
  tags: ModuleTag[];
  notes?: string;
}

export const ANALYSIS_MODULES: AnalysisModule[] = [
  {
    id: "indicators",
    name_ko: "기술 지표",
    name_en: "indicators",
    summary: "RSI·MACD·볼린저·이동평균 등 12개 기술 지표 계산.",
    description:
      "OHLCV 시계열에서 단·중·장기 추세, 모멘텀, 변동성 지표를 산출. compute_indicators MCP 툴이 일일 리포트 작성 시 자동 호출. rsi14 등 일부 지표는 stock_daily 컬럼에 저장.",
    inputs: ["stock_daily.OHLCV", "lookback_days"],
    outputs: ["RSI14", "MACD", "SMA(20/60/120)", "BB", "ADX", "Stoch", "ATR", "전환선/기준선"],
    mcp_tools: ["compute_indicators"],
    db_tables: ["stock_daily"],
    tags: ["technical"],
    notes: "rsi14 NULL 버그 follow-up 존재 (indicators.py 컬럼명 매핑 수정 필요)",
  },
  {
    id: "signals",
    name_ko: "트레이딩 시그널",
    name_en: "signals",
    summary: "12개 시그널 + 차트 패턴 인식 (골든크로스·이중바닥 등).",
    description:
      "지표 + 가격 패턴을 결합해 매수/매도/관찰 시그널을 생성. compute_signals MCP 툴이 일일 verdict 산출에 사용.",
    inputs: ["indicators 결과", "OHLCV"],
    outputs: ["signals[]", "verdict 후보", "패턴 라벨"],
    mcp_tools: ["compute_signals"],
    db_tables: ["stock_daily"],
    tags: ["technical"],
  },
  {
    id: "financials",
    name_ko: "재무 분석",
    name_en: "financials",
    summary: "PER/PBR/ROE/매출성장·영업이익률·실적 서프라이즈.",
    description:
      "재무 비율, YoY 성장, 컨센서스 대비 서프라이즈를 계산. stock_base 의 financial_score 기여. 신규 분석으로 v6 Step 4 에 추가.",
    inputs: ["DART 재무제표", "consensus.estimates"],
    outputs: ["재무비율", "성장률", "서프라이즈%", "재무 점수"],
    mcp_tools: ["compute_financials", "detect_earnings_surprise_tool"],
    db_tables: ["stock_base", "analyst_reports"],
    tags: ["fundamental"],
  },
  {
    id: "momentum",
    name_ko: "모멘텀 랭킹",
    name_en: "momentum",
    summary: "크로스섹셔널 6차원 모멘텀 스코어·랭킹 — stock-research 의 모멘텀 차원으로 흡수 (v17).",
    description:
      "전체 유니버스(또는 보유) 종목을 상대평가해 모멘텀 점수 부여. v17 부터 stock-momentum skill 폐지, stock-research 의 6차원 분석 (모멘텀 차원) + base-economy 의 시장 국면으로 흡수됨. Dual Momentum 시그널은 detect_market_regime 으로 통합.",
    inputs: ["전체 종목 OHLCV", "lookback_months"],
    outputs: ["모멘텀 스코어", "상대 랭킹", "(시장 국면 판정은 regime 모듈)"],
    mcp_tools: ["rank_momentum", "rank_momentum_wide"],
    db_tables: ["stock_daily"],
    tags: ["technical", "portfolio"],
    notes: "v17 에서 stock-momentum skill DEPRECATED (2026-04-27)",
  },
  {
    id: "regime",
    name_ko: "시장 국면",
    name_en: "regime",
    summary: "KOSPI/SPY 4~5조건 검증으로 시장 국면 판정.",
    description:
      "Mebane Faber 10개월 MA + 200일선 + 단기 모멘텀 + (US: VIX·Yield curve / KR: 신고가 비율) 결합. 모멘텀 전략 가동/중단 스위치.",
    inputs: ["KOSPI/SPY OHLCV", "VIX", "Yield curve"],
    outputs: ["국면 라벨", "통과 조건", "모멘텀_가동 bool"],
    mcp_tools: ["detect_market_regime"],
    db_tables: [],
    tags: ["macro"],
    notes: "캐싱 없음 — 매 호출마다 5~30초 외부 fetch (issue #1)",
  },
  {
    id: "concentration",
    name_ko: "포지션 집중도",
    name_en: "concentration",
    summary: "단일 종목/섹터 비중 상한 검증·포지션 플래너.",
    description:
      "현재 보유 비중을 임계치(KR 25%, US 35%)와 비교해 critical/warning 경고. 신규 진입 시 비중 시뮬레이션.",
    inputs: ["positions(Active)", "cash", "임계치"],
    outputs: ["alerts[]", "weights%", "신규 진입 시 시뮬"],
    mcp_tools: ["check_concentration", "detect_portfolio_concentration", "propose_position_params"],
    db_tables: ["positions", "cash"],
    tags: ["portfolio"],
  },
  {
    id: "scoring",
    name_ko: "스코어링",
    name_en: "scoring",
    summary: "5차원 × 4타임프레임 가중평균 종합 점수.",
    description:
      "재무·산업·경제·기술·밸류에이션 5차원 점수 × score_weight_defaults / overrides 가중치로 종합 점수 산출. stock_base.total_score 가 결과.",
    inputs: ["5차원 부분 점수", "score_weight 테이블"],
    outputs: ["total_score 0~100", "grade(Premium/Standard/Cautious/Defensive)"],
    mcp_tools: ["compute_score", "get_applied_weights", "override_score_weights", "reset_score_weights"],
    db_tables: ["stock_base", "score_weight_defaults", "score_weight_overrides"],
    tags: ["fundamental", "portfolio"],
  },
  {
    id: "backtest",
    name_ko: "백테스트",
    name_en: "backtest",
    summary: "전략별 종목 승률·로그 (현재 raw markdown 캐시).",
    description:
      "과거 OHLCV 에 시그널·전략 적용해 승률 계산. 결과는 backtest_cache.result JSONB 에 raw_md 로 보관. 향후 win_rate/sharpe 컬럼화 예정.",
    inputs: ["과거 OHLCV", "전략 정의"],
    outputs: ["raw_md (현재)", "win_rate (예정)", "sharpe (예정)"],
    mcp_tools: [],
    db_tables: ["backtest_cache"],
    tags: ["technical"],
    notes: "현재 KR 5종만 캐시 — NVDA/GOOGL 미존재",
  },
  {
    id: "flow",
    name_ko: "수급 분석",
    name_en: "flow",
    summary: "기관/외국인/공매도 순매수·집중도 분석.",
    description:
      "기관·외국인·개인 순매수 z-score, 10일 이상거래, 공매도 잔고 추적. 수급 반전 시그널 감지.",
    inputs: ["KIS investor_flow", "KRX 공매도"],
    outputs: ["기관/외인 z-score", "이상거래", "공매도 잔고"],
    mcp_tools: ["analyze_flow"],
    db_tables: ["stock_daily"],
    tags: ["technical"],
  },
  {
    id: "events",
    name_ko: "이벤트 감지",
    name_en: "events",
    summary: "실적 D-N, 52주 신고가, 등급 변경, 집중도 경고.",
    description:
      "캘린더 기반 어닝 D-N 카운트다운, 52w 돌파 감지, analyst rating 변동, 포트폴리오 집중도 알림 통합.",
    inputs: ["earnings_calendar", "OHLCV", "analyst_reports", "positions"],
    outputs: ["events[]", "alerts[]"],
    mcp_tools: ["detect_events"],
    db_tables: ["analyst_reports", "stock_daily", "positions"],
    tags: ["technical", "fundamental", "portfolio"],
  },
  {
    id: "correlation",
    name_ko: "포트 상관",
    name_en: "correlation",
    summary: "보유 종목 간 상관계수·effective holdings·diversification.",
    description:
      "포트폴리오 종목 간 페어 상관, 실효 종목 수(effective N), 다양성 점수. 상관 > 0.6 페어 경고.",
    inputs: ["positions OHLCV", "lookback_days"],
    outputs: ["pair_corr matrix", "effective_n", "diversification_score"],
    mcp_tools: ["portfolio_correlation"],
    db_tables: ["positions", "stock_daily"],
    tags: ["portfolio"],
  },
  {
    id: "volatility",
    name_ko: "변동성",
    name_en: "volatility",
    summary: "Realized vol·Parkinson·베타·drawdown·regime.",
    description:
      "여러 측정법(historical/Parkinson/Garman-Klass)으로 변동성, 시장 베타, 최대 drawdown, vol regime(저변동/고변동) 판정.",
    inputs: ["OHLCV", "벤치마크"],
    outputs: ["realized_vol", "beta", "max_dd", "vol_regime"],
    mcp_tools: ["analyze_volatility"],
    db_tables: ["stock_daily"],
    tags: ["technical", "portfolio"],
  },
  {
    id: "sensitivity",
    name_ko: "민감도",
    name_en: "sensitivity",
    summary: "금리·환율·유가·VIX 베타로 거시 노출 측정.",
    description:
      "각 거시 변수에 대한 종목 수익률 회귀 계수. 금리 인상 시 영향, 환율 변동 시 영향 등 시나리오 분석.",
    inputs: ["종목 수익률", "거시 시계열(FRED)"],
    outputs: ["베타_금리", "베타_환율", "베타_유가", "베타_VIX"],
    mcp_tools: [],
    db_tables: ["stock_daily", "macro_series"],
    tags: ["macro"],
  },
  {
    id: "consensus",
    name_ko: "애널 컨센서스",
    name_en: "consensus",
    summary: "목표가 momentum·rating wave·beat history.",
    description:
      "최근 N개 애널 리포트의 목표가 변화 추세, 등급 변경 흐름, 분기별 어닝 beat/miss 히스토리 집계.",
    inputs: ["analyst_reports", "earnings_calendar"],
    outputs: ["target_momentum", "rating_wave", "beat_history"],
    mcp_tools: ["analyze_consensus_trend", "record_analyst_report", "list_analyst_reports", "get_analyst_consensus"],
    db_tables: ["analyst_reports"],
    tags: ["fundamental"],
  },
  {
    id: "valuation",
    name_ko: "밸류에이션",
    name_en: "valuation",
    summary: "DCF·Comps·Reverse DCF 적정가 산출.",
    description:
      "Forward DCF, 동종 비교(Comps), 시장가에 내재된 성장률을 역산하는 Reverse DCF. stock_base.fair_value_min/avg/max 출력.",
    inputs: ["재무 추정", "WACC", "성장률"],
    outputs: ["fair_value 밴드", "implied_growth"],
    mcp_tools: [],
    db_tables: ["stock_base"],
    tags: ["fundamental"],
  },
  {
    id: "chart_analysis",
    name_ko: "차트 패턴",
    name_en: "chart_analysis",
    summary: "이중바닥·삼각수렴·헤드앤숄더 등 패턴 인식.",
    description:
      "OHLCV 의 swing high/low 추출 후 룰 기반 패턴 매칭. 신뢰도 점수 + 목표가 추정 함께 반환.",
    inputs: ["OHLCV"],
    outputs: ["pattern label", "confidence", "implied_target"],
    mcp_tools: [],
    db_tables: ["stock_daily"],
    tags: ["technical"],
  },
];

export const ALL_TAGS: Array<{ key: ModuleTag | "all"; label: string }> = [
  { key: "all", label: "전체" },
  { key: "technical", label: "기술" },
  { key: "fundamental", label: "재무" },
  { key: "portfolio", label: "포트" },
  { key: "macro", label: "거시" },
];

export const TAG_LABEL: Record<ModuleTag, string> = {
  technical: "기술",
  fundamental: "재무",
  portfolio: "포트",
  macro: "거시",
};
