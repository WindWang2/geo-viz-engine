import React from 'react';
import { IntervalItem } from './types';

interface LithologyTrackProps {
  intervals: IntervalItem[];
  depthRange: [number, number];
  pixelRatio: number;
}

const ROCK_MAP: Record<string, { pattern: string; color: string }> = {
  '砂岩': { pattern: 'pattern-sandstone', color: '#fef08a' }, // yellow-200
  '泥岩': { pattern: 'pattern-shale', color: '#e5e7eb' },    // gray-200
  '石灰岩': { pattern: 'pattern-limestone', color: '#dbeafe' }, // blue-100
  '白云岩': { pattern: 'pattern-dolomite', color: '#f3e8ff' },  // purple-100
  '粉砂岩': { pattern: 'pattern-siltstone', color: '#f3f4f6' },  // gray-100
};

function getRockStyle(name: string) {
  for (const [key, value] of Object.entries(ROCK_MAP)) {
    if (name.includes(key)) return value;
  }
  return { pattern: '', color: '#ffffff' };
}

/**
 * LithologyTrack - Renders rock symbols and colors based on interval data.
 */
export const LithologyTrack: React.FC<LithologyTrackProps> = ({ intervals, depthRange, pixelRatio }) => {
  const [minDepth, maxDepth] = depthRange;
  const totalHeight = (maxDepth - minDepth) * pixelRatio;

  return (
    <div className="track-cell bg-white relative overflow-hidden" style={{ height: totalHeight }}>
      {intervals.map((interval, i) => {
        const top = (interval.top - minDepth) * pixelRatio;
        const height = (interval.bottom - interval.top) * pixelRatio;
        const style = getRockStyle(interval.name);

        return (
          <div
            key={i}
            className="absolute left-0 right-0 border-b border-black/10 last:border-0"
            style={{ top, height, backgroundColor: style.color }}
            title={interval.name}
          >
            {style.pattern && (
              <svg width="100%" height="100%">
                <rect width="100%" height="100%" fill={`url(#${style.pattern})`} />
              </svg>
            )}
          </div>
        );
      })}
    </div>
  );
};
