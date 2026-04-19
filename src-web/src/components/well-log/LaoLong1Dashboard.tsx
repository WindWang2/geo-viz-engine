import React, { useRef } from 'react';
import { LaoLong1Chart, ChartRef } from './LaoLong1Chart';
import type { WellLogData } from './types';

interface Props {
  data: WellLogData;
  onDataChange?: (data: WellLogData) => void;
}

export const LaoLong1Dashboard: React.FC<Props> = ({ data, onDataChange }) => {
  const chartRef = useRef<ChartRef>(null);

  return (
    <div className="flex flex-col h-full bg-gray-100 text-black overflow-hidden">
      {/* Scrollable centered chart */}
      <div className="flex-1 overflow-auto">
        <div className="flex justify-center py-4 px-4">
          <LaoLong1Chart ref={chartRef} data={data} onDataChange={onDataChange} />
        </div>
      </div>

      {/* Export toolbar */}
      <div className="border-t border-gray-300 px-4 py-2 bg-gray-50 text-xs text-gray-500 flex justify-between items-center shrink-0">
        <span>{data.well_name} — 深度 {data.depth_start}m - {data.depth_end}m</span>
        <div className="flex gap-2">
          <button onClick={() => chartRef.current?.exportSVG()} className="px-3 py-1 bg-purple-600 text-white rounded hover:bg-purple-700 text-xs">Export SVG</button>
          <button onClick={() => chartRef.current?.exportPNG()} className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 text-xs">Export PNG</button>
          <button onClick={() => chartRef.current?.exportPDF()} className="px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700 text-xs">Export PDF</button>
        </div>
      </div>
    </div>
  );
};
