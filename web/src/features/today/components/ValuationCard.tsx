import { Card } from "@tremor/react";
import { toNum } from "@/lib/decimal";

interface ValuationCardProps {
  per: string | null;
  pbr: string | null;
  psr: string | null;
  roe: string | null;
  opMargin: string | null;
}

const formatRatio = (v: string | null, digits = 2): string => {
  if (v === null) return "-";
  return toNum(v).toFixed(digits);
};

interface StatProps {
  label: string;
  value: string;
  suffix?: string;
}

const Stat = ({ label, value, suffix }: StatProps) => (
  <div className="rounded-md border border-gray-100 bg-gray-50 p-2 text-center">
    <p className="text-xs text-gray-500">{label}</p>
    <p className="mt-0.5 tabular-nums text-sm font-semibold text-gray-900">
      {value}
      {suffix && <span className="ml-0.5 text-xs font-normal text-gray-500">{suffix}</span>}
    </p>
  </div>
);

export const ValuationCard = ({ per, pbr, psr, roe, opMargin }: ValuationCardProps) => {
  return (
    <Card>
      <p className="text-xs text-gray-500">밸류에이션 · 수익성</p>
      <div className="mt-2 grid grid-cols-3 gap-2">
        <Stat label="PER" value={formatRatio(per)} />
        <Stat label="PBR" value={formatRatio(pbr)} />
        <Stat label="PSR" value={formatRatio(psr)} />
      </div>
      {(roe || opMargin) && (
        <div className="mt-2 grid grid-cols-2 gap-2">
          <Stat label="ROE" value={formatRatio(roe, 1)} suffix="%" />
          <Stat label="영업이익률" value={formatRatio(opMargin, 1)} suffix="%" />
        </div>
      )}
    </Card>
  );
};
