import type { ChartConfig } from '../engine/types';
import type { WellLogData } from '../types';

export const laolong1Config: ChartConfig = {
  columns: [
    { width: 40, type: 'intervals', label: '地层系统', label2: '系', dataKey: 'series', rotate: true, mergeWith: 0 },
    { width: 40, type: 'intervals', label: '统', label2: '统', dataKey: 'system', rotate: true, mergeWith: 0 },
    { width: 40, type: 'intervals', label: '组', label2: '组', dataKey: 'formation', rotate: true, mergeWith: 0 },
    { width: 120, type: 'curves', label: 'AC/GR', curveFilter: ['AC', 'GR'], altShading: true },
    { width: 40, type: 'depth', label: '深度', label2: '(m)' },
    { width: 60, type: 'lithology', label: '岩性', dataKey: 'lithology' },
    { width: 120, type: 'curves', label: 'RT/RXO', curveFilter: ['RT', 'RXO'], altShading: true },
    { width: 150, type: 'description', label: '岩性描述', editable: true },
    { width: 120, type: 'curves', label: 'SH/PERM\n/PHIE', curveFilter: ['SH', 'PERM', 'PHIE'], altShading: true },
    { width: 80, type: 'facies', label: '微相', label2: '微相', faciesLevel: 'micro_phase' },
    { width: 80, type: 'facies', label: '亚相', label2: '亚相', faciesLevel: 'sub_phase' },
    { width: 80, type: 'facies', label: '相', label2: '相', faciesLevel: 'phase' },
    { width: 60, type: 'systems_tract', label: '体系域' },
    { width: 40, type: 'intervals', label: '层序', dataKey: 'sequence', rotate: true },
  ],

  header: {
    titleTemplate: (data: WellLogData) => `${data.well_name} 综合测井解释图`,
    subtitleTemplate: (data: WellLogData) => `DEPTH ${data.depth_start}m – ${data.depth_end}m  |  Well ID: ${data.well_id}`,
    h1Labels: [
      { label: '地层系统', colSpan: [0, 2] },
      { label: 'AC/GR', curveCol: true },
      { label: '深度' },
      { label: '岩性' },
      { label: 'RT/RXO', curveCol: true },
      { label: '岩性描述' },
      { label: 'SH/PERM/PHIE', curveCol: true },
      { label: '沉积相', colSpan: [9, 11] },
      { label: '体系域' },
      { label: '层序' },
    ],
    h2Labels: ['系', '统', '组', '', '(m)', '', '', '', '', '微相', '亚相', '相', '', ''],
    mergedCols: new Set([1, 2, 10, 11]),
  },

  lithologyMapping: {
    patterns: {
      '白云岩': 'dolomite', '白云质': 'dolomite', '砂质白云岩': 'dolomite',
      '砂岩': 'sandstone', '细砂岩': 'sandstone',
      '粉砂岩': 'siltstone', '泥质粉砂岩': 'siltstone',
      '泥岩': 'mudstone',
      '页岩': 'shale',
      '灰岩': 'limestone', '石灰岩': 'limestone',
    },
    colors: {
      '白云岩': '#dbeafe', '白云质': '#bfdbfe', '砂质白云岩': '#93c5fd',
      '砂岩': '#fef08a', '细砂岩': '#fef9c3', '粉砂岩': '#f3f4f6', '泥质粉砂岩': '#e2e8f0',
      '泥岩': '#d1d5db', '页岩': '#9ca3af', '灰岩': '#e0e7ff', '石灰岩': '#c7d2fe',
      '紫红色': '#fecaca', '灰绿色': '#bbf7d0', '灰黑色': '#6b7280', '深灰色': '#9ca3af',
      '浅灰色': '#f3f4f6', '灰色': '#e5e7eb',
    },
  },

  faciesMapping: {
    patterns: {
      '潮坪': 'tidal_flat', '陆棚': 'shelf',
      '砂坪': 'sand_flat', '泥坪': 'mud_flat',
      '混积': 'mixed', '碎屑岩': 'clastic_shelf', '云质': 'dolomitic_flat',
      '泥质': 'muddy_shelf', '砂质': 'sandy_shelf', '砂泥质': 'sand_mud_shelf',
    },
    colors: {
      '潮坪': '#dbeafe', '陆棚': '#d1fae5', '砂坪': '#fef3c7', '泥坪': '#e5e7eb',
      '陆棚夹': '#bfdbfe', '混积': '#fde68a', '碎屑岩': '#fcd34d', '云质': '#93c5fd',
      '砂泥质': '#fef9c3', '泥质': '#e2e8f0', '砂质': '#fef08a',
      '河流相': '#fef3c7', '三角洲相': '#dbeafe', '滨岸相': '#d1fae5',
    },
  },

  pixelRatio: 14,
  gridInterval: 1,
  eventNamespace: '.laolong1',
};
