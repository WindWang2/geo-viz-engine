import { createBrowserRouter } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import DashboardPage from "./pages/DashboardPage";
import WellLogPage from "./pages/WellLogPage";
import MapHomePage from "./pages/MapHomePage";
import WellTablePage from "./pages/WellTablePage";

/** 占位页 — 各模块建设期间 */
function PlaceholderPage({ moduleName }: { moduleName: string }) {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <p className="text-lg font-medium text-geo-text mb-2">{moduleName}</p>
        <p className="text-sm text-geo-muted">[ 即将到来 ]</p>
      </div>
    </div>
  );
}

/*
  路由架构（设计文档 §3.4）：
    / (首页仪表盘)          → DashboardPage + AppLayout
    /well-log (测井可视化)  → WellLogPage   + AppLayout
    /seismic  (地震剖面)    → Placeholder   + AppLayout
    /contour  (等值线图)    → Placeholder   + AppLayout
    /3d-viewer(三围地质)    → Placeholder   + AppLayout
    /map (地图总览)         → MapHomePage   + AppLayout

  以下路由不受 AppLayout 约束，保持独立：
    /table (数据表)         → WellTablePage（BottomTabBar 移动端风格）
    /well/:well_id (井详情) → MapHomePage（同 DetailPanel slide-over）
*/
const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "well-log", element: <WellLogPage /> },
      { path: "seismic", element: <PlaceholderPage moduleName="地震剖面" /> },
      { path: "contour", element: <PlaceholderPage moduleName="等值线图" /> },
      { path: "3d-viewer", element: <PlaceholderPage moduleName="三维地质" /> },
      { path: "map", element: <MapHomePage /> },
    ],
  },
  // 这两条路由不走 AppLayout，保持独立
  { path: "/table", element: <WellTablePage /> },
  { path: "/well/:well_id", element: <MapHomePage /> },
  {
    path: "*",
    loader: () => {
      throw new Response("", { status: 302, headers: { Location: "/" } });
    },
  },
]);

export default router;