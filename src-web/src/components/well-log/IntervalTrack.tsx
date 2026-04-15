import React from 'react';
import { IntervalItem } from './types';

interface IntervalTrackProps {
  intervals: IntervalItem[];
  depthRange: [number, number];
  pixelRatio: number;
  className?: string;
  verticalText?: boolean;
}

/**
 * IntervalTrack - Renders discrete depth intervals with labels.
 * Used for stratigraphic units, facies, and sequences.
 */
export const IntervalTrack: React.FC<IntervalTrackProps> = ({ 
  intervals, 
  depthRange, 
  pixelRatio,
  className = '',
  verticalText = false
}) => {
  const [minDepth, maxDepth] = depthRange;
  const totalHeight = (maxDepth - minDepth) * pixelRatio;

  return (
    <div className={`track-cell bg-white relative overflow-hidden ${className}`} style={{ height: totalHeight }}>
      {intervals.map((interval, i) => {
        const top = (interval.top - minDepth) * pixelRatio;
        const height = (interval.bottom - interval.top) * pixelRatio;

        return (
          <div
            key={i}
            className="absolute left-0 right-0 border-b border-black flex items-center justify-center p-0.5 text-center bg-white"
            style={{ top, height, borderBottomWidth: i === intervals.length - 1 ? 0 : 1 }}
            title={`${interval.top}m - ${interval.bottom}m: ${interval.name}`}
          >
            <span className={`${verticalText ? 'vertical-text' : ''} text-[10px] leading-[1.1] select-none break-all`}>
              {interval.name}
            </span>
          </div>
        );
      })}
    </div>
  );
}
