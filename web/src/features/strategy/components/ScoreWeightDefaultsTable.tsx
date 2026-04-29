import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@tremor/react";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { useScoreWeightsDefaults } from "@/hooks/useScoreWeightsDefaults";
import {
  DIM_DESCRIPTION,
  DIM_LABEL,
  DIM_ORDER,
  TIMEFRAME_LABEL,
  TIMEFRAME_OPTIONS,
} from "@/lib/strategyConstants";
import { toNum } from "@/lib/decimal";
import type { Dim, Timeframe } from "@/types/api";

export const ScoreWeightDefaultsTable = () => {
  const query = useScoreWeightsDefaults();

  if (query.isLoading) return <LoadingSkeleton rows={4} />;
  if (query.error)
    return <ErrorNotice error={query.error} title="기본 가중치 조회 실패" />;

  const grid = buildGrid(query.data?.rows ?? []);

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHead>
          <TableRow>
            <TableHeaderCell>타임프레임</TableHeaderCell>
            {DIM_ORDER.map((dim) => (
              <TableHeaderCell key={dim} className="text-right">
                <span title={DIM_DESCRIPTION[dim]} className="cursor-help">
                  {DIM_LABEL[dim]}
                </span>
              </TableHeaderCell>
            ))}
            <TableHeaderCell className="text-right">합계</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {TIMEFRAME_OPTIONS.map((tf) => {
            const row = grid[tf];
            const sum = DIM_ORDER.reduce((s, d) => s + toNum(row?.[d]), 0);
            const isBaseline = tf === "swing";
            return (
              <TableRow key={tf} className={isBaseline ? "bg-amber-50/50" : ""}>
                <TableCell>
                  <span
                    className={`font-medium ${
                      isBaseline ? "text-amber-900" : "text-gray-900"
                    }`}
                  >
                    {TIMEFRAME_LABEL[tf]}
                  </span>
                  <span className="ml-2 text-xs text-gray-400">{tf}</span>
                  {isBaseline && (
                    <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">
                      v17 baseline
                    </span>
                  )}
                </TableCell>
                {DIM_ORDER.map((dim) => (
                  <TableCell key={dim} className="text-right tabular-nums">
                    {row?.[dim] != null ? `${(toNum(row[dim]!) * 100).toFixed(0)}%` : "-"}
                  </TableCell>
                ))}
                <TableCell className="text-right tabular-nums text-xs text-gray-500">
                  {(sum * 100).toFixed(0)}%
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
};

const buildGrid = (
  rows: Array<{ timeframe: Timeframe; dim: Dim; weight: string }>,
): Record<Timeframe, Partial<Record<Dim, string>>> => {
  const grid: Record<Timeframe, Partial<Record<Dim, string>>> = {
    "day-trade": {},
    swing: {},
    "long-term": {},
    momentum: {},
  };
  for (const r of rows) {
    grid[r.timeframe][r.dim] = r.weight;
  }
  return grid;
};
