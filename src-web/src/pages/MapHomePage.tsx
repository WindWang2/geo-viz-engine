import { useEffect, useState } from 'react';
import { useWellStore } from '../stores/useWellStore';
import { useMapStore } from '../stores/useMapStore';
import { useApi } from '../hooks/useApi';
import WellMap from '../components/map/WellMap';
import DetailPanel from '../components/panel/DetailPanel';
import type { WellLogData } from '../components/well-log/types';

export default function MapHomePage() {
  const { wells, setWells } = useWellStore();
  const { panelOpen, selectedWellId, selectWell, closePanel } = useMapStore();
  const { request } = useApi();

  const [wellData, setWellData] = useState<WellLogData | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [realWells, setRealWells] = useState<Array<{well_name: string; longitude: number; latitude: number}>>([]);

  // Load wells list on mount
  useEffect(() => {
    if (wells.length > 0) return;
    (async () => {
      try {
        const data = await request<any[]>('/api/data/list');
        if (Array.isArray(data) && data.length > 0) {
          setWells(data);
        } else {
          // Trigger generation if no cached wells
          const gen = await request<any>('/api/data/generate', { method: 'POST' });
          setWells(gen?.wells ?? []);
        }
      } catch {
        // Silently fail on initial load
      }
    })();
  }, []);

  // Load real well coordinates on mount
  useEffect(() => {
    (async () => {
      try {
        const data = await request<Array<{well_name: string; longitude: number; latitude: number}>>('/api/data/real-wells');
        if (Array.isArray(data) && data.length > 0) {
          setRealWells(data);
        }
      } catch {
        // Silently fail
      }
    })();
  }, [request]);

  // Watch selectedWellId → fetch full well data
  useEffect(() => {
    if (!selectedWellId) {
      setWellData(null);
      return;
    }
    setDetailLoading(true);
    setDetailError(null);
    request<WellLogData>(`/api/data/well/${selectedWellId}`)
      .then(setWellData)
      .catch((e) => setDetailError(e?.message ?? '加载失败'))
      .finally(() => setDetailLoading(false));
  }, [selectedWellId, request]);

  const selectedWell = wells.find((w) => w.well_id === selectedWellId);
  const selectedWellName = selectedWell?.well_name ?? selectedWellId ?? '';

  return (
    <div className="relative w-full h-full overflow-hidden">
      <WellMap
        wells={wells}
        realWells={realWells}
        onWellClick={(id) => selectWell(id)}
        selectedWellId={selectedWellId}
      />

      <DetailPanel
        wellId={selectedWellId ?? ''}
        wellName={selectedWellName}
        wellData={wellData}
        open={panelOpen}
        loading={detailLoading}
        error={detailError}
        onClose={closePanel}
        onBack={closePanel}
      />
    </div>
  );
}
