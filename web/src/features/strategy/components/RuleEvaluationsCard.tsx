import { Card } from "@tremor/react";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { useWeeklyContext } from "@/hooks/useWeeklyContext";

const LOW_WIN_THRESHOLD = 50;
const ROLLING_WEEKS = 4;

export const RuleEvaluationsCard = () => {
  const query = useWeeklyContext(ROLLING_WEEKS);

  return (
    <Card>
      <header className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          룰 평가 (최근 {ROLLING_WEEKS}주 rolling)
        </h3>
        <p className="mt-1 text-sm text-gray-500">
          `weekly_reviews.win_rate` 의 룰별 승률을 합산. 승률 &lt; {LOW_WIN_THRESHOLD}% 룰은 추가 검증 대상.
          매매 집행 전 체크리스트의 "W17 회고 룰" 라이브 피드백.
        </p>
      </header>

      {query.isLoading && <LoadingSkeleton rows={3} />}
      {query.error && <ErrorNotice error={query.error} title="회고 컨텍스트 조회 실패" />}

      {query.data && (() => {
        const rs = query.data.rolling_stats;
        const ruleEntries = Object.entries(rs.rule_win_rates);

        if (rs.weeks_count === 0 || ruleEntries.length === 0) {
          return (
            <p className="rounded bg-gray-50 px-3 py-2 text-xs text-gray-500">
              회고 데이터 없음 — `save_weekly_review` MCP 툴로 첫 회고를 작성하세요.
            </p>
          );
        }

        return (
          <>
            <div className="mb-3 flex flex-wrap gap-3 text-xs text-gray-600">
              <span>
                집계 주차: <span className="font-semibold">{rs.weeks_count}</span>
              </span>
              <span>
                총 거래: <span className="font-semibold tabular-nums">{rs.trade_count_total}</span>건
              </span>
              <span>
                실현 합계 (KR): <span className="font-semibold tabular-nums">
                  {rs.total_realized_pnl_kr > 0 ? "+" : ""}
                  ₩{rs.total_realized_pnl_kr.toLocaleString("ko-KR")}
                </span>
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse text-sm">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">
                      룰
                    </th>
                    <th className="border border-gray-200 px-3 py-2 text-right text-xs font-semibold text-gray-700">
                      시도
                    </th>
                    <th className="border border-gray-200 px-3 py-2 text-right text-xs font-semibold text-gray-700">
                      승
                    </th>
                    <th className="border border-gray-200 px-3 py-2 text-right text-xs font-semibold text-gray-700">
                      승률
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {ruleEntries.map(([rule, stats]) => {
                    const isLow = stats.pct < LOW_WIN_THRESHOLD;
                    return (
                      <tr key={rule}>
                        <td className="border border-gray-200 px-3 py-2 text-xs text-gray-800">
                          {rule}
                        </td>
                        <td className="border border-gray-200 px-3 py-2 text-right text-xs tabular-nums text-gray-700">
                          {stats.tries}
                        </td>
                        <td className="border border-gray-200 px-3 py-2 text-right text-xs tabular-nums text-gray-700">
                          {stats.wins}
                        </td>
                        <td
                          className={`border border-gray-200 px-3 py-2 text-right text-xs font-semibold tabular-nums ${
                            isLow ? "text-red-700" : "text-emerald-700"
                          }`}
                        >
                          {stats.pct.toFixed(1)}%
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs text-blue-700">
              <a href="/review" className="underline hover:text-blue-900">
                전체 주간 회고 →
              </a>
            </p>
          </>
        );
      })()}
    </Card>
  );
};
