import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { useEconomyBase } from "@/hooks/useEconomyBase";
import { useEconomyDaily } from "@/hooks/useEconomyDaily";
import type { Market } from "@/types/api";
import { EconomyBaseSection } from "../components/EconomyBaseSection";
import { EconomyDailySection } from "../components/EconomyDailySection";
import type { MarketFilter } from "../components/MarketToggle";

interface EconomyTabProps {
  date: string | null;
  market: MarketFilter;
}

export const EconomyTab = ({ date, market }: EconomyTabProps) => {
  const markets: Market[] = market === "all" ? ["kr", "us"] : [market];
  return (
    <div className="space-y-6">
      {markets.map((m) => (
        <MarketSection key={m} market={m} date={date} />
      ))}
    </div>
  );
};

interface MarketSectionProps {
  market: Market;
  date: string | null;
}

const MARKET_HEADING: Record<Market, string> = {
  kr: "🇰🇷 한국",
  us: "🇺🇸 미국",
};

const MarketSection = ({ market, date }: MarketSectionProps) => {
  const dailyQuery = useEconomyDaily(market, date);
  const baseQuery = useEconomyBase(market);

  if (dailyQuery.isLoading || baseQuery.isLoading)
    return <LoadingSkeleton rows={3} />;

  return (
    <section className="space-y-3">
      <h3 className="text-sm font-semibold text-gray-700">
        {MARKET_HEADING[market]}
      </h3>
      {dailyQuery.error ? (
        <ErrorNotice error={dailyQuery.error} title="경제 일일 조회 실패" />
      ) : (
        <EconomyDailySection daily={dailyQuery.data ?? null} />
      )}
      {baseQuery.error ? (
        <ErrorNotice error={baseQuery.error} title="경제 기본 조회 실패" />
      ) : (
        <EconomyBaseSection base={baseQuery.data ?? null} />
      )}
    </section>
  );
};
