import { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useWellStore } from '../stores/useWellStore';
import { useMapStore } from '../stores/useMapStore';
import { Eye } from 'lucide-react';

export default function WellTablePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { wells } = useWellStore();
  const { selectWell } = useMapStore();
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    if (!search.trim()) return wells;
    const q = search.toLowerCase();
    return wells.filter(
      (w) =>
        w.well_id.toLowerCase().includes(q) ||
        w.well_name.toLowerCase().includes(q)
    );
  }, [wells, search]);

  const handleView = (wellId: string) => {
    selectWell(wellId);
    navigate('/');
  };

  return (
    <div className="flex flex-col h-full p-6 gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-geo-text">
          {t('page.table.title')}
        </h1>
        <input
          type="search"
          placeholder={t('page.table.searchPlaceholder')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="px-3 py-2 border border-geo-border rounded-lg text-sm w-64 focus:outline-none focus:border-geo-accent"
        />
      </div>

      <div className="flex-1 overflow-auto border border-geo-border rounded-lg">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-geo-surface text-left text-xs uppercase text-geo-muted border-b border-geo-border">
            <tr>
              <th className="px-4 py-3 font-medium">井号</th>
              <th className="px-4 py-3 font-medium">井名</th>
              <th className="px-4 py-3 font-medium">深度范围 (m)</th>
              <th className="px-4 py-3 font-medium">曲线</th>
              <th className="px-4 py-3 font-medium">经度</th>
              <th className="px-4 py-3 font-medium">纬度</th>
              <th className="px-4 py-3 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-geo-border">
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-geo-muted">
                  {t('page.table.noResults')}
                </td>
              </tr>
            )}
            {filtered.map((well) => (
              <tr
                key={well.well_id}
                className="hover:bg-geo-surface/60 transition-colors"
              >
                <td className="px-4 py-2.5 font-mono text-xs">{well.well_id}</td>
                <td className="px-4 py-2.5">{well.well_name}</td>
                <td className="px-4 py-2.5 text-geo-muted">
                  {well.depth_start.toFixed(1)} – {well.depth_end.toFixed(1)}
                </td>
                <td className="px-4 py-2.5 text-geo-muted">
                  {well.curve_names.join(', ')}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-geo-muted">
                  {well.longitude?.toFixed(4) ?? '—'}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-geo-muted">
                  {well.latitude?.toFixed(4) ?? '—'}
                </td>
                <td className="px-4 py-2.5 text-right">
                  <button
                    onClick={() => handleView(well.well_id)}
                    className="inline-flex items-center gap-1 text-geo-accent hover:text-geo-accent/80 text-xs"
                  >
                    <Eye size={14} />
                    查看
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
