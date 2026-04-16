import React from 'react';
import { CurveData } from './types';

interface CurveTrackProps {
  curves: CurveData[];
  depthRange: [number, number];
  pixelRatio: number;
}

/**
 * CurveTrack - Renders multiple well log curves in a single track using SVG.
 */
export const CurveTrack: React.FC<CurveTrackProps> = ({ curves, depthRange, pixelRatio }) => {
  const [minDepth, maxDepth] = depthRange;
  const totalHeight = (maxDepth - minDepth) * pixelRatio;

  const renderCurve = (curve: CurveData) => {
    if (!curve.data.length) return null;

    const points = curve.depth.map((d, i) => {
      const x = ((curve.data[i] - curve.display_range[0]) / (curve.display_range[1] - curve.display_range[0])) * 100;
      const y = (d - minDepth) * pixelRatio;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    }).join(' ');

    return (
      <polyline
        key={curve.name}
        points={points}
        fill="none"
        stroke={curve.color}
        strokeWidth="1.5"
        strokeDasharray={curve.line_style === 'dashed' ? '4,2' : curve.line_style === 'dotted' ? '1,1' : 'none'}
      />
    );
  };

  return (
    <div className="track-cell bg-[#fafafa] relative overflow-hidden" style={{ height: totalHeight }}>
      {/* Grid Lines */}
      <div className="absolute inset-0 flex justify-between pointer-events-none opacity-10">
        {[20, 40, 60, 80].map(x => (
          <div key={x} className="h-full border-r border-black" style={{ left: `${x}%` }}></div>
        ))}
      </div>
      
      <svg width="100%" height="100%" preserveAspectRatio="none" viewBox={`0 0 100 ${totalHeight}`}>
        {curves.map(renderCurve)}
      </svg>
    </div>
  );
};
