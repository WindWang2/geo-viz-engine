"""Visual defaults for the Data Manager horizon/surface preview."""

from PySide6.QtGui import QColor

from geoviz_plots.surface.surface_widget import SurfaceWidget


def test_surface_widget_uses_the_light_workbench_canvas_palette(qtbot):
    widget = SurfaceWidget()
    qtbot.addWidget(widget)
    widget.resize(320, 220)
    widget.show()

    image = widget.grab().toImage()
    assert widget.bg_color == QColor("#f1f5f9")
    assert widget.plot_bg_color == QColor("#ffffff")
    assert image.pixelColor(8, 8) == QColor("#f1f5f9")
    assert image.pixelColor(160, 110) == QColor("#ffffff")
