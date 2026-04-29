import { NavLink, Outlet } from "react-router-dom";

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
}

const NAV_ITEMS: readonly NavItem[] = [
  { to: "/", label: "포트폴리오", end: true },
  { to: "/today", label: "데일리 리포트" },
  { to: "/trades", label: "매매 기록" },
  { to: "/review", label: "주간 회고" },
  { to: "/strategy", label: "전략·로직" },
];

const REFERENCE_ITEMS: readonly NavItem[] = [
  { to: "/skills", label: "스킬 매뉴얼" },
];

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-2 text-sm font-medium transition-colors ${
    isActive
      ? "bg-blue-50 text-blue-700"
      : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
  }`;

const App = () => {
  return (
    <div className="flex min-h-full bg-gray-50">
      <aside className="flex w-56 shrink-0 flex-col border-r border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-5 py-4">
          <h1 className="text-lg font-semibold text-gray-900">stock-manager</h1>
          <p className="text-xs text-gray-500">dashboard</p>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-3">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
              {item.label}
            </NavLink>
          ))}
          <div className="mt-auto border-t border-gray-100 pt-3">
            <p className="px-3 pb-1 text-xs font-medium uppercase tracking-wide text-gray-400">
              참고
            </p>
            {REFERENCE_ITEMS.map((item) => (
              <NavLink key={item.to} to={item.to} className={navClass}>
                {item.label}
              </NavLink>
            ))}
          </div>
        </nav>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="mx-auto max-w-7xl px-6 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default App;
