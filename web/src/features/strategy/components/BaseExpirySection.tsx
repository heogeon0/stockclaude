import { Badge, Card } from "@tremor/react";
import { BASE_EXPIRY_RULES, CASCADE_PRINCIPLE } from "@/lib/baseExpiryRules";

export const BaseExpirySection = () => (
  <Card>
    <header className="mb-4">
      <h3 className="text-lg font-semibold text-gray-900">Base 만기·갱신 규칙</h3>
      <p className="mt-1 text-sm text-gray-500">
        3계층 base — 경제(1일) / 산업(7일) / 종목(30일). 하위 skill 호출 시 만료 base 자동 연쇄 갱신.
      </p>
    </header>

    <div className="grid gap-3 md:grid-cols-3">
      {BASE_EXPIRY_RULES.map((rule) => (
        <div
          key={rule.layer}
          className="rounded-md border border-emerald-100 bg-emerald-50/50 p-4"
        >
          <div className="flex items-baseline justify-between">
            <h4 className="text-sm font-semibold text-emerald-900">{rule.label}</h4>
            <Badge color="emerald" size="xs">
              /{rule.skill}
            </Badge>
          </div>

          <div className="mt-3">
            <p className="text-xs font-medium text-gray-600">갱신 트리거</p>
            <ul className="mt-1 space-y-0.5 text-xs text-gray-700">
              {rule.triggers.map((t) => (
                <li key={t} className="flex gap-1.5">
                  <span className="text-emerald-600">·</span>
                  <span>{t}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-3">
            <p className="text-xs font-medium text-gray-600">만료 시 자동 호출자</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {rule.refreshedBy.map((s) => (
                <span
                  key={s}
                  className="rounded border border-emerald-200 bg-white px-1.5 py-0.5 font-mono text-xs text-emerald-700"
                >
                  /{s}
                </span>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>

    <p className="mt-4 rounded bg-amber-50 px-3 py-2 text-xs text-amber-800">
      <span className="font-semibold">Cascade 원칙:</span> {CASCADE_PRINCIPLE}
    </p>
  </Card>
);
