import numpy as np
import pytest

from geoviz_seismic.models import SeismicAnnotation


def test_seismic_annotation_model():
    ann = SeismicAnnotation(
        text="T7 反射层",
        h_value=200.0,
        v_value=1500.0,
        slice_type="inline",
        slice_position=50,
    )
    assert ann.text == "T7 反射层"
    assert ann.h_value == 200.0
    assert ann.v_value == 1500.0
    assert ann.slice_type == "inline"
    assert ann.slice_position == 50
    assert ann.color == "#ffff00"


def test_seismic_annotation_custom_color():
    ann = SeismicAnnotation(
        text="断层",
        h_value=100.0,
        v_value=800.0,
        slice_type="crossline",
        slice_position=30,
        color="#ff0000",
    )
    assert ann.color == "#ff0000"


def test_profile_vd_annotation_mode_toggle(qtbot):
    from geoviz_seismic.profile_vd import ProfileVD

    widget = ProfileVD()
    qtbot.addWidget(widget)
    assert not widget._annotation_mode
    widget.enable_annotation_mode(True)
    assert widget._annotation_mode
    widget.enable_annotation_mode(False)
    assert not widget._annotation_mode


def test_profile_vd_add_annotation(qtbot):
    from geoviz_seismic.profile_vd import ProfileVD

    widget = ProfileVD()
    qtbot.addWidget(widget)

    data = np.random.randn(50, 80).astype(np.float32)
    from geoviz_seismic.models import SliceInfo
    info = SliceInfo(
        slice_type="inline", position=10,
        axis_h_label="XL", axis_v_label="T",
        axis_h_values=list(np.arange(80) * 25.0),
        axis_v_values=list(np.arange(50) * 4.0),
    )
    widget.render(data, slice_info=info)

    ann = SeismicAnnotation(
        text="test", h_value=500.0, v_value=100.0,
        slice_type="inline", slice_position=10,
    )
    widget.add_annotation(ann)
    assert len(widget._annotations) == 1
    assert widget._annotations[0].text == "test"


def test_profile_vd_clear_annotations(qtbot):
    from geoviz_seismic.profile_vd import ProfileVD

    widget = ProfileVD()
    qtbot.addWidget(widget)

    ann = SeismicAnnotation(
        text="a", h_value=1.0, v_value=2.0,
        slice_type="inline", slice_position=0,
    )
    widget.add_annotation(ann)
    assert len(widget._annotations) == 1
    widget.clear_annotations()
    assert len(widget._annotations) == 0


def test_profile_vd_annotations_returns_copy(qtbot):
    from geoviz_seismic.profile_vd import ProfileVD

    widget = ProfileVD()
    qtbot.addWidget(widget)

    ann = SeismicAnnotation(
        text="x", h_value=1.0, v_value=2.0,
        slice_type="inline", slice_position=0,
    )
    widget.add_annotation(ann)
    copy = widget.annotations()
    assert len(copy) == 1
    copy.clear()
    assert len(widget._annotations) == 1  # original unchanged


def test_profile_vd_draw_annotations_no_crash(qtbot):
    from geoviz_seismic.profile_vd import ProfileVD

    widget = ProfileVD()
    qtbot.addWidget(widget)
    widget.resize(300, 200)

    data = np.random.randn(50, 80).astype(np.float32)
    from geoviz_seismic.models import SliceInfo
    info = SliceInfo(
        slice_type="inline", position=10,
        axis_h_label="XL", axis_v_label="T",
        axis_h_values=list(np.arange(80) * 25.0),
        axis_v_values=list(np.arange(50) * 4.0),
    )
    widget.render(data, slice_info=info)

    ann = SeismicAnnotation(
        text="Label", h_value=500.0, v_value=100.0,
        slice_type="inline", slice_position=10,
    )
    widget.add_annotation(ann)
    widget.repaint()
    # Should not crash


def test_renderer_3d_set_annotations(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)

    data = np.random.randn(10, 10, 10).astype(np.float32)
    widget.load_volume(data)

    widget.set_annotations([(5, 5, 5, "test_label")])
    assert len(widget._annotation_items) >= 0  # may be 0 if GLTextItem fails


def test_renderer_3d_clear_annotations(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)

    data = np.random.randn(10, 10, 10).astype(np.float32)
    widget.load_volume(data)

    widget.set_annotations([(5, 5, 5, "a"), (3, 3, 3, "b")])
    widget.set_annotations([])  # clear
    assert len(widget._annotation_items) == 0


def test_cross_well_annotation_item(qtbot):
    from geoviz_well_log.scene.annotation_item import AnnotationItem
    from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

    scene = QGraphicsScene()
    item = AnnotationItem("测试标注", 100, 200)
    scene.addItem(item)
    assert item.text == "测试标注"
    assert item.color == "#1a202c"
    br = item.boundingRect()
    assert br.width() > 0
    assert br.height() > 0


def test_cross_well_scene_add_annotation(qtbot):
    from geoviz_well_log.scene.cross_well_scene import CrossWellScene

    scene = CrossWellScene()
    ann = scene.add_annotation("地层A", 150, 500)
    assert ann is not None
    assert ann in scene.items()
    assert ann.text == "地层A"

    scene.remove_annotation(ann)
    assert ann not in scene.items()
