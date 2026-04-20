import { forwardRef } from 'react';
import { WellLogChart } from './engine/WellLogChart';
import { laolong1Config } from './configs/laolong1';
import type { WellLogData } from './types';
import type { ChartRef } from './engine/types';

interface Props {
  data: WellLogData;
  onDataChange?: (data: WellLogData) => void;
}

export { type ChartRef } from './engine/types';

export const LaoLong1Chart = forwardRef<ChartRef, Props>(({ data, onDataChange }, ref) => (
  <WellLogChart ref={ref} data={data} config={laolong1Config} onDataChange={onDataChange} />
));

LaoLong1Chart.displayName = 'LaoLong1Chart';
export default LaoLong1Chart;
