import { format, parseISO } from "date-fns";

interface DateSelectorProps {
  dates: string[];
  value: string | null;
  onChange: (next: string) => void;
  disabled?: boolean;
}

export const DateSelector = ({
  dates,
  value,
  onChange,
  disabled,
}: DateSelectorProps) => {
  if (dates.length === 0) {
    return null;
  }

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="daily-date" className="text-sm font-medium text-gray-700">
        리포트 날짜
      </label>
      <select
        id="daily-date"
        className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
        value={value ?? dates[0]}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      >
        {dates.map((d) => (
          <option key={d} value={d}>
            {format(parseISO(d), "yyyy-MM-dd (EEE)")}
          </option>
        ))}
      </select>
    </div>
  );
};
