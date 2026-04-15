import React from 'react';
import { LogHeader } from './LogHeader';
import { CurveTrack } from './CurveTrack';
import { LithologyTrack } from './LithologyTrack';
import { IntervalTrack } from './IntervalTrack';
import { SequenceStructureTrack } from './SequenceStructureTrack';
import { WellDetailData } from './types';

interface WellLogDashboardProps {
  data: WellDetailData;
}

/**
 * WellLogDashboard - Main container for the 1:1 replica well log visualization.
 * Uses CSS Grid to manage 17 tracks aligned with multi-level headers.
 */
export const WellLogDashboard: React.FC<WellLogDashboardProps> = ({ data }) => {
  // Use first curve's depth range or default
  const firstCurve = data.curves[0];
  const startDepth = firstCurve?.depth[0] ?? 2515;
  const endDepth = firstCurve?.depth[firstCurve.depth.length - 1] ?? 2610;
  
  const pixelRatio = 10; // 1m = 10px
  const depthRange: [number, number] = [startDepth, endDepth];
  const totalHeight = (endDepth - startDepth) * pixelRatio;

  // Group curves for tracks
  const leftCurves = data.curves.filter(c => ['AC', 'GR'].includes(c.name.toUpperCase()));
  const rightCurves = data.curves.filter(c => ['RT', 'RXO'].includes(c.name.toUpperCase()));

  return (
    <div className="flex flex-col h-full bg-white overflow-hidden">
      {/* Title */}
      <div className="text-center py-4 bg-white border-b border-black select-none shrink-0">
        <h2 className="text-xl font-serif flex items-center justify-center gap-4">
          <span>&</span><span>「{data.well_name}」 综合测井解释图</span>
        </h2>
      </div>

      {/* Main Grid Area */}
      <div className="flex-1 overflow-auto bg-gray-50 scrollbar-thin scrollbar-thumb-gray-300">
        <div className="min-w-max p-4 bg-white">
          <LogHeader />
          
          <div 
            className="log-grid relative" 
            style={{ height: totalHeight }}
          >
            {/* 1-4: 地层系统 (系, 统, 组, 段) */}
            <IntervalTrack intervals={data.intervals.series} depthRange={depthRange} pixelRatio={pixelRatio} verticalText />
            <IntervalTrack intervals={data.intervals.system} depthRange={depthRange} pixelRatio={pixelRatio} verticalText />
            <IntervalTrack intervals={data.intervals.formation} depthRange={depthRange} pixelRatio={pixelRatio} verticalText />
            <IntervalTrack intervals={data.intervals.member} depthRange={depthRange} pixelRatio={pixelRatio} verticalText />
            
            {/* 5: AC/GR Curves */}
            <CurveTrack curves={leftCurves} depthRange={depthRange} pixelRatio={pixelRatio} />
            
            {/* 6: Depth Track */}
            <div className="track-cell bg-white flex flex-col items-center py-1 text-[10px] font-mono font-bold text-red-700 select-none">
              {Array.from({ length: Math.floor((endDepth - startDepth) / 5) + 1 }).map((_, i) => (
                <span key={i} className="absolute" style={{ top: i * 5 * pixelRatio }}>
                  {Math.floor(startDepth + i * 5)}
                </span>
              ))}
            </div>

            {/* 7: 取心 (Placeholder) */}
            <div className="track-cell bg-white"></div>

            {/* 8: 岩性符号 */}
            <LithologyTrack intervals={data.intervals.lithology} depthRange={depthRange} pixelRatio={pixelRatio} />

            {/* 9: 照片 (Placeholder) */}
            <div className="track-cell bg-white flex flex-col items-center justify-start p-1 pt-10">
               {/* Fixed photo mockup from demo.jpg */}
               <div className="w-full aspect-square border border-red-500 relative flex items-center justify-center bg-white">
                  <div className="absolute inset-0 flex items-center justify-center opacity-20">
                    <div className="w-full h-px bg-red-500 rotate-45"></div>
                    <div className="w-full h-px bg-red-500 -rotate-45"></div>
                  </div>
                  <span className="text-[8px] font-bold text-red-500 bg-white px-1 relative z-10">PHOTO</span>
               </div>
            </div>

            {/* 10: RT/RXO Curves */}
            <CurveTrack curves={rightCurves} depthRange={depthRange} pixelRatio={pixelRatio} />

            {/* 11: 岩性描述 */}
            <div className="track-cell bg-white relative">
              {data.intervals.lithology.map((interval, i) => (
                <div
                  key={i}
                  className="absolute left-0 right-0 border-b border-gray-100 p-2 text-[10px] leading-tight overflow-hidden"
                  style={{ top: (interval.top - startDepth) * pixelRatio, height: (interval.bottom - interval.top) * pixelRatio }}
                >
                  {interval.name}
                </div>
              ))}
            </div>
            
            {/* 12-14: 沉积相 (微相, 亚相, 相) */}
            <IntervalTrack intervals={data.intervals.facies.micro_phase} depthRange={depthRange} pixelRatio={pixelRatio} />
            <IntervalTrack intervals={data.intervals.facies.sub_phase} depthRange={depthRange} pixelRatio={pixelRatio} />
            <IntervalTrack intervals={data.intervals.facies.phase} depthRange={depthRange} pixelRatio={pixelRatio} />
            
            {/* 15-17: 三级层序 (层序结构, 体系域, 层序) */}
            <SequenceStructureTrack intervals={data.intervals.systems_tract} depthRange={depthRange} pixelRatio={pixelRatio} />
            <IntervalTrack intervals={data.intervals.systems_tract} depthRange={depthRange} pixelRatio={pixelRatio} />
            <IntervalTrack intervals={data.intervals.sequence} depthRange={depthRange} pixelRatio={pixelRatio} verticalText />
          </div>
        </div>
      </div>
    </div>
  );
};
