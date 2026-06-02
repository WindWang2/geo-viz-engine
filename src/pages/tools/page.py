import os
from pathlib import Path
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QFrame, QGridLayout, QLineEdit,
)

from scripts.convert_xml_to_laolong import convert_to_laolong_xls
from src.utils.paths import get_resources_dir
from src.pages.tools.dialogs import (
    SEGYHeaderInspectorDialog,
    LASCurveResamplerDialog,
    DeviationTVDDialog,
    XMLCoordsConverterDialog,
    TopsCompletionDialog,
)


def _get_ui_icon(name: str) -> QIcon:
    path = get_resources_dir() / "icons" / "ui" / name
    return QIcon(str(path)) if path.exists() else QIcon()


class ToolCard(QFrame):
    """Azurite-style tool card: accent-soft icon + name + tag + description + hover shadow."""

    def __init__(self, icon_name: str, name: str, tag: str, description: str, parent=None):
        super().__init__(parent)
        self.setObjectName("toolCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            #toolCard {
                background: #ffffff;
                border: 1px solid #e5eaf1;
                border-radius: 12px;
                padding: 16px;
            }
            #toolCard:hover {
                border-color: #1f66d4;
                background: #f8faff;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Left: accent-soft icon container
        icon_frame = QFrame()
        icon_frame.setFixedSize(42, 42)
        icon_frame.setStyleSheet(
            "QFrame { background: #e9effa; border-radius: 10px; }"
        )
        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(_get_ui_icon(icon_name).pixmap(QSize(20, 20)))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(icon_lbl)
        layout.addWidget(icon_frame)

        # Right: name + tag row, then description
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(3)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-weight: 600; font-size: 13px; color: #1a2433; border: none;")
        name_row.addWidget(name_lbl)

        tag_lbl = QLabel(tag)
        tag_lbl.setStyleSheet(
            "background: #e9effa; color: #1f66d4; font-size: 10px; font-weight: 600;"
            "border-radius: 4px; padding: 1px 7px; border: none;"
        )
        name_row.addWidget(tag_lbl)
        name_row.addStretch()
        text_col.addLayout(name_row)

        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #586878; font-size: 11.5px; border: none;")
        text_col.addWidget(desc_lbl)

        layout.addLayout(text_col, 1)


# 6 tools matching Task 20.5 spec + Phase 21.2 roadmap
_TOOLS = [
    ("convert.svg", "测井 XML 转 Excel", "LaoLong", "将测井 XML 数据转换为 LaoLong 格式 Excel 文件"),
    ("table.svg",   "SEGY 头信息查看器", "SEGY",   "导入 SEGY 文件，直观呈现 EBCDIC 文本头及二进制线头数据"),
    ("wave.svg",    "测井曲线深度采样器", "LAS",    "导入测井曲线，设置采样间隔步长进行降采样并输出对比"),
    ("crosshair.svg","井斜校正计算器", "TVD",     "输入测斜表 (MD/Incl/Azim)，最小曲率法计算 TVD/X/Y 轨迹"),
    ("globe.svg",   "XML 坐标转换工具", "投影",    "北京54/西安80/CGCS2000 投影坐标与经纬度批量换算"),
    ("grid3d.svg",  "地层分层缺失插值器", "插值",   "向导式缺失层位推导工具，辅助生成连井背景层"),
]


class ToolsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("工具箱")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1a2433;")
        header.addWidget(title)
        subtitle = QLabel("独立小工具集")
        subtitle.setStyleSheet("font-size: 12px; color: #92a0b0;")
        header.addWidget(subtitle)
        layout.addLayout(header)

        # Tool cards grid (2 columns)
        self._card_grid = QGridLayout()
        self._card_grid.setSpacing(14)
        self._cards: list[ToolCard] = []

        for i, (icon, name, tag, desc) in enumerate(_TOOLS):
            card = ToolCard(icon, name, tag, desc)
            row, col = divmod(i, 2)
            self._card_grid.addWidget(card, row, col)
            self._cards.append(card)

        layout.addLayout(self._card_grid)
        layout.addStretch()

        # Wire each card to its dialog handler
        self._card_handlers = [
            self._open_xml_converter,
            self._open_segy_inspector,
            self._open_las_resampler,
            self._open_tvd_calculator,
            self._open_xml_coords,
            self._open_tops_interpolator,
        ]
        for i, handler in enumerate(self._card_handlers):
            self._cards[i].mousePressEvent = lambda e, h=handler: h()

    # ------------------------------------------------------------------
    # Dialog openers for each tool card
    # ------------------------------------------------------------------
    def _open_segy_inspector(self):
        dlg = SEGYHeaderInspectorDialog(self.window())
        dlg.exec()

    def _open_las_resampler(self):
        dlg = LASCurveResamplerDialog(self.window())
        dlg.exec()

    def _open_tvd_calculator(self):
        dlg = DeviationTVDDialog(self.window())
        dlg.exec()

    def _open_xml_coords(self):
        dlg = XMLCoordsConverterDialog(self.window())
        dlg.exec()

    def _open_tops_interpolator(self):
        dlg = TopsCompletionDialog(self.window())
        dlg.exec()

    # ------------------------------------------------------------------
    # XML → Excel converter (existing functionality, now in a dialog)
    # ------------------------------------------------------------------
    def _open_xml_converter(self):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("测井 XML 转 Excel")
        dlg.setText("选择 XML 文件并转换为 LaoLong 格式 Excel。")

        # Build a custom dialog with file pickers
        dialog = QFrame(self.window())
        dialog.setWindowFlags(Qt.WindowType.Dialog)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setFixedSize(480, 220)
        dialog.setWindowTitle("测井 XML 转 Excel (LaoLong 格式)")
        dialog.setStyleSheet(
            "QFrame { background: #ffffff; border-radius: 12px; }"
        )
        dl = QVBoxLayout(dialog)
        dl.setContentsMargins(20, 20, 20, 20)
        dl.setSpacing(12)

        # Input row
        in_layout = QHBoxLayout()
        self._in_xml = QLineEdit()
        self._in_xml.setPlaceholderText("选择输入的 XML 文件...")
        self._in_xml.setReadOnly(True)
        in_btn = QPushButton(" 浏览")
        in_btn.setIcon(_get_ui_icon("search.svg"))
        in_btn.clicked.connect(self._select_input_xml)
        in_layout.addWidget(QLabel("输入 XML:"), 0)
        in_layout.addWidget(self._in_xml, 1)
        in_layout.addWidget(in_btn, 0)
        dl.addLayout(in_layout)

        # Output row
        out_layout = QHBoxLayout()
        self._out_xls = QLineEdit()
        self._out_xls.setPlaceholderText("选择输出的 Excel 文件路径...")
        out_btn = QPushButton(" 浏览")
        out_btn.setIcon(_get_ui_icon("search.svg"))
        out_btn.clicked.connect(self._select_output_xls)
        out_layout.addWidget(QLabel("输出 Excel:"), 0)
        out_layout.addWidget(self._out_xls, 1)
        out_layout.addWidget(out_btn, 0)
        dl.addLayout(out_layout)

        # Run button
        self._run_btn = QPushButton(" 执行转换")
        self._run_btn.setMinimumWidth(110)
        self._run_btn.setIcon(_get_ui_icon("play.svg"))
        self._run_btn.setStyleSheet(
            "QPushButton { background: #1f66d4; color: #ffffff; border: none; border-radius: 8px; padding: 8px 18px; font-weight: 600; }"
            "QPushButton:hover { background: #1552b0; }"
        )
        self._run_btn.clicked.connect(self._run_conversion)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._run_btn)
        dl.addLayout(btn_row)

        dialog.show()

    def _select_input_xml(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 XML 文件", "", "XML Files (*.xml)")
        if path:
            self._in_xml.setText(path)
            self._out_xls.setText(str(Path(path).with_suffix(".xls")))

    def _select_output_xls(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存为 Excel 文件", self._out_xls.text(), "Excel Files (*.xls *.xlsx)")
        if path:
            self._out_xls.setText(path)

    def _run_conversion(self):
        in_path = self._in_xml.text()
        out_path = self._out_xls.text()
        if not in_path or not out_path:
            QMessageBox.warning(self, "缺少参数", "请指定输入和输出文件路径。")
            return
        if not os.path.exists(in_path):
            QMessageBox.critical(self, "文件不存在", "指定的输入 XML 文件不存在。")
            return
        self._run_btn.setEnabled(False)
        self._run_btn.setText("转换中...")
        try:
            convert_to_laolong_xls(in_path, out_path)
            QMessageBox.information(self, "转换成功", f"文件已成功转换为 LaoLong 格式 Excel。\n输出路径: {out_path}")
        except Exception as e:
            QMessageBox.critical(self, "转换失败", f"转换过程中发生错误:\n{str(e)}")
        finally:
            self._run_btn.setEnabled(True)
            self._run_btn.setText(" 执行转换")
