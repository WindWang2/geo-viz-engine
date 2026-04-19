import React, { useRef, useEffect, useCallback, forwardRef, useImperativeHandle } from 'react';
import { FaciesData } from './types';

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
  // 老龙1井专用相名
  '潮坪': '#dbeafe',
  '陆棚': '#d1fae5',
  '砂坪': '#fef3c7',
  '泥坪': '#e5e7eb',
  '陆棚夹': '#bfdbfe',
  '混积': '#fde68a',
  '碎屑岩': '#fcd34d',
  '云质': '#93c5fd',
  '砂泥质': '#fef9c3',
  '泥质': '#e2e8f0',
  '砂质': '#fef08a',
};

function getFaciesColor(name: string): string {
  for (const [key, color] of Object.entries(FACIES_COLORS)) {
    if (name.includes(key)) return color;
  }
  return '#f3f4f6';
}

export interface FaciesTrackProps {
  faciesData: FaciesData;
  depthRange: [number, number];
  pixelRatio: number;
  onChange: (level: keyof FaciesData, index: number, newName: string) => void;
  width: number;
  level?: keyof FaciesData;
}

export interface FaciesTrackRef {
  getCanvasImage: () => string | null;
}

export const FaciesTrack = forwardRef<FaciesTrackRef, FaciesTrackProps>(({
  faciesData,
  depthRange,
  pixelRatio,
  onChange,
  width,
  level,
}, ref) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;

  const [minDepth, maxDepth] = depthRange;
  const totalHeight = (maxDepth - minDepth) * pixelRatio;

  useImperativeHandle(ref, () => ({
    getCanvasImage: () => {
      const canvas = canvasRef.current;
      if (!canvas) return null;
      return canvas.toDataURL('image/png');
    }
  }));

  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    let resolvedLevel: keyof FaciesData;
    if (level) {
      resolvedLevel = level;
    } else {
      const colWidth = width / 3;
      if (x < colWidth) resolvedLevel = 'micro_phase';
      else if (x < colWidth * 2) resolvedLevel = 'sub_phase';
      else resolvedLevel = 'phase';
    }

    const depthY = minDepth + y / pixelRatio;
    const intervals = faciesData[resolvedLevel];
    const hitIndex = intervals.findIndex(
      iv => depthY >= iv.top && depthY <= iv.bottom
    );

    if (hitIndex >= 0) {
      const currentName = intervals[hitIndex].name;
      const newName = prompt('请输入新的沉积相名称:', currentName);
      if (newName && newName.trim()) {
        onChange(resolvedLevel, hitIndex, newName.trim());
      }
    }
  }, [faciesData, minDepth, pixelRatio, width, onChange, level]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set physical size at DPR scale for sharp rendering
    canvas.width = width * dpr;
    canvas.height = totalHeight * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, totalHeight);

    const colWidth = level ? width : width / 3;
    const levels: Array<{ key: keyof FaciesData; x: number }> = level
      ? [{ key: level, x: 0 }]
      : [
          { key: 'micro_phase', x: 0 },
          { key: 'sub_phase', x: colWidth },
          { key: 'phase', x: colWidth * 2 },
        ];

    levels.forEach(({ key, x }) => {
      const intervals = faciesData[key];

      intervals.forEach((interval) => {
        const topY = (interval.top - minDepth) * pixelRatio;
        const bottomY = (interval.bottom - minDepth) * pixelRatio;
        const height = bottomY - topY;
        const color = getFaciesColor(interval.name);

        ctx.fillStyle = color;
        ctx.fillRect(x + 1, topY, colWidth - 2, height);

        ctx.strokeStyle = '#00000030';
        ctx.lineWidth = 0.5;
        ctx.strokeRect(x + 1, topY, colWidth - 2, height);

        if (height > 10) {
          ctx.fillStyle = '#1f2937';
          ctx.font = '12px sans-serif';
          const textY = topY + height / 2 + 4;
          const maxTextWidth = colWidth - 4;
          ctx.fillText(interval.name, x + 2, textY, maxTextWidth);
        }
      });

      ctx.strokeStyle = '#e0e0e0';
      ctx.lineWidth = 0.5;
      ctx.strokeRect(x, 0, colWidth, totalHeight);
    });
  }, [faciesData, depthRange, pixelRatio, width, totalHeight, level, dpr]);

  return (
    <div className="track-cell bg-white relative overflow-hidden">
      <canvas
        ref={canvasRef}
        onClick={handleClick}
        style={{ display: 'block', cursor: 'pointer', width, height: totalHeight }}
        className="interactive-facies-canvas"
      />
    </div>
  );
});

FaciesTrack.displayName = 'FaciesTrack';

export default FaciesTrack;
