import { Badge, Card } from "@tremor/react";
import { formatKRW, toNum } from "@/lib/decimal";
import type { RuleEvaluation } from "@/types/api";

interface Props {
  rows: RuleEvaluation[];
}

export const RuleEvaluationsTable = ({ rows }: Props) => {
  if (rows.length === 0) {
    return (
      <Card>
        <h4 className="text-sm font-semibold text-gray-700">룰 평가</h4>
        <p className="mt-2 text-xs text-gray-400">평가 데이터 없음</p>
      </Card>
    );
  }

  return (
    <Card>
      <h4 className="text-sm font-semibold text-gray-700">룰 평가</h4>
      <p className="mt-1 text-xs text-gray-500">
        실거래의 사전 결정 vs 사후 결과 — `smart` (좋은 결정) / `early` (성급) / 기타.
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr className="bg-gray-50">
              <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">
                룰
              </th>
              <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">
                종목
              </th>
              <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">
                평가
              </th>
              <th className="border border-gray-200 px-3 py-2 text-right text-xs font-semibold text-gray-700">
                forgone PnL
              </th>
              <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">
                메모
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const forgone = row.foregone_pnl;
              const forgoneNum =
                forgone === undefined || forgone === null
                  ? null
                  : toNum(forgone as string | number);
              const evalLabel = (row.smart_or_early as string | undefined) ?? "—";
              const evalColor: "emerald" | "amber" | "gray" =
                evalLabel === "smart"
                  ? "emerald"
                  : evalLabel === "early"
                    ? "amber"
                    : "gray";
              const codeLabel = row.name ?? row.code ?? "—";
              return (
                <tr key={i}>
                  <td className="border border-gray-200 px-3 py-2 text-xs text-gray-800">
                    {row.rule ?? "—"}
                  </td>
                  <td className="border border-gray-200 px-3 py-2 text-xs text-gray-700">
                    {codeLabel}
                    {row.code && row.name && (
                      <span className="ml-1 font-mono text-[10px] text-gray-400">
                        {row.code}
                      </span>
                    )}
                  </td>
                  <td className="border border-gray-200 px-3 py-2 text-xs">
                    <Badge color={evalColor} size="xs">
                      {evalLabel}
                    </Badge>
                  </td>
                  <td className="border border-gray-200 px-3 py-2 text-right text-xs tabular-nums text-gray-700">
                    {forgoneNum === null
                      ? "—"
                      : forgoneNum > 0
                        ? `+${formatKRW(forgoneNum)}`
                        : formatKRW(forgoneNum)}
                  </td>
                  <td className="border border-gray-200 px-3 py-2 text-xs text-gray-600">
                    {row.note ?? row.post_outcome ?? "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
};
