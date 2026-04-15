import { RouterProvider } from "react-router-dom";
import router from "./router";
import "./i18n";
import { LithologyPatterns } from "./components/well-log";

export default function App() {
  return (
    <>
      <LithologyPatterns />
      <RouterProvider router={router} />
    </>
  );
}
