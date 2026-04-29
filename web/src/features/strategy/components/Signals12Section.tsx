import { Badge, Card } from "@tremor/react";
import {
  SIGNALS_12,
  SIGNAL_USAGE_RULES,
  VCP_NOTE,
  VERDICT_RULES,
} from "@/lib/signals12";

export const Signals12Section = () => (
  <Card>
    <header className="mb-4">
      <h3 className="text-lg font-semibold text-gray-900">12 기술 시그널 + Verdict</h3>
      <p className="mt-1 text-sm text-gray-500">
        `compute_signals(code).signals` 의 12 전략 + 가중합 종합 판정. 단일 시그널 의존 금지 — 종합 verdict 우선.
      </p>
    </header>

    <div className="overflow-x-auto">
      <table className="min-w-full border-collapse text-sm">
        <thead>
          <tr className="bg-gray-50">
            <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">#</th>
            <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">전략</th>
            <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">매수 조건</th>
            <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">매도 조건</th>
            <th className="border border-gray-200 px-3 py-2 text-right text-xs font-semibold text-gray-700">매수 W</th>
            <th className="border border-gray-200 px-3 py-2 text-right text-xs font-semibold text-gray-700">매도 W</th>
          </tr>
        </thead>
        <tbody>
          {SIGNALS_12.map((s) => (
            <tr key={s.no}>
              <td className="border border-gray-200 px-3 py-2 text-xs text-gray-500">{s.no}</td>
              <td className="border border-gray-200 px-3 py-2 text-xs font-medium text-gray-900">
                {s.name}
              </td>
              <td className="border border-gray-200 px-3 py-2 text-xs text-gray-700">{s.buyCondition}</td>
              <td className="border border-gray-200 px-3 py-2 text-xs text-gray-700">{s.sellCondition}</td>
              <td className="border border-gray-200 px-3 py-2 text-right text-xs tabular-nums text-emerald-700">
                {s.buyWeight ?? "—"}
              </td>
              <td className="border border-gray-200 px-3 py-2 text-right text-xs tabular-nums text-red-700">
                {s.sellWeight ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>

    <section className="mt-6">
      <h4 className="mb-2 text-sm font-semibold text-gray-700">Verdict 산정 룰</h4>
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr className="bg-gray-50">
              <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">verdict</th>
              <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">매수 가중합</th>
              <th className="border border-gray-200 px-3 py-2 text-left text-xs font-semibold text-gray-700">매도 가중합</th>
            </tr>
          </thead>
          <tbody>
            {VERDICT_RULES.map((v) => (
              <tr key={v.verdict}>
                <td className="border border-gray-200 px-3 py-2">
                  <Badge color={v.color}>{v.verdict}</Badge>
                </td>
                <td className="border border-gray-200 px-3 py-2 text-xs text-gray-700">{v.buyCondition}</td>
                <td className="border border-gray-200 px-3 py-2 text-xs text-gray-700">{v.sellCondition}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>

    <section className="mt-6">
      <h4 className="mb-2 text-sm font-semibold text-gray-700">활용 룰</h4>
      <ul className="space-y-1 text-xs text-gray-700">
        {SIGNAL_USAGE_RULES.map((r, i) => (
          <li
            key={i}
            className="flex gap-2"
            dangerouslySetInnerHTML={{ __html: `<span class="text-gray-400">·</span> ${formatBold(r)}` }}
          />
        ))}
      </ul>
    </section>

    <p className="mt-4 rounded bg-violet-50 px-3 py-2 text-xs text-violet-900">
      <span className="font-semibold">VCP 패턴 (미너비니 SEPA 부가정보):</span> {VCP_NOTE}
    </p>
  </Card>
);

const formatBold = (text: string): string =>
  text.replace(/\*\*(.+?)\*\*/g, '<strong class="text-gray-900">$1</strong>');
