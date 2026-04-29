import type { Market, Side } from "@/types/api";

export type MarketFilterValue = Market | "all";

export interface TradesFilterValue {
  code: string;
  since: string;
  side: Side | "all";
  market: MarketFilterValue;
}

interface TradesFilterProps {
  value: TradesFilterValue;
  onChange: (next: TradesFilterValue) => void;
  onReset: () => void;
}

const MARKET_OPTIONS: Array<{ key: MarketFilterValue; label: string }> = [
  { key: "all", label: "전체" },
  { key: "kr", label: "KR" },
  { key: "us", label: "US" },
];

export const TradesFilter = ({ value, onChange, onReset }: TradesFilterProps) => {
  const set = <K extends keyof TradesFilterValue>(
    key: K,
    next: TradesFilterValue[K],
  ) => {
    onChange({ ...value, [key]: next });
  };

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-md border border-gray-200 bg-white px-4 py-3">
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-600">시장</label>
        <div className="inline-flex rounded-md border border-gray-200 bg-white p-0.5">
          {MARKET_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              type="button"
              onClick={() => set("market", opt.key)}
              className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                value.market === opt.key
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="filter-code" className="text-xs font-medium text-gray-600">
          종목 코드
        </label>
        <input
          id="filter-code"
          type="text"
          placeholder="005930"
          value={value.code}
          onChange={(e) => set("code", e.target.value)}
          className="w-32 rounded-md border border-gray-300 px-2.5 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="filter-since" className="text-xs font-medium text-gray-600">
          시작일
        </label>
        <input
          id="filter-since"
          type="date"
          value={value.since}
          onChange={(e) => set("since", e.target.value)}
          className="rounded-md border border-gray-300 px-2.5 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="filter-side" className="text-xs font-medium text-gray-600">
          매매 구분
        </label>
        <select
          id="filter-side"
          value={value.side}
          onChange={(e) => set("side", e.target.value as Side | "all")}
          className="rounded-md border border-gray-300 px-2.5 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="all">전체</option>
          <option value="buy">매수</option>
          <option value="sell">매도</option>
        </select>
      </div>
      <button
        type="button"
        onClick={onReset}
        className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:bg-gray-50"
      >
        초기화
      </button>
    </div>
  );
};
