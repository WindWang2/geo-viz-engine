import { useRef, useEffect, useImperativeHandle, forwardRef } from 'react';
import * as d3 from 'd3';
import type { WellLogData, WellIntervals, IntervalItem, CurveData, FaciesData } from '../types';
import type { ChartConfig, ChartRef, RenderContext } from './types';
import { registerAllPatterns } from './patterns';
import { drawHeader, drawGrid, drawIntervals, drawCurves, drawFaciesColumn, drawLithologyColumn, drawDescriptionColumn, drawDepthTicks, drawSystemsTractColumn } from './renderers';
import { setupInteraction } from './interaction';
import { doExportSVG, doExportPNG, doExportPDF } from './export';

interface Props {
  data: WellLogData;
  config: ChartConfig;
  onDataChange?: (data: WellLogData) => void;
}

const HEADER_H1 = 50, HEADER_H2 = 30, HEADER_TOTAL = HEADER_H1 + HEADER_H2;

export const WellLogChart = forwardRef<ChartRef, Props>(({ data, config, onDataChange }, ref) => {
  const svgRef = useRef<SVGSVGElement>(null);

  const startDepth = data.depth_start;
  const endDepth = data.depth_end;
  const intervals = data.intervals ?? {
    series: [], system: [], formation: [], member: [],
    lithology: [], systems_tract: [], sequence: [],
    facies: { phase: [], sub_phase: [], micro_phase: [] },
  } as WellIntervals;

  const colWidths = config.columns.map(c => c.width);
  const totalWidth = colWidths.reduce((a, b) => a + b, 0);
  const pixelRatio = config.pixelRatio;

  const allItems = [
    ...intervals.series, ...intervals.system, ...intervals.formation,
    ...intervals.lithology, ...intervals.systems_tract, ...intervals.sequence,
    ...intervals.facies.micro_phase, ...intervals.facies.sub_phase, ...intervals.facies.phase,
  ];
  const maxDepth = allItems.reduce((m, iv) => Math.max(m, iv.bottom), endDepth);
  const gridHeight = (maxDepth - startDepth) * pixelRatio;
  const bodyStart = 40 + HEADER_TOTAL;
  const totalHeight = bodyStart + gridHeight + 2;

  const colX: number[] = [];
  let cx = 0;
  for (const w of colWidths) { colX.push(cx); cx += w; }

  const yScale = d3.scaleLinear().domain([startDepth, maxDepth]).range([0, gridHeight]);

  // Build curve groups from config
  const curveGroups = new Map<number, CurveData[]>();
  config.columns.forEach((col, i) => {
    if (col.curveFilter) {
      const filtered = data.curves.filter(c => col.curveFilter!.some(f => f.toUpperCase() === c.name.toUpperCase()));
      if (filtered.length > 0) curveGroups.set(i, filtered);
    }
  });

  useEffect(() => {
    const svg = d3.select<SVGSVGElement, unknown>(svgRef.current!);
    svg.selectAll('*').remove();

    const defs = svg.append('defs');
    registerAllPatterns(defs);

    for (let i = 0; i < colWidths.length; i++) {
      defs.append('clipPath').attr('id', `clip-${i}`)
        .append('rect').attr('x', colX[i]).attr('y', 0).attr('width', colWidths[i]).attr('height', gridHeight);
    }

    const renderCtx: RenderContext = {
      svg, body: null as any, defs, data, intervals, config,
      colX, colWidths, totalWidth, gridHeight, totalHeight,
      bodyStart, yScale, startDepth, maxDepth,
    };

    drawHeader(renderCtx, curveGroups);
    const body = drawGrid(renderCtx, bodyStart);
    renderCtx.body = body;

    // Draw all columns based on config
    config.columns.forEach((col, i) => {
      switch (col.type) {
        case 'intervals':
          if (col.dataKey) {
            const items = (intervals as any)[col.dataKey] as IntervalItem[];
            if (items) drawIntervals(body, items, i, renderCtx, { fill: undefined, rotate: col.rotate });
          }
          break;
        case 'curves': {
          const curves = curveGroups.get(i);
          if (curves) drawCurves(body, curves, i, renderCtx);
          break;
        }
        case 'depth':
          drawDepthTicks(body, i, renderCtx);
          break;
        case 'lithology':
          if (col.dataKey) {
            const items = (intervals as any)[col.dataKey] as IntervalItem[];
            if (items) drawLithologyColumn(body, items, i, renderCtx);
          }
          break;
        case 'description':
          drawDescriptionColumn(body, intervals.lithology, i, renderCtx, onDataChange);
          break;
        case 'facies':
          if (col.faciesLevel) {
            const items = intervals.facies[col.faciesLevel as keyof typeof intervals.facies];
            if (items) drawFaciesColumn(body, items, i, col.faciesLevel as keyof FaciesData, renderCtx, onDataChange);
          }
          break;
        case 'systems_tract':
          drawSystemsTractColumn(body, intervals.systems_tract, i, renderCtx);
          break;
      }
    });

    // Bottom border
    body.append('line')
      .attr('x1', 0).attr('y1', gridHeight).attr('x2', totalWidth).attr('y2', gridHeight)
      .attr('stroke', '#334155').attr('stroke-width', 1);

    // Interaction
    const cleanup = setupInteraction({
      svgRef: svgRef.current!,
      body, bodyNode: body.node()!,
      curves: data.curves, intervals,
      totalWidth, gridHeight, yScale, config,
    });

    return cleanup;
  }, [data, intervals, config, curveGroups, startDepth, maxDepth, gridHeight, totalWidth, totalHeight, yScale, colX, colWidths, onDataChange]);

  useImperativeHandle(ref, () => ({
    exportSVG: () => { if (svgRef.current) doExportSVG(svgRef.current, data, startDepth, endDepth); },
    exportPNG: async () => { if (svgRef.current) await doExportPNG(svgRef.current, data, startDepth, endDepth); },
    exportPDF: () => { if (svgRef.current) doExportPDF(svgRef.current, data); },
  }));

  return (
    <svg
      ref={svgRef}
      width={totalWidth}
      height={totalHeight}
      viewBox={`0 0 ${totalWidth} ${totalHeight}`}
      style={{ display: 'block', backgroundColor: '#fff', fontFamily: "'Noto Sans SC', 'Microsoft YaHei', sans-serif" }}
    />
  );
});

WellLogChart.displayName = 'WellLogChart';
export default WellLogChart;
