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
import { format } from "date-fns";
import { SIDE_COLOR, SIDE_LABEL } from "@/lib/constants";
import { formatKRW, formatQty, formatUSD, toNum } from "@/lib/decimal";
import type { Market, TradeOut } from "@/types/api";

interface TradesTableProps {
  trades: TradeOut[];
}

export const TradesTable = ({ trades }: TradesTableProps) => {
  if (trades.length === 0) {
    return (
      <Card>
        <p className="py-8 text-center text-sm text-gray-500">
          조건에 맞는 매매 기록이 없습니다.
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <Table>
        <TableHead>
          <TableRow>
            <TableHeaderCell>시각</TableHeaderCell>
            <TableHeaderCell>종목</TableHeaderCell>
            <TableHeaderCell>구분</TableHeaderCell>
            <TableHeaderCell className="text-right">수량</TableHeaderCell>
            <TableHeaderCell className="text-right">단가</TableHeaderCell>
            <TableHeaderCell className="text-right">금액</TableHeaderCell>
            <TableHeaderCell className="text-right">실현손익</TableHeaderCell>
            <TableHeaderCell>메모</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {trades.map((t) => {
            const amount = toNum(t.qty) * toNum(t.price);
            return (
              <TableRow key={t.id}>
                <TableCell className="whitespace-nowrap text-sm text-gray-600">
                  {format(new Date(t.executed_at), "yyyy-MM-dd HH:mm")}
                </TableCell>
                <TableCell>
                  <div className="flex flex-col">
                    <span className="font-medium text-gray-900">
                      {t.name ?? t.code}
                    </span>
                    <span className="text-xs text-gray-500">{t.code}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge color={SIDE_COLOR[t.side]}>{SIDE_LABEL[t.side]}</Badge>
                </TableCell>
                <TableCell className="text-right">{formatQty(t.qty)}</TableCell>
                <TableCell className="text-right">
                  {formatByMarket(t.market, t.price)}
                </TableCell>
                <TableCell className="text-right">
                  {formatByMarket(t.market, amount)}
                </TableCell>
                <TableCell className="text-right">
                  {t.realized_pnl !== null
                    ? formatPnl(t.market, t.realized_pnl)
                    : "—"}
                </TableCell>
                <TableCell className="max-w-xs truncate text-sm text-gray-600">
                  {t.trigger_note ?? "—"}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Card>
  );
};

const formatByMarket = (
  market: Market | null,
  value: string | number | null | undefined,
) => {
  if (value === null || value === undefined) return "—";
  return market === "us" ? formatUSD(toNum(value)) : formatKRW(toNum(value));
};

const formatPnl = (market: Market | null, value: string) => {
  const n = toNum(value);
  const text = formatByMarket(market, Math.abs(n));
  const sign = n > 0 ? "+" : n < 0 ? "-" : "";
  const className =
    n > 0 ? "text-emerald-600" : n < 0 ? "text-red-600" : "text-gray-600";
  return <span className={className}>{sign}{text}</span>;
};
