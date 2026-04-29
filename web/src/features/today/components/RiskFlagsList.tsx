import { Badge, Card } from "@tremor/react";
import { RISK_LEVEL_COLOR, RISK_TYPE_LABEL } from "@/lib/constants";
import type { RiskFlag } from "@/types/api";

interface RiskFlagsListProps {
  flags: RiskFlag[];
}

export const RiskFlagsList = ({ flags }: RiskFlagsListProps) => {
  if (flags.length === 0) return null;
  return (
    <Card>
      <h3 className="mb-3 text-base font-semibold text-gray-900">리스크 경고</h3>
      <ul className="space-y-2">
        {flags.map((f, idx) => (
          <li
            key={`${f.type}-${f.code ?? f.scope ?? idx}`}
            className="flex items-start justify-between gap-4 rounded-md border border-gray-100 bg-gray-50 p-3"
          >
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <Badge color={RISK_LEVEL_COLOR[f.level]} size="xs">
                  {f.level === "critical" ? "심각" : "경고"}
                </Badge>
                <span className="text-sm font-medium text-gray-800">
                  {RISK_TYPE_LABEL[f.type] ?? f.type}
                </span>
                {f.code && (
                  <span className="text-xs text-gray-500">· {f.code}</span>
                )}
                {f.scope && !f.code && (
                  <span className="text-xs text-gray-500">· {f.scope}</span>
                )}
              </div>
              {f.detail && (
                <p className="text-xs text-gray-600">{f.detail}</p>
              )}
            </div>
            {f.weight_pct != null && (
              <span className="tabular-nums text-sm font-medium text-gray-700">
                {f.weight_pct.toFixed(1)}%
              </span>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
};
