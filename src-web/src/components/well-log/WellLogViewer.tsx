import React, { useEffect } from 'react';
import { WellLogViewerProps } from './types';
import { WellLogCanvas } from './WellLogCanvas';

/**
 * WellLogViewer - Container component for well log visualization
 * Provides scrolling, loading states, and responsive layout
 */
export const WellLogViewer: React.FC<WellLogViewerProps> = ({
  wellData,
  className = '',
  trackWidth = 120,
  depthPixelRatio = 0.3,
  loading = false,
  error = null,
}) => {
  const _containerHeight = 600;

  // When well data changes, reset scroll to top handled by browser
  useEffect(() => {
    // Reset when well changes - browser scroll container will stay at top automatically
  }, [wellData.well_id]);

  if (loading) {
    return (
      <div className={`well-log-viewer ${className} p-4 bg-gray-50 rounded-lg text-center`}>
        <div className="animate-pulse text-gray-500">Loading well log data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`well-log-viewer ${className} p-4 bg-red-50 rounded-lg text-red-600`}>
        Error: {error}
      </div>
    );
  }

  const hasMultipleCurves = wellData.curves.length > 1;
  const totalWidth = wellData.curves.length * trackWidth;
  const depthRange = wellData.depth_end - wellData.depth_start;
  const totalHeight = depthRange * depthPixelRatio;
  const sampleCount = wellData.curves[0]?.depth.length || 0;

  // Dummy handler to satisfy prop type
  const _handleHeightCalculated = () => {};

  return (
    <div className={`well-log-viewer ${className}`}>
      {/* Header with well info */}
      <div className="well-log-header mb-3 p-3 bg-gray-50 rounded-lg">
        <h3 className="text-lg font-semibold text-black">
          {wellData.well_name} <span className="text-black/60 font-normal">({wellData.well_id})</span>
        </h3>
        <div className="text-sm text-black mt-1">
          Depth range: {wellData.depth_start.toFixed(0)}m - {wellData.depth_end.toFixed(0)}m
          {hasMultipleCurves && ` • ${wellData.curves.length} curves`}
          {' • '}{sampleCount.toLocaleString()} samples
        </div>
      </div>

      {/* Main scrolling container */}
      <div
        className="well-log-scroll-container border border-gray-200 rounded-lg bg-white overflow-y-auto"
        style={{ height: Math.min(_containerHeight, totalHeight + 40), maxHeight: '80vh' }}
      >
        <div
          className="well-log-content"
          style={{ width: totalWidth, minWidth: '100%' }}
        >
          <WellLogCanvas
            wellData={wellData}
            trackWidth={trackWidth}
            depthPixelRatio={depthPixelRatio}
            onHeightCalculated={_handleHeightCalculated}
          />
        </div>
      </div>

      {/* Scale info footer */}
      <div className="well-log-footer mt-2 text-xs text-black/60 text-right">
        Scale: 1m = {depthPixelRatio}px • Track width: {trackWidth}px
      </div>
    </div>
  );
};

export default WellLogViewer;
