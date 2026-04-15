'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMapStore } from '../stores/useMapStore';
import { WellLogViewer } from './well-log';
import type { WellLogData } from './well-log';
import { useApi } from '../hooks/useApi';

/**
 * Slide-over detail panel for well geology profile.
 * Appears when a well marker is clicked on the map (selectedWellId != null).
 * Layout: full-height right-side panel with header (back button + close),
 * scrollable content area hosting WellLogViewer,
 * and embedded NavigationControls at bottom.
 *
 * Design spec: Direction A — full-screen takeover with visible back controls.
 * Three-way back navigation guaranteed:
 *   1. Top-left "← 返回地图" button (goes to /)
 *   2. Top-right "✕" close button (clears selectedWellId)
 *   3. Bottom NavigationControls ← / → arrows
 *
 * WellLogViewer now renders directly inside the panel rather than via routing.
 */
export default function DetailPanel() {
  const { well_id } = useParams<{ well_id: string }>();
  const navigate = useNavigate();
  const { selectedWellId, isPanelOpen, closePanel } = useMapStore();
  const { request } = useApi();

  // Fetch well data when panel opens with a selected well
  const [wellData, setWellData] = useState<WellLogData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isPanelOpen || !selectedWellId) {
      setWellData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setWellData(null);

    async function loadWell() {
      try {
        const d = await request<WellLogData>(`/api/data/well/${encodeURIComponent(selectedWellId!)}`);
        if (!cancelled) { setWellData(d); setLoading(false); }
      } catch (e) {
        if (!cancelled) { setError(e instanceof Error ? e.message : String(e)); setLoading(false); }
      }
    }
    loadWell();

    return () => { cancelled = true; };
  }, [isPanelOpen, selectedWellId, request]);

  // Sync URL param → store (covers both initial mount hydration and subsequent navigations)
  const hasHydrated = useRef(false);
  useEffect(() => {
    if (!hasHydrated.current && well_id) {
      hasHydrated.current = true;
      useMapStore.getState().setSelectedWellId(well_id);
    } else if (well_id && well_id !== selectedWellId) {
      useMapStore.getState().setSelectedWellId(well_id);
    }
  }, [well_id, selectedWellId]);

  if (!isPanelOpen) return null;

  return (
    <>
      {/* Backdrop */}
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
            <button
              onClick={() => { closePanel(); navigate('/', { replace: true }); }}
              className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100 active:bg-gray-200"
            >
              <span>←</span><span>返回地图</span>
            </button>
            {selectedWellId && (
              <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-600">
                {selectedWellId}
              </span>
            )}
          </div>
          <button
            onClick={closePanel}
            className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
            aria-label="关闭详情"
          >
            <span className="text-xl leading-none">✕</span>
          </button>
        </header>

        {/* Content: WellLogViewer renders here inside the panel */}
        <main className="min-h-0 flex-1 overflow-y-auto p-4">
          {loading && (
            <div className="flex h-48 items-center justify-center text-gray-400 text-sm animate-pulse">
              加载中…
            </div>
          )}
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
              错误：{error}
            </div>
          )}
          {wellData && !loading && (
            <div className="h-full border border-gray-200 rounded-lg overflow-hidden">
              <WellLogViewer wellData={wellData} />
            </div>
          )}
          {!loading && !error && !wellData && (
            <div className="flex h-48 items-center justify-center text-gray-400 text-sm">
              选择一口井查看详情
            </div>
          )}
        </main>

        {/* Footer: NavigationControls */}
        <footer className="shrink-0 border-t border-gray-100 bg-white px-4 py-3">
          <NavigationControls wellId={selectedWellId} />
        </footer>
      </aside>
    </>
  );
}

/** Inline NavigationControls — prev/next well browsing */
function NavigationControls({ wellId }: { wellId: string | null }) {
  const navigate = useNavigate();

  if (!wellId) return null;

  // Try parsing numeric suffix; show disabled nav if no pattern
  const numMatch = wellId.match(/\d+$/);
  const num = numMatch ? parseInt(numMatch[0], 10) : null;
  const hasPrev = num !== null && num > 1;

  const handleNav = (direction: 'prev' | 'next') => {
    if (!wellId || num === null) return;
    const newNum = direction === 'prev' ? num - 1 : num + 1;
    if (newNum <= 0) return;
    const newId = wellId.replace(/\d+$/, String(newNum));
    useMapStore.getState().setSelectedWellId(newId);
    navigate(`/well/${encodeURIComponent(newId)}`);
  };

  return (
    <div className="flex items-center justify-between">
      <button
        onClick={() => handleNav('prev')}
        disabled={!hasPrev}
        className={`flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm transition-colors ${
          hasPrev
            ? 'text-gray-600 hover:bg-gray-100 active:bg-gray-200'
            : 'text-gray-300 cursor-not-allowed'
        }`}
      >
        <span>←</span><span>上一口</span>
      </button>

      <span className="text-xs text-gray-400">切换测井</span>

      <button
        onClick={() => handleNav('next')}
        className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm text-gray-600 transition-colors hover:bg-gray-100 active:bg-gray-200"
      >
        <span>下一口</span><span>→</span>
      </button>
    </div>
  );
}