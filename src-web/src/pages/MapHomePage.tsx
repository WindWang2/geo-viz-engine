'use client';

import { Outlet } from 'react-router-dom';
import WellMap from '../components/WellMap';
import DetailPanel from '../components/DetailPanel';
import BottomTabBar from '../components/BottomTabBar';

export default function MapHomePage() {
  return (
    <div className="flex h-screen w-full flex-col overflow-hidden">
      {/* Main content: map fills remaining space */}
      <div className="relative min-h-0 flex-1">
        <WellMap />
        {/* DetailPanel overlays when a well is selected */}
        <DetailPanel />
      </div>

      {/* Bottom tab bar */}
      <BottomTabBar />

      {/* Nested route outlet for sub-pages (GeologicalProfileViewer renders inside this outlet) */}
      <Outlet />
    </div>
  );
}