import { Outlet } from "react-router-dom";
import Toolbar from "../common/Toolbar";
import Sidebar from "../common/Sidebar";
import StatusBar from "../common/StatusBar";

export default function AppLayout() {
  return (
    <div className="flex flex-col h-full bg-geo-bg text-geo-text">
      <Toolbar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
      <StatusBar />
    </div>
  );
}
