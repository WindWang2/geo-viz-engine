from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication

from geoviz_well_log.renderer.label_layout import compute_header_label_policy, compute_label_policy, fit_label_text


def test_label_policy_uses_one_font_size_per_track_column():
    policy = compute_label_policy(
        QRectF(0, 0, 80, 800),
        depth_span=300.0,
        interval_heights=[42.0, 96.0, 180.0, 260.0],
    )

    assert policy.font_px >= 11
    assert len({policy.font_px for _ in range(4)}) == 1


def test_label_policy_grows_when_depth_scale_is_zoomed_in():
    zoomed_out = compute_label_policy(
        QRectF(0, 0, 80, 800),
        depth_span=800.0,
        interval_heights=[40.0, 48.0, 52.0],
    )
    zoomed_in = compute_label_policy(
        QRectF(0, 0, 80, 800),
        depth_span=80.0,
        interval_heights=[180.0, 220.0, 260.0],
    )

    assert zoomed_in.font_px > zoomed_out.font_px
    assert zoomed_out.font_px >= 11


def test_long_label_is_wrapped_or_elided_inside_rect():
    QApplication.instance() or QApplication([])
    policy = compute_label_policy(
        QRectF(0, 0, 92, 800),
        depth_span=160.0,
        interval_heights=[120.0],
    )
    font = QFont()
    font.setPixelSize(policy.font_px)
    metrics = QFontMetrics(font)
    rect = QRectF(0, 0, 92, 44)

    lines = fit_label_text("非常长的三角洲前缘水下分流河道砂体", rect, policy, metrics)

    assert 1 <= len(lines) <= 2
    assert any(line.endswith("…") or len(lines) > 1 for line in lines)
    assert all(metrics.horizontalAdvance(line) <= rect.width() for line in lines)


def test_label_is_hidden_when_interval_is_too_short_to_read():
    QApplication.instance() or QApplication([])
    policy = compute_label_policy(
        QRectF(0, 0, 80, 800),
        depth_span=800.0,
        interval_heights=[8.0],
    )
    font = QFont()
    font.setPixelSize(policy.font_px)
    metrics = QFontMetrics(font)

    assert fit_label_text("泥岩", QRectF(0, 0, 80, 8), policy, metrics) == []


def test_narrow_interval_like_track_uses_vertical_labels():
    policy = compute_label_policy(
        QRectF(0, 0, 64, 800),
        depth_span=300.0,
        interval_heights=[120.0, 180.0, 240.0],
    )

    assert policy.vertical is True
    assert policy.max_lines == 1


def test_vertical_label_uses_full_text_without_ellipsis():
    QApplication.instance() or QApplication([])
    policy = compute_label_policy(
        QRectF(0, 0, 64, 800),
        depth_span=300.0,
        interval_heights=[160.0],
    )
    font = QFont()
    font.setPixelSize(policy.font_px)
    metrics = QFontMetrics(font)

    lines = fit_label_text("下寒统沉积体系域", QRectF(0, 0, 64, 44), policy, metrics)

    assert lines == ["下寒统沉积体系域"]
    assert all("…" not in line for line in lines)


def test_facies_like_label_policy_uses_readable_font_size():
    policy = compute_label_policy(
        QRectF(0, 0, 80, 800),
        depth_span=300.0,
        interval_heights=[80.0, 120.0, 180.0],
    )

    assert policy.font_px >= 13


def test_header_label_policy_is_larger_and_wraps_long_titles():
    QApplication.instance() or QApplication([])
    policy = compute_header_label_policy(QRectF(0, 0, 80, 56))
    font = QFont()
    font.setPixelSize(policy.font_px)
    font.setBold(True)
    metrics = QFontMetrics(font)

    lines = fit_label_text("沉积相综合解释", QRectF(0, 0, 80, 56), policy, metrics)

    assert policy.font_px >= 16
    assert policy.max_lines == 2
    assert 1 <= len(lines) <= 2
    assert all(metrics.horizontalAdvance(line) <= 80 for line in lines)


def test_body_label_policy_does_not_exceed_header_font_size():
    header = compute_header_label_policy(QRectF(0, 0, 80, 56))
    body = compute_label_policy(
        QRectF(0, 0, 80, 800),
        depth_span=80.0,
        interval_heights=[180.0, 220.0, 260.0],
    )

    assert body.font_px <= header.font_px
