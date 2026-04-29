import type { Market } from "@/types/api";

export type MarketFilter = "all" | Market;

const OPTIONS: Array<{ key: MarketFilter; label: string }> = [
  { key: "all", label: "전체" },
  { key: "kr", label: "KR" },
  { key: "us", label: "US" },
];

interface Props {
  value: MarketFilter;
  onChange: (next: MarketFilter) => void;
}

export const MarketToggle = ({ value, onChange }: Props) => (
  <div className="inline-flex rounded-md border border-gray-200 bg-white p-0.5">
    {OPTIONS.map((opt) => (
      <button
        key={opt.key}
        type="button"
        onClick={() => onChange(opt.key)}
        className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
          value === opt.key
            ? "bg-blue-50 text-blue-700"
            : "text-gray-600 hover:bg-gray-50"
        }`}
      >
        {opt.label}
      </button>
    ))}
  </div>
);
