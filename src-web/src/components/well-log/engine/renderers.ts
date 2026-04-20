import * as d3 from 'd3';
import type { CurveData, FaciesData, IntervalItem } from '../types';
import type { RenderContext } from './types';
import { wrapText } from './utils';
import { lookupPattern, lookupColor } from './patterns';

export function drawHeader(ctx: RenderContext, curveGroups: Map<number, CurveData[]>): number {
  const { svg, config, colX, colWidths, totalWidth, data } = ctx;
  const HEADER_H1 = 50, HEADER_H2 = 30;

  // Title
  svg.append('text')
    .attr('x', totalWidth / 2).attr('y', 16)
    .attr('text-anchor', 'middle').attr('font-size', 15).attr('font-weight', 'bold')
    .attr('font-family', "'Noto Serif SC', 'SimSun', serif").attr('fill', '#1a1a2e')
    .text(config.header.titleTemplate(data));
  svg.append('text')
    .attr('x', totalWidth / 2).attr('y', 32)
    .attr('text-anchor', 'middle').attr('font-size', 9).attr('fill', '#6b7280').attr('font-family', 'monospace')
    .text(config.header.subtitleTemplate(data));

  // Header Row 1
  const h1y = 40;
  svg.append('rect').attr('x', 0).attr('y', h1y).attr('width', totalWidth).attr('height', HEADER_H1)
    .attr('fill', '#f8fafc').attr('stroke', '#334155').attr('stroke-width', 1);

  for (const entry of config.header.h1Labels) {
    const colIdx = config.columns.findIndex(c => c.label === entry.label);
    let x: number, w: number;
    if (entry.colSpan) {
      x = colX[entry.colSpan[0]];
      w = colX[entry.colSpan[1]] + colWidths[entry.colSpan[1]] - x;
    } else if (colIdx >= 0) {
      x = colX[colIdx]; w = colWidths[colIdx];
    } else continue;

    svg.append('text')
      .attr('x', x + w / 2).attr('y', h1y + 13)
      .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
      .attr('font-size', 10).attr('font-weight', 'bold').attr('fill', '#1e293b')
      .attr('font-family', "'Noto Sans SC', sans-serif")
      .text(entry.label);

    if (entry.curveCol && colIdx >= 0) {
      const curves = curveGroups.get(colIdx) ?? [];
      curves.forEach((curve, ci) => {
        const ly = h1y + 26 + ci * 12;
        const lx = x + 3;
        svg.append('line')
          .attr('x1', lx).attr('y1', ly).attr('x2', lx + 14).attr('y2', ly)
          .attr('stroke', curve.color).attr('stroke-width', 1.8)
          .attr('stroke-dasharray', curve.line_style === 'dashed' ? '4,2' : curve.line_style === 'dotted' ? '1,1' : 'none');
        svg.append('text')
          .attr('x', lx + 17).attr('y', ly + 1)
          .attr('dominant-baseline', 'middle').attr('font-size', 6).attr('fill', curve.color)
          .attr('font-family', 'monospace').attr('font-weight', 'bold')
          .text(`${curve.name} ${curve.display_range[0]}–${curve.display_range[1]}`);
      });
    }
  }

  for (let i = 1; i < colWidths.length; i++) {
    if (config.header.mergedCols.has(i)) continue;
    svg.append('line').attr('x1', colX[i]).attr('y1', h1y).attr('x2', colX[i]).attr('y2', h1y + HEADER_H1)
      .attr('stroke', '#cbd5e1').attr('stroke-width', 0.5);
  }

  // Header Row 2
  const h2y = h1y + HEADER_H1;
  svg.append('rect').attr('x', 0).attr('y', h2y).attr('width', totalWidth).attr('height', HEADER_H2)
    .attr('fill', '#f1f5f9').attr('stroke', '#334155').attr('stroke-width', 1);
  for (let i = 0; i < config.header.h2Labels.length; i++) {
    if (config.header.h2Labels[i]) {
      svg.append('text')
        .attr('x', colX[i] + colWidths[i] / 2).attr('y', h2y + HEADER_H2 / 2)
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('font-size', 9).attr('font-weight', '600').attr('fill', '#475569')
        .attr('font-family', "'Noto Sans SC', sans-serif")
        .text(config.header.h2Labels[i]);
    }
    if (i > 0) {
      svg.append('line').attr('x1', colX[i]).attr('y1', h2y).attr('x2', colX[i]).attr('y2', h2y + HEADER_H2)
        .attr('stroke', '#cbd5e1').attr('stroke-width', 0.5);
    }
  }

  return h2y + HEADER_H2;
}

