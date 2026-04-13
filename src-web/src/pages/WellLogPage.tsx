import { useTranslation } from "react-i18next";
import { useWellStore } from "../stores/useWellStore";
import { useApi } from "../hooks/useApi";

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

  async function handleGenerate() {
    setLoading(true);
    setError(null);
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
              className="p-3 bg-geo-surface border border-geo-border rounded-lg text-sm"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-geo-text">{well.well_name}</span>
                <span className="text-geo-muted text-xs">{well.well_id}</span>
              </div>
              <div className="text-geo-muted text-xs mt-1">
                {well.depth_start}m - {well.depth_end.toFixed(0)}m | {" "}
                {well.curve_names.join(", ")}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
