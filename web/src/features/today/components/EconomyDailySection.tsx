import { Card } from "@tremor/react";
import type { EconomyDailyOut } from "@/types/api";
import { DailyReportContent } from "./DailyReportContent";

interface EconomyDailySectionProps {
  daily: EconomyDailyOut | null;
}

const formatBigNum = (v: number | null | undefined): string => {
  if (v == null) return "-";
  return v.toLocaleString("ko-KR");
};

export const EconomyDailySection = ({ daily }: EconomyDailySectionProps) => {
  if (!daily) {
    return (
      <Card>
        <p className="text-sm text-gray-500">
          해당 시점 경제 지표(economy_daily)가 아직 수집되지 않았습니다.
        </p>
      </Card>
    );
  }

  const indexEntries = Object.entries(daily.index_values ?? {});

  return (
    <Card>
      <div className="flex items-baseline justify-between">
        <h3 className="text-base font-semibold text-gray-900">일일 지표 (Daily)</h3>
        <span className="text-xs text-gray-500">{daily.date}</span>
      </div>
      {indexEntries.length > 0 && (
        <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {indexEntries.map(([key, value]) => (
            <div key={key} className="rounded-md border border-gray-100 bg-gray-50 p-2">
              <dt className="text-xs text-gray-500">{key}</dt>
              <dd className="mt-0.5 text-sm font-medium text-gray-800 tabular-nums">
                {String(value)}
              </dd>
            </div>
          ))}
        </dl>
      )}
      <div className="mt-3 grid grid-cols-2 gap-3">
        <div className="rounded-md border border-gray-100 p-2">
          <p className="text-xs text-gray-500">외국인 순매수</p>
          <p className="mt-0.5 text-sm font-medium text-gray-800 tabular-nums">
            {formatBigNum(daily.foreign_net)}
          </p>
        </div>
        <div className="rounded-md border border-gray-100 p-2">
          <p className="text-xs text-gray-500">기관 순매수</p>
          <p className="mt-0.5 text-sm font-medium text-gray-800 tabular-nums">
            {formatBigNum(daily.institution_net)}
          </p>
        </div>
      </div>
      {daily.events.length > 0 && (
        <div className="mt-3">
          <h4 className="text-sm font-medium text-gray-700">이벤트</h4>
          <ul className="mt-1 list-disc pl-5 text-sm text-gray-700">
            {daily.events.map((e, idx) => (
              <li key={idx}>{JSON.stringify(e)}</li>
            ))}
          </ul>
        </div>
      )}
      {daily.content && (
        <div className="mt-4 border-t border-gray-100 pt-3">
          <DailyReportContent content={daily.content} />
        </div>
      )}
    </Card>
  );
};
