import {
  Accordion,
  AccordionBody,
  AccordionHeader,
  AccordionList,
  Badge,
} from "@tremor/react";
import { useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { useIndustries } from "@/hooks/useIndustries";
import { MARKET_LABEL, scoreColor } from "@/lib/constants";
import type { IndustryOut } from "@/types/api";
import { DailyReportContent } from "../components/DailyReportContent";
import type { MarketFilter } from "../components/MarketToggle";

type ScopeKey = "holdings" | "all";

const SCOPES: Array<{ key: ScopeKey; label: string }> = [
  { key: "holdings", label: "보유만" },
  { key: "all", label: "전체" },
];

interface IndustriesTabProps {
  market: MarketFilter;
}

export const IndustriesTab = ({ market }: IndustriesTabProps) => {
  const [scope, setScope] = useState<ScopeKey>("holdings");
  const serverMarket = market === "all" ? undefined : market;
  const query = useIndustries(scope === "holdings", serverMarket);

  return (
    <div className="space-y-4">
      <ScopeBar value={scope} onChange={setScope} />
      {renderBody()}
    </div>
  );

  function renderBody() {
    if (query.isLoading) return <LoadingSkeleton rows={4} />;
    if (query.error)
      return <ErrorNotice error={query.error} title="산업 정보 조회 실패" />;
    const rows = query.data?.industries ?? [];
    if (rows.length === 0) {
      const desc =
        scope === "holdings"
          ? market === "all"
            ? "현재 보유 종목에 연결된 산업 정보가 없습니다."
            : `보유한 ${MARKET_LABEL[market as Exclude<MarketFilter, "all">]} 종목의 산업 정보가 없습니다.`
          : "해당 필터에 매칭되는 산업이 없습니다.";
      return <EmptyState title="표시할 산업이 없습니다" description={desc} />;
    }
    return (
      <AccordionList>
        {rows.map((industry) => (
          <Accordion key={industry.code}>
            <AccordionHeader>
              <IndustryRowHeader industry={industry} />
            </AccordionHeader>
            <AccordionBody>
              <DailyReportContent
                content={industry.content}
                emptyPlaceholder="산업 리포트 본문이 없습니다."
              />
            </AccordionBody>
          </Accordion>
        ))}
      </AccordionList>
    );
  }
};

interface ScopeBarProps {
  value: ScopeKey;
  onChange: (v: ScopeKey) => void;
}

const ScopeBar = ({ value, onChange }: ScopeBarProps) => (
  <div className="inline-flex rounded-md border border-gray-200 bg-white p-0.5">
    {SCOPES.map((s) => (
      <button
        key={s.key}
        type="button"
        onClick={() => onChange(s.key)}
        className={`rounded px-3 py-1.5 text-sm font-medium transition-colors ${
          value === s.key
            ? "bg-blue-50 text-blue-700"
            : "text-gray-600 hover:bg-gray-50"
        }`}
      >
        {s.label}
      </button>
    ))}
  </div>
);

const IndustryRowHeader = ({ industry }: { industry: IndustryOut }) => (
  <div className="flex flex-1 items-center justify-between gap-3 pr-3 text-left">
    <div className="flex items-baseline gap-2 min-w-0">
      <span className="font-semibold text-gray-900 truncate">
        {industry.name}
      </span>
      <span className="text-xs text-gray-400">{industry.code}</span>
      {industry.market && (
        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
          {MARKET_LABEL[industry.market]}
        </span>
      )}
    </div>
    {industry.score != null && (
      <Badge color={scoreColor(industry.score)} size="xs">
        {industry.score}
      </Badge>
    )}
  </div>
);
