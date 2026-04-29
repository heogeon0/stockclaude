import { Badge, Card, Title } from "@tremor/react";
import { format } from "date-fns";
import { SIDE_COLOR, SIDE_LABEL } from "@/lib/constants";
import { formatKRW, formatQty, formatUSD, toNum } from "@/lib/decimal";
import type { Market, TradeOut } from "@/types/api";

interface RecentTradesCardProps {
  trades: TradeOut[];
}

const formatPrice = (v: string, market: Market | null) =>
  market === "us" ? formatUSD(v) : formatKRW(v);

const formatAmount = (amount: number, market: Market | null) => {
  if (market === "us") {
    return `$${amount.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
  }
  return `₩${amount.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}`;
};

export const RecentTradesCard = ({ trades }: RecentTradesCardProps) => (
  <Card>
    <Title>최근 매매</Title>
    {trades.length === 0 ? (
      <p className="mt-3 text-sm text-gray-500">매매 기록이 없습니다.</p>
    ) : (
      <ul className="mt-3 divide-y divide-gray-100">
        {trades.map((t) => {
          const amount = toNum(t.qty) * toNum(t.price);
          return (
            <li
              key={t.id}
              className="flex items-center justify-between gap-3 py-2.5"
            >
              <div className="flex items-center gap-3">
                <Badge color={SIDE_COLOR[t.side]} size="xs">
                  {SIDE_LABEL[t.side]}
                </Badge>
                <div className="flex flex-col">
                  <span className="text-sm font-medium text-gray-900">
                    {t.name ?? t.code}
                  </span>
                  <span className="text-xs text-gray-500">
                    {format(new Date(t.executed_at), "yyyy-MM-dd HH:mm")}
                  </span>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm text-gray-900 tabular-nums">
                  {formatQty(t.qty)} 주 @ {formatPrice(t.price, t.market)}
                </div>
                <div className="text-xs font-medium text-gray-700 tabular-nums">
                  {formatAmount(amount, t.market)}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    )}
  </Card>
);
