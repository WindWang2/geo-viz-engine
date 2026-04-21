import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useApi } from '../hooks/useApi';
import { LaoLong1Dashboard } from '../components/well-log/LaoLong1Dashboard';
import type { WellLogData, CurveData, WellDetailData } from '../components/well-log/types';
import { convertWellDetailToWellLogData } from '../utils/wellDataConverter';

type Tab = 'chart' | 'data';

export default function WellDetailPage() {
  const { wellName } = useParams<{ wellName: string }>();
  const navigate = useNavigate();
  const { request } = useApi();
  const [data, setData] = useState<WellLogData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('chart');

  useEffect(() => {
    if (!wellName) {
      setError('未指定井名称');
      return;
    }
    request<WellDetailData>(`/api/data/well-detail/${wellName}`)
      .then(detailData => {
        const wellLogData = convertWellDetailToWellLogData(detailData, wellName);
        setData(wellLogData);
      })
      .catch(e => setError(e?.message ?? '加载失败'));
  }, [request, wellName]);

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center text-red-600">
          <p className="text-lg font-medium">加载失败</p>
          <p className="text-sm mt-1">{error}</p>
          <button onClick={() => navigate(-1)} className="mt-3 text-sm text-blue-500 hover:underline">← 返回</button>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-500">加载 {wellName} 数据...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700 bg-gray-900">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-white text-sm">← 返回</button>
          <h1 className="text-white font-medium">{data.well_name}</h1>
          <span className="text-xs text-gray-500">深度 {data.depth_start}m - {data.depth_end}m</span>
        </div>
        <div className="flex bg-gray-800 rounded-lg p-0.5">
          <button
            onClick={() => setTab('chart')}
            className={`px-3 py-1 text-xs rounded-md transition ${tab === 'chart' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
          >测井图</button>
          <button
            onClick={() => setTab('data')}
            className={`px-3 py-1 text-xs rounded-md transition ${tab === 'data' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
          >数据</button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {tab === 'chart' ? (
          <LaoLong1Dashboard data={data} onDataChange={setData} />
        ) : (
          <DataTable curves={data.curves} />
        )}
      </div>
    </div>
  );
}

function DataTable({ curves }: { curves: CurveData[] }) {
  if (!curves.length) {
    return <div className="p-4 text-gray-500 text-center">暂无曲线数据</div>;
  }

  const depths = curves[0].depth;
  return (
    <div className="overflow-auto p-4">
      <table className="text-xs border-collapse w-full">
        <thead>
          <tr className="bg-gray-800">
            <th className="border border-gray-700 px-2 py-1 text-gray-300 text-left sticky left-0 bg-gray-800">深度(m)</th>
            {curves.map(c => (
              <th key={c.name} className="border border-gray-700 px-2 py-1 text-gray-300 text-left whitespace-nowrap">
                {c.name} <span className="text-gray-500">({c.unit})</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {depths.map((d, i) => (
            <tr key={i} className={i % 2 === 0 ? 'bg-gray-900' : 'bg-gray-850'}>
              <td className="border border-gray-700 px-2 py-0.5 text-gray-300 sticky left-0 bg-inherit">{d.toFixed(2)}</td>
              {curves.map(c => (
                <td key={c.name} className="border border-gray-700 px-2 py-0.5 text-gray-400">{c.data[i]?.toFixed(4) ?? '-'}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
