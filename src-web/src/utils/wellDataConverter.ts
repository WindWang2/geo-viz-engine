/**
 * Convert WellDetailData (from well-detail API) to WellLogData (for LaoLong1Dashboard).
 */
import type { WellDetailData, WellLogData, CurveData, WellIntervals, IntervalItem, FaciesData } from '../components/well-log/types';

/** Map Chinese curve names to standard abbreviations matching the chart config */
function mapCurveName(name: string): string {
  const mapping: Record<string, string> = {
    '孔隙度': 'PHIE',
    '渗透率': 'PERM',
    '含水饱和度': 'SH',  // SH position in the original config holds water saturation for this well
    '含氘饱和度': 'SH',
  };
  return mapping[name] || name;
}

function getDefaultDisplayRange(name: string): [number, number] {
  const standardName = mapCurveName(name);
  switch (standardName) {
    case 'GR': return [0, 150];
    case 'AC': return [40, 80];
    case 'RT': case 'RXO': case 'R39AC': case 'R15PC': case 'R27PC': case 'R39PC':
      return [0.1, 1000];
    case 'CALI': case 'BS':
      return [6, 12];
    case 'TNPH':
      return [0, 0.6];
    case 'RHOB':
      return [1.5, 3.0];
    case 'PE':
      return [0, 10];
    case 'PHIE':
      return [0, 0.3];
    case 'PERM':
      return [0, 10];
    case 'SH':
      return [0, 1];
    default:
      return [0, 100];
  }
}

function getDefaultColor(name: string): string {
  const standardName = mapCurveName(name);
  const colors: Record<string, string> = {
    'GR': '#00AA00',
    'AC': '#0000CC',
    'RT': '#AA0000',
    'RXO': '#CC6600',
    'R39AC': '#0000CC',
    'R15PC': '#AA0000',
    'R27PC': '#AA00AA',
    'R39PC': '#00AAAA',
    'CALI': '#8B4513',
    'BS': '#666666',
    'TNPH': '#4B0082',
    'RHOB': '#008080',
    'PE': '#800080',
    'PHIE': '#008080',
    'PERM': '#4B0082',
    'SH': '#AA0000',
  };
  return colors[standardName] || '#000000';
}

function getDefaultLineStyle(name: string): 'solid' | 'dashed' | 'dotted' {
  const standardName = mapCurveName(name);
  if (standardName.includes('AC') || standardName.includes('RXO') || standardName.includes('PERM')) {
    return 'dashed';
  }
  if (standardName.includes('PE') || standardName.includes('PHIE')) {
    return 'dotted';
  }
  return 'solid';
}

export function convertWellDetailToWellLogData(
  detail: WellDetailData,
  wellName: string
): WellLogData {
  // Convert curves
  const curves: CurveData[] = detail.curves.map(curve => {
    const data = curve.data as number[];
    const depth = curve.depth as number[];
    const mappedName = mapCurveName(curve.name);
    const validData = data.filter(v => typeof v === 'number' && !isNaN(v));
    const min = validData.length > 0 ? Math.min(...validData) : 0;
    const max = validData.length > 0 ? Math.max(...validData) : 100;
    const [lo, hi] = getDefaultDisplayRange(curve.name);

    // Map units
    let unit = curve.unit || '';
    if (!unit) {
      const unitMap: Record<string, string> = {
        '孔隙度': 'v/v',
        '渗透率': 'mD',
        '含水饱和度': 'v/v',
      };
      unit = unitMap[curve.name] || '';
    }

    return {
      name: mappedName,
      unit: unit,
      data: data,
      depth: depth,
      min_value: min,
      max_value: max,
      display_range: [lo, hi],
      color: getDefaultColor(curve.name),
      line_style: getDefaultLineStyle(curve.name),
    } as CurveData;
  });

  // Get depth range from first curve
  let depth_start = 0;
  let depth_end = 3000;
  let depth_step = 0.125;
  if (curves.length > 0 && curves[0].depth.length > 0) {
    const depths = curves[0].depth;
    depth_start = depths[0];
    depth_end = depths[depths.length - 1];
    if (depths.length > 1) {
      depth_step = depths[1] - depths[0];
    }
  }

  // Convert intervals
  const intervals: WellIntervals = {
    series: [],
    system: [],
    formation: (detail.intervals.formation || []).map(convertInterval),
    member: (detail.intervals.member || []).map(convertInterval),
    lithology: (detail.intervals.lithology || []).map(convertInterval),
    systems_tract: (detail.intervals.systems_tract || []).map(convertInterval),
    sequence: (detail.intervals.sequence || []).map(convertInterval),
    facies: convertFacies(detail.intervals.facies),
  };

  return {
    well_id: wellName.replace(/\s+/g, '-'),
    well_name: wellName,
    depth_start,
    depth_end,
    depth_step,
    location: null,
    longitude: undefined,
    latitude: undefined,
    curves,
    intervals,
  } as WellLogData;
}

function convertInterval(item: { top: number; bottom: number; name: string }): IntervalItem {
  return {
    top: item.top,
    bottom: item.bottom,
    name: item.name,
  };
}

function convertFacies(facies?: {
  phase?: Array<{ top: number; bottom: number; name: string }>;
  sub_phase?: Array<{ top: number; bottom: number; name: string }>;
  micro_phase?: Array<{ top: number; bottom: number; name: string }>;
}): FaciesData {
  return {
    phase: (facies?.phase || []).map(convertInterval),
    sub_phase: (facies?.sub_phase || []).map(convertInterval),
    micro_phase: (facies?.micro_phase || []).map(convertInterval),
  };
}
