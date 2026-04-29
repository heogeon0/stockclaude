import {
  Badge,
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Title,
} from "@tremor/react";
import { formatKRW, formatQty, formatUSD, toNum } from "@/lib/decimal";
import { MARKET_LABEL, STATUS_COLOR, STATUS_LABEL } from "@/lib/constants";
import type { PositionOut } from "@/types/api";

interface PositionsTableProps {
  positions: PositionOut[];
}

export const PositionsTable = ({ positions }: PositionsTableProps) => {
  if (positions.length === 0) {
    return (
      <Card>
        <Title>보유 종목</Title>
        <p className="mt-3 text-sm text-gray-500">보유 종목이 없습니다.</p>
      </Card>
    );
  }

  return (
    <Card>
      <Title>보유 종목 ({positions.length})</Title>
      <Table className="mt-4">
        <TableHead>
          <TableRow>
            <TableHeaderCell>종목</TableHeaderCell>
            <TableHeaderCell>시장</TableHeaderCell>
            <TableHeaderCell className="text-right">수량</TableHeaderCell>
            <TableHeaderCell className="text-right">평단</TableHeaderCell>
            <TableHeaderCell className="text-right">원금</TableHeaderCell>
            <TableHeaderCell>상태</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {positions.map((p) => (
            <TableRow key={`${p.code}-${p.status}`}>
              <TableCell>
                <div className="flex flex-col">
                  <span className="font-medium text-gray-900">
                    {p.name ?? p.code}
                  </span>
                  <span className="text-xs text-gray-500">{p.code}</span>
                </div>
              </TableCell>
              <TableCell>{p.market ? MARKET_LABEL[p.market] : "—"}</TableCell>
              <TableCell className="text-right">{formatQty(p.qty)}</TableCell>
              <TableCell className="text-right">
                {formatPrice(p.market, p.avg_price)}
              </TableCell>
              <TableCell className="text-right">
                {formatPrice(p.market, p.cost_basis)}
              </TableCell>
              <TableCell>
                <Badge color={STATUS_COLOR[p.status]}>
                  {STATUS_LABEL[p.status]}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
};

const formatPrice = (
  market: PositionOut["market"],
  value: string | number | null | undefined,
) => {
  if (value === null || value === undefined) return "—";
  return market === "us" ? formatUSD(toNum(value)) : formatKRW(toNum(value));
};
