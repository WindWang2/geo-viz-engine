import { Outlet } from 'react-router-dom';
import BottomTabBar from '../common/BottomTabBar';

export default function AppLayout() {
  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-geo-bg">
      <header className="flex-initial flex items-center justify-end px-4 py-2 border-b border-geo-border bg-geo-surface">
        <BottomTabBar />
      </header>
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}