import {
  Badge,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@tremor/react";
import { useMemo, useState } from "react";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { usePortfolio } from "@/hooks/usePortfolio";
import { useScoreWeightsApplied } from "@/hooks/useScoreWeightsApplied";
import {
  DIM_LABEL,
  TIMEFRAME_LABEL,
  TIMEFRAME_OPTIONS,
  WEIGHT_SOURCE_COLOR,
  WEIGHT_SOURCE_LABEL,
} from "@/lib/strategyConstants";
import { toNum } from "@/lib/decimal";
import type { Timeframe } from "@/types/api";

export const AppliedWeightsLookup = () => {
  const [code, setCode] = useState<string | null>(null);
  const [timeframe, setTimeframe] = useState<Timeframe>("swing");
  const [codeInput, setCodeInput] = useState("");

  const portfolio = usePortfolio();
  const positions = useMemo(
    () =>
      (portfolio.data?.positions ?? []).map((p) => ({
        code: p.code,
        name: p.name ?? p.code,
      })),
    [portfolio.data],
  );

  const query = useScoreWeightsApplied(code, timeframe);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col text-xs text-gray-500">
          종목 코드
          <input
            type="text"
            value={codeInput}
            onChange={(e) => setCodeInput(e.target.value.trim())}
            placeholder="예: 005930"
            className="mt-1 w-32 rounded border border-gray-200 px-2 py-1 text-sm"
          />
        </label>
        <label className="flex flex-col text-xs text-gray-500">
          타임프레임
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value as Timeframe)}
            className="mt-1 rounded border border-gray-200 px-2 py-1 text-sm"
          >
            {TIMEFRAME_OPTIONS.map((tf) => (
              <option key={tf} value={tf}>
                {TIMEFRAME_LABEL[tf]} ({tf})
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={() => setCode(codeInput || null)}
          disabled={!codeInput}
          className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white disabled:bg-gray-300"
        >
          조회
        </button>
      </div>

      {positions.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-gray-500">보유 종목:</span>
          {positions.map((p) => (
            <button
              key={p.code}
              type="button"
              onClick={() => {
                setCodeInput(p.code);
                setCode(p.code);
              }}
              className="rounded-full border border-gray-200 bg-white px-2.5 py-0.5 text-xs text-gray-700 hover:bg-gray-50"
            >
              {p.name}
            </button>
          ))}
        </div>
      )}

      {!code && (
        <p className="text-sm text-gray-400">종목을 선택하거나 코드를 입력하세요.</p>
      )}
      {code && query.isLoading && <LoadingSkeleton rows={3} />}
      {code && query.error && (
        <ErrorNotice error={query.error} title="가중치 조회 실패" />
      )}
      {code && query.data && (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>차원</TableHeaderCell>
              <TableHeaderCell className="text-right">가중치</TableHeaderCell>
              <TableHeaderCell>출처</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {query.data.rows.map((r) => (
              <TableRow key={r.dim}>
                <TableCell className="font-medium text-gray-900">
                  {DIM_LABEL[r.dim]}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {(toNum(r.weight) * 100).toFixed(0)}%
                </TableCell>
                <TableCell>
                  <Badge color={WEIGHT_SOURCE_COLOR[r.source]} size="xs">
                    {WEIGHT_SOURCE_LABEL[r.source]}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
};
