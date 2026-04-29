import {
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@tremor/react";
import { VerdictBadge } from "./VerdictBadge";
import type { PerStockSummary, Verdict } from "@/types/api";

interface PerStockSummaryTableProps {
  rows: PerStockSummary[];
}

const formatNumber = (v: number | null | undefined, digits = 0): string => {
  if (v == null) return "-";
  return v.toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
};

const formatSignedPct = (v: number | null | undefined): string => {
  if (v == null) return "-";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
};

const pctColor = (v: number | null | undefined): string => {
  if (v == null) return "text-gray-500";
  if (v > 0) return "text-emerald-600";
  if (v < 0) return "text-red-600";
  return "text-gray-500";
};

export const PerStockSummaryTable = ({ rows }: PerStockSummaryTableProps) => {
  if (rows.length === 0) return null;
  return (
    <Card>
      <h3 className="mb-3 text-base font-semibold text-gray-900">종목별 요약</h3>
      <Table>
        <TableHead>
          <TableRow>
            <TableHeaderCell>종목</TableHeaderCell>
            <TableHeaderCell className="text-right">종가</TableHeaderCell>
            <TableHeaderCell className="text-right">등락</TableHeaderCell>
            <TableHeaderCell className="text-right">평가손익</TableHeaderCell>
            <TableHeaderCell>판정</TableHeaderCell>
            <TableHeaderCell>코멘트</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.code}>
              <TableCell>
                <div className="flex flex-col">
                  <span className="font-medium text-gray-900">
                    {r.name ?? r.code}
                  </span>
                  <span className="text-xs text-gray-400">{r.code}</span>
                </div>
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(r.close)}
              </TableCell>
              <TableCell className={`text-right tabular-nums ${pctColor(r.change_pct)}`}>
                {formatSignedPct(r.change_pct)}
              </TableCell>
              <TableCell className={`text-right tabular-nums ${pctColor(r.pnl_pct)}`}>
                {formatSignedPct(r.pnl_pct)}
              </TableCell>
              <TableCell>
                <VerdictBadge verdict={(r.verdict as Verdict | undefined) ?? null} />
              </TableCell>
              <TableCell className="max-w-[280px] text-xs text-gray-600">
                {r.note ?? "-"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
};
