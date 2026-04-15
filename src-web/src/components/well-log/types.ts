// Frontend types matching the Pydantic backend models

export interface CurveData {
  name: string;
  unit: string;
  data: number[];      // curve values (this is 'values' in my earlier mistake, backend calls it 'data')
  depth: number[];     // depth points for this curve
  min_value: number;
  max_value: number;
  display_range: [number, number];
  color: string;
  line_style: 'solid' | 'dashed' | 'dotted';
}

export interface WellLogData {
  well_id: string;
  well_name: string;
  depth_start: number;
  depth_end: number;
  depth_step: number;
  location: [number, number] | null;
  curves: CurveData[];
  longitude?: number;
  latitude?: number;
}

export interface WellMetadata {
  well_id: string;
  well_name: string;
  depth_start: number;
  depth_end: number;
  curve_names: string[];
  longitude?: number | null;
  latitude?: number | null;
}

export interface WellLogCanvasProps {
  wellData: WellLogData;
  trackWidth: number;
  depthPixelRatio: number; // pixels per meter
  onHeightCalculated?: (height: number) => void;
}

export interface WellLogViewerProps {
  wellData: WellLogData;
  className?: string;
  trackWidth?: number;
  depthPixelRatio?: number;
  loading?: boolean;
  error?: string | null;
}

export interface IntervalItem {
  top: number;
  bottom: number;
  name: string;
}

export interface FaciesData {
  phase: IntervalItem[];
  sub_phase: IntervalItem[];
  micro_phase: IntervalItem[];
}

export interface WellIntervals {
  series: IntervalItem[];
  system: IntervalItem[];
  formation: IntervalItem[];
  member: IntervalItem[];
  lithology: IntervalItem[];
  systems_tract: IntervalItem[];
  sequence: IntervalItem[];
  facies: FaciesData;
}

export interface WellDetailData {
  well_id: string;
  well_name: string;
  curves: CurveData[];
  intervals: WellIntervals;
}
