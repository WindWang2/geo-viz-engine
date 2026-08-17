from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QFrame, QLabel, QGroupBox
)
from PySide6.QtCore import Qt

from geoviz_seismic import SeismicView


class SeismicPage(SeismicView):
    """App-level seismic page — inherits and refactors visual layout to premium high-fidelity."""

    def __init__(self, parent=None, auto_load: bool = True):
        super().__init__(parent, auto_load=auto_load)

        # 1. Create right sidebar container (width 226px)
        self.right_sidebar = QFrame()
        self.right_sidebar.setFixedWidth(226)
        self.right_sidebar.setStyleSheet(
            "QFrame { background: #ffffff; border-left: 1px solid #e5eaf1; }"
        )
        sidebar_layout = QVBoxLayout(self.right_sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(16)

        # Title: Section 1 (剖面切片控制)
        lbl_sec1 = QLabel("剖面切片控制")
        lbl_sec1.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a2433; border: none;")
        sidebar_layout.addWidget(lbl_sec1)

        # Inline Slider Section
        lbl_il = QLabel("Inline 剖面位置")
        lbl_il.setStyleSheet("color: #586878; font-size: 11px; border: none;")
        sidebar_layout.addWidget(lbl_il)
        sidebar_layout.addWidget(self._tb_il_slider)

        # Crossline Slider Section
        lbl_xl = QLabel("Crossline 剖面位置")
        lbl_xl.setStyleSheet("color: #586878; font-size: 11px; border: none;")
        sidebar_layout.addWidget(lbl_xl)
        sidebar_layout.addWidget(self._tb_xl_slider)

        # Time Slider Section
        lbl_t = QLabel("Time / 深度切片位置")
        lbl_t.setStyleSheet("color: #586878; font-size: 11px; border: none;")
        sidebar_layout.addWidget(lbl_t)
        sidebar_layout.addWidget(self._tb_t_slider)

        # Title: Section 2 (渲染选项)
        lbl_sec2 = QLabel("三维体及渲染选项")
        lbl_sec2.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a2433; border: none; margin-top: 12px;")
        sidebar_layout.addWidget(lbl_sec2)

        # Colormap Select
        lbl_cmap = QLabel("色彩映射 (Colormap)")
        lbl_cmap.setStyleSheet("color: #586878; font-size: 11px; border: none;")
        sidebar_layout.addWidget(lbl_cmap)
        self._cmap_combo.setStyleSheet(
            "QComboBox { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 2px 10px; color: #1a2433; }"
        )
        sidebar_layout.addWidget(self._cmap_combo)

        # 3D Display Mode
        lbl_3d = QLabel("3D 显示模式")
        lbl_3d.setStyleSheet("color: #586878; font-size: 11px; border: none;")
        sidebar_layout.addWidget(lbl_3d)
        self._3d_mode_combo.setStyleSheet(
            "QComboBox { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 2px 10px; color: #1a2433; }"
        )
        sidebar_layout.addWidget(self._3d_mode_combo)

        # Opacity Formula
        lbl_op = QLabel("透明度传递函数")
        lbl_op.setStyleSheet("color: #586878; font-size: 11px; border: none;")
        sidebar_layout.addWidget(lbl_op)
        self._opacity_combo.setStyleSheet(
            "QComboBox { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 2px 10px; color: #1a2433; }"
        )
        sidebar_layout.addWidget(self._opacity_combo)

        # Clip SpinBox
        lbl_clip = QLabel("波形削波百分比 (Clip)")
        lbl_clip.setStyleSheet("color: #586878; font-size: 11px; border: none;")
        sidebar_layout.addWidget(lbl_clip)
        self._clip_spin.setStyleSheet(
            "QDoubleSpinBox { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 2px 10px; color: #1a2433; }"
        )
        sidebar_layout.addWidget(self._clip_spin)

        # Title: Section 3 (井震标定)
        lbl_sec3 = QLabel("井震标定 Auto-Tie")
        lbl_sec3.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a2433; border: none; margin-top: 12px;")
        sidebar_layout.addWidget(lbl_sec3)

        self._tie_quality_label = QLabel("时间偏置: —\n相位旋转: —\n相关度: 未标定")
        self._tie_quality_label.setStyleSheet("color: #2ca36b; font-size: 11.5px; font-weight: bold; border: none; padding: 4px;")
        sidebar_layout.addWidget(self._tie_quality_label)

        sidebar_layout.addStretch()

        # Find the QHBoxLayout (contains splitter + colorbar) and insert right_sidebar
        main_layout = self.layout()
        h_layout = None
        for i in range(main_layout.count()):
            item = main_layout.itemAt(i)
            if item.layout() and isinstance(item.layout(), QHBoxLayout):
                h_layout = item.layout()
                break

        if h_layout:
            h_layout.addWidget(self.right_sidebar)