export function drawGrid(ctx: RenderContext, bodyStart: number) {
  const { svg, body: _unused, config, colX, colWidths, totalWidth, gridHeight, yScale, startDepth, maxDepth } = ctx;
  const body = svg.append('g').attr('transform', `translate(0, ${bodyStart})`);

  body.append('rect').attr('x', 0).attr('y', 0).attr('width', totalWidth).attr('height', gridHeight)
    .attr('fill', '#ffffff').attr('stroke', '#334155').attr('stroke-width', 1);

  for (const col of config.columns) {
    const i = config.columns.indexOf(col);
    if (col.altShading) {
      body.append('rect').attr('x', colX[i]).attr('y', 0).attr('width', colWidths[i]).attr('height', gridHeight)
        .attr('fill', '#fafbfd');
    }
  }

  for (let i = 1; i < colWidths.length; i++) {
    body.append('line').attr('x1', colX[i]).attr('y1', 0).attr('x2', colX[i]).attr('y2', gridHeight)
      .attr('stroke', '#94a3b8').attr('stroke-width', 0.8);
  }

  for (let d = Math.ceil(startDepth); d <= maxDepth; d += config.gridInterval) {
    const dy = yScale(d);
    if (dy < 0 || dy > gridHeight) continue;
    body.append('line')
      .attr('x1', 0).attr('y1', dy).attr('x2', totalWidth).attr('y2', dy)
      .attr('stroke', '#f1f5f9').attr('stroke-width', 0.3);
  }

  return body;
}

export function drawIntervals(
  body: d3.Selection<SVGGElement, unknown, null, undefined>,
  items: IntervalItem[], colIdx: number,
  ctx: RenderContext, opts?: { fill?: string; rotate?: boolean },
) {
  const { colX, colWidths, yScale } = ctx;
  const x = colX[colIdx], w = colWidths[colIdx];
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
      const tx = x + w / 2, ty = y1 + h / 2;
      if (opts?.rotate) {
        const fs = Math.min(11, h * 0.15);
        if (fs >= 7) {
          const t = g.append('text')
            .attr('x', tx).attr('y', ty).attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
            .attr('font-size', fs).attr('font-weight', 'bold')
            .attr('transform', `rotate(-90, ${tx}, ${ty})`);
          wrapText(t, iv.name, h - 8, fs);
        }
      } else {
        const fs = Math.min(10, h * 0.5);
        const t = g.append('text')
          .attr('x', tx).attr('y', ty).attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
          .attr('font-size', fs);
        wrapText(t, iv.name, w - 8, fs);
      }
    }
  }
}

export function drawCurves(
  body: d3.Selection<SVGGElement, unknown, null, undefined>,
  curves: CurveData[], colIdx: number, ctx: RenderContext,
) {
  const { colX, colWidths, yScale } = ctx;
  const x = colX[colIdx], w = colWidths[colIdx];
  const g = body.append('g').attr('clip-path', `url(#clip-${colIdx})`);
  for (const curve of curves) {
    const xScale = d3.scaleLinear().domain([curve.display_range[0], curve.display_range[1]]).range([x + 2, x + w - 2]);
    const line = d3.line<{ depth: number; val: number }>().x(d => xScale(d.val)).y(d => yScale(d.depth));
    const points = curve.depth.map((d, i) => ({ depth: d, val: curve.data[i] }));
    const step = Math.max(1, Math.floor(points.length / 600));
    const sampled = points.filter((_, i) => i % step === 0 || i === points.length - 1);
    g.append('path').datum(sampled).attr('d', line).attr('fill', 'none')
      .attr('stroke', curve.color).attr('stroke-width', 1.2)
      .attr('stroke-dasharray', curve.line_style === 'dashed' ? '4,2' : curve.line_style === 'dotted' ? '1,1' : 'none');
  }
}

export function drawFaciesColumn(
  body: d3.Selection<SVGGElement, unknown, null, undefined>,
  items: IntervalItem[], colIdx: number, level: keyof FaciesData,
  ctx: RenderContext, onDataChange?: (data: typeof ctx.data) => void,
) {
  const { colX, colWidths, yScale, config, data } = ctx;
  const x = colX[colIdx], w = colWidths[colIdx];
  const g = body.append('g').attr('clip-path', `url(#clip-${colIdx})`);
  items.forEach((iv, idx) => {
    const y1 = yScale(iv.top);
    const h = yScale(iv.bottom) - y1;
    const fp = lookupPattern(iv.name, config.faciesMapping);
    const fill = fp ? `url(#pat-${fp})` : lookupColor(iv.name, config.faciesMapping);
    g.append('rect').attr('x', x + 1).attr('y', y1).attr('width', w - 2).attr('height', h)
      .attr('fill', fill).attr('stroke', '#00000030').attr('stroke-width', 0.5)
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
        .attr('font-size', fs).attr('fill', '#1f2937').attr('pointer-events', 'none');
      wrapText(t, iv.name, w - 8, fs);
    }
  });
}

