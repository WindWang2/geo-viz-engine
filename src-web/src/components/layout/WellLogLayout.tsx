import { Outlet } from "react-router-dom";
import BottomTabBar from "../common/BottomTabBar";

export default function WellLogLayout() {
  return (
    <div className="flex flex-col h-full w-full overflow-hidden">
      <header className="flex-initial flex items-center justify-end px-4 py-2 border-b border-geo-border bg-geo-surface z-10">
        <BottomTabBar />
      </header>
      <main className="flex-1 overflow-hidden relative">
        <Outlet />
      </main>
    </div>
  );
}
