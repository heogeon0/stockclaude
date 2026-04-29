import { Card, Metric, Text, Flex } from "@tremor/react";
import { formatKRW, formatUSD, toNum } from "@/lib/decimal";
import type { PortfolioOut } from "@/types/api";

interface AssetSummaryCardsProps {
  portfolio: PortfolioOut;
}

export const AssetSummaryCards = ({ portfolio }: AssetSummaryCardsProps) => {
  const krwCash = toNum(portfolio.cash.KRW);
  const usdCash = toNum(portfolio.cash.USD);
  const krwRealized = toNum(portfolio.realized_pnl.KRW);
  const usdRealized = toNum(portfolio.realized_pnl.USD);

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <Card>
        <Text>KR 총자산</Text>
        <Metric>{formatKRW(portfolio.kr_total_krw)}</Metric>
        <Flex className="mt-3 border-t border-gray-100 pt-2" justifyContent="between">
          <Text className="text-xs">예수금</Text>
          <Text className="text-xs font-medium">{formatKRW(krwCash)}</Text>
        </Flex>
      </Card>

      <Card>
        <Text>US 총자산</Text>
        <Metric>{formatUSD(portfolio.us_total_usd)}</Metric>
        <Flex className="mt-3 border-t border-gray-100 pt-2" justifyContent="between">
          <Text className="text-xs">예수금</Text>
          <Text className="text-xs font-medium">{formatUSD(usdCash)}</Text>
        </Flex>
      </Card>

      <Card>
        <Text>누적 실현손익</Text>
        <div className="mt-1 space-y-1">
          <Flex justifyContent="between">
            <Text className="text-xs">KRW</Text>
            <Metric
              className={krwRealized < 0 ? "text-red-600" : "text-emerald-600"}
            >
              {formatKRW(krwRealized)}
            </Metric>
          </Flex>
          <Flex justifyContent="between" className="border-t border-gray-100 pt-2">
            <Text className="text-xs">USD</Text>
            <Text
              className={`text-sm font-semibold ${
                usdRealized < 0 ? "text-red-600" : "text-emerald-600"
              }`}
            >
              {formatUSD(usdRealized)}
            </Text>
          </Flex>
        </div>
      </Card>
    </div>
  );
};
