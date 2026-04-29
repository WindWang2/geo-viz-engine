from PySide6.QtWidgets import QWidget, QVBoxLayout
from src.data.models import (
    WellLogData, CurveData, IntervalItem, WellIntervals, FaciesData,
)
from src.renderers.well_log.chart_engine import ChartEngine
from src.renderers.well_log.configs.laolong1 import laolong1_config


def _sample_well_log() -> WellLogData:
    depths = list(range(0, 200))
    import math
    gr_vals = [50 + 30 * math.sin(d * 0.1) for d in depths]
    rt_vals = [10 * math.exp(0.01 * d) for d in depths]
    ac_vals = [2400 - 200 * math.sin(d * 0.05) for d in depths]

    return WellLogData(
        well_name="HZ25-10-1",
        top_depth=0,
        bottom_depth=200,
        curves=[
            CurveData(name="GR", unit="gAPI", depth=depths, values=gr_vals,
                      display_range=(0, 150), color="#63b3ed"),
            CurveData(name="RT", unit="Ω·m", depth=depths, values=rt_vals,
                      display_range=(0.2, 2000), color="#f6ad55"),
            CurveData(name="AC", unit="μs/ft", depth=depths, values=ac_vals,
                      display_range=(2000, 2600), color="#68d391"),
        ],
        intervals=WellIntervals(
            lithology=[
                IntervalItem(top=0, bottom=40, name="砂岩"),
                IntervalItem(top=40, bottom=80, name="泥岩"),
                IntervalItem(top=80, bottom=120, name="灰岩"),
                IntervalItem(top=120, bottom=160, name="页岩"),
                IntervalItem(top=160, bottom=200, name="白云岩"),
            ],
            facies=FaciesData(
                phase=[
                    IntervalItem(top=0, bottom=100, name="潮坪"),
                    IntervalItem(top=100, bottom=200, name="陆棚"),
                ],
                sub_phase=[
                    IntervalItem(top=0, bottom=60, name="砂坪"),
                    IntervalItem(top=60, bottom=130, name="陆棚"),
                    IntervalItem(top=130, bottom=200, name="砂坪"),
                ],
                micro_phase=[
                    IntervalItem(top=0, bottom=40, name="砂坪"),
                    IntervalItem(top=40, bottom=80, name="泥坪"),
                    IntervalItem(top=80, bottom=130, name="陆棚"),
                    IntervalItem(top=130, bottom=200, name="砂坪"),
                ],
            ),
            systems_tract=[
                IntervalItem(top=0, bottom=80, name="TST"),
                IntervalItem(top=80, bottom=160, name="HST"),
                IntervalItem(top=160, bottom=200, name="TST"),
            ],
            sequence=[
                IntervalItem(top=0, bottom=100, name="SQ1"),
                IntervalItem(top=100, bottom=200, name="SQ2"),
            ],
        ),
    )


class WellLogPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.chart = ChartEngine(_sample_well_log(), laolong1_config)
        layout.addWidget(self.chart)
