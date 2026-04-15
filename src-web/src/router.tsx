import { createBrowserRouter } from "react-router-dom";
import MapHomePage from "./pages/MapHomePage";
import WellTablePage from "./pages/WellTablePage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <MapHomePage />,
  },
  {
    // Deep-link to well detail: same page, DetailPanel reads well_id param and opens
    path: "/well/:well_id",
    element: <MapHomePage />,
  },
  {
    path: "/table",
    element: <WellTablePage />,
  },
  {
    path: "*",
    loader: () => { throw new Response("", { status: 302, headers: { Location: "/" } }); },
  },
]);

export default router;