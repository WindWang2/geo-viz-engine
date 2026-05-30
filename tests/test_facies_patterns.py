from PySide6.QtGui import QBrush, QColor
from geoviz_paleo_map.models import FaciesStyle


def test_facies_style_has_pattern_id():
    brush = QBrush(QColor("#ff0000"))
    style = FaciesStyle(base_color=QColor("#ff0000"), brush=brush, pattern_id="delta")
    assert style.pattern_id == "delta"


def test_facies_style_pattern_id_defaults_to_none():
    brush = QBrush(QColor("#ff0000"))
    style = FaciesStyle(base_color=QColor("#ff0000"), brush=brush)
    assert style.pattern_id is None
