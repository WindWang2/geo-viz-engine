import { useRef, useEffect, useImperativeHandle, forwardRef } from 'react';
import * as d3 from 'd3';
import type { WellLogData, WellIntervals, IntervalItem, CurveData, FaciesData } from './types';

interface Props {
  data: WellLogData;
  onDataChange?: (data: WellLogData) => void;
}

export interface ChartRef {
  exportSVG: () => void;
  exportPNG: () => void;
  exportPDF: () => void;
}

const COL_WIDTHS = [40, 40, 40, 120, 40, 60, 120, 150, 120, 80, 80, 80, 60, 40];
const HEADER_H1 = 50;
const HEADER_H2 = 30;
const HEADER_TOTAL = HEADER_H1 + HEADER_H2;

const FACIES_COLORS: Record<string, string> = {
  '潮坪': '#dbeafe', '陆棚': '#d1fae5', '砂坪': '#fef3c7', '泥坪': '#e5e7eb',
  '陆棚夹': '#bfdbfe', '混积': '#fde68a', '碎屑岩': '#fcd34d', '云质': '#93c5fd',
  '砂泥质': '#fef9c3', '泥质': '#e2e8f0', '砂质': '#fef08a',
  '河流相': '#fef3c7', '三角洲相': '#dbeafe', '滨岸相': '#d1fae5',
  '泥岩': '#e5e7eb', '砂岩': '#fef08a', '粉砂岩': '#f3f4f6', '石灰岩': '#dbeafe',
};

function faciesColor(name: string): string {
  for (const [k, v] of Object.entries(FACIES_COLORS)) {
    if (name.includes(k)) return v;
  }
  return '#f3f4f6';
}

const LITHO_COLORS: Record<string, string> = {
  '白云岩': '#dbeafe', '白云质': '#bfdbfe', '砂质白云岩': '#93c5fd',
  '砂岩': '#fef08a', '细砂岩': '#fef9c3', '粉砂岩': '#f3f4f6', '泥质粉砂岩': '#e2e8f0',
  '泥岩': '#d1d5db', '页岩': '#9ca3af', '灰岩': '#e0e7ff', '石灰岩': '#c7d2fe',
  '紫红色': '#fecaca', '灰绿色': '#bbf7d0', '灰黑色': '#6b7280', '深灰色': '#9ca3af',
  '浅灰色': '#f3f4f6', '灰色': '#e5e7eb',
};

function lithoColor(name: string): string {
  for (const [k, v] of Object.entries(LITHO_COLORS)) {
    if (name.includes(k)) return v;
  }
  return '#f3f4f6';
}

type LithoPattern = 'dolomite' | 'sandstone' | 'siltstone' | 'mudstone' | 'shale' | 'limestone';
const LITHO_PATTERNS: Record<string, LithoPattern> = {
  '白云岩': 'dolomite', '白云质': 'dolomite', '砂质白云岩': 'dolomite',
  '砂岩': 'sandstone', '细砂岩': 'sandstone',
  '粉砂岩': 'siltstone', '泥质粉砂岩': 'siltstone',
  '泥岩': 'mudstone',
  '页岩': 'shale',
  '灰岩': 'limestone', '石灰岩': 'limestone',
};

function lithoPatternType(name: string): LithoPattern | null {
  for (const [k, v] of Object.entries(LITHO_PATTERNS)) {
    if (name.includes(k)) return v;
  }
  return null;
}

