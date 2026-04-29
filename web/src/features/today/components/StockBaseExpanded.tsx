import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { useStockBase } from "@/hooks/useStockBase";
import type { Market, StockBaseOut } from "@/types/api";
import { DailyReportContent } from "./DailyReportContent";
import { FairValueCard } from "./FairValueCard";
import { StockScoreCard } from "./StockScoreCard";
import { ValuationCard } from "./ValuationCard";

interface StockBaseExpandedProps {
  code: string;
  market: Market | null;
  dailyContent: string | null;
}

export const StockBaseExpanded = ({
  code,
  market,
  dailyContent,
}: StockBaseExpandedProps) => {
  const baseQuery = useStockBase(code);
  const base = baseQuery.data ?? null;

  return (
    <div className="space-y-4">
      {baseQuery.isLoading ? (
        <LoadingSkeleton rows={2} />
      ) : baseQuery.error ? (
        <ErrorNotice error={baseQuery.error} title={`${code} 기본분석 조회 실패`} />
      ) : base ? (
        <BaseCardsGrid base={base} market={market} />
      ) : (
        <p className="text-xs text-gray-400">기본 분석 레포트가 아직 없습니다.</p>
      )}

      <section>
        <h4 className="text-sm font-semibold text-gray-700">오늘 리포트 (Daily)</h4>
        <div className="mt-2">
          <DailyReportContent
            content={dailyContent}
            emptyPlaceholder="오늘 리포트가 없습니다."
          />
        </div>
      </section>

      {base && <BaseDetailsDetails base={base} />}
    </div>
  );
};

const BaseCardsGrid = ({
  base,
  market,
}: {
  base: StockBaseOut;
  market: Market | null;
}) => (
  <div className="grid gap-3 md:grid-cols-3">
    <StockScoreCard
      totalScore={base.total_score}
      grade={base.grade}
      financialScore={base.financial_score}
      industryScore={base.industry_score}
      economyScore={base.economy_score}
    />
    <FairValueCard
      fairMin={base.fair_value_min}
      fairAvg={base.fair_value_avg}
      fairMax={base.fair_value_max}
      analystAvg={base.analyst_target_avg}
      analystMax={base.analyst_target_max}
      consensusCount={base.analyst_consensus_count}
      market={market}
    />
    <ValuationCard
      per={base.per}
      pbr={base.pbr}
      psr={base.psr}
      roe={base.roe}
      opMargin={base.op_margin}
    />
  </div>
);

const BaseDetailsDetails = ({ base }: { base: StockBaseOut }) => {
  const hasAny = base.narrative || base.risks || base.scenarios || base.content;
  if (!hasAny) return null;
  return (
    <details className="rounded-md border border-gray-100 bg-gray-50 p-3">
      <summary className="cursor-pointer text-sm font-medium text-gray-700">
        기본 분석 전문 (Base)
      </summary>
      <div className="mt-3 space-y-3">
        {base.narrative && (
          <section>
            <h5 className="text-xs font-semibold text-gray-600">내러티브</h5>
            <p className="mt-1 whitespace-pre-line text-sm text-gray-700">
              {base.narrative}
            </p>
          </section>
        )}
        {base.risks && (
          <section>
            <h5 className="text-xs font-semibold text-gray-600">리스크</h5>
            <p className="mt-1 whitespace-pre-line text-sm text-gray-700">
              {base.risks}
            </p>
          </section>
        )}
        {base.scenarios && (
          <section>
            <h5 className="text-xs font-semibold text-gray-600">시나리오</h5>
            <p className="mt-1 whitespace-pre-line text-sm text-gray-700">
              {base.scenarios}
            </p>
          </section>
        )}
        {base.content && (
          <section className="border-t border-gray-200 pt-3">
            <DailyReportContent content={base.content} />
          </section>
        )}
        {base.updated_at && (
          <p className="text-xs text-gray-400">
            base 업데이트 {new Date(base.updated_at).toLocaleDateString("ko-KR")}
          </p>
        )}
      </div>
    </details>
  );
};
