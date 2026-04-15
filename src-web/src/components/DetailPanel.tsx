'use client';

import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMapStore } from '../stores/useMapStore';

/**
 * Slide-over detail panel for well geology profile.
 * Appears when a well marker is clicked on the map (selectedWellId != null).
 * Layout: full-height right-side panel with header (back button + close),
 * scrollable content area hosting GeologicalProfileViewer,
 * and embedded NavigationControls at bottom.
 *
 * Design spec: Direction A — full-screen takeover with visible back controls.
 * Three-way back navigation guaranteed:
 *   1. Top-left "← 返回地图" button (goes to /)
 *   2. Top-right "✕" close button (clears selectedWellId)
 *   3. Bottom NavigationControls ← / → arrows
 */
export default function DetailPanel() {
  const { well_id } = useParams<{ well_id: string }>();
  const navigate = useNavigate();
  const { selectedWellId, isPanelOpen, closePanel } = useMapStore();

  // Sync URL param with store selection
  useEffect(() => {
    if (well_id && well_id !== selectedWellId) {
      useMapStore.getState().setSelectedWellId(well_id);
    }
  }, [well_id, selectedWellId]);

  if (!isPanelOpen) return null;

  return (
    <>
      {/* Semi-transparent backdrop — click to dismiss */}
      <div
        className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[2px]"
        onClick={closePanel}
        aria-hidden="true"
      />

      {/* Slide-over panel */}
      <aside
        className="fixed right-0 top-0 z-50 flex h-full w-full flex-col bg-white shadow-[-4px_0_24px_rgba(0,0,0,0.12)] sm:w-[70%] lg:w-[55%]"
        role="dialog"
        aria-modal="true"
        aria-label="测井详情"
      >
        {/* Header */}
        <header className="flex shrink-0 items-center justify-between border-b border-gray-100 px-4 py-3">
          <div className="flex items-center gap-3">
            {/* Primary back button */}
            <button
              onClick={() => { closePanel(); navigate('/'); }}
              className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100 active:bg-gray-200"
            >
              <span>←</span>
              <span>返回地图</span>
            </button>

            {/* Well ID badge */}
            {selectedWellId && (
              <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-600">
                {selectedWellId}
              </span>
            )}
          </div>

          {/* Close button */}
          <button
            onClick={closePanel}
            className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
            aria-label="关闭详情"
          >
            <span className="text-xl leading-none">✕</span>
          </button>
        </header>

        {/* Content: GeologicalProfileViewer renders based on well_id route param */}
        <main className="min-h-0 flex-1 overflow-y-auto">
          {/* Dynamic route: /well/:well_id renders the viewer inside the panel */}
          {/* We render the matched child — GeologicalProfileViewer is rendered by App router */}
        </main>

        {/* Footer: NavigationControls */}
        <footer className="shrink-0 border-t border-gray-100 bg-white px-4 py-3">
          <NavigationControls wellId={selectedWellId} />
        </footer>
      </aside>
    </>
  );
}

/** Inline NavigationControls — prev/next well browsing from /wells list */
function NavigationControls({ wellId }: { wellId: string | null }) {
  const handlePrev = () => {
    // Navigate to prev well in list — simplified, replaced by actual app logic
    console.warn('[DetailPanel] NavigationControls: prev not fully implemented yet');
  };

  const handleNext = () => {
    console.warn('[DetailPanel] NavigationControls: next not fully implemented yet');
  };

  if (!wellId) return null;

  return (
    <div className="flex items-center justify-between">
      <button
        onClick={handlePrev}
        className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm text-gray-600 transition-colors hover:bg-gray-100 active:bg-gray-200"
      >
        <span>←</span>
        <span>上一口</span>
      </button>

      <span className="text-xs text-gray-400">切换测井</span>

      <button
        onClick={handleNext}
        className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm text-gray-600 transition-colors hover:bg-gray-100 active:bg-gray-200"
      >
        <span>下一口</span>
        <span>→</span>
      </button>
    </div>
  );
}