import {
  Badge,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@tremor/react";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { useScoreWeightsOverrides } from "@/hooks/useScoreWeightsOverrides";
import {
  DIM_LABEL,
  TIMEFRAME_LABEL,
  WEIGHT_SOURCE_COLOR,
  WEIGHT_SOURCE_LABEL,
} from "@/lib/strategyConstants";
import { toNum } from "@/lib/decimal";

export const OverridesTable = () => {
  const query = useScoreWeightsOverrides(true);

  if (query.isLoading) return <LoadingSkeleton rows={3} />;
  if (query.error)
    return <ErrorNotice error={query.error} title="overrides 조회 실패" />;

  const rows = query.data?.overrides ?? [];
  if (rows.length === 0) {
    return (
      <EmptyState
        title="활성 override 없음"
        description="MCP override_score_weights 툴 사용 시 여기에 표시됩니다."
      />
    );
  }

  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeaderCell>종목</TableHeaderCell>
          <TableHeaderCell>타임프레임</TableHeaderCell>
          <TableHeaderCell>차원</TableHeaderCell>
          <TableHeaderCell className="text-right">가중치</TableHeaderCell>
          <TableHeaderCell>출처</TableHeaderCell>
          <TableHeaderCell>사유</TableHeaderCell>
          <TableHeaderCell>만료</TableHeaderCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={`${r.code}-${r.timeframe}-${r.dim}`}>
            <TableCell>
              <div className="flex flex-col">
                <span className="font-medium text-gray-900">
                  {r.name ?? r.code}
                </span>
                <span className="text-xs text-gray-400">{r.code}</span>
              </div>
            </TableCell>
            <TableCell className="text-xs text-gray-700">
              {TIMEFRAME_LABEL[r.timeframe]}
            </TableCell>
            <TableCell>{DIM_LABEL[r.dim]}</TableCell>
            <TableCell className="text-right tabular-nums">
              {(toNum(r.weight) * 100).toFixed(0)}%
            </TableCell>
            <TableCell>
              {r.source && (
                <Badge color={WEIGHT_SOURCE_COLOR[r.source]} size="xs">
                  {WEIGHT_SOURCE_LABEL[r.source]}
                </Badge>
              )}
            </TableCell>
            <TableCell className="max-w-[280px] text-xs text-gray-600">
              {r.reason ?? "-"}
            </TableCell>
            <TableCell className="text-xs text-gray-500">
              {r.expires_at
                ? new Date(r.expires_at).toLocaleDateString("ko-KR")
                : "-"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};
