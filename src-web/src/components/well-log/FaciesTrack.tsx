import React, { useRef, useEffect, useCallback, forwardRef, useImperativeHandle } from 'react';
import { FaciesData, IntervalItem } from './types';

const FACIES_COLORS: Record<string, string> = {
  '河流相': '#fef3c7',
  '三角洲相': '#dbeafe',
  '滨岸相': '#d1fae5',
  '浅海相': '#bfdbfe',
  '半深海相': '#93c5fd',
  '深海相': '#60a5fa',
  '湖相': '#fecaca',
  '三角洲平原': '#fde68a',
  '三角洲前缘': '#fcd34d',
  '前三角洲': '#fbbf24',
  '水下分流河道': '#f59e0b',
  '河口坝': '#d97706',
  '席状砂': '#b45309',
  '泥岩': '#e5e7eb',
  '砂岩': '#fef08a',
  '粉砂岩': '#f3f4f6',
  '石灰岩': '#dbeafe',
};

function getFaciesColor(name: string): string {
  for (const [key, color] of Object.entries(FACIES_COLORS)) {
    if (name.includes(key)) return color;
  }
  return '#f3f4f6';
}

interface HitInfo {
  level: keyof FaciesData;
  index: number;
  interval: IntervalItem;
}

export interface FaciesTrackProps {
  faciesData: FaciesData;
  depthRange: [number, number];
  pixelRatio: number;
  onChange: (level: keyof FaciesData, index: number, newName: string) => void;
  width: number;
}

export interface FaciesTrackRef {
  getCanvasImage: () => string | null;
}

/**
 * FaciesTrack - Canvas-based interactive sedimentary facies visualization
 * Supports three-level display (phase / sub_phase / micro_phase)
 * Allows click to edit facies type
 * Supports PNG export via canvas ref
 */
export const FaciesTrack = forwardRef<FaciesTrackRef, FaciesTrackProps>(({
  faciesData,
  depthRange,
  pixelRatio,
  onChange,
  width,
}, ref) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hitMapRef = useRef<HitInfo[]>([]);

  const [minDepth, maxDepth] = depthRange;
  const totalHeight = (maxDepth - minDepth) * pixelRatio;

  // Expose export method to parent
  useImperativeHandle(ref, () => ({
    getCanvasImage: () => {
      const canvas = canvasRef.current;
      if (!canvas) return null;
      return canvas.toDataURL('image/png');
    }
  }));

  // Handle click - hit detection
  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Find which column (level) the click is in
    const colWidth = width / 3;
    let level: keyof FaciesData;
    if (x < colWidth) {
      level = 'micro_phase';
    } else if (x < colWidth * 2) {
      level = 'sub_phase';
    } else {
      level = 'phase';
    }

    // Find which interval by Y coordinate
    const depthY = minDepth + y / pixelRatio;
    const intervals = faciesData[level];
    const hitIndex = intervals.findIndex(
      iv => depthY >= iv.top && depthY <= iv.bottom
    );

    if (hitIndex >= 0) {
      const currentName = intervals[hitIndex].name;
      const newName = prompt('请输入新的沉积相名称:', currentName);
      if (newName && newName.trim()) {
        onChange(level, hitIndex, newName.trim());
      }
    }
  }, [faciesData, minDepth, pixelRatio, width, onChange]);

  // Render to canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = width;
    canvas.height = totalHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const colWidth = width / 3;
    const levels: Array<{ key: keyof FaciesData; name: string; x: number }> = [
      { key: 'micro_phase', name: '微相', x: 0 },
      { key: 'sub_phase', name: '亚相', x: colWidth },
      { key: 'phase', name: '相', x: colWidth * 2 },
    ];

    const hitMap: HitInfo[] = [];

    levels.forEach(({ key, name, x }) => {
      const intervals = faciesData[key];
      
      // Draw header
      ctx.fillStyle = '#2c3e50';
      ctx.font = '12px sans-serif';
      ctx.fillText(name, x + 4, 14);

      const plotTop = 20;
      
      intervals.forEach((interval, index) => {
        const topY = plotTop + (interval.top - minDepth) * pixelRatio;
        const bottomY = plotTop + (interval.bottom - minDepth) * pixelRatio;
        const height = bottomY - topY;
        const color = getFaciesColor(interval.name);

        // Draw filled rectangle
        ctx.fillStyle = color;
        ctx.fillRect(x + 1, topY, colWidth - 2, height);

        // Draw border
        ctx.strokeStyle = '#00000020';
        ctx.lineWidth = 1;
        ctx.strokeRect(x + 1, topY, colWidth - 2, height);

        // Draw text label if enough height
        if (height > 16) {
          ctx.fillStyle = '#1f2937';
          ctx.font = '10px sans-serif';
          const textY = topY + height / 2 + 3;
          const maxTextWidth = colWidth - 6;
          ctx.fillText(interval.name, x + 4, textY, maxTextWidth);
        }

        // Add to hit map
        hitMap.push({
          level: key,
          index,
          interval,
        });
      });

      // Draw column border
      ctx.strokeStyle = '#e0e0e0';
      ctx.lineWidth = 1;
      ctx.strokeRect(x, 0, colWidth, totalHeight);
    });

    hitMapRef.current = hitMap;
  }, [faciesData, depthRange, pixelRatio, width, totalHeight]);

  return (
    <div className="facies-track bg-white relative overflow-hidden">
      <canvas
        ref={canvasRef}
        width={width}
        height={totalHeight}
        onClick={handleClick}
        style={{ display: 'block', cursor: 'pointer' }}
        className="interactive-facies-canvas"
      />
    </div>
  );
});

FaciesTrack.displayName = 'FaciesTrack';

export default FaciesTrack;
