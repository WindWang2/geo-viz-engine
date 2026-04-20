import type { WellLogData, WellIntervals, FaciesData } from '../types';

export interface ChartRef {
  exportSVG: () => void;
  exportPNG: () => void;
  exportPDF: () => void;
}

export interface PatternMapping {
  patterns: Record<string, string>;
  colors: Record<string, string>;
}

export type ColumnType = 'intervals' | 'curves' | 'lithology' | 'depth' | 'description' | 'facies' | 'systems_tract';

export interface ColumnDef {
  width: number;
  type: ColumnType;
  label: string;
  label2?: string;
  mergeWith?: number;
  dataKey?: string;
  curveFilter?: string[];
  rotate?: boolean;
  editable?: boolean;
  faciesLevel?: keyof FaciesData;
  altShading?: boolean;
}

export interface ChartConfig {
  columns: ColumnDef[];
  header: {
    titleTemplate: (data: WellLogData) => string;
    subtitleTemplate: (data: WellLogData) => string;
    h1Labels: Array<{ label: string; colSpan?: [number, number]; curveCol?: boolean }>;
    h2Labels: string[];
    mergedCols: Set<number>;
  };
  lithologyMapping: PatternMapping;
  faciesMapping: PatternMapping;
  pixelRatio: number;
  gridInterval: number;
  eventNamespace: string;
}

export interface RenderContext {
  svg: d3.Selection<SVGSVGElement, unknown, null, undefined>;
  body: d3.Selection<SVGGElement, unknown, null, undefined>;
  defs: d3.Selection<SVGDefsElement, unknown, null, undefined>;
  data: WellLogData;
  intervals: WellIntervals;
  config: ChartConfig;
  colX: number[];
  colWidths: number[];
  totalWidth: number;
  gridHeight: number;
  totalHeight: number;
  bodyStart: number;
  yScale: d3.ScaleLinear<number, number>;
  startDepth: number;
  maxDepth: number;
}
