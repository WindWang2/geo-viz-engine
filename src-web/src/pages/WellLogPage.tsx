import { useState, useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useWellStore } from "../stores/useWellStore";
import { useApi } from "../hooks/useApi";
import { WellLogViewer } from "../components/well-log";
import type { WellLogData, WellMetadata } from "../components/well-log";

interface GenerateDataResponse {
  wells: Array<{
    well_id: string;
    well_name: string;
    depth_start: number;
    depth_end: number;
    curve_names: string[];
  }>;
  generated_count: number;
  message: string;
}

export default function WellLogPage() {
  const { t } = useTranslation();
  const { wells, setWells, isLoading, setLoading, error, setError } = useWellStore();
  const { request } = useApi();

  const [selectedWellId, setSelectedWellId] = useState<string | null>(null);
  const [wellLogData, setWellLogData] = useState<WellLogData | null>(null);
  const [wellLoading, setWellLoading] = useState(false);
  const [wellError, setWellError] = useState<string | null>(null);

  // Auto-load list of cached wells on page load (includes static mock data)
  useEffect(() => {
    async function loadCachedWells() {
      if (wells.length > 0) return; // already loaded
      setLoading(true);
      setError(null);
      try {
        const data = await request<WellMetadata[]>("/api/data/list", {
          method: "GET",
        });
        if (data.length > 0) {
          setWells(data);
        }
      } catch (err) {
        // Don't set error for initial load - it's okay if it fails
        console.warn("Failed to load cached wells:", err);
      } finally {
        setLoading(false);
      }
    }
    loadCachedWells();
  }, [request, wells.length, setWells, setLoading, setError]);

  async function handleGenerate() {
    setLoading(true);
    setError(null);
    setSelectedWellId(null);
    setWellLogData(null);
    try {
      const data = await request<GenerateDataResponse>("/api/data/generate", {
        method: "POST",
      });
      setWells(data.wells);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate data");
    } finally {
      setLoading(false);
    }
  }

  const handleSelectWell = useCallback(async (wellId: string) => {
    setSelectedWellId(wellId);
    setWellLogData(null);
    setWellError(null);
    setWellLoading(true);
    try {
      const data = await request<WellLogData>(`/api/data/well/${wellId}`);
      setWellLogData(data);
    } catch (err) {
      setWellError(err instanceof Error ? err.message : "Failed to load well data");
    } finally {
      setWellLoading(false);
    }
  }, [request]);

  function handleBack() {
    setSelectedWellId(null);
    setWellLogData(null);
    setWellError(null);
  }

  // ── Viewer mode ──────────────────────────────────────────────────────────
  if (selectedWellId) {
    const wellName = wells.find((w) => w.well_id === selectedWellId)?.well_name ?? selectedWellId;

    return (
      <div className="flex flex-col h-full p-4">
        <div className="flex items-center gap-3 mb-4 flex-shrink-0">
          <button
            onClick={handleBack}
            className="text-sm text-geo-accent hover:underline"
          >
            ← {t("page.wellLog.backToList")}
          </button>
          <h1 className="text-xl font-semibold text-geo-text">{wellName}</h1>
        </div>

        {wellError && (
          <div className="mb-4 p-3 bg-geo-red/10 border border-geo-red/30 rounded-lg text-geo-red text-sm">
            {wellError}
          </div>
        )}

        {wellLoading && (
          <div className="flex items-center justify-center h-48 text-geo-muted text-sm">
            {t("page.wellLog.loadingWell")}
          </div>
        )}

        {wellLogData && !wellLoading && (
          <div className="flex-1 overflow-hidden border border-geo-border rounded-lg">
            <WellLogViewer wellData={wellLogData} />
          </div>
        )}
      </div>
    );
  }

  // ── List mode ────────────────────────────────────────────────────────────
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-geo-text">
          {t("page.wellLog.title")}
        </h1>
        <button
          onClick={handleGenerate}
          disabled={isLoading}
          className="inline-flex items-center gap-2 bg-geo-accent hover:bg-geo-accent/80 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {isLoading ? t("page.wellLog.generating") : t("page.wellLog.generateData")}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-geo-red/10 border border-geo-red/30 rounded-lg text-geo-red text-sm">
          {error}
        </div>
      )}

      {wells.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-geo-muted">
          <p className="text-sm">{t("page.wellLog.noData")}</p>
        </div>
      ) : (
        <ul className="space-y-2">
          {wells.map((well) => (
            <li
              key={well.well_id}
              className="p-3 bg-geo-surface border border-geo-border rounded-lg text-sm cursor-pointer hover:border-geo-accent transition-colors"
              onClick={() => handleSelectWell(well.well_id)}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-geo-text">{well.well_name}</span>
                <span className="text-geo-muted text-xs">{well.well_id}</span>
              </div>
              <div className="text-geo-muted text-xs mt-1">
                {well.depth_start}m - {well.depth_end.toFixed(0)}m |{" "}
                {well.curve_names.join(", ")}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
