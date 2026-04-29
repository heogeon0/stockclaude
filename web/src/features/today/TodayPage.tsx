import { Tab, TabGroup, TabList, TabPanel, TabPanels } from "@tremor/react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useDailyReportDates } from "@/hooks/useDailyReportDates";
import { DateSelector } from "./components/DateSelector";
import { MarketToggle, type MarketFilter } from "./components/MarketToggle";
import { EconomyTab } from "./tabs/EconomyTab";
import { IndustriesTab } from "./tabs/IndustriesTab";
import { StockDailyTab } from "./tabs/StockDailyTab";
import { SummaryTab } from "./tabs/SummaryTab";

type TabKey = "summary" | "stocks" | "industries" | "economy";

const TAB_KEYS: readonly TabKey[] = ["summary", "stocks", "industries", "economy"];

const isMarketFilter = (v: string | null): v is MarketFilter =>
  v === "all" || v === "kr" || v === "us";

export const TodayPage = () => {
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  const datesQuery = useDailyReportDates();
  const effectiveDate = selectedDate ?? datesQuery.data?.dates[0] ?? null;

  const market: MarketFilter = useMemo(() => {
    const raw = searchParams.get("market");
    return isMarketFilter(raw) ? raw : "all";
  }, [searchParams]);

  const handleMarketChange = (next: MarketFilter) => {
    const sp = new URLSearchParams(searchParams);
    if (next === "all") sp.delete("market");
    else sp.set("market", next);
    setSearchParams(sp, { replace: true });
  };

  const activeIndex = useMemo(() => {
    const key = (searchParams.get("tab") ?? "summary") as TabKey;
    const idx = TAB_KEYS.indexOf(key);
    return idx === -1 ? 0 : idx;
  }, [searchParams]);

  const handleIndexChange = (idx: number) => {
    const key = TAB_KEYS[idx];
    const next = new URLSearchParams(searchParams);
    if (key === "summary") {
      next.delete("tab");
    } else {
      next.set("tab", key);
    }
    setSearchParams(next, { replace: true });
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900">데일리 리포트</h2>
          <p className="mt-1 text-sm text-gray-500">
            거시 → 산업 → 종목 → 포트폴리오 종합. 시장 토글로 KR/US 분리.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <MarketToggle value={market} onChange={handleMarketChange} />
          {datesQuery.data && datesQuery.data.dates.length > 0 && (
            <DateSelector
              dates={datesQuery.data.dates}
              value={effectiveDate}
              onChange={setSelectedDate}
            />
          )}
        </div>
      </header>

      <TabGroup index={activeIndex} onIndexChange={handleIndexChange}>
        <TabList>
          <Tab>종합</Tab>
          <Tab>종목</Tab>
          <Tab>산업</Tab>
          <Tab>경제</Tab>
        </TabList>
        <TabPanels>
          <TabPanel>
            <div className="mt-4">
              <SummaryTab date={effectiveDate} market={market} />
            </div>
          </TabPanel>
          <TabPanel>
            <div className="mt-4">
              <StockDailyTab date={effectiveDate} market={market} />
            </div>
          </TabPanel>
          <TabPanel>
            <div className="mt-4">
              <IndustriesTab market={market} />
            </div>
          </TabPanel>
          <TabPanel>
            <div className="mt-4">
              <EconomyTab date={effectiveDate} market={market} />
            </div>
          </TabPanel>
        </TabPanels>
      </TabGroup>
    </div>
  );
};
