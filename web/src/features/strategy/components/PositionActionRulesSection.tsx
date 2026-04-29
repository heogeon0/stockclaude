import { Card } from "@tremor/react";
import {
  ACTION_MATRIX,
  POSITION_RULES,
  PRE_EXECUTION_CHECKLIST,
  SPLIT_PROFIT_REASON,
  SPLIT_PROFIT_RULE,
  STOP_STAGES,
} from "@/lib/positionActionRules";

const TONE_BG: Record<"buy" | "neutral" | "sell", string> = {
  buy: "bg-emerald-50 text-emerald-900",
  neutral: "bg-gray-50 text-gray-700",
  sell: "bg-red-50 text-red-900",
};

const isCritical = (text: string): boolean =>
  /즉시|❌|손절|본전컷|부분 익절/.test(text) && !text.includes("점검") && !text.includes("검토");

export const PositionActionRulesSection = () => (
  <Card>
    <header className="mb-4">
      <h3 className="text-lg font-semibold text-gray-900">포지션 액션 룰</h3>
      <p className="mt-1 text-sm text-gray-500">
        보유 종목 액션 결정 6대 룰 + 수익률 × verdict 매트릭스 + 손절 단계.
        매매 집행 전 9개 체크리스트 통과 필수.
      </p>
    </header>

    <section>
      <h4 className="mb-2 text-sm font-semibold text-gray-700">6대 룰</h4>
      <ul className="space-y-2">
        {POSITION_RULES.map((r) => (
          <li
            key={r.no}
            className="rounded-md border border-gray-100 bg-gray-50 p-3 text-sm"
          >
            <div className="flex gap-2">
              <span className="shrink-0 text-xs font-bold text-blue-700">#{r.no}</span>
              <div>
                <p className="font-semibold text-gray-900">{r.title}</p>
                <p className="mt-0.5 text-xs text-gray-700">{r.body}</p>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>

    <section className="mt-6 border-t border-gray-100 pt-4">
      <h4 className="mb-2 text-sm font-semibold text-gray-700">
        수익률 × Verdict 액션 매트릭스
      </h4>
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr className="bg-gray-50">
              <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">
                수익률
              </th>
              <th className="border border-gray-200 px-3 py-2 text-xs font-semibold text-emerald-700">
                매수우세
              </th>
              <th className="border border-gray-200 px-3 py-2 text-xs font-semibold text-gray-600">
                중립
              </th>
              <th className="border border-gray-200 px-3 py-2 text-xs font-semibold text-red-700">
                매도우세
              </th>
            </tr>
          </thead>
          <tbody>
            {ACTION_MATRIX.map((row) => (
              <tr key={row.bucket}>
                <td className="border border-gray-200 bg-gray-50 px-3 py-2 text-xs font-medium text-gray-900">
                  {row.bucket}
                </td>
                {(["buy", "neutral", "sell"] as const).map((tone) => {
                  const text = row[tone];
                  return (
                    <td
                      key={tone}
                      className={`border border-gray-200 px-3 py-2 text-center text-xs ${TONE_BG[tone]} ${
                        isCritical(text) ? "font-semibold" : ""
                      }`}
                    >
                      {text}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>

    <section className="mt-6 border-t border-gray-100 pt-4">
      <h4 className="mb-2 text-sm font-semibold text-gray-700">손절 단계 (변동성×재무 셀의 손절폭 기반)</h4>
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr className="bg-gray-50">
              <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">단계</th>
              <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">계산</th>
              <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">액션</th>
              <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">예시 (% 셀)</th>
              <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">예시 (ATR 셀)</th>
            </tr>
          </thead>
          <tbody>
            {STOP_STAGES.map((s) => (
              <tr key={s.stage}>
                <td className="border border-gray-200 px-3 py-2 text-xs font-semibold text-gray-900">{s.stage}</td>
                <td className="border border-gray-200 px-3 py-2 text-xs text-gray-700">{s.ratio}</td>
                <td className="border border-gray-200 px-3 py-2 text-xs text-amber-700">{s.action}</td>
                <td className="border border-gray-200 px-3 py-2 text-xs text-gray-600 tabular-nums">{s.example}</td>
                <td className="border border-gray-200 px-3 py-2 text-xs text-gray-600 tabular-nums">{s.atrExample}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>

    <section className="mt-6 grid gap-4 border-t border-gray-100 pt-4 md:grid-cols-2">
      <div>
        <h4 className="mb-2 text-sm font-semibold text-gray-700">분할 익절 룰 (W17)</h4>
        <ul className="space-y-1 text-xs text-gray-700">
          {SPLIT_PROFIT_RULE.map((r, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-gray-400">·</span>
              <span>{r}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 rounded bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {SPLIT_PROFIT_REASON}
        </p>
      </div>
      <div>
        <h4 className="mb-2 text-sm font-semibold text-gray-700">매매 집행 전 체크리스트</h4>
        <ul className="space-y-1 text-xs text-gray-700">
          {PRE_EXECUTION_CHECKLIST.map((c, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-blue-600">☐</span>
              <span>{c}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  </Card>
);
