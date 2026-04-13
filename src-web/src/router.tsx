import { createBrowserRouter } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import HomePage from "./pages/HomePage";
import WellLogPage from "./pages/WellLogPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "well-log", element: <WellLogPage /> },
    ],
  },
]);

export default router;