export function drawLithologyColumn(
  body: d3.Selection<SVGGElement, unknown, null, undefined>,
  items: IntervalItem[], colIdx: number, ctx: RenderContext,
) {
  const { colX, colWidths, yScale, config } = ctx;
  const x = colX[colIdx], w = colWidths[colIdx];
  const g = body.append('g').attr('clip-path', `url(#clip-${colIdx})`);
  for (const iv of items) {
    const y1 = yScale(iv.top);
    const h = yScale(iv.bottom) - y1;
    const pt = lookupPattern(iv.name, config.lithologyMapping);
    const fill = pt ? `url(#pat-${pt})` : lookupColor(iv.name, config.lithologyMapping);
    g.append('rect').attr('x', x + 1).attr('y', y1).attr('width', w - 2).attr('height', h)
      .attr('fill', fill).attr('stroke', '#00000040').attr('stroke-width', 0.5);
  }
}

export function drawDescriptionColumn(
  body: d3.Selection<SVGGElement, unknown, null, undefined>,
  items: IntervalItem[], colIdx: number,
  ctx: RenderContext, onDataChange?: (data: typeof ctx.data) => void,
) {
  const { colX, colWidths, yScale, data } = ctx;
  const x = colX[colIdx], w = colWidths[colIdx];
  const g = body.append('g').attr('clip-path', `url(#clip-${colIdx})`);
  items.forEach((iv, idx) => {
    const y1 = yScale(iv.top);
    const h = yScale(iv.bottom) - y1;
    g.append('line').attr('x1', x).attr('y1', y1).attr('x2', x + w).attr('y2', y1)
      .attr('stroke', '#00000040').attr('stroke-width', 0.5);
    g.append('rect').attr('x', x).attr('y', y1).attr('width', w).attr('height', h)
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
      const t = g.append('text')
        .attr('x', x + 5).attr('y', y1 + h / 2)
        .attr('text-anchor', 'start').attr('dominant-baseline', 'middle')
        .attr('font-size', fs).attr('pointer-events', 'none');
      wrapText(t, iv.name, w - 10, fs, 'start');
    }
  });
}

export function drawDepthTicks(
  body: d3.Selection<SVGGElement, unknown, null, undefined>,
  colIdx: number, ctx: RenderContext,
) {
  const { colX, colWidths, yScale, startDepth, maxDepth } = ctx;
  const x = colX[colIdx], w = colWidths[colIdx];
  for (let d = Math.ceil(startDepth / 5) * 5; d <= maxDepth; d += 5) {
    const dy = yScale(d);
    if (dy < 8) continue;
    body.append('line').attr('x1', x).attr('y1', dy).attr('x2', x + 6).attr('y2', dy)
      .attr('stroke', '#94a3b8').attr('stroke-width', 0.4);
    body.append('line').attr('x1', x + w - 6).attr('y1', dy).attr('x2', x + w).attr('y2', dy)
      .attr('stroke', '#94a3b8').attr('stroke-width', 0.4);
    body.append('text')
      .attr('x', x + w / 2).attr('y', dy + 1)
      .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
      .attr('font-size', 6.5).attr('font-family', 'monospace').attr('font-weight', '600')
      .attr('fill', '#475569')
      .text(d);
  }
}

export function drawSystemsTractColumn(
  body: d3.Selection<SVGGElement, unknown, null, undefined>,
  items: IntervalItem[], colIdx: number, ctx: RenderContext,
) {
  const { colX, colWidths, yScale } = ctx;
  const x = colX[colIdx], w = colWidths[colIdx];
  const g = body.append('g').attr('clip-path', `url(#clip-${colIdx})`);
  for (const iv of items) {
    const y1 = yScale(iv.top);
    const y2 = yScale(iv.bottom);
    const h = y2 - y1;
    g.append('line').attr('x1', x).attr('y1', y1).attr('x2', x + w).attr('y2', y1)
      .attr('stroke', '#00000040').attr('stroke-width', 0.5);
    if (h > 4) {
      const cmx = x + w / 2;
      const name = iv.name.toUpperCase();
      if (name.includes('TST')) {
        g.append('polygon')
          .attr('points', `${cmx},${y1 + 2} ${x + 2},${y2 - 2} ${x + w - 2},${y2 - 2}`)
          .attr('fill', '#bfdbfe').attr('stroke', '#333').attr('stroke-width', 0.5);
      } else if (name.includes('HST')) {
        g.append('polygon')
          .attr('points', `${x + 2},${y1 + 2} ${x + w - 2},${y1 + 2} ${cmx},${y2 - 2}`)
          .attr('fill', '#fde68a').attr('stroke', '#333').attr('stroke-width', 0.5);
      } else {
        g.append('rect').attr('x', x + 1).attr('y', y1).attr('width', w - 2).attr('height', h)
          .attr('fill', '#e5e7eb').attr('stroke', '#00000030').attr('stroke-width', 0.5);
      }
      if (h > 16) {
        const tt = g.append('text')
          .attr('x', cmx).attr('y', (y1 + y2) / 2)
          .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
          .attr('font-size', 9).attr('font-weight', 'bold');
        wrapText(tt, iv.name, w - 8, 9);
      }
    }
  }
}
