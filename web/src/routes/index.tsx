import { createBrowserRouter } from "react-router-dom";
import App from "@/App";
import { PortfolioPage } from "@/features/portfolio/PortfolioPage";
import { ReviewPage } from "@/features/review/ReviewPage";
import { SkillsPage } from "@/features/skills/SkillsPage";
import { StrategyPage } from "@/features/strategy/StrategyPage";
import { TodayPage } from "@/features/today/TodayPage";
import { TradesPage } from "@/features/trades/TradesPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <PortfolioPage /> },
      { path: "today", element: <TodayPage /> },
      { path: "trades", element: <TradesPage /> },
      { path: "review", element: <ReviewPage /> },
      { path: "strategy", element: <StrategyPage /> },
      { path: "skills", element: <SkillsPage /> },
    ],
  },
]);
