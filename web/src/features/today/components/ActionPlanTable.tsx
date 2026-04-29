import {
  Badge,
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@tremor/react";
import {
  ACTION_STATUS_COLOR,
  ACTION_STATUS_LABEL,
  SIDE_COLOR,
  SIDE_LABEL,
} from "@/lib/constants";
import type { ActionPlanItem, ActionStatus, Side } from "@/types/api";
import { formatQty } from "@/lib/decimal";

interface ActionPlanTableProps {
  actions: ActionPlanItem[];
}

export const ActionPlanTable = ({ actions }: ActionPlanTableProps) => {
  if (actions.length === 0) return null;
  const sorted = [...actions].sort(
    (a, b) => (a.priority ?? 99) - (b.priority ?? 99),
  );
  return (
    <Card>
      <h3 className="mb-3 text-base font-semibold text-gray-900">액션 플랜</h3>
      <Table>
        <TableHead>
          <TableRow>
            <TableHeaderCell>#</TableHeaderCell>
            <TableHeaderCell>종목</TableHeaderCell>
            <TableHeaderCell>구분</TableHeaderCell>
            <TableHeaderCell className="text-right">수량</TableHeaderCell>
            <TableHeaderCell>트리거</TableHeaderCell>
            <TableHeaderCell>조건</TableHeaderCell>
            <TableHeaderCell>상태</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {sorted.map((a, idx) => {
            const side = a.action as Side;
            const status = a.status as ActionStatus;
            return (
              <TableRow key={`${a.code}-${idx}`}>
                <TableCell className="text-gray-500">
                  {a.priority ?? idx + 1}
                </TableCell>
                <TableCell>
                  <div className="flex flex-col">
                    <span className="font-medium text-gray-900">
                      {a.name ?? a.code}
                    </span>
                    <span className="text-xs text-gray-400">{a.code}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge color={SIDE_COLOR[side]} size="xs">
                    {SIDE_LABEL[side]}
                  </Badge>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {a.qty != null ? formatQty(a.qty) : "-"}
                </TableCell>
                <TableCell className="max-w-[220px] text-sm text-gray-700">
                  {a.trigger ?? "-"}
                </TableCell>
                <TableCell className="max-w-[260px] text-xs text-gray-500">
                  {a.condition ?? a.reason ?? "-"}
                </TableCell>
                <TableCell>
                  <Badge color={ACTION_STATUS_COLOR[status]} size="xs">
                    {ACTION_STATUS_LABEL[status]}
                  </Badge>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Card>
  );
};
