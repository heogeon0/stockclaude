import { Card } from "@tremor/react";
import { AppliedWeightsLookup } from "./AppliedWeightsLookup";
import { OverridesTable } from "./OverridesTable";
import { ScoreWeightDefaultsTable } from "./ScoreWeightDefaultsTable";

export const WeightsSection = () => (
  <Card>
    <header className="mb-4">
      <h3 className="text-lg font-semibold text-gray-900">스코어 가중치</h3>
      <p className="mt-1 text-sm text-gray-600">
        종합 스코어는 5차원(재무·산업·경제·기술·밸류에이션) 가중평균. 출처(source) 4종 — 기본값/사용자/Claude/백테스트.
      </p>
      <p className="mt-2 rounded bg-amber-50 px-3 py-2 text-xs text-amber-900">
        <span className="font-semibold">v17 변경:</span> 단타/스윙/중장기/모멘텀 4타임프레임 폐지. 모든 종목 단일 룰
        <strong className="px-1">(swing 기본값 유지: 재무 30 / 산업 25 / 경제 20 / 기술 5 / 밸류 20)</strong>
        + 변동성×재무 12셀 매트릭스로 액션 차등. DB 의 4타임프레임 표는 호환성 보존용.
      </p>
    </header>

    <section>
      <h4 className="mb-2 text-sm font-semibold text-gray-700">
        기본값 매트릭스
        <span className="ml-2 text-xs font-normal text-amber-700">— swing 행이 v17 baseline</span>
      </h4>
      <ScoreWeightDefaultsTable />
    </section>

    <section className="mt-6 border-t border-gray-100 pt-4">
      <h4 className="mb-2 text-sm font-semibold text-gray-700">종목별 적용 가중치 조회</h4>
      <AppliedWeightsLookup />
    </section>

    <section className="mt-6 border-t border-gray-100 pt-4">
      <h4 className="mb-2 text-sm font-semibold text-gray-700">활성 override</h4>
      <OverridesTable />
    </section>
  </Card>
);
