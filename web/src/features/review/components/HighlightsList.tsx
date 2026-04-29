import { Card } from "@tremor/react";
import type { Highlight } from "@/types/api";

const TYPE_META: Record<string, { label: string; bg: string; border: string; text: string }> = {
  insight: {
    label: "Insight",
    bg: "bg-blue-50",
    border: "border-blue-200",
    text: "text-blue-900",
  },
  pattern: {
    label: "Pattern",
    bg: "bg-violet-50",
    border: "border-violet-200",
    text: "text-violet-900",
  },
  warning: {
    label: "Warning",
    bg: "bg-amber-50",
    border: "border-amber-200",
    text: "text-amber-900",
  },
};

interface Props {
  highlights: Highlight[];
}

export const HighlightsList = ({ highlights }: Props) => {
  if (highlights.length === 0) {
    return (
      <Card>
        <h4 className="text-sm font-semibold text-gray-700">하이라이트</h4>
        <p className="mt-2 text-xs text-gray-400">데이터 없음</p>
      </Card>
    );
  }

  return (
    <Card>
      <h4 className="text-sm font-semibold text-gray-700">하이라이트</h4>
      <ul className="mt-3 space-y-2">
        {highlights.map((h, i) => {
          const meta = TYPE_META[h.type] ?? {
            label: h.type,
            bg: "bg-gray-50",
            border: "border-gray-200",
            text: "text-gray-900",
          };
          return (
            <li
              key={i}
              className={`flex gap-3 rounded-md border ${meta.border} ${meta.bg} px-3 py-2`}
            >
              <span
                className={`shrink-0 rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${meta.text}`}
              >
                {meta.label}
              </span>
              <p className={`text-xs ${meta.text}`}>{h.detail}</p>
            </li>
          );
        })}
      </ul>
    </Card>
  );
};
