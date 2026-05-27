from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from geoviz_map import MapCanvas, ReferenceLabel, WellMarker


WORLD_GEOJSON = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "properties": {"ISO_A3": "ABC"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [110.0, 18.0], [120.0, 18.0],
                [120.0, 28.0], [110.0, 28.0], [110.0, 18.0],
            ]],
        },
    }],
}

CHINA_GEOJSON = {"type": "FeatureCollection", "features": []}


def _make_canvas(qtbot):
    wells = [WellMarker(name="HZ-1", lng=114.5, lat=22.0, color="#ef4444",
                        has_data=True)]
    labels = [ReferenceLabel(name="香港", lng=114.17, lat=22.32, kind="city")]
    canvas = MapCanvas(wells=wells, world_geojson=WORLD_GEOJSON,
                       china_geojson=CHINA_GEOJSON, reference_labels=labels,
                       initial_center=(114.5, 22.0), initial_zoom=8.0)
    qtbot.addWidget(canvas)
    canvas.resize(800, 800)
    canvas.show()
    qtbot.waitExposed(canvas)
    return canvas


def test_canvas_grab_produces_nonempty_image(qtbot):
    canvas = _make_canvas(qtbot)
    pixmap = canvas.grab()
    assert not pixmap.isNull()
    dpr = pixmap.devicePixelRatio()
    assert pixmap.width() == int(800 * dpr)
    assert pixmap.height() == int(800 * dpr)


def test_well_clicked_signal_fires_with_name(qtbot):
    canvas = _make_canvas(qtbot)
    canvas.repaint()  # ensure layers have cached screen positions
    well_pt = canvas._viewport.lnglat_to_screen(114.5, 22.0)
    received: list[str] = []
    canvas.well_clicked.connect(received.append)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton,
                     pos=QPoint(int(well_pt.x()), int(well_pt.y())))
    assert received == ["HZ-1"]


def test_resize_updates_viewport_dimensions(qtbot):
    canvas = _make_canvas(qtbot)
    canvas.resize(400, 300)
    qtbot.wait(20)
    assert canvas._viewport.width == 400
    assert canvas._viewport.height == 300
