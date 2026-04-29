from PySide6.QtWidgets import QWidget, QVBoxLayout
from src.data.models import WellLogData, CurveData, LithologyInterval, FaciesInterval
from src.renderers.well_log.chart_engine import ChartEngine


def _sample_well_log() -> WellLogData:
    depths = list(range(0, 200))
    import math
    gr_vals = [50 + 30 * math.sin(d * 0.1) for d in depths]
    rt_vals = [10 * math.exp(0.01 * d) for d in depths]

    return WellLogData(
        well_name="HZ25-10-1",
        top_depth=0,
        bottom_depth=200,
        curves=[
            CurveData(name="GR", unit="gAPI", depth=depths, values=gr_vals),
            CurveData(name="RT", unit="Ω·m", depth=depths, values=rt_vals),
        ],
        lithology=[
            LithologyInterval(top=0, bottom=40, lithology="sandstone", description="砂岩"),
            LithologyInterval(top=40, bottom=80, lithology="mudstone", description="泥岩"),
            LithologyInterval(top=80, bottom=120, lithology="limestone", description="灰岩"),
            LithologyInterval(top=120, bottom=160, lithology="shale", description="页岩"),
            LithologyInterval(top=160, bottom=200, lithology="dolomite", description="白云岩"),
        ],
        facies=[
            FaciesInterval(top=0, bottom=60, facies="tidal_flat", sub_facies="砂坪"),
            FaciesInterval(top=60, bottom=130, facies="shelf", sub_facies="陆棚"),
            FaciesInterval(top=130, bottom=200, facies="sand_flat", sub_facies="砂坪"),
        ],
    )


class WellLogPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.chart = ChartEngine(_sample_well_log())
        layout.addWidget(self.chart)
