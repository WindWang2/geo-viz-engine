import * as d3 from 'd3';
import type { CurveData, WellIntervals } from '../types';
import type { ChartConfig } from './types';
import { interpolateCurve, svgToScreenCoords, hitTestIntervals } from './utils';

interface InteractionSetup {
  svgRef: SVGSVGElement;
  body: d3.Selection<SVGGElement, unknown, null, undefined>;
  bodyNode: SVGGElement;
  curves: CurveData[];
  intervals: WellIntervals;
  totalWidth: number;
  gridHeight: number;
  yScale: d3.ScaleLinear<number, number>;
  config: ChartConfig;
}

export function setupInteraction(ctx: InteractionSetup): () => void {
  const { svgRef, body, bodyNode, curves, intervals, totalWidth, gridHeight, yScale, config } = ctx;

  const interG = body.append('g').attr('class', 'interaction-layer').style('pointer-events', 'none');

  const hLine = interG.append('line')
    .attr('x1', 0).attr('y1', 0).attr('x2', totalWidth).attr('y2', 0)
    .attr('stroke', '#e11d48').attr('stroke-width', 0.5).attr('stroke-dasharray', '3,3')
    .attr('display', 'none');

  const depthLabel = interG.append('g').attr('display', 'none');
  depthLabel.append('rect').attr('x', -2).attr('y', -8).attr('width', 44).attr('height', 16)
    .attr('fill', '#e11d48').attr('rx', 2);
  const depthLabelText = depthLabel.append('text')
    .attr('x', 20).attr('y', 1)
    .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
    .attr('font-size', 8).attr('font-weight', 'bold').attr('fill', '#fff').attr('font-family', 'monospace');

  const tooltipW = 160, tooltipLineH = 14, tooltipPad = 4;
  const tooltip = interG.append('g').attr('display', 'none');
  const tooltipBg = tooltip.append('rect')
    .attr('width', tooltipW).attr('height', 10)
    .attr('fill', 'rgba(255,255,255,0.95)').attr('rx', 5).attr('stroke', '#3b82f6').attr('stroke-width', 1);

  const nCurveLines = curves.length;
  const faciesLevels = [
    { label: '微相', items: intervals.facies.micro_phase },
    { label: '亚相', items: intervals.facies.sub_phase },
    { label: '相', items: intervals.facies.phase },
  ];
  const extraLines = 1 + faciesLevels.length;
  const totalLines = 1 + nCurveLines + extraLines;
  const tooltipTotalH = tooltipPad * 2 + tooltipLineH * totalLines;
  tooltipBg.attr('height', tooltipTotalH);

  const tooltipDepthText = tooltip.append('text')
    .attr('x', tooltipPad + 4).attr('y', 0)
    .attr('font-size', 9).attr('font-weight', 'bold').attr('fill', '#1e40af').attr('font-family', 'monospace');

  const tooltipCurveTexts = curves.map(() =>
    tooltip.append('text').attr('x', tooltipPad + 4).attr('y', 0).attr('font-size', 7.5).attr('font-family', 'monospace')
  );

  const tooltipLithoText = tooltip.append('text')
    .attr('x', tooltipPad + 4).attr('y', 0)
    .attr('font-size', 7.5).attr('fill', '#b45309').attr('font-weight', 'bold').attr('font-family', 'monospace');

  const tooltipFaciesTexts = faciesLevels.map(fl => ({
    label: fl.label,
    el: tooltip.append('text')
      .attr('x', tooltipPad + 4).attr('y', 0)
      .attr('font-size', 7.5).attr('fill', '#6d28d9').attr('font-family', 'monospace'),
  }));

  const ns = config.eventNamespace;
  const svgEl = d3.select(svgRef);

  svgEl.on(`mousemove${ns}`, function (event: MouseEvent) {
    const { mx, my } = svgToScreenCoords(bodyNode, event);
    if (my < 0 || my > gridHeight || mx < 0 || mx > totalWidth) {
      hLine.attr('display', 'none'); depthLabel.attr('display', 'none'); tooltip.attr('display', 'none');
      return;
    }
    const depth = yScale.invert(my);
    hLine.attr('y1', my).attr('y2', my).attr('display', null);
    depthLabel.attr('display', null).attr('transform', `translate(0, ${my})`);
    depthLabelText.text(depth.toFixed(1) + 'm');

    const curveValues = curves.map(c => {
      const v = interpolateCurve(c, depth);
      return v !== null ? v.toFixed(c.name === 'PERM' ? 2 : 3) : '--';
    });

    let tx = totalWidth - tooltipW - 4;
    let ty = my - tooltipTotalH / 2;
    if (ty < 0) ty = 2;
    if (ty + tooltipTotalH > gridHeight) ty = gridHeight - tooltipTotalH - 2;

    tooltip.attr('display', null).attr('transform', `translate(${tx}, ${ty})`);
    tooltipDepthText.text(`深度: ${depth.toFixed(2)}m`).attr('y', tooltipPad + tooltipLineH * 0.5 + 2);

    tooltipCurveTexts.forEach((txt, i) => {
      txt.attr('fill', curves[i].color)
        .text(`${curves[i].name}: ${curveValues[i]} ${curves[i].unit}`)
        .attr('y', tooltipPad + tooltipLineH * (i + 1) + tooltipLineH * 0.5 + 2);
    });

    const lithoHit = hitTestIntervals(intervals.lithology, depth);
    const lithoRow = nCurveLines + 1;
    tooltipLithoText.text(`岩性: ${lithoHit ? lithoHit.name : '--'}`)
      .attr('y', tooltipPad + tooltipLineH * lithoRow + tooltipLineH * 0.5 + 2);

    faciesLevels.forEach((fl, fi) => {
      const hit = hitTestIntervals(fl.items, depth);
      tooltipFaciesTexts[fi].el
        .text(`${fl.label}: ${hit ? hit.name : '--'}`)
        .attr('y', tooltipPad + tooltipLineH * (lithoRow + 1 + fi) + tooltipLineH * 0.5 + 2);
    });
  }).on(`mouseleave${ns}`, () => {
    hLine.attr('display', 'none'); depthLabel.attr('display', 'none'); tooltip.attr('display', 'none');
  });

  return () => { svgEl.on(`${ns}`, null); };
}
