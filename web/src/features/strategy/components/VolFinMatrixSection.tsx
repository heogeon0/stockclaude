import { Card } from "@tremor/react";
import {
  FIN_TIERS,
  PYRAMIDING_DESCRIPTION,
  SIZE_DESCRIPTION,
  VOL_TIERS,
  lookupCell,
  type FinTier,
  type VolTier,
} from "@/lib/volFinMatrix";

const SIZE_BG: Record<string, string> = {
  풀: "bg-emerald-100 text-emerald-900",
  "70%": "bg-blue-100 text-blue-900",
  "50%": "bg-amber-100 text-amber-900",
  "30%": "bg-orange-100 text-orange-900",
  비추: "bg-red-100 text-red-900",
};

export const VolFinMatrixSection = () => (
  <Card>
    <header className="mb-4">
      <h3 className="text-lg font-semibold text-gray-900">
        변동성 × 재무 헬스 12셀 매트릭스
        <span className="ml-2 rounded bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
          v17 핵심
        </span>
      </h3>
      <p className="mt-1 text-sm text-gray-500">
        진입 사이즈 / 피라미딩 / 손절폭 결정. 변동성 = `analyze_volatility(code).regime`,
        재무 = `compute_score(code).breakdown.financial` 룩업.
      </p>
    </header>

    <div className="overflow-x-auto">
      <table className="min-w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className="border border-gray-200 bg-gray-50 px-3 py-2 text-left text-xs font-semibold text-gray-700">
              재무 \ 변동성
            </th>
            {VOL_TIERS.map((vt) => (
              <th
                key={vt.tier}
                className="border border-gray-200 bg-gray-50 px-3 py-2 text-xs font-semibold text-gray-700"
              >
                <div>{vt.tier}</div>
                <div className="text-[10px] font-normal text-gray-500">{vt.range}</div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {FIN_TIERS.map((ft) => (
            <tr key={ft.tier}>
              <td className="border border-gray-200 bg-gray-50 px-3 py-2">
                <div className="text-sm font-semibold text-gray-900">{ft.tier}급</div>
                <div className="text-[10px] text-gray-500">{ft.range}</div>
              </td>
              {VOL_TIERS.map((vt) => {
                const cell = lookupCell(ft.tier as FinTier, vt.tier as VolTier);
                if (!cell) return <td key={vt.tier} className="border border-gray-200" />;
                return (
                  <td
                    key={vt.tier}
                    className={`border border-gray-200 px-3 py-2 text-center ${
                      SIZE_BG[cell.size] ?? ""
                    }`}
                  >
                    <div className="text-sm font-semibold">
                      {cell.isAvoid ? "❌ 비추" : cell.size}
                    </div>
                    {!cell.isAvoid && (
                      <div className="mt-0.5 text-[10px] tabular-nums">
                        {cell.pyramiding}단 / {cell.stopMethod === "%" ? `${cell.stopPct}%` : cell.stopMethod}
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>

    <div className="mt-4 grid gap-4 md:grid-cols-2">
      <div>
        <h4 className="text-xs font-semibold text-gray-700">진입 사이즈</h4>
        <ul className="mt-1 space-y-0.5 text-xs text-gray-600">
          {Object.entries(SIZE_DESCRIPTION).map(([k, v]) => (
            <li key={k} className="flex gap-2">
              <span className="font-mono w-12 shrink-0 text-gray-700">{k}</span>
              <span>{v}</span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <h4 className="text-xs font-semibold text-gray-700">피라미딩 단계</h4>
        <ul className="mt-1 space-y-0.5 text-xs text-gray-600">
          {Object.entries(PYRAMIDING_DESCRIPTION).map(([k, v]) => (
            <li key={k} className="flex gap-2">
              <span className="font-mono w-12 shrink-0 text-gray-700">{k}단</span>
              <span>{v}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>

    <p className="mt-4 rounded bg-red-50 px-3 py-2 text-xs text-red-800">
      <span className="font-semibold">D급 + extreme 셀 = ❌ 진입 비추</span> — 자동 탈락.
    </p>
    <p className="mt-2 rounded bg-amber-50 px-3 py-2 text-xs text-amber-800">
      <span className="font-semibold">v17 변경:</span> 단타/스윙/중장기/모멘텀 4종 폐지. 모든 종목 단일 룰 + 매트릭스 차등.
      v18+ 에서 `apply_volatility_finance_matrix(code)` MCP 툴로 자동 주입 예정.
    </p>
  </Card>
);
