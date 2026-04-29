import { Card } from "@tremor/react";
import { toNum } from "@/lib/decimal";
import type { Market } from "@/types/api";

interface FairValueCardProps {
  fairMin: string | null;
  fairAvg: string | null;
  fairMax: string | null;
  analystAvg: string | null;
  analystMax: string | null;
  consensusCount: number | null;
  market: Market | null;
}

const formatPrice = (v: string | null, market: Market | null): string => {
  if (v === null) return "-";
  const n = toNum(v);
  if (market === "us") {
    return `$${n.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
  }
  return `₩${n.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}`;
};

export const FairValueCard = ({
  fairMin,
  fairAvg,
  fairMax,
  analystAvg,
  analystMax,
  consensusCount,
  market,
}: FairValueCardProps) => {
  const hasFair = fairMin || fairAvg || fairMax;
  const hasAnalyst = analystAvg || analystMax;
  if (!hasFair && !hasAnalyst) return null;

  return (
    <Card>
      <p className="text-xs text-gray-500">Fair Value · 애널 목표</p>
      {hasFair && (
        <div className="mt-2">
          <p className="text-xs text-gray-400">적정가 밴드</p>
          <div className="mt-0.5 flex items-baseline gap-2 text-gray-900">
            <span className="text-sm tabular-nums">{formatPrice(fairMin, market)}</span>
            <span className="text-gray-300">~</span>
            <span className="text-lg font-semibold tabular-nums">
              {formatPrice(fairAvg, market)}
            </span>
            <span className="text-gray-300">~</span>
            <span className="text-sm tabular-nums">{formatPrice(fairMax, market)}</span>
          </div>
        </div>
      )}
      {hasAnalyst && (
        <div className="mt-3 border-t border-gray-100 pt-2">
          <p className="text-xs text-gray-400">
            애널 목표가 {consensusCount != null && `(n=${consensusCount})`}
          </p>
          <div className="mt-0.5 flex items-baseline gap-3 text-gray-900">
            <span className="text-sm tabular-nums">
              avg {formatPrice(analystAvg, market)}
            </span>
            <span className="text-xs text-gray-400">
              max {formatPrice(analystMax, market)}
            </span>
          </div>
        </div>
      )}
    </Card>
  );
};