function registerLithoPatterns(defs: d3.Selection<SVGDefsElement, unknown, null, undefined>) {
  const sz = 10;

  const dolomite = defs.append('pattern').attr('id', 'pat-dolomite')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', sz).attr('height', sz);
  dolomite.append('rect').attr('width', sz).attr('height', sz).attr('fill', '#dbeafe');
  dolomite.append('line').attr('x1', 0).attr('y1', sz / 2).attr('x2', sz).attr('y2', sz / 2)
    .attr('stroke', '#666').attr('stroke-width', 0.5);
  dolomite.append('line').attr('x1', 0).attr('y1', 0).attr('x2', sz / 2).attr('y2', sz / 2)
    .attr('stroke', '#888').attr('stroke-width', 0.4);
  dolomite.append('line').attr('x1', sz / 2).attr('y1', 0).attr('x2', sz).attr('y2', sz / 2)
    .attr('stroke', '#888').attr('stroke-width', 0.4);

  const sandstone = defs.append('pattern').attr('id', 'pat-sandstone')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', sz).attr('height', sz);
  sandstone.append('rect').attr('width', sz).attr('height', sz).attr('fill', '#fef9c3');
  sandstone.append('circle').attr('cx', 2).attr('cy', 2).attr('r', 0.7).attr('fill', '#b45309');
  sandstone.append('circle').attr('cx', 7).attr('cy', 5).attr('r', 0.7).attr('fill', '#b45309');
  sandstone.append('circle').attr('cx', 4).attr('cy', 8).attr('r', 0.7).attr('fill', '#b45309');

  const siltstone = defs.append('pattern').attr('id', 'pat-siltstone')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', sz).attr('height', sz);
  siltstone.append('rect').attr('width', sz).attr('height', sz).attr('fill', '#f3f4f6');
  siltstone.append('circle').attr('cx', 3).attr('cy', 3).attr('r', 0.4).attr('fill', '#999');
  siltstone.append('circle').attr('cx', 8).attr('cy', 7).attr('r', 0.4).attr('fill', '#999');

  const mudstone = defs.append('pattern').attr('id', 'pat-mudstone')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', sz).attr('height', sz);
  mudstone.append('rect').attr('width', sz).attr('height', sz).attr('fill', '#d1d5db');
  mudstone.append('line').attr('x1', 0).attr('y1', 3).attr('x2', sz).attr('y2', 3)
    .attr('stroke', '#666').attr('stroke-width', 0.4).attr('stroke-dasharray', '2,2');
  mudstone.append('line').attr('x1', 0).attr('y1', 7).attr('x2', sz).attr('y2', 7)
    .attr('stroke', '#666').attr('stroke-width', 0.4).attr('stroke-dasharray', '2,2');

  const shale = defs.append('pattern').attr('id', 'pat-shale')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', sz).attr('height', sz);
  shale.append('rect').attr('width', sz).attr('height', sz).attr('fill', '#9ca3af');
  shale.append('line').attr('x1', 0).attr('y1', 2).attr('x2', sz).attr('y2', 2)
    .attr('stroke', '#555').attr('stroke-width', 0.6);
  shale.append('line').attr('x1', 0).attr('y1', 5).attr('x2', sz).attr('y2', 5)
    .attr('stroke', '#555').attr('stroke-width', 0.6);
  shale.append('line').attr('x1', 0).attr('y1', 8).attr('x2', sz).attr('y2', 8)
    .attr('stroke', '#555').attr('stroke-width', 0.6);

  const limestone = defs.append('pattern').attr('id', 'pat-limestone')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', sz).attr('height', sz);
  limestone.append('rect').attr('width', sz).attr('height', sz).attr('fill', '#e0e7ff');
  limestone.append('line').attr('x1', 0).attr('y1', sz / 2).attr('x2', sz).attr('y2', sz / 2)
    .attr('stroke', '#666').attr('stroke-width', 0.5);
  limestone.append('line').attr('x1', 0).attr('y1', 0).attr('x2', 0).attr('y2', sz / 2)
    .attr('stroke', '#666').attr('stroke-width', 0.4);
  limestone.append('line').attr('x1', sz / 2).attr('y1', sz / 2).attr('x2', sz / 2).attr('y2', sz)
    .attr('stroke', '#666').attr('stroke-width', 0.4);
}

function interpolateCurve(curve: CurveData, depth: number): number | null {
  if (curve.depth.length === 0) return null;
  if (depth < curve.depth[0] || depth > curve.depth[curve.depth.length - 1]) return null;
  const bisect = d3.bisector((d: number) => d).left;
  const idx = bisect(curve.depth, depth);
  if (idx === 0) return curve.data[0];
  if (idx >= curve.depth.length) return curve.data[curve.depth.length - 1];
  const d0 = curve.depth[idx - 1], d1 = curve.depth[idx];
  const t = (depth - d0) / (d1 - d0);
  return curve.data[idx - 1] * (1 - t) + curve.data[idx] * t;
}

