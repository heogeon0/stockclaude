import { Card } from "@tremor/react";
import type { WinRateStats } from "@/types/api";

const LOW_WIN_THRESHOLD = 50;

interface Props {
  winRate: Record<string, WinRateStats>;
}

export const WinRateCard = ({ winRate }: Props) => {
  const entries = Object.entries(winRate);
  if (entries.length === 0) {
    return (
      <Card>
        <h4 className="text-sm font-semibold text-gray-700">룰별 승률</h4>
        <p className="mt-2 text-xs text-gray-400">데이터 없음</p>
      </Card>
    );
  }

  return (
    <Card>
      <h4 className="text-sm font-semibold text-gray-700">룰별 승률</h4>
      <table className="mt-3 w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100 text-left text-xs text-gray-500">
            <th className="pb-2">룰</th>
            <th className="pb-2 text-right">시도</th>
            <th className="pb-2 text-right">승</th>
            <th className="pb-2 text-right">승률</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([rule, stats]) => {
            const isLow = stats.pct < LOW_WIN_THRESHOLD;
            return (
              <tr key={rule} className="border-b border-gray-50">
                <td className="py-1.5 text-xs text-gray-800">{rule}</td>
                <td className="py-1.5 text-right text-xs tabular-nums text-gray-600">
                  {stats.tries}
                </td>
                <td className="py-1.5 text-right text-xs tabular-nums text-gray-600">
                  {stats.wins}
                </td>
                <td
                  className={`py-1.5 text-right text-xs font-semibold tabular-nums ${
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
      <p className="mt-2 text-[10px] text-gray-400">
        승률 &lt; {LOW_WIN_THRESHOLD}% 룰은 빨강 — 추가 검증 대상
      </p>
    </Card>
  );
};
