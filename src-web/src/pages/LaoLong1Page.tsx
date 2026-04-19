import { useEffect, useState } from 'react';
import { useApi } from '../hooks/useApi';
import { LaoLong1Dashboard } from '../components/well-log/LaoLong1Dashboard';
import type { WellLogData } from '../components/well-log/types';

export default function LaoLong1Page() {
  const { request } = useApi();
  const [data, setData] = useState<WellLogData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    request<WellLogData>('/api/data/laolong1')
      .then(setData)
      .catch(e => setError(e?.message ?? '加载失败'));
  }, [request]);

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center text-red-600">
          <p className="text-lg font-medium">加载失败</p>
          <p className="text-sm mt-1">{error}</p>
          <p className="text-xs mt-2 text-gray-400">请确保后端已启动且老龙1井 XLS 文件可访问</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-500">加载老龙1井数据...</p>
      </div>
    );
  }

  return <LaoLong1Dashboard data={data} onDataChange={setData} />;
}