export const LaoLong1Chart = forwardRef<ChartRef, Props>(({ data, onDataChange }, ref) => {
  const svgRef = useRef<SVGSVGElement>(null);

  const startDepth = data.depth_start;
  const endDepth = data.depth_end;
  const intervals = data.intervals ?? {
    series: [], system: [], formation: [], member: [],
    lithology: [], systems_tract: [], sequence: [],
    facies: { phase: [], sub_phase: [], micro_phase: [] },
  } as WellIntervals;

  const pixelRatio = 14;
  const totalWidth = COL_WIDTHS.reduce((a, b) => a + b, 0);

  const allItems = [
    ...intervals.series, ...intervals.system, ...intervals.formation,
    ...intervals.lithology, ...intervals.systems_tract, ...intervals.sequence,
    ...intervals.facies.micro_phase, ...intervals.facies.sub_phase, ...intervals.facies.phase,
  ];
  const maxDepth = allItems.reduce((m, iv) => Math.max(m, iv.bottom), endDepth);
  const gridHeight = (maxDepth - startDepth) * pixelRatio;
  const totalHeight = HEADER_TOTAL + gridHeight + 2;

  const colX: number[] = [];
  let cx = 0;
  for (const w of COL_WIDTHS) { colX.push(cx); cx += w; }

  const yScale = d3.scaleLinear().domain([startDepth, maxDepth]).range([0, gridHeight]);

  const acGrCurves = data.curves.filter(c => ['AC', 'GR'].includes(c.name.toUpperCase()));
  const rtRxoCurves = data.curves.filter(c => ['RT', 'RXO'].includes(c.name.toUpperCase()));
  const shPermAphie = data.curves.filter(c => ['SH', 'PERM', 'PHIE'].includes(c.name.toUpperCase()));

  useEffect(() => {
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const defs = svg.append('defs');
    registerLithoPatterns(defs);

    for (let i = 0; i < COL_WIDTHS.length; i++) {
      defs.append('clipPath').attr('id', `clip-${i}`)
        .append('rect').attr('x', colX[i]).attr('y', 0).attr('width', COL_WIDTHS[i]).attr('height', gridHeight);
    }

    // --- Title ---
    svg.append('text')
      .attr('x', totalWidth / 2).attr('y', 16)
      .attr('text-anchor', 'middle')
      .attr('font-size', 15).attr('font-weight', 'bold').attr('font-family', "'Noto Serif SC', 'SimSun', serif")
      .attr('fill', '#1a1a2e')
      .text(`${data.well_name} 综合测井解释图`);
    svg.append('text')
      .attr('x', totalWidth / 2).attr('y', 32)
      .attr('text-anchor', 'middle')
      .attr('font-size', 9).attr('fill', '#6b7280').attr('font-family', 'monospace')
      .text(`DEPTH ${startDepth}m – ${endDepth}m  |  Well ID: ${data.well_id}`);

    // --- Header Row 1 ---
    const h1y = 40;
    svg.append('rect').attr('x', 0).attr('y', h1y).attr('width', totalWidth).attr('height', HEADER_H1)
      .attr('fill', '#f8fafc').attr('stroke', '#334155').attr('stroke-width', 1);

    const h1Labels: Array<{ label: string; x: number; w: number; colIdx: number }> = [
      { label: '地层系统', x: colX[0], w: COL_WIDTHS[0] + COL_WIDTHS[1] + COL_WIDTHS[2], colIdx: -1 },
      { label: 'AC/GR', x: colX[3], w: COL_WIDTHS[3], colIdx: 3 },
      { label: '深度', x: colX[4], w: COL_WIDTHS[4], colIdx: -1 },
      { label: '岩性', x: colX[5], w: COL_WIDTHS[5], colIdx: -1 },
      { label: 'RT/RXO', x: colX[6], w: COL_WIDTHS[6], colIdx: 6 },
      { label: '岩性描述', x: colX[7], w: COL_WIDTHS[7], colIdx: -1 },
      { label: 'SH/PERM\n/PHIE', x: colX[8], w: COL_WIDTHS[8], colIdx: 8 },
      { label: '沉积相', x: colX[9], w: COL_WIDTHS[9] + COL_WIDTHS[10] + COL_WIDTHS[11], colIdx: -1 },
      { label: '体系域', x: colX[12], w: COL_WIDTHS[12], colIdx: -1 },
      { label: '层序', x: colX[13], w: COL_WIDTHS[13], colIdx: -1 },
    ];

    for (const { label, x, w, colIdx } of h1Labels) {
      svg.append('text')
        .attr('x', x + w / 2).attr('y', h1y + 13)
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('font-size', 10).attr('font-weight', 'bold').attr('fill', '#1e293b')
        .attr('font-family', "'Noto Sans SC', sans-serif")
        .text(label.replace('\n', ''));

      if (colIdx >= 0) {
        let curves: CurveData[] = [];
        if (colIdx === 3) curves = acGrCurves;
        else if (colIdx === 6) curves = rtRxoCurves;
        else if (colIdx === 8) curves = shPermAphie;

        const legendStartY = h1y + 26;
        const legendSpacing = 12;
        curves.forEach((curve, ci) => {
          const ly = legendStartY + ci * legendSpacing;
          const lx = x + 3;
          svg.append('line')
            .attr('x1', lx).attr('y1', ly).attr('x2', lx + 14).attr('y2', ly)
            .attr('stroke', curve.color).attr('stroke-width', 1.8)
            .attr('stroke-dasharray', curve.line_style === 'dashed' ? '4,2' : curve.line_style === 'dotted' ? '1,1' : 'none');
          svg.append('text')
            .attr('x', lx + 17).attr('y', ly + 1)
            .attr('dominant-baseline', 'middle')
            .attr('font-size', 6).attr('fill', curve.color).attr('font-family', 'monospace').attr('font-weight', 'bold')
            .text(`${curve.name} ${curve.display_range[0]}–${curve.display_range[1]}`);
        });
      }
    }

    // Row 1 column lines — skip merged groups
    const mergedCols = new Set([1, 2, 10, 11]);
    for (let i = 1; i < COL_WIDTHS.length; i++) {
      if (mergedCols.has(i)) continue;
      svg.append('line').attr('x1', colX[i]).attr('y1', h1y).attr('x2', colX[i]).attr('y2', h1y + HEADER_H1)
        .attr('stroke', '#cbd5e1').attr('stroke-width', 0.5);
    }

    // --- Header Row 2 ---
    const h2y = h1y + HEADER_H1;
    svg.append('rect').attr('x', 0).attr('y', h2y).attr('width', totalWidth).attr('height', HEADER_H2)
      .attr('fill', '#f1f5f9').attr('stroke', '#334155').attr('stroke-width', 1);
    const h2Labels = ['系', '统', '组', '', '(m)', '', '', '', '', '微相', '亚相', '相', '', ''];
    for (let i = 0; i < h2Labels.length; i++) {
      if (h2Labels[i]) {
        svg.append('text')
          .attr('x', colX[i] + COL_WIDTHS[i] / 2).attr('y', h2y + HEADER_H2 / 2)
          .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
          .attr('font-size', 9).attr('font-weight', '600').attr('fill', '#475569')
          .attr('font-family', "'Noto Sans SC', sans-serif")
          .text(h2Labels[i]);
      }
      if (i > 0) {
        svg.append('line').attr('x1', colX[i]).attr('y1', h2y).attr('x2', colX[i]).attr('y2', h2y + HEADER_H2)
          .attr('stroke', '#cbd5e1').attr('stroke-width', 0.5);
      }
    }

    // --- Grid Body ---
    const gy = h2y + HEADER_H2;
    const body = svg.append('g').attr('transform', `translate(0, ${gy})`);

    // White background
    body.append('rect').attr('x', 0).attr('y', 0).attr('width', totalWidth).attr('height', gridHeight)
      .attr('fill', '#ffffff').attr('stroke', '#334155').attr('stroke-width', 1);

    // Alternating column shading for curve tracks (3, 6, 8)
    const altTrackIdxs = [3, 6, 8];
    for (const ci of altTrackIdxs) {
      body.append('rect').attr('x', colX[ci]).attr('y', 0).attr('width', COL_WIDTHS[ci]).attr('height', gridHeight)
        .attr('fill', '#fafbfd');
    }

    // Column lines
    for (let i = 1; i < COL_WIDTHS.length; i++) {
      body.append('line').attr('x1', colX[i]).attr('y1', 0).attr('x2', colX[i]).attr('y2', gridHeight)
        .attr('stroke', '#cbd5e1').attr('stroke-width', 0.4);
    }

    // Fine horizontal grid lines every 5m
    for (let d = Math.ceil(startDepth); d <= maxDepth; d += 1) {
      const dy = yScale(d);
      if (dy < 0 || dy > gridHeight) continue;
      body.append('line')
        .attr('x1', 0).attr('y1', dy).attr('x2', totalWidth).attr('y2', dy)
        .attr('stroke', d % 5 === 0 ? '#e2e8f0' : '#f1f5f9').attr('stroke-width', d % 5 === 0 ? 0.5 : 0.3);
    }

    // --- Helper: wrap text into tspans, centered ---
    function wrapText(parent: d3.Selection<SVGTextElement, unknown, null, undefined>, text: string, maxW: number, fontSize: number, align: 'middle' | 'start' = 'middle') {
      // Chinese chars are ~1.0em wide; use conservative estimate
      const charW = fontSize * 0.85;
      const maxChars = Math.floor(maxW / charW);
      if (maxChars <= 0 || !text) return;
      if (text.length <= maxChars) {
        parent.text(text);
        return;
      }
      const lines: string[] = [];
      let remaining = text;
      while (remaining.length > maxChars) {
        lines.push(remaining.slice(0, maxChars));
        remaining = remaining.slice(maxChars);
      }
      if (remaining) lines.push(remaining);

      const lineH = fontSize * 1.25;
      const totalTextH = lines.length * lineH;
      // Clear existing content
      parent.selectAll('tspan').remove();

      lines.forEach((line, li) => {
        const tspan = parent.append('tspan')
          .attr('x', parent.attr('x'))
          .text(line);
        if (li === 0) {
          // First line: set dy to offset so the block is centered
          const firstLineDy = align === 'middle'
            ? -(totalTextH / 2) + lineH * 0.35
            : 0;
          tspan.attr('dy', `${firstLineDy}px`);
        } else {
          tspan.attr('dy', `${lineH}px`);
        }
      });
    }

    // --- Helper: draw interval column ---
    function drawIntervals(items: IntervalItem[], colIdx: number, opts?: { fill?: string; rotate?: boolean }) {
      const x = colX[colIdx];
      const w = COL_WIDTHS[colIdx];
      const g = body.append('g').attr('clip-path', `url(#clip-${colIdx})`);
      for (const iv of items) {
        const y1 = yScale(iv.top);
        const h = yScale(iv.bottom) - y1;
        if (opts?.fill) {
          g.append('rect').attr('x', x + 1).attr('y', y1).attr('width', w - 2).attr('height', h)
            .attr('fill', opts.fill).attr('stroke', '#00000020').attr('stroke-width', 0.5);
        }
        g.append('line').attr('x1', x).attr('y1', y1).attr('x2', x + w).attr('y2', y1)
          .attr('stroke', '#00000030').attr('stroke-width', 0.5);
        if (h > 10) {
          const tx = x + w / 2;
          const ty = y1 + h / 2;
          if (opts?.rotate) {
            const fs = Math.min(11, h * 0.15);
            if (fs >= 7) {
              const t = g.append('text')
                .attr('x', tx).attr('y', ty)
                .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
                .attr('font-size', fs).attr('font-weight', 'bold')
                .attr('transform', `rotate(-90, ${tx}, ${ty})`);
              wrapText(t, iv.name, h - 8, fs);
            }
          } else {
            const fs = Math.min(10, h * 0.5);
            const t = g.append('text')
              .attr('x', tx).attr('y', ty)
              .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
              .attr('font-size', fs);
            wrapText(t, iv.name, w - 8, fs);
          }
        }
      }
    }

    // --- Helper: draw curve column ---
    function drawCurves(curves: CurveData[], colIdx: number) {
      const x = colX[colIdx];
      const w = COL_WIDTHS[colIdx];
      const g = body.append('g').attr('clip-path', `url(#clip-${colIdx})`);
      for (const curve of curves) {
        const xScale = d3.scaleLinear().domain([curve.display_range[0], curve.display_range[1]]).range([x + 2, x + w - 2]);
        const line = d3.line<{ depth: number; val: number }>()
          .x(d => xScale(d.val))
          .y(d => yScale(d.depth));
        const points = curve.depth.map((d, i) => ({ depth: d, val: curve.data[i] }));
        const step = Math.max(1, Math.floor(points.length / 600));
        const sampled = points.filter((_, i) => i % step === 0 || i === points.length - 1);
        g.append('path')
          .datum(sampled)
          .attr('d', line)
          .attr('fill', 'none')
          .attr('stroke', curve.color)
          .attr('stroke-width', 1.2)
          .attr('stroke-dasharray', curve.line_style === 'dashed' ? '4,2' : curve.line_style === 'dotted' ? '1,1' : 'none');
      }
    }

    // --- Helper: draw facies column with click-to-edit ---
    function drawFacies(items: IntervalItem[], colIdx: number, level: keyof FaciesData) {
      const x = colX[colIdx];
      const w = COL_WIDTHS[colIdx];
      const g = body.append('g').attr('clip-path', `url(#clip-${colIdx})`);
      items.forEach((iv, idx) => {
        const y1 = yScale(iv.top);
        const h = yScale(iv.bottom) - y1;
        g.append('rect').attr('x', x + 1).attr('y', y1).attr('width', w - 2).attr('height', h)
          .attr('fill', faciesColor(iv.name)).attr('stroke', '#00000030').attr('stroke-width', 0.5)
          .attr('cursor', 'pointer')
          .on('click', () => {
            if (!onDataChange) return;
            const newName = prompt('请输入新的沉积相名称:', iv.name);
            if (newName && newName.trim() && newName.trim() !== iv.name) {
              const updated = structuredClone(data);
              const arr = updated.intervals!.facies[level];
              arr[idx] = { ...arr[idx], name: newName.trim() };
              onDataChange(updated);
            }
          });
        if (h > 10) {
          const fs = Math.min(11, h * 0.5);
          const t = g.append('text')
            .attr('x', x + w / 2).attr('y', y1 + h / 2)
            .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
            .attr('font-size', fs).attr('fill', '#1f2937')
            .attr('pointer-events', 'none');
          wrapText(t, iv.name, w - 8, fs);
        }
      });
    }

    // --- Draw all columns ---
    drawIntervals(intervals.series, 0, { rotate: true });
    drawIntervals(intervals.system, 1, { rotate: true });
    drawIntervals(intervals.formation, 2, { rotate: true });
    drawCurves(acGrCurves, 3);

    // Depth ticks
    const depthX = colX[4];
    const depthW = COL_WIDTHS[4];
    for (let d = Math.ceil(startDepth / 5) * 5; d <= maxDepth; d += 5) {
      const dy = yScale(d);
      if (dy < 8) continue;
      // Short tick lines at column edges
      body.append('line')
        .attr('x1', depthX).attr('y1', dy).attr('x2', depthX + 6).attr('y2', dy)
        .attr('stroke', '#94a3b8').attr('stroke-width', 0.4);
      body.append('line')
        .attr('x1', depthX + depthW - 6).attr('y1', dy).attr('x2', depthX + depthW).attr('y2', dy)
        .attr('stroke', '#94a3b8').attr('stroke-width', 0.4);
      body.append('text')
        .attr('x', depthX + depthW / 2).attr('y', dy + 1)
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('font-size', 6.5).attr('font-family', 'monospace').attr('font-weight', '600')
        .attr('fill', '#475569')
        .text(d);
    }

    // Lithology with SVG patterns
    const lithoX = colX[5];
    const lithoW = COL_WIDTHS[5];
    const lithoG = body.append('g').attr('clip-path', `url(#clip-5)`);
    for (const iv of intervals.lithology) {
      const y1 = yScale(iv.top);
      const h = yScale(iv.bottom) - y1;
      const pt = lithoPatternType(iv.name);
      const fill = pt ? `url(#pat-${pt})` : lithoColor(iv.name);
      lithoG.append('rect').attr('x', lithoX + 1).attr('y', y1).attr('width', lithoW - 2).attr('height', h)
        .attr('fill', fill).attr('stroke', '#00000040').attr('stroke-width', 0.5);
    }

    drawCurves(rtRxoCurves, 6);

    // Lithology description with click-to-edit
    const descX = colX[7];
    const descW = COL_WIDTHS[7];
    const descG = body.append('g').attr('clip-path', `url(#clip-7)`);
    intervals.lithology.forEach((iv, idx) => {
      const y1 = yScale(iv.top);
      const y2 = yScale(iv.bottom);
      const h = y2 - y1;
      descG.append('line').attr('x1', descX).attr('y1', y1).attr('x2', descX + descW).attr('y2', y1)
        .attr('stroke', '#00000040').attr('stroke-width', 0.5);

      // Transparent clickable rect covering the whole interval
      descG.append('rect').attr('x', descX).attr('y', y1).attr('width', descW).attr('height', h)
        .attr('fill', 'transparent').attr('cursor', 'pointer')
        .on('click', () => {
          if (!onDataChange) return;
          const newName = prompt('请输入新的岩性描述:', iv.name);
          if (newName !== null && newName.trim() !== iv.name) {
            const updated = structuredClone(data);
            updated.intervals!.lithology[idx] = { ...updated.intervals!.lithology[idx], name: newName.trim() };
            onDataChange(updated);
          }
        });

      if (h > 8 && iv.name) {
        const fs = Math.min(10, h * 0.4);
        const t = descG.append('text')
          .attr('x', descX + 5).attr('y', y1 + h / 2)
          .attr('text-anchor', 'start').attr('dominant-baseline', 'middle')
          .attr('font-size', fs).attr('pointer-events', 'none');
        wrapText(t, iv.name, descW - 10, fs, 'start');
      }
    });

    drawCurves(shPermAphie, 8);
    drawFacies(intervals.facies.micro_phase, 9, 'micro_phase');
    drawFacies(intervals.facies.sub_phase, 10, 'sub_phase');
    drawFacies(intervals.facies.phase, 11, 'phase');

    // Systems tract — triangles
    {
      const tractX = colX[12];
      const tractW = COL_WIDTHS[12];
      const tractG = body.append('g').attr('clip-path', `url(#clip-12)`);
      for (const iv of intervals.systems_tract) {
        const y1 = yScale(iv.top);
        const y2 = yScale(iv.bottom);
        const h = y2 - y1;
        tractG.append('line').attr('x1', tractX).attr('y1', y1).attr('x2', tractX + tractW).attr('y2', y1)
          .attr('stroke', '#00000040').attr('stroke-width', 0.5);
        if (h > 4) {
          const cmx = tractX + tractW / 2;
          const name = iv.name.toUpperCase();
          if (name.includes('TST')) {
            tractG.append('polygon')
              .attr('points', `${cmx},${y1 + 2} ${tractX + 2},${y2 - 2} ${tractX + tractW - 2},${y2 - 2}`)
              .attr('fill', '#bfdbfe').attr('stroke', '#333').attr('stroke-width', 0.5);
          } else if (name.includes('HST')) {
            tractG.append('polygon')
              .attr('points', `${tractX + 2},${y1 + 2} ${tractX + tractW - 2},${y1 + 2} ${cmx},${y2 - 2}`)
              .attr('fill', '#fde68a').attr('stroke', '#333').attr('stroke-width', 0.5);
          } else {
            tractG.append('rect').attr('x', tractX + 1).attr('y', y1).attr('width', tractW - 2).attr('height', h)
              .attr('fill', '#e5e7eb').attr('stroke', '#00000030').attr('stroke-width', 0.5);
          }
          if (h > 16) {
            const tt = tractG.append('text')
              .attr('x', cmx).attr('y', (y1 + y2) / 2)
              .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
              .attr('font-size', 9).attr('font-weight', 'bold');
            wrapText(tt, iv.name, tractW - 8, 9);
          }
        }
      }
    }

    drawIntervals(intervals.sequence, 13, { rotate: true });

    // Bottom border
    body.append('line')
      .attr('x1', 0).attr('y1', gridHeight).attr('x2', totalWidth).attr('y2', gridHeight)
      .attr('stroke', '#334155').attr('stroke-width', 1);

    // =============================================
    // --- Interaction Layer: Crosshair + Tooltip ---
    // =============================================
    const interG = body.append('g').attr('class', 'interaction-layer')
      .style('pointer-events', 'none');

    // Horizontal crosshair line
    const hLine = interG.append('line')
      .attr('x1', 0).attr('y1', 0).attr('x2', totalWidth).attr('y2', 0)
      .attr('stroke', '#e11d48').attr('stroke-width', 0.5).attr('stroke-dasharray', '3,3')
      .attr('display', 'none');

    // Depth label on the left
    const depthLabel = interG.append('g').attr('display', 'none');
    depthLabel.append('rect').attr('x', -2).attr('y', -8).attr('width', 44).attr('height', 16)
      .attr('fill', '#e11d48').attr('rx', 2);
    const depthLabelText = depthLabel.append('text')
      .attr('x', 20).attr('y', 1)
      .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
      .attr('font-size', 8).attr('font-weight', 'bold').attr('fill', '#fff')
      .attr('font-family', 'monospace');

    // Tooltip box
    const tooltipW = 160;
    const tooltipLineH = 14;
    const tooltipPad = 4;
    const tooltip = interG.append('g').attr('display', 'none');

    // Tooltip background
    const tooltipBg = tooltip.append('rect')
      .attr('width', tooltipW).attr('height', 10)
      .attr('fill', 'rgba(255,255,255,0.95)').attr('rx', 5).attr('stroke', '#3b82f6').attr('stroke-width', 1);

    // Build all tooltip rows: depth + curves + litho + facies
    const nCurveLines = data.curves.length;
    const extraLines = 1 + 3; // litho + micro/sub/phase
    const totalLines = 1 + nCurveLines + extraLines;

    const tooltipDepthText = tooltip.append('text')
      .attr('x', tooltipPad + 4).attr('y', 0)
      .attr('font-size', 9).attr('font-weight', 'bold').attr('fill', '#1e40af')
      .attr('font-family', 'monospace');

    const tooltipCurveTexts = data.curves.map(() => {
      return tooltip.append('text')
        .attr('x', tooltipPad + 4).attr('y', 0)
        .attr('font-size', 7.5).attr('font-family', 'monospace');
    });

    const tooltipLithoText = tooltip.append('text')
      .attr('x', tooltipPad + 4).attr('y', 0)
      .attr('font-size', 7.5).attr('fill', '#b45309').attr('font-weight', 'bold').attr('font-family', 'monospace');

    const tooltipFaciesTexts = ['微相', '亚相', '相'].map(label => {
      return { label, el: tooltip.append('text')
        .attr('x', tooltipPad + 4).attr('y', 0)
        .attr('font-size', 7.5).attr('fill', '#6d28d9').attr('font-family', 'monospace') };
    });

    const tooltipTotalH = tooltipPad * 2 + tooltipLineH * totalLines;
    tooltipBg.attr('height', tooltipTotalH);

    // Attach mousemove to the SVG element itself so clicks pass through to facies/litho
    const svgEl = d3.select(svgRef.current);
    const bodyNode = body.node()!;
    svgEl
      .on('mousemove.laolong1', function (event: MouseEvent) {
        // Convert screen coords to body local coords via CTM
        const ctm = bodyNode.getScreenCTM();
        if (!ctm) return;
        const mx = (event.clientX - ctm.e) / ctm.a;
        const my = (event.clientY - ctm.f) / ctm.d;

        if (my < 0 || my > gridHeight || mx < 0 || mx > totalWidth) {
          hLine.attr('display', 'none');
          depthLabel.attr('display', 'none');
          tooltip.attr('display', 'none');
          return;
        }

        const depth = yScale.invert(my);

        hLine.attr('y1', my).attr('y2', my).attr('display', null);
        depthLabel.attr('display', null).attr('transform', `translate(0, ${my})`);
        depthLabelText.text(depth.toFixed(1) + 'm');

        const curveValues = data.curves.map(c => {
          const v = interpolateCurve(c, depth);
          return v !== null ? v.toFixed(c.name === 'PERM' ? 2 : 3) : '--';
        });

        let tx = totalWidth - tooltipW - 4;
        let ty = my - tooltipTotalH / 2;
        if (ty < 0) ty = 2;
        if (ty + tooltipTotalH > gridHeight) ty = gridHeight - tooltipTotalH - 2;

        tooltip.attr('display', null).attr('transform', `translate(${tx}, ${ty})`);
        tooltipDepthText
          .text(`深度: ${depth.toFixed(2)}m`)
          .attr('y', tooltipPad + tooltipLineH * 0.5 + 2);

        tooltipCurveTexts.forEach((txt, i) => {
          txt.attr('fill', data.curves[i].color)
            .text(`${data.curves[i].name}: ${curveValues[i]} ${data.curves[i].unit}`)
            .attr('y', tooltipPad + tooltipLineH * (i + 1) + tooltipLineH * 0.5 + 2);
        });

        // Lithology at this depth
        const lithoHit = intervals.lithology.find(iv => depth >= iv.top && depth <= iv.bottom);
        const lithoRow = nCurveLines + 1;
        tooltipLithoText
          .text(`岩性: ${lithoHit ? lithoHit.name : '--'}`)
          .attr('y', tooltipPad + tooltipLineH * lithoRow + tooltipLineH * 0.5 + 2);

        // Facies at this depth
        const faciesLevels: Array<{ label: string; items: IntervalItem[] }> = [
          { label: '微相', items: intervals.facies.micro_phase },
          { label: '亚相', items: intervals.facies.sub_phase },
          { label: '相', items: intervals.facies.phase },
        ];
        faciesLevels.forEach((fl, fi) => {
          const hit = fl.items.find(iv => depth >= iv.top && depth <= iv.bottom);
          tooltipFaciesTexts[fi].el
            .text(`${fl.label}: ${hit ? hit.name : '--'}`)
            .attr('y', tooltipPad + tooltipLineH * (lithoRow + 1 + fi) + tooltipLineH * 0.5 + 2);
        });
      })
      .on('mouseleave.laolong1', () => {
        hLine.attr('display', 'none');
        depthLabel.attr('display', 'none');
        tooltip.attr('display', 'none');
        depthLabel.attr('display', 'none');
        hLine.attr('display', 'none');
      });

    // Cleanup D3 event listeners on unmount
    return () => {
      d3.select(svgRef.current).on('.laolong1', null);
    };

  }, [data, intervals, acGrCurves, rtRxoCurves, shPermAphie, startDepth, maxDepth, gridHeight, totalWidth, totalHeight, yScale, colX, onDataChange]);

  // --- Export ---
  async function svgToCanvas(scale: number): Promise<HTMLCanvasElement> {
    const svgEl = svgRef.current!;
    // Clone SVG and remove interaction layer for clean export
    const cloned = svgEl.cloneNode(true) as SVGSVGElement;
    cloned.querySelectorAll('.interaction-layer').forEach(el => el.remove());

    const serializer = new XMLSerializer();
    const svgStr = serializer.serializeToString(cloned);
    const svgBlob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(svgBlob);

    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = img.width * scale;
        canvas.height = img.height * scale;
        const ctx = canvas.getContext('2d')!;
        ctx.scale(scale, scale);
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, img.width, img.height);
        ctx.drawImage(img, 0, 0);
        URL.revokeObjectURL(url);
        resolve(canvas);
      };
      img.onerror = reject;
      img.src = url;
    });
  }

  useImperativeHandle(ref, () => ({
    exportSVG: () => {
      const svg = svgRef.current;
      if (!svg) return;
      const cloned = svg.cloneNode(true) as SVGSVGElement;
      cloned.querySelectorAll('.interaction-layer').forEach(el => el.remove());
      const serializer = new XMLSerializer();
      const svgStr = serializer.serializeToString(cloned);
      const blob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
      const link = document.createElement('a');
      link.download = `${data.well_name}_${startDepth}-${endDepth}m.svg`;
      link.href = URL.createObjectURL(blob);
      link.click();
      URL.revokeObjectURL(link.href);
    },

    exportPNG: async () => {
      const canvas = await svgToCanvas(3);
      const link = document.createElement('a');
      link.download = `${data.well_name}_${startDepth}-${endDepth}m.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();
    },

    exportPDF: () => {
      const svg = svgRef.current;
      if (!svg) return;
      const cloned = svg.cloneNode(true) as SVGSVGElement;
      cloned.querySelectorAll('.interaction-layer').forEach(el => el.remove());
      const serializer = new XMLSerializer();
      const svgStr = serializer.serializeToString(cloned);
      const win = window.open('', '_blank');
      if (!win) return;
      win.document.write(`<!DOCTYPE html><html><head><title>${data.well_name}</title>
        <style>
          @page { size: auto; margin: 10mm; }
          body { margin: 0; display: flex; justify-content: center; }
          svg { max-width: 100%; height: auto; }
        </style>
      </head><body>${svgStr}</body></html>`);
      win.document.close();
      win.onload = () => {
        win.print();
        setTimeout(() => win.close(), 1000);
      };
    },
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

LaoLong1Chart.displayName = 'LaoLong1Chart';
export default LaoLong1Chart;
