'use client';

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMapStore } from '../stores/useMapStore';
import BottomTabBar from '../components/BottomTabBar';
import type { WellLocation } from '../types/coordinate';

const PAGE_SIZE = 20;

export default function WellTablePage() {
  const navigate = useNavigate();
  const { setSelectedWellId } = useMapStore();

  const [wells, setWells] = useState<WellLocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    fetch('/api/wells')
      .then((r) => r.json())
      .then((data: WellLocation[]) => {
        setWells(data);
        setTotal(data.length);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const filtered = wells.filter((w) => {
    const q = search.toLowerCase();
    return (
      w.well_id.toLowerCase().includes(q) ||
      w.well_name.toLowerCase().includes(q)
    );
  });

  const pageCount = Math.ceil(filtered.length / PAGE_SIZE);
  const paginated = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const handleViewDetail = (well: WellLocation) => {
    setSelectedWellId(well.well_id);
    navigate(`/well/${encodeURIComponent(well.well_id)}`);
  };

  const handlePrev = () => setPage((p) => Math.max(0, p - 1));
  const handleNext = () => setPage((p) => Math.min(pageCount - 1, p + 1));

  return (
    <div className="flex h-screen flex-col bg-gray-50">
      {/* Header */}
      <header className="shrink-0 border-b border-gray-200 bg-white px-4 py-3">
        <h1 className="mb-2 text-base font-semibold text-gray-800">测井数据表</h1>
        <input
          type="search"
          placeholder="搜索井号或名称..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(0); }}
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100"
        />
      </header>

      {/* Table */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <span className="text-gray-400">加载中...</span>
          </div>
        ) : (
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 bg-gray-100 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-4 py-2">井号</th>
                <th className="px-4 py-2">名称</th>
                <th className="px-4 py-2">经度</th>
                <th className="px-4 py-2">纬度</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {paginated.map((well) => (
                <tr key={well.well_id} className="hover:bg-blue-50">
                  <td className="px-4 py-2.5 font-mono text-xs">{well.well_id}</td>
                  <td className="px-4 py-2.5">{well.well_name}</td>
                  <td className="px-4 py-2.5 text-gray-500">{well.longitude?.toFixed(4)}°</td>
                  <td className="px-4 py-2.5 text-gray-500">{well.latitude?.toFixed(4)}°</td>
                  <td className="px-4 py-2.5 text-right">
                    <button
                      onClick={() => handleViewDetail(well)}
                      className="rounded-lg bg-blue-500 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-blue-600 active:bg-blue-700"
                    >
                      查看详情 →
                    </button>
                  </td>
                </tr>
              ))}
              {paginated.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                    无匹配结果
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination footer */}
      {!loading && total > 0 && (
        <footer className="flex shrink-0 items-center justify-between border-t border-gray-200 bg-white px-4 py-2 text-sm text-gray-500">
          <span>
            第 {page + 1}/{Math.max(1, pageCount)} 页，共 {filtered.length} 口井
          </span>
          <div className="flex gap-2">
            <button
              onClick={handlePrev}
              disabled={page === 0}
              className="rounded-lg px-3 py-1 transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
            >
              ← 上一页
            </button>
            <button
              onClick={handleNext}
              disabled={page >= pageCount - 1}
              className="rounded-lg px-3 py-1 transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
            >
              下一页 →
            </button>
          </div>
        </footer>
      )}

      {/* Bottom tab bar */}
      <BottomTabBar />
    </div>
  );
}