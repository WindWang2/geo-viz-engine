import React from 'react';
import { IntervalItem } from './types';

interface SequenceStructureTrackProps {
  intervals: IntervalItem[];
  depthRange: [number, number];
  pixelRatio: number;
}

/**
 * SequenceStructureTrack - Renders transgression/regression wedge shapes (triangles).
 * Triangle pointing up: TST (Transgressive Systems Tract)
 * Triangle pointing down: HST (Highstand Systems Tract)
 */
export const SequenceStructureTrack: React.FC<SequenceStructureTrackProps> = ({ 
  intervals, 
  depthRange, 
  pixelRatio 
}) => {
  const [minDepth, maxDepth] = depthRange;
  const totalHeight = (maxDepth - minDepth) * pixelRatio;

  return (
    <div className="track-cell bg-white relative overflow-hidden" style={{ height: totalHeight }}>
      {intervals.map((interval, i) => {
        const top = (interval.top - minDepth) * pixelRatio;
        const height = (interval.bottom - interval.top) * pixelRatio;
        const isTST = interval.name.toUpperCase().includes('TST');
        const isHST = interval.name.toUpperCase().includes('HST');

        return (
          <div
            key={i}
            className="absolute left-0 right-0 border-b border-black/20 last:border-0 p-1"
            style={{ top, height }}
          >
            <svg width="100%" height="100%" preserveAspectRatio="none" viewBox="0 0 100 100">
              {isTST && (
                <polygon points="50,0 100,100 0,100" fill="none" stroke="black" strokeWidth="1" />
              )}
              {isHST && (
                <polygon points="0,0 100,0 50,100" fill="none" stroke="black" strokeWidth="1" />
              )}
            </svg>
          </div>
        );
      })}
    </div>
  );
};
