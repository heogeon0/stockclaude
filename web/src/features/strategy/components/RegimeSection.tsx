import { Badge, Card, ProgressBar } from "@tremor/react";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { useRegime } from "@/hooks/useRegime";
import { REGIME_COLOR } from "@/lib/strategyConstants";
import type { Market, RegimeOut } from "@/types/api";

export const RegimeSection = () => (
  <Card>
    <header className="mb-4">
      <h3 className="text-lg font-semibold text-gray-900">시장 국면 (Live)</h3>
      <p className="mt-1 text-sm text-gray-500">
        KOSPI / SPY 지수 기반. 외부 fetch 5~30초 소요 — 5분 캐시 적용.
      </p>
    </header>
    <div className="grid gap-3 md:grid-cols-2">
      <RegimeCard market="kr" />
      <RegimeCard market="us" />
    </div>
  </Card>
);

const MARKET_LABEL_FULL: Record<Market, string> = {
  kr: "KR (KOSPI 4조건)",
  us: "US (SPY 5조건)",
};

const RegimeCard = ({ market }: { market: Market }) => {
  const query = useRegime(market);

  if (query.isLoading) {
    return (
      <div className="rounded-md border border-gray-100 bg-gray-50 p-4">
        <p className="mb-2 text-sm font-medium text-gray-700">
          {MARKET_LABEL_FULL[market]} — 계산 중...
        </p>
        <LoadingSkeleton rows={3} />
      </div>
    );
  }
  if (query.error) {
    return <ErrorNotice error={query.error} title={`${MARKET_LABEL_FULL[market]} 조회 실패`} />;
  }

  const data = query.data;
  if (!data) return null;
  return <RegimeBody data={data} />;
};

const RegimeBody = ({ data }: { data: RegimeOut }) => {
  const color = REGIME_COLOR[data.label] ?? "gray";
  const computedAt = new Date(data.computed_at).toLocaleString("ko-KR");
  const ratio =
    data.total_conditions > 0
      ? (data.conditions_met / data.total_conditions) * 100
      : 0;

  return (
    <div className="rounded-md border border-gray-100 p-4">
      <div className="flex items-baseline justify-between">
        <p className="text-sm font-medium text-gray-700">
          {MARKET_LABEL_FULL[data.market]}
        </p>
        <span className="text-xs text-gray-400">{computedAt}</span>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <Badge color={color}>{data.label || "—"}</Badge>
        {data.momentum_on ? (
          <span className="text-xs text-emerald-600">모멘텀 가동</span>
        ) : (
          <span className="text-xs text-amber-600">모멘텀 중단 권장</span>
        )}
      </div>

      <div className="mt-3">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>조건 통과</span>
          <span className="tabular-nums">
            {data.conditions_met} / {data.total_conditions}
          </span>
        </div>
        <ProgressBar value={ratio} color="blue" className="mt-1" />
      </div>

      {Object.keys(data.checks).length > 0 && (
        <ul className="mt-3 space-y-1 text-xs">
          {Object.entries(data.checks).map(([key, ok]) => (
            <li key={key} className="flex items-center gap-2">
              <span className={ok ? "text-emerald-600" : "text-gray-400"}>
                {ok ? "✓" : "·"}
              </span>
              <span className="text-gray-700">{key.replace(/_/g, " ")}</span>
            </li>
          ))}
        </ul>
      )}

      {data.interpretation && (
        <p className="mt-3 rounded bg-gray-50 px-3 py-2 text-xs text-gray-600">
          {data.interpretation}
        </p>
      )}

      {data.error && (
        <p className="mt-3 rounded bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {data.error}
        </p>
      )}
    </div>
  );
};
