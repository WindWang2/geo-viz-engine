import * as d3 from 'd3';
import type { PatternMapping } from './types';

export function lookupPattern(name: string, mapping: PatternMapping): string | null {
  for (const [k, v] of Object.entries(mapping.patterns)) {
    if (name.includes(k)) return v;
  }
  return null;
}

export function lookupColor(name: string, mapping: PatternMapping): string {
  for (const [k, v] of Object.entries(mapping.colors)) {
    if (name.includes(k)) return v;
  }
  return '#f3f4f6';
}

export function registerLithoPatterns(defs: d3.Selection<SVGDefsElement, unknown, null, undefined>) {
  const sandstone = defs.append('pattern').attr('id', 'pat-sandstone')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', 20).attr('height', 20);
  sandstone.append('rect').attr('width', 20).attr('height', 20).attr('fill', '#fef9c3');
  [[3,3,1.2],[10,6,1.0],[16,2,0.8],[6,10,1.1],[14,11,1.0],[2,16,0.9],[9,14,1.2],[17,17,1.0],[12,18,0.8],[18,8,0.9]]
    .forEach(([cx,cy,r]) => sandstone.append('circle').attr('cx',cx).attr('cy',cy).attr('r',r).attr('fill','#92400e'));

  const siltstone = defs.append('pattern').attr('id', 'pat-siltstone')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', 12).attr('height', 12);
  siltstone.append('rect').attr('width', 12).attr('height', 12).attr('fill', '#f3f4f6');
  [[2,2,0.5],[7,4,0.4],[4,7,0.5],[10,2,0.4],[1,10,0.5],[6,9,0.4],[10,7,0.5],[9,11,0.4],[3,5,0.3],[8,1,0.3]]
    .forEach(([cx,cy,r]) => siltstone.append('circle').attr('cx',cx).attr('cy',cy).attr('r',r).attr('fill','#6b7280'));

  const mudstone = defs.append('pattern').attr('id', 'pat-mudstone')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', 16).attr('height', 8);
  mudstone.append('rect').attr('width', 16).attr('height', 8).attr('fill', '#d1d5db');
  mudstone.append('line').attr('x1',0).attr('y1',2).attr('x2',6).attr('y2',2).attr('stroke','#4b5563').attr('stroke-width',0.5);
  mudstone.append('line').attr('x1',9).attr('y1',4).attr('x2',16).attr('y2',4).attr('stroke','#4b5563').attr('stroke-width',0.5);
  mudstone.append('line').attr('x1',2).attr('y1',6).attr('x2',8).attr('y2',6).attr('stroke','#4b5563').attr('stroke-width',0.5);

  const shale = defs.append('pattern').attr('id', 'pat-shale')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', 16).attr('height', 6);
  shale.append('rect').attr('width', 16).attr('height', 6).attr('fill', '#9ca3af');
  shale.append('line').attr('x1',0).attr('y1',1.5).attr('x2',16).attr('y2',1.5).attr('stroke','#374151').attr('stroke-width',0.6);
  shale.append('line').attr('x1',0).attr('y1',4.5).attr('x2',16).attr('y2',4.5).attr('stroke','#374151').attr('stroke-width',0.6);

  const limestone = defs.append('pattern').attr('id', 'pat-limestone')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', 24).attr('height', 16);
  limestone.append('rect').attr('width', 24).attr('height', 16).attr('fill', '#e0e7ff');
  limestone.append('line').attr('x1',0).attr('y1',0).attr('x2',24).attr('y2',0).attr('stroke','#4338ca').attr('stroke-width',0.6);
  limestone.append('line').attr('x1',0).attr('y1',8).attr('x2',24).attr('y2',8).attr('stroke','#4338ca').attr('stroke-width',0.6);
  limestone.append('line').attr('x1',8).attr('y1',0).attr('x2',8).attr('y2',8).attr('stroke','#4338ca').attr('stroke-width',0.4);
  limestone.append('line').attr('x1',18).attr('y1',0).attr('x2',18).attr('y2',8).attr('stroke','#4338ca').attr('stroke-width',0.4);
  limestone.append('line').attr('x1',4).attr('y1',8).attr('x2',4).attr('y2',16).attr('stroke','#4338ca').attr('stroke-width',0.4);
  limestone.append('line').attr('x1',14).attr('y1',8).attr('x2',14).attr('y2',16).attr('stroke','#4338ca').attr('stroke-width',0.4);

  const dolomite = defs.append('pattern').attr('id', 'pat-dolomite')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', 16).attr('height', 16);
  dolomite.append('rect').attr('width', 16).attr('height', 16).attr('fill', '#dbeafe');
  dolomite.append('line').attr('x1',0).attr('y1',0).attr('x2',16).attr('y2',0).attr('stroke','#1e40af').attr('stroke-width',0.5);
  dolomite.append('line').attr('x1',0).attr('y1',8).attr('x2',16).attr('y2',8).attr('stroke','#1e40af').attr('stroke-width',0.5);
  dolomite.append('line').attr('x1',4).attr('y1',0).attr('x2',8).attr('y2',8).attr('stroke','#1e40af').attr('stroke-width',0.4);
  dolomite.append('line').attr('x1',12).attr('y1',0).attr('x2',16).attr('y2',8).attr('stroke','#1e40af').attr('stroke-width',0.4);
  dolomite.append('line').attr('x1',0).attr('y1',0).attr('x2',4).attr('y2',8).attr('stroke','#1e40af').attr('stroke-width',0.4);
  dolomite.append('line').attr('x1',8).attr('y1',0).attr('x2',12).attr('y2',8).attr('stroke','#1e40af').attr('stroke-width',0.4);
}

