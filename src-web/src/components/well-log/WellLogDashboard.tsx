import React, { useRef, useState, useEffect } from 'react';
import { LogHeader } from './LogHeader';
import { CurveTrack } from './CurveTrack';
import { LithologyTrack } from './LithologyTrack';
import { IntervalTrack } from './IntervalTrack';
import { SequenceStructureTrack } from './SequenceStructureTrack';
import { FaciesTrack, FaciesTrackRef } from './FaciesTrack';
import { WellLogData, WellIntervals, FaciesData } from './types';
import jsPDF from 'jspdf';

const EMPTY_INTERVALS: WellIntervals = {
  series: [], system: [], formation: [], member: [],
  lithology: [], systems_tract: [], sequence: [],
  facies: { phase: [], sub_phase: [], micro_phase: [] },
};

interface WellLogDashboardProps {
  data: WellLogData;
};

/**
 * WellLogDashboard - Main container for the 1:1 replica well log visualization.
 * Uses CSS Grid to manage 17 tracks aligned with multi-level headers.
 */
export const WellLogDashboard: React.FC<WellLogDashboardProps> = ({ data }) => {
  // Use depth range from metadata or curves
  const startDepth = data.depth_start ?? data.curves[0]?.depth[0] ?? 0;
  const endDepth = data.depth_end ?? data.curves[0]?.depth[data.curves[0].depth.length - 1] ?? 1000;
  
  const pixelRatio = 10; // 1m = 10px
  const depthRange: [number, number] = [startDepth, endDepth];
  const totalHeight = (endDepth - startDepth) * pixelRatio;
  const faciesTrackWidth = 100; // width for each facies column

  // Group curves for tracks
  const leftCurves = data.curves.filter(c => ['AC', 'GR', 'DEN'].includes(c.name.toUpperCase()));
  const rightCurves = data.curves.filter(c => ['RT', 'RXO', 'NPHI'].includes(c.name.toUpperCase()));

  const intervals = data.intervals ?? EMPTY_INTERVALS;
  const [faciesData, setFaciesData] = useState<FaciesData>(intervals.facies);

  useEffect(() => {
    setFaciesData(intervals.facies);
  }, [intervals.facies]);

  const faciesCanvasRef = useRef<FaciesTrackRef>(null);
  const faciesCanvasRef2 = useRef<FaciesTrackRef>(null);
  const faciesCanvasRef3 = useRef<FaciesTrackRef>(null);

  const handleFaciesChange = (level: keyof FaciesData, index: number, newName: string) => {
    const newData = { ...faciesData };
    newData[level] = [...newData[level]];
    newData[level][index] = { ...newData[level][index], name: newName };
    setFaciesData(newData);
  };

  const MAX_EXPORT_HEIGHT = 8000;

  const getExportCanvases = (): HTMLCanvasElement[] => {
    const refs = [faciesCanvasRef, faciesCanvasRef2, faciesCanvasRef3];
    return refs.map(r => r.current?.getCanvasImage?.()).filter((v): v is string => !!v)
      .map(dataUrl => {
        const img = new Image();
        img.src = dataUrl;
        return img;
      })
      .map(img => {
        const srcHeight = img.naturalHeight;
        const scale = srcHeight > MAX_EXPORT_HEIGHT ? MAX_EXPORT_HEIGHT / srcHeight : 1;
        const c = document.createElement('canvas');
        c.width = Math.round(img.naturalWidth * scale);
        c.height = Math.round(srcHeight * scale);
        const ctx = c.getContext('2d')!;
        ctx.drawImage(img, 0, 0, c.width, c.height);
        return c;
      });
  };

  const exportPNG = () => {
    const canvases = getExportCanvases();
    if (canvases.length === 0) {
      alert('No facies canvas found for export');
      return;
    }
    // Composite all facies columns side by side
    const totalWidth = canvases.reduce((s, c) => s + c.width, 0);
    const height = Math.max(...canvases.map(c => c.height));
    const merged = document.createElement('canvas');
    merged.width = totalWidth;
    merged.height = height;
    const ctx = merged.getContext('2d')!;
    let x = 0;
    for (const c of canvases) {
      ctx.drawImage(c, x, 0);
      x += c.width;
    }
    const link = document.createElement('a');
    link.download = `${data.well_name}_facies_${startDepth}_${endDepth}.png`;
    link.href = merged.toDataURL('image/png');
    link.click();
  };

  const exportPDF = () => {
    const canvases = getExportCanvases();
    if (canvases.length === 0) {
      alert('No facies canvas found for export');
      return;
    }
    // Composite all facies columns side by side
    const totalWidth = canvases.reduce((s, c) => s + c.width, 0);
    const height = Math.max(...canvases.map(c => c.height));
    const merged = document.createElement('canvas');
    merged.width = totalWidth;
    merged.height = height;
    const ctx = merged.getContext('2d')!;
    let x = 0;
    for (const c of canvases) {
      ctx.drawImage(c, x, 0);
      x += c.width;
    }
    const dataUrl = merged.toDataURL('image/png');
    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4',
    });
    const img = new Image();
    img.src = dataUrl;
    img.onload = () => {
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const imgWidth = pageWidth - 20;
      const imgHeight = (img.height * imgWidth) / img.width;
      pdf.addImage(img, 'PNG', 10, 10, imgWidth, Math.min(imgHeight, pageHeight - 20));
      pdf.save(`${data.well_name}_facies_${startDepth}_${endDepth}.pdf`);
    };
  };

  return (
    <div className="flex flex-col h-full bg-white overflow-hidden text-black">
      {/* Title */}
      <div className="text-center py-4 bg-white border-b border-black select-none shrink-0 text-black">
        <h2 className="text-xl font-serif flex items-center justify-center gap-4 text-black">
          <span>&</span><span>「{data.well_name}」 综合测井解释图</span>
        </h2>
      </div>

      {/* Main Grid Area */}
      <div className="flex-1 overflow-auto bg-white scrollbar-thin scrollbar-thumb-gray-400">
        <div className="min-w-max p-4 bg-white text-black">
          <LogHeader />
          
          <div 
            className="log-grid relative" 
            style={{ height: totalHeight }}
          >
            {/* 1-4: 地层系统 (系, 统, 组, 段) */}
            <IntervalTrack intervals={intervals.series} depthRange={depthRange} pixelRatio={pixelRatio} verticalText />
            <IntervalTrack intervals={intervals.system} depthRange={depthRange} pixelRatio={pixelRatio} verticalText />
            <IntervalTrack intervals={intervals.formation} depthRange={depthRange} pixelRatio={pixelRatio} verticalText />
            <IntervalTrack intervals={intervals.member} depthRange={depthRange} pixelRatio={pixelRatio} verticalText />
            
            {/* 5: AC/GR/DEN Curves */}
            <CurveTrack curves={leftCurves} depthRange={depthRange} pixelRatio={pixelRatio} />
            
            {/* 6: Depth Track */}
            <div className="track-cell bg-white flex flex-col items-center py-1 text-[10px] font-mono font-bold text-black select-none">
              {Array.from({ length: Math.floor((endDepth - startDepth) / 5) + 1 }).map((_, i) => (
                <span key={i} className="absolute" style={{ top: i * 5 * pixelRatio }}>
                  {Math.floor(startDepth + i * 5)}
                </span>
              ))}
            </div>

            {/* 7: 取心 (Placeholder) */}
            <div className="track-cell bg-white"></div>

            {/* 8: 岩性符号 */}
            <LithologyTrack intervals={intervals.lithology} depthRange={depthRange} pixelRatio={pixelRatio} />

            {/* 9: 照片 (Placeholder) */}
            <div className="track-cell bg-white flex flex-col items-center justify-start p-1 pt-10">
               <div className="w-full aspect-square border border-red-500 relative flex items-center justify-center bg-white">
                  <div className="absolute inset-0 flex items-center justify-center opacity-20">
                    <div className="w-full h-px bg-red-500 rotate-45"></div>
                    <div className="w-full h-px bg-red-500 -rotate-45"></div>
                  </div>
                  <span className="text-[8px] font-bold text-red-500 bg-white px-1 relative z-10">PHOTO</span>
               </div>
            </div>

            {/* 10: RT/RXO/NPHI Curves */}
            <CurveTrack curves={rightCurves} depthRange={depthRange} pixelRatio={pixelRatio} />

            <div className="track-cell bg-white relative text-black">
              {intervals.lithology.map((interval, i) => (
                <div
                  key={i}
                  className="absolute left-0 right-0 border-b border-black/10 p-2 text-[10px] leading-tight overflow-hidden"
                  style={{ top: (interval.top - startDepth) * pixelRatio, height: (interval.bottom - interval.top) * pixelRatio }}
                >
                  {interval.name}
                </div>
              ))}
            </div>
            
            {/* 12-14: 沉积相 (微相, 亚相, 相) - Interactive Canvas */}
            <FaciesTrack
              faciesData={faciesData}
              depthRange={depthRange}
              pixelRatio={pixelRatio}
              onChange={handleFaciesChange}
              width={faciesTrackWidth}
              level="micro_phase"
              ref={faciesCanvasRef}
            />
            <FaciesTrack
              faciesData={faciesData}
              depthRange={depthRange}
              pixelRatio={pixelRatio}
              onChange={handleFaciesChange}
              width={faciesTrackWidth}
              level="sub_phase"
              ref={faciesCanvasRef2}
            />
            <FaciesTrack
              faciesData={faciesData}
              depthRange={depthRange}
              pixelRatio={pixelRatio}
              onChange={handleFaciesChange}
              width={faciesTrackWidth}
              level="phase"
              ref={faciesCanvasRef3}
            />
            
            {/* 15-17: 三级层序 (层序结构, 体系域, 层序) */}
            <SequenceStructureTrack intervals={intervals.systems_tract} depthRange={depthRange} pixelRatio={pixelRatio} />
            <IntervalTrack intervals={intervals.systems_tract} depthRange={depthRange} pixelRatio={pixelRatio} />
            <IntervalTrack intervals={intervals.sequence} depthRange={depthRange} pixelRatio={pixelRatio} verticalText />
          </div>
        </div>
      </div>

      {/* Export toolbar */}
      <div className="border-t border-gray-200 p-3 bg-gray-50 flex gap-3 justify-end">
        <button
          onClick={exportPNG}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors text-sm"
        >
          🖼️ Export PNG
        </button>
        <button
          onClick={exportPDF}
          className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition-colors text-sm"
        >
          📄 Export PDF
        </button>
      </div>
    </div>
  );
};
