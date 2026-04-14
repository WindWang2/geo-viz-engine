import React, { useEffect, useRef } from 'react';
import { WellLogData, WellLogCanvasProps } from './types';
import { CurveData } from './types';

/**
 * WellLogCanvas - Core canvas-based renderer for well log curves
 * Uses Canvas 2D for high-performance rendering of large datasets
 * Supports multiple tracks, vertical scrolling, and d3-based coordinate mapping
 */
export const WellLogCanvas: React.FC<WellLogCanvasProps> = ({
  wellData,
  trackWidth,
  depthPixelRatio,
  onHeightCalculated,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Calculate total height based on depth range and pixel ratio
  const depthRange = wellData.depth_end - wellData.depth_start;
  const totalHeight = depthRange * depthPixelRatio;

  // Notify parent of calculated height
  useEffect(() => {
    if (onHeightCalculated) {
      onHeightCalculated(totalHeight);
    }
  }, [totalHeight, onHeightCalculated]);

  // Main render function
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    const totalWidth = wellData.curves.length * trackWidth;
    canvas.width = totalWidth;
    canvas.height = totalHeight;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw each curve in its own track
    wellData.curves.forEach((curve, index) => {
      const trackX = index * trackWidth;
      drawCurve(ctx, curve, index, wellData, trackX, trackWidth, totalHeight, depthPixelRatio);
    });

  }, [wellData, trackWidth, depthPixelRatio, totalHeight]);

  /**
   * Draw a single curve in its track
   */
  const drawCurve = (
    ctx: CanvasRenderingContext2D,
    curve: CurveData,
    index: number,
    well: WellLogData,
    trackX: number,
    trackWidth: number,
    totalHeight: number,
    depthPixelRatio: number,
  ) => {
    // Draw track border
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 1;
    ctx.strokeRect(trackX, 0, trackWidth, totalHeight);

    // Draw track header (name and unit)
    ctx.fillStyle = '#2c3e50';
    ctx.font = '12px sans-serif';
    const headerText = `${curve.name}${curve.unit ? ` (${curve.unit})` : ''}`;
    ctx.fillText(headerText, trackX + 4, 14);

    // Plot area is from y=20px to bottom
    const plotTop = 20;

    // Set up coordinate mapping
    const [minVal, maxVal] = curve.display_range;
    const valueRange = maxVal - minVal;

    // Begin path
    ctx.beginPath();
    ctx.strokeStyle = curve.color || getDefaultColor(curve.name);
    ctx.lineWidth = curve.line_style === 'dashed' ? 1 : 1.5;
    ctx.setLineDash(curve.line_style === 'dashed' ? [5, 3] : []);

    // Sample points to avoid over-drawing (keep at most 2000 points per curve)
    const totalSamples = curve.depth.length;
    const sampleStep = Math.max(Math.floor(totalSamples / 2000), 1);

    let firstPoint = true;
    for (let i = 0; i < totalSamples; i += sampleStep) {
      const depth = curve.depth[i];
      const value = curve.data[i];

      // Map depth to y (depth increases downward)
      const y = plotTop + (depth - well.depth_start) * depthPixelRatio;
      // Map value to x within the track
      const x = trackX + 5 + ((value - minVal) / valueRange) * (trackWidth - 10);

      if (firstPoint) {
        ctx.moveTo(x, y);
        firstPoint = false;
      } else {
        ctx.lineTo(x, y);
      }
    }

    ctx.stroke();
    ctx.setLineDash([]);

    // Draw Y-axis (depth ticks on the left edge of first track)
    if (index === 0) {
      drawDepthAxis(ctx, well, plotTop, totalHeight, depthPixelRatio);
    }
  };

  /**
   * Draw depth axis ticks on left edge
   */
  const drawDepthAxis = (
    ctx: CanvasRenderingContext2D,
    well: WellLogData,
    plotTop: number,
    _totalHeight: number,
    depthPixelRatio: number,
  ) => {
    ctx.strokeStyle = '#999';
    ctx.fillStyle = '#666';
    ctx.font = '10px sans-serif';
    ctx.lineWidth = 1;

    // Generate tick every 100 meters
    const startTick = Math.ceil(well.depth_start / 100) * 100;
    const endTick = Math.floor(well.depth_end / 100) * 100;

    for (let tickDepth = startTick; tickDepth <= endTick; tickDepth += 100) {
      const y = plotTop + (tickDepth - well.depth_start) * depthPixelRatio;

      // Tick mark
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(10, y);
      ctx.stroke();

      // Tick label
      ctx.fillText(`${tickDepth}m`, 12, y + 3);
    }
  };

  /**
   * Get default color based on curve name hash
   */
  const getDefaultColor = (name: string): string => {
    const colors = [
      '#e74c3c', '#3498db', '#2ecc71', '#9b59b6', '#f39c12',
      '#1abc9c', '#34495e', '#e67e22', '#16a085', '#8e44ad',
    ];
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
  };

  return (
    <div ref={containerRef} className="overflow-x-auto overflow-y-auto bg-white">
      <canvas
        ref={canvasRef}
        style={{ display: 'block' }}
        className="well-log-canvas"
      />
    </div>
  );
};

export default WellLogCanvas;
