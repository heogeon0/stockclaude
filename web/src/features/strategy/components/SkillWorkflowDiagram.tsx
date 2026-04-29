/**
 * v17 스킬 워크플로우 다이어그램 — 8 skill (1 hub + 6 active + 1 deprecated)
 * + 3계층 base cascade (경제 1d → 산업 7d → 종목 30d).
 *
 * 핵심 포인트:
 * - stock-research 가 공통 6차원 분석 모듈 (daily / discover 가 호출)
 * - base 만기 도래 시 하위 skill 호출이 상위 base 자동 연쇄 갱신 (점선)
 * - stock-momentum 은 DEPRECATED (회색 + 취소선)
 */
export const SkillWorkflowDiagram = () => (
  <svg
    viewBox="0 0 880 480"
    role="img"
    aria-label="v17 스킬 워크플로우 다이어그램"
    className="w-full max-w-[880px]"
  >
    <defs>
      <marker
        id="arrow"
        viewBox="0 0 10 10"
        refX="9"
        refY="5"
        markerWidth="6"
        markerHeight="6"
        orient="auto-start-reverse"
      >
        <path d="M0,0 L10,5 L0,10 z" fill="#475569" />
      </marker>
      <marker
        id="arrow-dashed"
        viewBox="0 0 10 10"
        refX="9"
        refY="5"
        markerWidth="6"
        markerHeight="6"
        orient="auto-start-reverse"
      >
        <path d="M0,0 L10,5 L0,10 z" fill="#d97706" />
      </marker>
    </defs>

    {/* Row 1: Hub */}
    <SkillNode
      x={340}
      y={20}
      w={200}
      h={60}
      title="/stock"
      subtitle="허브 (공통 규칙·MCP 인벤토리)"
      variant="hub"
    />

    {/* Row 2: Entry points */}
    <SkillNode
      x={60}
      y={130}
      w={180}
      h={70}
      title="/stock-daily"
      subtitle="보유·Pending 일일 점검"
      variant="entry"
    />
    <SkillNode
      x={620}
      y={130}
      w={180}
      h={70}
      title="/stock-discover"
      subtitle="신규 발굴 Top 3~5"
      variant="entry"
    />

    {/* Row 3: Common module */}
    <SkillNode
      x={340}
      y={250}
      w={200}
      h={70}
      title="/stock-research"
      subtitle="공통 6차원 심도 분석"
      variant="module"
    />

    {/* Row 4: Base layers (3-tier cascade) */}
    <BaseNode x={20} y={380} w={220} h={70} title="base-economy" expiry="만기 1일" />
    <BaseNode x={330} y={380} w={220} h={70} title="base-industry" expiry="만기 7일" />
    <BaseNode x={640} y={380} w={220} h={70} title="base-stock" expiry="만기 30일" />

    {/* Deprecated */}
    <DeprecatedNode
      x={620}
      y={20}
      w={200}
      h={60}
      title="stock-momentum"
      subtitle="DEPRECATED (v17)"
    />

    {/* hub → entries (정의 참조) */}
    <Arrow x1={400} y1={80} x2={180} y2={130} label="" />
    <Arrow x1={480} y1={80} x2={700} y2={130} label="" />
    <Arrow x1={440} y1={80} x2={440} y2={250} label="" />

    {/* entries → research (호출) */}
    <Arrow x1={180} y1={200} x2={380} y2={260} label="호출" />
    <Arrow x1={700} y1={200} x2={500} y2={260} label="호출" />

    {/* research → base layers (만기 시 갱신) */}
    <DashedArrow
      d="M 360,320 C 200,360 150,360 130,380"
      label="만기 시 자동 호출"
    />
    <DashedArrow d="M 440,320 L 440,380" label="" />
    <DashedArrow
      d="M 520,320 C 680,360 730,360 750,380"
      label=""
    />

    {/* base cascade — 상위 base 가 하위 base 에 의존 */}
    <Arrow x1={240} y1={415} x2={330} y2={415} label="참조" />
    <Arrow x1={550} y1={415} x2={640} y2={415} label="참조" />
  </svg>
);

interface NodeProps {
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  subtitle: string;
  variant?: "hub" | "entry" | "module";
}

const VARIANT_FILL = {
  hub: "#f1f5f9",
  entry: "#eff6ff",
  module: "#f5f3ff",
};
const VARIANT_STROKE = {
  hub: "#64748b",
  entry: "#3b82f6",
  module: "#8b5cf6",
};
const VARIANT_TEXT = {
  hub: "#334155",
  entry: "#1d4ed8",
  module: "#6d28d9",
};

const SkillNode = ({ x, y, w, h, title, subtitle, variant = "entry" }: NodeProps) => (
  <g>
    <rect
      x={x}
      y={y}
      width={w}
      height={h}
      rx={8}
      fill={VARIANT_FILL[variant]}
      stroke={VARIANT_STROKE[variant]}
      strokeWidth={1.5}
    />
    <text
      x={x + w / 2}
      y={y + 26}
      textAnchor="middle"
      fill={VARIANT_TEXT[variant]}
      fontSize={14}
      fontWeight={600}
    >
      {title}
    </text>
    <text
      x={x + w / 2}
      y={y + 46}
      textAnchor="middle"
      fill={VARIANT_TEXT[variant]}
      fontSize={11}
    >
      {subtitle}
    </text>
  </g>
);

const BaseNode = ({
  x,
  y,
  w,
  h,
  title,
  expiry,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  expiry: string;
}) => (
  <g>
    <rect
      x={x}
      y={y}
      width={w}
      height={h}
      rx={8}
      fill="#ecfdf5"
      stroke="#10b981"
      strokeWidth={1.5}
    />
    <text
      x={x + w / 2}
      y={y + 28}
      textAnchor="middle"
      fill="#047857"
      fontSize={13}
      fontWeight={600}
    >
      {title}
    </text>
    <text
      x={x + w / 2}
      y={y + 48}
      textAnchor="middle"
      fill="#059669"
      fontSize={11}
    >
      {expiry}
    </text>
  </g>
);

const DeprecatedNode = ({ x, y, w, h, title, subtitle }: NodeProps) => (
  <g>
    <rect
      x={x}
      y={y}
      width={w}
      height={h}
      rx={8}
      fill="#f9fafb"
      stroke="#9ca3af"
      strokeWidth={1.5}
      strokeDasharray="4 3"
    />
    <text
      x={x + w / 2}
      y={y + 26}
      textAnchor="middle"
      fill="#6b7280"
      fontSize={13}
      fontWeight={500}
      textDecoration="line-through"
    >
      {title}
    </text>
    <text
      x={x + w / 2}
      y={y + 46}
      textAnchor="middle"
      fill="#9ca3af"
      fontSize={10}
    >
      {subtitle}
    </text>
  </g>
);

const Arrow = ({
  x1,
  y1,
  x2,
  y2,
  label,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  label: string;
}) => {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  return (
    <g>
      <line
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke="#475569"
        strokeWidth={1.5}
        markerEnd="url(#arrow)"
      />
      {label && (
        <text x={mx} y={my - 4} textAnchor="middle" fill="#64748b" fontSize={10}>
          {label}
        </text>
      )}
    </g>
  );
};

const DashedArrow = ({ d, label }: { d: string; label: string }) => (
  <g>
    <path
      d={d}
      fill="none"
      stroke="#d97706"
      strokeWidth={1.5}
      strokeDasharray="6 4"
      markerEnd="url(#arrow-dashed)"
    />
    {label && (
      <text x={290} y={355} textAnchor="middle" fill="#b45309" fontSize={10}>
        {label}
      </text>
    )}
  </g>
);
