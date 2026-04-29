from src.data.models import CurveData
from src.renderers.well_log.curve_renderer import CurveRenderer


def test_curve_renderer_creates_plot(qtbot):
    curve = CurveData(name="GR", unit="gAPI", depth=[0, 1, 2, 3, 4], values=[10, 25, 40, 30, 15])
    renderer = CurveRenderer(curve, width=120)
    qtbot.addWidget(renderer)
    assert renderer.curve_name == "GR"


def test_curve_renderer_has_plot_item(qtbot):
    curve = CurveData(name="RT", unit="Ω·m", depth=[0, 1, 2], values=[1, 5, 10])
    renderer = CurveRenderer(curve, width=120)
    qtbot.addWidget(renderer)
    assert renderer.plot_item is not None
