import { Badge, Card } from "@tremor/react";
import { ACTION_STATUS_COLOR, ACTION_STATUS_LABEL, SIDE_LABEL } from "@/lib/constants";
import type { ActionPlanItem } from "@/types/api";

interface Props {
  actions: ActionPlanItem[];
}

export const NextWeekActionsList = ({ actions }: Props) => {
  if (actions.length === 0) {
    return (
      <Card>
        <h4 className="text-sm font-semibold text-gray-700">다음 주 액션</h4>
        <p className="mt-2 text-xs text-gray-400">데이터 없음</p>
      </Card>
    );
  }

  return (
    <Card>
      <h4 className="text-sm font-semibold text-gray-700">다음 주 액션</h4>
      <div className="mt-3 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left text-xs text-gray-500">
              <th className="pb-2">우선</th>
              <th className="pb-2">종목</th>
              <th className="pb-2">방향</th>
              <th className="pb-2 text-right">수량</th>
              <th className="pb-2">트리거</th>
              <th className="pb-2">상태</th>
            </tr>
          </thead>
          <tbody>
            {actions.map((a, i) => (
              <tr key={i} className="border-b border-gray-50">
                <td className="py-2 text-xs tabular-nums text-gray-500">
                  {a.priority ?? "—"}
                </td>
                <td className="py-2 text-xs text-gray-800">
                  {a.name ?? a.code}
                  {a.code && a.name && (
                    <span className="ml-1 font-mono text-[10px] text-gray-400">{a.code}</span>
                  )}
                </td>
                <td className="py-2 text-xs">
                  <Badge color={a.action === "buy" ? "blue" : "amber"} size="xs">
                    {SIDE_LABEL[a.action]}
                  </Badge>
                </td>
                <td className="py-2 text-right text-xs tabular-nums text-gray-700">
                  {a.qty ?? "—"}
                </td>
                <td className="py-2 text-xs text-gray-600">{a.trigger ?? a.condition ?? "—"}</td>
                <td className="py-2 text-xs">
                  <Badge color={ACTION_STATUS_COLOR[a.status]} size="xs">
                    {ACTION_STATUS_LABEL[a.status]}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};
