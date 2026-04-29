import { Card } from "@tremor/react";
import { useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { useBacktest } from "@/hooks/useBacktest";
import { DailyReportContent } from "@/features/today/components/DailyReportContent";
import { MARKET_LABEL } from "@/lib/constants";

export const BacktestSection = () => {
  const query = useBacktest();
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <Card>
      <header className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900">백테스트</h3>
        <p className="mt-1 text-sm text-gray-500">
          현재는 raw markdown 캐시. 향후 win_rate / sharpe / strategy 별 구조화 예정.
          KR 종목만 캐시되어 있고 NVDA / GOOGL 은 미존재.
        </p>
      </header>

      {query.isLoading && <LoadingSkeleton rows={4} />}
      {query.error && (
        <ErrorNotice error={query.error} title="백테스트 조회 실패" />
      )}

      {query.data && (
        <>
          <div className="mb-4 flex flex-wrap gap-2">
            {query.data.rows.length === 0 ? (
              <EmptyState title="백테스트 캐시가 없습니다" />
            ) : (
              query.data.rows.map((r) => {
                const active = selected === r.code;
                return (
                  <button
                    key={r.code}
                    type="button"
                    onClick={() => setSelected(active ? null : r.code)}
                    className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                      active
                        ? "border-blue-500 bg-blue-50 text-blue-700"
                        : "border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
                    }`}
                  >
                    {r.name ?? r.code}
                    {r.market && (
                      <span className="ml-1 text-gray-400">
                        · {MARKET_LABEL[r.market]}
                      </span>
                    )}
                  </button>
                );
              })
            )}
          </div>

          {selected ? (
            (() => {
              const row = query.data.rows.find((r) => r.code === selected);
              if (!row) return null;
              return (
                <div className="rounded-md border border-gray-100 bg-white p-4">
                  <p className="mb-2 text-xs text-gray-500">
                    {row.code} · 캐시 {new Date(row.computed_at).toLocaleDateString("ko-KR")}
                  </p>
                  <DailyReportContent
                    content={row.raw_md}
                    emptyPlaceholder="raw_md 가 비어있습니다."
                  />
                </div>
              );
            })()
          ) : (
            query.data.rows.length > 0 && (
              <p className="text-sm text-gray-400">
                종목을 선택하세요.
              </p>
            )
          )}
        </>
      )}
    </Card>
  );
};