export function registerFaciesPatterns(defs: d3.Selection<SVGDefsElement, unknown, null, undefined>) {
  const tidal_flat = defs.append('pattern').attr('id', 'pat-tidal_flat')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', 20).attr('height', 10);
  tidal_flat.append('rect').attr('width', 20).attr('height', 10).attr('fill', '#dbeafe');
  tidal_flat.append('path').attr('d', 'M0,3 Q5,1 10,3 Q15,5 20,3').attr('stroke', '#3b82f6').attr('stroke-width', 0.5).attr('fill', 'none');
  tidal_flat.append('path').attr('d', 'M0,7 Q5,5 10,7 Q15,9 20,7').attr('stroke', '#3b82f6').attr('stroke-width', 0.5).attr('fill', 'none');

  const shelf = defs.append('pattern').attr('id', 'pat-shelf')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', 16).attr('height', 8);
  shelf.append('rect').attr('width', 16).attr('height', 8).attr('fill', '#d1fae5');
  shelf.append('line').attr('x1', 0).attr('y1', 2).attr('x2', 16).attr('y2', 2).attr('stroke', '#059669').attr('stroke-width', 0.4);
  shelf.append('line').attr('x1', 0).attr('y1', 5).attr('x2', 16).attr('y2', 5).attr('stroke', '#059669').attr('stroke-width', 0.4);

  const sand_flat = defs.append('pattern').attr('id', 'pat-sand_flat')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', 14).attr('height', 14);
  sand_flat.append('rect').attr('width', 14).attr('height', 14).attr('fill', '#fef3c7');
  [[3,3,0.8,'#b45309'],[10,7,0.8,'#b45309'],[5,11,0.8,'#b45309'],[12,2,0.6,'#b45309'],[1,8,0.6,'#b45309']]
    .forEach(([cx,cy,r,f]) => sand_flat.append('circle').attr('cx',cx).attr('cy',cy).attr('r',r).attr('fill',f));

  const mud_flat = defs.append('pattern').attr('id', 'pat-mud_flat')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', 16).attr('height', 8);
  mud_flat.append('rect').attr('width', 16).attr('height', 8).attr('fill', '#e5e7eb');
  mud_flat.append('line').attr('x1', 0).attr('y1', 2).attr('x2', 7).attr('y2', 2).attr('stroke', '#6b7280').attr('stroke-width', 0.4);
  mud_flat.append('line').attr('x1', 9).attr('y1', 5).attr('x2', 16).attr('y2', 5).attr('stroke', '#6b7280').attr('stroke-width', 0.4);

  const mixed = defs.append('pattern').attr('id', 'pat-mixed')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', 16).attr('height', 12);
  mixed.append('rect').attr('width', 16).attr('height', 12).attr('fill', '#fde68a');
  mixed.append('circle').attr('cx', 3).attr('cy', 3).attr('r', 0.6).attr('fill', '#92400e');
  mixed.append('circle').attr('cx', 11).attr('cy', 8).attr('r', 0.6).attr('fill', '#92400e');
  mixed.append('line').attr('x1', 6).attr('y1', 6).attr('x2', 14).attr('y2', 6).attr('stroke', '#92400e').attr('stroke-width', 0.4);
  mixed.append('line').attr('x1', 0).attr('y1', 10).attr('x2', 5).attr('y2', 10).attr('stroke', '#92400e').attr('stroke-width', 0.4);

  const clastic_shelf = defs.append('pattern').attr('id', 'pat-clastic_shelf')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', 14).attr('height', 10);
  clastic_shelf.append('rect').attr('width', 14).attr('height', 10).attr('fill', '#fcd34d');
  clastic_shelf.append('line').attr('x1', 0).attr('y1', 2).attr('x2', 8).attr('y2', 2).attr('stroke', '#854d0e').attr('stroke-width', 0.4);
  clastic_shelf.append('line').attr('x1', 5).attr('y1', 5).attr('x2', 14).attr('y2', 5).attr('stroke', '#854d0e').attr('stroke-width', 0.4);
  clastic_shelf.append('line').attr('x1', 0).attr('y1', 8).attr('x2', 6).attr('y2', 8).attr('stroke', '#854d0e').attr('stroke-width', 0.4);

  const dolomitic_flat = defs.append('pattern').attr('id', 'pat-dolomitic_flat')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', 16).attr('height', 12);
  dolomitic_flat.append('rect').attr('width', 16).attr('height', 12).attr('fill', '#93c5fd');
  dolomitic_flat.append('circle').attr('cx', 4).attr('cy', 3).attr('r', 0.7).attr('fill', '#1e40af');
  dolomitic_flat.append('circle').attr('cx', 12).attr('cy', 9).attr('r', 0.7).attr('fill', '#1e40af');
  dolomitic_flat.append('line').attr('x1', 2).attr('y1', 6).attr('x2', 6).attr('y2', 12).attr('stroke', '#1e40af').attr('stroke-width', 0.4);
  dolomitic_flat.append('line').attr('x1', 6).attr('y1', 6).attr('x2', 2).attr('y2', 12).attr('stroke', '#1e40af').attr('stroke-width', 0.4);

  const muddy_shelf = defs.append('pattern').attr('id', 'pat-muddy_shelf')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', 12).attr('height', 8);
  muddy_shelf.append('rect').attr('width', 12).attr('height', 8).attr('fill', '#e2e8f0');
  muddy_shelf.append('line').attr('x1', 0).attr('y1', 2).attr('x2', 5).attr('y2', 2).attr('stroke', '#64748b').attr('stroke-width', 0.3);
  muddy_shelf.append('line').attr('x1', 7).attr('y1', 4).attr('x2', 12).attr('y2', 4).attr('stroke', '#64748b').attr('stroke-width', 0.3);
  muddy_shelf.append('line').attr('x1', 2).attr('y1', 6).attr('x2', 8).attr('y2', 6).attr('stroke', '#64748b').attr('stroke-width', 0.3);

  const sandy_shelf = defs.append('pattern').attr('id', 'pat-sandy_shelf')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', 14).attr('height', 14);
  sandy_shelf.append('rect').attr('width', 14).attr('height', 14).attr('fill', '#fef08a');
  [[4,4,0.9,'#a16207'],[10,10,0.9,'#a16207'],[2,11,0.6,'#a16207'],[12,3,0.6,'#a16207']]
    .forEach(([cx,cy,r,f]) => sandy_shelf.append('circle').attr('cx',cx).attr('cy',cy).attr('r',r).attr('fill',f));

  const sand_mud_shelf = defs.append('pattern').attr('id', 'pat-sand_mud_shelf')
    .attr('patternUnits', 'userSpaceOnUse').attr('width', 16).attr('height', 10);
  sand_mud_shelf.append('rect').attr('width', 16).attr('height', 10).attr('fill', '#fef9c3');
  sand_mud_shelf.append('circle').attr('cx', 3).attr('cy', 2).attr('r', 0.5).attr('fill', '#854d0e');
  sand_mud_shelf.append('circle').attr('cx', 13).attr('cy', 7).attr('r', 0.5).attr('fill', '#854d0e');
  sand_mud_shelf.append('line').attr('x1', 5).attr('y1', 5).attr('x2', 11).attr('y2', 5).attr('stroke', '#854d0e').attr('stroke-width', 0.3);
  sand_mud_shelf.append('line').attr('x1', 0).attr('y1', 9).attr('x2', 6).attr('y2', 9).attr('stroke', '#854d0e').attr('stroke-width', 0.3);
}

export function registerAllPatterns(defs: d3.Selection<SVGDefsElement, unknown, null, undefined>) {
  registerLithoPatterns(defs);
  registerFaciesPatterns(defs);
}
