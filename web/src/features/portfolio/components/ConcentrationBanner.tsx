import type { ConcentrationAlertOut } from "@/types/api";

interface ConcentrationBannerProps {
  alerts: ConcentrationAlertOut[];
  thresholdPct: number;
}

export const ConcentrationBanner = ({
  alerts,
  thresholdPct,
}: ConcentrationBannerProps) => {
  if (alerts.length === 0) return null;

  const hasCritical = alerts.some((a) => a.severity === "critical");
  const tone = hasCritical
    ? "border-red-200 bg-red-50 text-red-900"
    : "border-amber-200 bg-amber-50 text-amber-900";
  const title = hasCritical
    ? "집중도 경고 — 일부 종목이 critical 수준"
    : `집중도 경고 (${thresholdPct.toFixed(0)}% 초과)`;

  return (
    <div className={`rounded-md border px-4 py-3 ${tone}`}>
      <p className="text-sm font-semibold">{title}</p>
      <ul className="mt-2 space-y-1 text-sm">
        {alerts.map((a) => (
          <li key={a.code} className="flex items-baseline gap-2">
            <span
              className={
                a.severity === "critical"
                  ? "font-semibold text-red-700"
                  : "text-amber-800"
              }
            >
              {a.severity === "critical" ? "●" : "○"}
            </span>
            <span>{a.message}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};
