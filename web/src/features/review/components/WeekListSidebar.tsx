import { formatKRWCompact, toNum } from "@/lib/decimal";
import type { WeeklyReviewListItem } from "@/types/api";

interface Props {
  items: WeeklyReviewListItem[];
  selectedWeekStart: string | null;
  onSelect: (weekStart: string) => void;
}

export const WeekListSidebar = ({ items, selectedWeekStart, onSelect }: Props) => (
  <ul className="space-y-1.5">
    {items.map((item) => {
      const isSelected = selectedWeekStart === item.week_start;
      const pnl = toNum(item.realized_pnl_kr);
      const pnlClass = pnl > 0 ? "text-emerald-700" : pnl < 0 ? "text-red-700" : "text-gray-500";
      return (
        <li key={item.week_start}>
          <button
            type="button"
            onClick={() => onSelect(item.week_start)}
            className={`w-full rounded-md border px-3 py-2 text-left transition-colors ${
              isSelected
                ? "border-blue-500 bg-blue-50"
                : "border-gray-200 bg-white hover:bg-gray-50"
            }`}
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-mono text-xs font-medium text-gray-700">
                {item.week_start}
              </span>
              <span className={`text-xs tabular-nums ${pnlClass}`}>
                {pnl > 0 ? "+" : ""}
                {formatKRWCompact(item.realized_pnl_kr)}
              </span>
            </div>
            <p className="mt-1 line-clamp-2 text-xs text-gray-700">
              {item.headline ?? "(headline 없음)"}
            </p>
            <p className="mt-1 text-[10px] text-gray-400">
              거래 {item.trade_count}건
            </p>
          </button>
        </li>
      );
    })}
  </ul>
);
