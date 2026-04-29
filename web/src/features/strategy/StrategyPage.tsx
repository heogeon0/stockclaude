import { AnalysisModulesSection } from "./components/AnalysisModulesSection";
import { BacktestSection } from "./components/BacktestSection";
import { BaseExpirySection } from "./components/BaseExpirySection";
import { PositionActionRulesSection } from "./components/PositionActionRulesSection";
import { RegimeSection } from "./components/RegimeSection";
import { RuleEvaluationsCard } from "./components/RuleEvaluationsCard";
import { Signals12Section } from "./components/Signals12Section";
import { VolFinMatrixSection } from "./components/VolFinMatrixSection";
import { WeightsSection } from "./components/WeightsSection";
import { WorkflowSection } from "./components/WorkflowSection";

export const StrategyPage = () => (
  <div className="space-y-6">
    <header>
      <h2 className="text-2xl font-semibold text-gray-900">전략·로직</h2>
      <p className="mt-1 text-sm text-gray-500">
        MCP 서버가 어떻게 판단하는가 — v17 변동성×재무 매트릭스 기반.
        스킬 흐름·base 만기·12셀 매트릭스·시장 국면·가중치·시그널·포지션 룰·분석 모듈·백테스트.
      </p>
    </header>

    <WorkflowSection />
    <BaseExpirySection />
    <VolFinMatrixSection />
    <RegimeSection />
    <WeightsSection />
    <Signals12Section />
    <PositionActionRulesSection />
    <RuleEvaluationsCard />
    <AnalysisModulesSection />
    <BacktestSection />
  </div>
);
