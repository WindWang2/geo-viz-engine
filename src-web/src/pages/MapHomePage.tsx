'use client';

import WellMap from '../components/WellMap';
import DetailPanel from '../components/DetailPanel';
import BottomTabBar from '../components/BottomTabBar';

export default function MapHomePage() {
  return (
    <div className="flex h-screen w-full flex-col overflow-hidden">
      <div className="relative min-h-0 flex-1">
        <WellMap />
        {/* DetailPanel fetches and renders WellLogViewer directly when a well is selected */}
        <DetailPanel />
      </div>
      <BottomTabBar />
    </div>
  );
}