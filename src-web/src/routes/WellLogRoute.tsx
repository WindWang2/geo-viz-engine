'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { WellLogViewer } from '../components/well-log';
import type { WellLogData } from '../components/well-log';

/**
 * Standalone route-level wrapper for the /well/:well_id route.
 * Renders behind DetailPanel (via MapHomePage.Outlet stacking).
 * Displays a dimmed/grayscale ghost copy of the well log as visual affordance
 * that the URL changed — giving the user a cue that navigation occurred.
 */
export function WellLogRoute() {
  const { well_id } = useParams<{ well_id: string }>();
  const [data, setData] = useState<WellLogData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!well_id) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`/api/data/well/${encodeURIComponent(well_id)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<WellLogData>;
      })
      .then((d) => { if (!cancelled) { setData(d); setLoading(false); } })
      .catch((e) => { if (!cancelled) { setError(String(e)); setLoading(false); } });
    return () => { cancelled = true; };
  }, [well_id]);

  if (loading) return <div className="p-6 text-gray-400 animate-pulse">加载中…</div>;
  if (error) return <div className="p-6 text-red-500">错误：{error}</div>;
  if (!data) return null;

  return (
    /* Layered behind DetailPanel so pointer events pass through to the panel */
    <div className="pointer-events-none absolute inset-0 z-10 overflow-hidden">
      <div className="h-full w-full opacity-40 grayscale brightness-75">
        <WellLogViewer wellData={data} />
      </div>
    </div>
  );
}