import { createBrowserRouter } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import WellLogLayout from "./components/layout/WellLogLayout";
import DashboardPage from "./pages/DashboardPage";
import MapHomePage from "./pages/MapHomePage";
import WellTablePage from "./pages/WellTablePage";
import LaoLong1Page from "./pages/LaoLong1Page";

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

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "dashboard", element: <DashboardPage /> },
      { 
        path: "well-log", 
        element: <WellLogLayout />,
        children: [
          { index: true, element: <MapHomePage /> },
          { path: "table", element: <WellTablePage /> },
        ]
      },
      { path: "seismic", element: <PlaceholderPage moduleName="地震剖面" /> },
      { path: "contour", element: <PlaceholderPage moduleName="等值线图" /> },
      { path: "3d-viewer", element: <PlaceholderPage moduleName="三维地质" /> },
      { path: "map", element: <MapHomePage /> },
      { path: "laolong1", element: <LaoLong1Page /> },
    ],
  },
  {
    path: "*",
    loader: () => {
      throw new Response("", { status: 302, headers: { Location: "/" } });
    },
  },
]);

export default router;
