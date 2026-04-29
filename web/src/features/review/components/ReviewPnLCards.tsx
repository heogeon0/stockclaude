import { Card } from "@tremor/react";
import { formatKRW, formatUSD, toNum } from "@/lib/decimal";
import type { WeeklyReviewOut } from "@/types/api";

const pnlClass = (raw: string | null) => {
  const n = toNum(raw);
  if (n > 0) return "text-emerald-700";
  if (n < 0) return "text-red-700";
  return "text-gray-700";
};

const sign = (raw: string | null) => {
  const n = toNum(raw);
  return n > 0 ? "+" : "";
};

export const ReviewPnLCards = ({ review }: { review: WeeklyReviewOut }) => (
  <div className="grid gap-3 md:grid-cols-4">
    <PnLCard label="실현 KR" value={review.realized_pnl_kr} formatter={formatKRW} />
    <PnLCard label="실현 US" value={review.realized_pnl_us} formatter={formatUSD} />
    <PnLCard
      label="미실현 KR (주말)"
      value={review.unrealized_pnl_kr}
      formatter={formatKRW}
    />
    <PnLCard
      label="미실현 US (주말)"
      value={review.unrealized_pnl_us}
      formatter={formatUSD}
    />
  </div>
);

const PnLCard = ({
  label,
  value,
  formatter,
}: {
  label: string;
  value: string | null;
  formatter: (v: string | number | null) => string;
}) => (
  <Card className="p-4">
    <p className="text-xs text-gray-500">{label}</p>
    <p className={`mt-1 text-lg font-semibold tabular-nums ${pnlClass(value)}`}>
      {sign(value)}
      {formatter(value)}
    </p>
  </Card>
);
