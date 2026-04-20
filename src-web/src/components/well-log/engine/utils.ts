import * as d3 from 'd3';
import type { CurveData, IntervalItem } from '../types';

export function interpolateCurve(curve: CurveData, depth: number): number | null {
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

export function wrapText(
  parent: d3.Selection<SVGTextElement, unknown, null, undefined>,
  text: string, maxW: number, fontSize: number,
  align: 'middle' | 'start' = 'middle',
) {
  const charW = fontSize * 0.85;
  const maxChars = Math.floor(maxW / charW);
  if (maxChars <= 0 || !text) return;
  if (text.length <= maxChars) { parent.text(text); return; }

  const lines: string[] = [];
  let remaining = text;
  while (remaining.length > maxChars) {
    lines.push(remaining.slice(0, maxChars));
    remaining = remaining.slice(maxChars);
  }
  if (remaining) lines.push(remaining);

  const lineH = fontSize * 1.25;
  const totalTextH = lines.length * lineH;
  parent.selectAll('tspan').remove();

  lines.forEach((line, li) => {
    const tspan = parent.append('tspan').attr('x', parent.attr('x')).text(line);
    if (li === 0) {
      const firstLineDy = align === 'middle' ? -(totalTextH / 2) + lineH * 0.35 : 0;
      tspan.attr('dy', `${firstLineDy}px`);
    } else {
      tspan.attr('dy', `${lineH}px`);
    }
  });
}

export function svgToScreenCoords(bodyNode: SVGGElement, event: MouseEvent): { mx: number; my: number } {
  const ctm = bodyNode.getScreenCTM();
  if (!ctm) return { mx: -1, my: -1 };
  return {
    mx: (event.clientX - ctm.e) / ctm.a,
    my: (event.clientY - ctm.f) / ctm.d,
  };
}

export function hitTestIntervals(items: IntervalItem[], depth: number): IntervalItem | undefined {
  return items.find(iv => depth >= iv.top && depth <= iv.bottom);
}
