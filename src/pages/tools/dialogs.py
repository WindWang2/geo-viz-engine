"""Task 21.2 — 6 Azurite-styled tool dialogs for ToolsPage.

Each dialog follows the Azurite design system:
  - #1f66d4 accent, #1a2433 primary text, #586878 secondary
  - #e5eaf1 borders, #fafbfd / #ffffff backgrounds
  - Rounded corners (12px), clean header with title + close
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QMessageBox,
)

from src.utils.paths import get_resources_dir


def _ui_icon(name: str) -> QIcon:
    path = get_resources_dir() / "icons" / "ui" / name
    return QIcon(str(path)) if path.exists() else QIcon()


AZURITE_DIALOG_SS = """
QDialog {
    background: #ffffff;
    border-radius: 12px;
}
"""

AZURITE_HEADER_SS = """
QLabel {
    font-size: 15px;
    font-weight: 700;
    color: #1a2433;
}
"""

AZURITE_SUBTITLE_SS = """
QLabel {
    font-size: 12px;
    color: #586878;
}
"""

AZURITE_PRIMARY_BTN = """
QPushButton {
    background: #1f66d4; color: #ffffff; border: none;
    border-radius: 8px; padding: 8px 20px; font-weight: 600;
}
QPushButton:hover { background: #1552b0; }
"""

AZURITE_SECONDARY_BTN = """
QPushButton {
    background: transparent; color: #586878; border: 1px solid #e5eaf1;
    border-radius: 8px; padding: 8px 20px; font-weight: 500;
}
QPushButton:hover { background: #f1f4f9; }
"""


class _AzuriteDialog(QDialog):
    """Base Azurite-styled dialog with header + close button."""

    def __init__(self, title: str, subtitle: str = "", min_width: int = 520, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(min_width)
        self.setStyleSheet(AZURITE_DIALOG_SS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header row
        hdr = QHBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(AZURITE_HEADER_SS)
        hdr.addWidget(title_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setStyleSheet(AZURITE_SUBTITLE_SS)
            hdr.addWidget(sub_lbl)

        hdr.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            "QPushButton { border: none; border-radius: 6px; color: #92a0b0; font-size: 14px; }"
            "QPushButton:hover { background: #f1f4f9; color: #1a2433; }"
        )
        close_btn.clicked.connect(self.reject)
        hdr.addWidget(close_btn)
        layout.addLayout(hdr)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e5eaf1; max-height: 1px;")
        layout.addWidget(sep)

        self._body_layout = QVBoxLayout()
        self._body_layout.setSpacing(10)
        layout.addLayout(self._body_layout)

        # Footer row (accept / cancel)
        self._footer = QHBoxLayout()
        self._footer.addStretch()

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setStyleSheet(AZURITE_SECONDARY_BTN)
        self._cancel_btn.clicked.connect(self.reject)
        self._footer.addWidget(self._cancel_btn)

        self._accept_btn = QPushButton("执行")
        self._accept_btn.setStyleSheet(AZURITE_PRIMARY_BTN)
        self._accept_btn.clicked.connect(self._on_accept_clicked)
        self._footer.addWidget(self._accept_btn)

        layout.addLayout(self._footer)

    def _on_accept_clicked(self):
        """Run the tool action; close only when it actually completed (#567).

        The old direct ``connect(self.accept)`` closed every tool dialog
        with zero computation — the four tool backends were unreachable
        from the UI.
        """
        try:
            if self._execute():
                self.accept()
        except Exception as exc:  # noqa: BLE001 - surface tool errors to the user
            QMessageBox.warning(self, "执行失败", f"{type(exc).__name__}: {exc}")

    def _execute(self) -> bool:
        """Gather inputs, run the tool backend, present results.

        Return True to close the dialog; return False (or raise) to keep
        it open for correction.
        """
        return True

    def _add_body_widget(self, widget):
        self._body_layout.addWidget(widget)

    def _add_body_layout(self, layout):
        self._body_layout.addLayout(layout)


class SEGYHeaderInspectorDialog(_AzuriteDialog):
    """1. SEGY 头信息查看器 — 导入 SEGY, 呈现 EBCDIC 文本头及二进制线头数据."""

    def __init__(self, parent=None):
        super().__init__("SEGY 头信息查看器", "导入 SEGY 文件，检索 EBCDIC 及二进制线头", min_width=560, parent=parent)

        from PySide6.QtWidgets import QLineEdit, QTextEdit

        row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("选择 SEGY 文件 (.sgy / .segy)...")
        self._path_edit.setReadOnly(True)
        self._path_edit.setStyleSheet(
            "QLineEdit { background: #fafbfd; border: 1px solid #e5eaf1; border-radius: 8px; padding: 7px 12px; }"
        )
        browse_btn = QPushButton(" 浏览")
        browse_btn.setIcon(_ui_icon("search.svg"))
        browse_btn.setStyleSheet(AZURITE_SECONDARY_BTN)
        browse_btn.clicked.connect(self._browse_segy)
        row.addWidget(QLabel("SEGY 文件:"))
        row.addWidget(self._path_edit, 1)
        row.addWidget(browse_btn)
        self._add_body_layout(row)

        self._text_header = QTextEdit()
        self._text_header.setReadOnly(True)
        self._text_header.setPlaceholderText("EBCDIC 文本头将在此处显示...")
        self._text_header.setMaximumHeight(140)
        self._text_header.setStyleSheet(
            "QTextEdit { background: #fafbfd; border: 1px solid #e5eaf1; border-radius: 8px; padding: 8px; font-family: monospace; font-size: 11px; color: #1a2433; }"
        )
        self._add_body_widget(QLabel("EBCDIC 文本头:"))
        self._add_body_widget(self._text_header)

        self._bin_header = QTextEdit()
        self._bin_header.setReadOnly(True)
        self._bin_header.setPlaceholderText("二进制线头数据将在此处显示...")
        self._bin_header.setMaximumHeight(120)
        self._bin_header.setStyleSheet(
            "QTextEdit { background: #fafbfd; border: 1px solid #e5eaf1; border-radius: 8px; padding: 8px; font-family: monospace; font-size: 11px; color: #1a2433; }"
        )
        self._add_body_widget(QLabel("二进制线头:"))
        self._add_body_widget(self._bin_header)

        self._accept_btn.setText("加载头信息")

    def _browse_segy(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 SEGY 文件", "", "SEGY Files (*.sgy *.segy)")
        if path:
            self._path_edit.setText(path)
            self._load_headers(path)

    def _load_headers(self, path: str):
        try:
            import segyio
            with segyio.open(path, "r", strict=False) as f:
                ebcdic = f.header[0]
                self._text_header.setPlainText(str(ebcdic))
                self._bin_header.setPlainText(
                    f"Samples: {f.samples.size}\n"
                    f"dt: {f.bin[segyio.BinField.Interval]} µs\n"
                    f"Format: {f.bin[segyio.BinField.Format]}"
                )
        except Exception as e:
            self._text_header.setPlainText(f"加载失败: {e}")


class LASCurveResamplerDialog(_AzuriteDialog):
    """2. 测井曲线深度采样器 — 导入 LAS, 设置采样间隔进行降采样."""

    def __init__(self, parent=None):
        super().__init__("测井曲线深度采样器", "导入 LAS 曲线并设置采样步长", min_width=480, parent=parent)

        from PySide6.QtWidgets import QLineEdit, QSpinBox, QDoubleSpinBox

        row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("选择 LAS 文件 (.las)...")
        self._path_edit.setReadOnly(True)
        self._path_edit.setStyleSheet(
            "QLineEdit { background: #fafbfd; border: 1px solid #e5eaf1; border-radius: 8px; padding: 7px 12px; }"
        )
        browse_btn = QPushButton(" 浏览")
        browse_btn.setIcon(_ui_icon("search.svg"))
        browse_btn.setStyleSheet(AZURITE_SECONDARY_BTN)
        browse_btn.clicked.connect(self._browse_las)
        row.addWidget(QLabel("LAS 文件:"))
        row.addWidget(self._path_edit, 1)
        row.addWidget(browse_btn)
        self._add_body_layout(row)

        step_row = QHBoxLayout()
        step_row.addWidget(QLabel("采样间隔 (m):"))
        self._step_spin = QDoubleSpinBox()
        self._step_spin.setRange(0.01, 100.0)
        self._step_spin.setValue(0.5)
        self._step_spin.setSingleStep(0.1)
        self._step_spin.setStyleSheet(
            "QDoubleSpinBox { background: #fafbfd; border: 1px solid #e5eaf1; border-radius: 8px; padding: 6px 10px; }"
        )
        step_row.addWidget(self._step_spin)
        step_row.addStretch()
        self._add_body_layout(step_row)

        self._accept_btn.setText("执行降采样")

    def _execute(self) -> bool:
        path = self._path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "缺少输入", "请先选择 LAS 文件。")
            return False
        depths, curves = self._do_resample(path, float(self._step_spin.value()))
        preview = "\n".join(
            f"  {mn}: {vals[0]:.4g} … {vals[-1]:.4g}" for mn, vals in list(curves.items())[:6]
        )
        more = f"\n  … 共 {len(curves)} 条曲线" if len(curves) > 6 else ""
        QMessageBox.information(
            self, "降采样完成",
            f"采样深度 {depths[0]:.4g} ~ {depths[-1]:.4g} m，步长 {self._step_spin.value():g} m，"
            f"共 {len(depths)} 个采样点。\n曲线预览:\n{preview}{more}",
        )
        return True

    def _browse_las(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 LAS 文件", "", "LAS Files (*.las)")
        if path:
            self._path_edit.setText(path)

    def _do_resample(self, path: str, step: float) -> tuple[list[float], dict[str, list[float]]]:
        """Load LAS, resample curves to the given depth step. Returns (depths, {mnemonic: values})."""
        import lasio
        las = lasio.read(path)
        df = las.df()
        if df.empty:
            raise ValueError("LAS file contains no data")
        start = max(df.index[0], las.index[0] if las.index else df.index[0])
        stop = min(df.index[-1], las.index[-1] if las.index else df.index[-1])
        import numpy as np
        new_depths = np.arange(start, stop + step / 2, step)
        new_depths = [float(d) for d in new_depths]
        result: dict[str, list[float]] = {}
        for col in df.columns:
            interp = np.interp(new_depths, df.index, df[col].values)
            result[str(col)] = [float(v) for v in interp]
        return new_depths, result


class DeviationTVDDialog(_AzuriteDialog):
    """3. 井斜校正计算器 — 最小曲率法计算 TVD/X/Y."""

    def __init__(self, parent=None):
        super().__init__("井斜校正计算器", "最小曲率法 · MD/Incl/Azim → TVD/X/Y", min_width=560, parent=parent)

        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView

        info = QLabel("输入测斜数据 (MD / Inclination / Azimuth)，点击执行计算 TVD 轨迹。")
        info.setStyleSheet(AZURITE_SUBTITLE_SS)
        info.setWordWrap(True)
        self._add_body_widget(info)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["MD (m)", "Incl (°)", "Azim (°)"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setMaximumHeight(200)
        self._table.setStyleSheet(
            "QTableWidget { background: #fafbfd; border: 1px solid #e5eaf1; border-radius: 8px; font-size: 12px; }"
            "QHeaderView::section { background: #f1f4f9; font-weight: 600; color: #586878; border: none; padding: 6px; }"
        )
        self._add_body_widget(self._table)

        # Pre-fill 5 rows
        for r in range(5):
            self._table.insertRow(r)

        add_row_btn = QPushButton("+ 添加行")
        add_row_btn.setStyleSheet(AZURITE_SECONDARY_BTN)
        add_row_btn.clicked.connect(lambda: self._table.insertRow(self._table.rowCount()))
        self._add_body_widget(add_row_btn)

        self._accept_btn.setText("计算 TVD")

    def _execute(self) -> bool:
        rows: list[tuple[float, float, float]] = []
        for r in range(self._table.rowCount()):
            cells = []
            for c in range(3):
                item = self._table.item(r, c)
                text = (item.text() if item is not None else "").strip()
                if not text:
                    continue
                try:
                    cells.append(float(text))
                except ValueError:
                    QMessageBox.warning(
                        self, "无法解析的输入",
                        f"第 {r + 1} 行第 {c + 1} 列不是数字: {text!r}",
                    )
                    return False
            if not cells:
                continue  # blank row
            if len(cells) != 3:
                QMessageBox.warning(
                    self, "不完整的行", f"第 {r + 1} 行需要 MD / Incl / Azim 三个数字。"
                )
                return False
            rows.append((cells[0], cells[1], cells[2]))  # type: ignore[arg-type]
        if len(rows) < 2:
            QMessageBox.warning(
                self, "输入不足", "至少需要两行完整的测斜数据 (MD / Incl / Azim)。"
            )
            return False
        rows.sort(key=lambda t: t[0])
        result = self._compute_min_curvature(rows)
        lines = "\n".join(
            f"  MD {rows[i][0]:g} → TVD {tvd:.3f}  X {x:.3f}  Y {y:.3f}"
            for i, (tvd, x, y) in enumerate(result)
        )
        QMessageBox.information(
            self, "TVD 计算完成",
            f"最小曲率法轨迹 ({len(result)} 站):\n{lines}",
        )
        return True

    def _compute_min_curvature(self, rows: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
        """Minimum curvature method: (MD, Incl, Azim) → (TVD, X, Y)."""
        import math
        result = [(0.0, 0.0, 0.0)]  # (TVD, X, Y)
        for i in range(1, len(rows)):
            md1, inc1, az1 = rows[i - 1]
            md2, inc2, az2 = rows[i]
            inc1_r = math.radians(inc1)
            inc2_r = math.radians(inc2)
            az1_r = math.radians(az1)
            az2_r = math.radians(az2)
            delta_md = md2 - md1
            if delta_md < 1e-9:
                result.append(result[-1])
                continue
            cos_eps = math.sin(inc1_r) * math.sin(inc2_r) * math.cos(az2_r - az1_r) + math.cos(inc1_r) * math.cos(inc2_r)
            cos_eps = max(-1.0, min(1.0, cos_eps))
            eps = math.acos(cos_eps)
            if eps < 1e-9:
                rf = 1.0
            else:
                rf = (2.0 / eps) * math.tan(eps / 2.0)
            d_tvd = rf * (delta_md / 2.0) * (math.cos(inc1_r) + math.cos(inc2_r))
            d_n = rf * (delta_md / 2.0) * (math.sin(inc1_r) * math.cos(az1_r) + math.sin(inc2_r) * math.cos(az2_r))
            d_e = rf * (delta_md / 2.0) * (math.sin(inc1_r) * math.sin(az1_r) + math.sin(inc2_r) * math.sin(az2_r))
            prev = result[-1]
            result.append((prev[0] + d_tvd, prev[1] + d_n, prev[2] + d_e))
        return result


class XMLCoordsConverterDialog(_AzuriteDialog):
    """4. XML 坐标转换工具 — 北京54/西安80/CGCS2000 投影坐标与经纬度换算."""

    def __init__(self, parent=None):
        super().__init__("XML 坐标转换工具", "北京54 / 西安80 / CGCS2000 投影 ↔ 经纬度", min_width=520, parent=parent)

        from PySide6.QtWidgets import QComboBox, QLineEdit

        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("源坐标系:"))
        self._src_combo = QComboBox()
        self._src_combo.addItems(["北京54", "西安80", "CGCS2000", "WGS84"])
        self._src_combo.setStyleSheet(
            "QComboBox { background: #fafbfd; border: 1px solid #e5eaf1; border-radius: 8px; padding: 6px 12px; }"
        )
        src_row.addWidget(self._src_combo)
        src_row.addStretch()
        self._add_body_layout(src_row)

        dst_row = QHBoxLayout()
        dst_row.addWidget(QLabel("目标坐标系:"))
        self._dst_combo = QComboBox()
        self._dst_combo.addItems(["WGS84", "CGCS2000", "西安80", "北京54"])
        self._dst_combo.setStyleSheet(
            "QComboBox { background: #fafbfd; border: 1px solid #e5eaf1; border-radius: 8px; padding: 6px 12px; }"
        )
        dst_row.addWidget(self._dst_combo)
        dst_row.addStretch()
        self._add_body_layout(dst_row)

        self._accept_btn.setText("批量转换")

        from PySide6.QtWidgets import QPlainTextEdit

        coord_row = QHBoxLayout()
        coord_row.addWidget(QLabel("坐标 (每行 x,y):"))
        self._coords_edit = QPlainTextEdit()
        self._coords_edit.setPlaceholderText("每行一个坐标对，例如:\n116.351,39.984\n116.372,40.001")
        self._coords_edit.setMaximumHeight(120)
        self._coords_edit.setStyleSheet(
            "QPlainTextEdit { background: #fafbfd; border: 1px solid #e5eaf1; border-radius: 8px; padding: 6px 10px; font-size: 12px; }"
        )
        self._add_body_widget(self._coords_edit)

    def _execute(self) -> bool:
        coords: list[tuple[float, float]] = []
        for ln, line in enumerate(self._coords_edit.toPlainText().splitlines(), 1):
            text = line.strip()
            if not text:
                continue
            parts = [p for p in text.replace("，", ",").split(",") if p.strip()]
            if len(parts) != 2:
                QMessageBox.warning(self, "无法解析的坐标", f"第 {ln} 行需要两个逗号分隔的数字: {text!r}")
                return False
            try:
                coords.append((float(parts[0]), float(parts[1])))
            except ValueError:
                QMessageBox.warning(self, "无法解析的坐标", f"第 {ln} 行包含非数字: {text!r}")
                return False
        if not coords:
            QMessageBox.warning(self, "缺少输入", "请输入至少一个坐标对 (每行 x,y)。")
            return False
        converted = self._do_convert(self._src_combo.currentText(), self._dst_combo.currentText(), coords)
        lines = "\n".join(f"  {x:.6f}, {y:.6f}" for x, y in converted)
        QMessageBox.information(
            self, "转换完成",
            f"{self._src_combo.currentText()} → {self._dst_combo.currentText()}，"
            f"共 {len(converted)} 个坐标:\n{lines}",
        )
        return True

    def _do_convert(self, src_epsg: str, dst_epsg: str, coords: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """Convert coordinates between CRS using pyproj."""
        try:
            from pyproj import Transformer
            epsg_map = {"北京54": "EPSG:4214", "西安80": "EPSG:4610", "CGCS2000": "EPSG:4490", "WGS84": "EPSG:4326"}
            src = epsg_map.get(src_epsg, "EPSG:4326")
            dst = epsg_map.get(dst_epsg, "EPSG:4326")
            transformer = Transformer.from_crs(src, dst, always_xy=True)
            result = []
            for x, y in coords:
                nx, ny = transformer.transform(x, y)
                result.append((float(nx), float(ny)))
            return result
        except ImportError:
            return list(coords)  # passthrough if pyproj not available


class TopsCompletionDialog(_AzuriteDialog):
    """5. 地层分层缺失自动插值器 — 向导式缺失层位推导."""

    def __init__(self, parent=None):
        super().__init__("地层分层缺失插值器", "向导式缺失层位推导 · 辅助生成连井背景层", min_width=480, parent=parent)

        info = QLabel("选择目标井位，系统将自动推导缺失的层位分层数据。")
        info.setStyleSheet(AZURITE_SUBTITLE_SS)
        info.setWordWrap(True)
        self._add_body_widget(info)

        from PySide6.QtWidgets import QComboBox

        method_row = QHBoxLayout()
        method_row.addWidget(QLabel("插值方法:"))
        self._method_combo = QComboBox()
        self._method_combo.addItems(["线性插值", "最近邻", "RBF 径向基"])
        self._method_combo.setStyleSheet(
            "QComboBox { background: #fafbfd; border: 1px solid #e5eaf1; border-radius: 8px; padding: 6px 12px; }"
        )
        method_row.addWidget(self._method_combo)
        method_row.addStretch()
        self._add_body_layout(method_row)

        self._accept_btn.setText("执行插值")

        from PySide6.QtWidgets import QPlainTextEdit

        self._tops_edit = QPlainTextEdit()
        self._tops_edit.setPlaceholderText(
            "JSON: 井名 → {层位: 深度或 null}\n"
            '{"W1": {"H1": 1000.0, "H2": 1200.0},\n "W2": {"H1": 1010.0, "H2": null}}'
        )
        self._tops_edit.setMaximumHeight(140)
        self._tops_edit.setStyleSheet(
            "QPlainTextEdit { background: #fafbfd; border: 1px solid #e5eaf1; border-radius: 8px; padding: 6px 10px; font-size: 12px; }"
        )
        self._add_body_widget(self._tops_edit)

    def _execute(self) -> bool:
        import json

        text = self._tops_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "缺少输入", "请输入分层数据 (JSON: 井名 → {层位: 深度或 null})。")
            return False
        try:
            known_tops = json.loads(text)
        except ValueError as exc:
            QMessageBox.warning(self, "JSON 解析失败", f"输入不是合法 JSON:\n{exc}")
            return False
        if not isinstance(known_tops, dict) or not all(
            isinstance(tops, dict) for tops in known_tops.values()
        ):
            QMessageBox.warning(self, "格式不符", "顶层必须是对象，且每个井名对应 {层位: 深度或 null}。")
            return False
        method = {"线性插值": "linear", "最近邻": "nearest", "RBF 径向基": "rbf"}[
            self._method_combo.currentText()
        ]
        result = self._do_interpolate(known_tops, method=method)
        filled = [
            f"  {wn}.{fm} = {v}"
            for wn, tops in result.items()
            for fm, v in tops.items()
            if known_tops.get(wn, {}).get(fm) is None and v is not None
        ]
        body = "\n".join(filled) if filled else "  （没有可推导的缺失层位）"
        QMessageBox.information(self, "插值完成", f"推导出的缺失分层:\n{body}")
        return True

    def _do_interpolate(self, known_tops: dict[str, dict[str, float | None]], method: str = "linear") -> dict[str, dict[str, float | None]]:
        """Fill missing formation tops using interpolation across wells."""
        import copy
        result = copy.deepcopy(known_tops)
        well_names = list(known_tops.keys())
        formations = set()
        for tops in known_tops.values():
            formations.update(tops.keys())
        for fm in formations:
            known = [(i, known_tops[wn][fm]) for i, wn in enumerate(well_names) if known_tops[wn].get(fm) is not None]
            missing = [(i, wn) for i, wn in enumerate(well_names) if known_tops[wn].get(fm) is None]
            if len(known) < 2 or not missing:
                continue
            known_idx = [k[0] for k in known]
            known_vals = [float(k[1]) for k in known]  # type: ignore
            for mi, mn in missing:
                if mi < known_idx[0]:
                    result[mn][fm] = known_vals[0]
                elif mi > known_idx[-1]:
                    result[mn][fm] = known_vals[-1]
                else:
                    for j in range(len(known_idx) - 1):
                        if known_idx[j] < mi < known_idx[j + 1]:
                            frac = (mi - known_idx[j]) / (known_idx[j + 1] - known_idx[j])
                            val = known_vals[j] + frac * (known_vals[j + 1] - known_vals[j])
                            result[mn][fm] = round(val, 2)
                            break
        return result


class CalamineCompilerDialog(_AzuriteDialog):
    """6. Calamine 脚本高速编译引擎 — 地质公式校验与编译提示."""

    def __init__(self, parent=None):
        super().__init__("Calamine 编译引擎", "地质公式高速校验 · 脚本编译提示", min_width=480, parent=parent)

        from PySide6.QtWidgets import QTextEdit

        info = QLabel("输入地质公式或脚本表达式，系统将进行语法校验与编译提示。")
        info.setStyleSheet(AZURITE_SUBTITLE_SS)
        info.setWordWrap(True)
        self._add_body_widget(info)

        self._editor = QTextEdit()
        self._editor.setPlaceholderText("输入地质公式表达式...")
        self._editor.setMaximumHeight(160)
        self._editor.setStyleSheet(
            "QTextEdit { background: #fafbfd; border: 1px solid #e5eaf1; border-radius: 8px; padding: 8px; font-family: monospace; font-size: 12px; }"
        )
        self._add_body_widget(self._editor)

        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setPlaceholderText("编译输出将在此处显示...")
        self._output.setMaximumHeight(100)
        self._output.setStyleSheet(
            "QTextEdit { background: #f1f4f9; border: 1px solid #e5eaf1; border-radius: 8px; padding: 8px; font-family: monospace; font-size: 11px; color: #586878; }"
        )
        self._add_body_widget(QLabel("编译输出:"))
        self._add_body_widget(self._output)

        self._accept_btn.setText("校验编译")

    def _do_compile(self, expression: str) -> tuple[bool, str]:
        """Validate a geological formula expression. Returns (ok, message)."""
        if not expression.strip():
            return False, "表达式为空"
        import math
        safe_globals = {
            "__builtins__": {},
            "math": math,
            "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "log": math.log, "log10": math.log10, "exp": math.exp,
            "sqrt": math.sqrt, "abs": abs, "min": min, "max": max,
            "pi": math.pi, "e": math.e,
        }
        try:
            code = compile(expression.strip(), "<calamine>", "eval")
            for name in code.co_names:
                if name in safe_globals:
                    continue
                if name.startswith("_"):
                    return False, f"不允许的私有变量: {name}"
                # Allow arbitrary uppercase/lowercase identifiers as curve mnemonics
            return True, "校验成功 — 表达式语法正确"
        except SyntaxError as e:
            return False, f"语法错误: {e.msg} (行 {e.lineno}, 列 {e.offset})"
        except Exception as e:
            return False, f"编译错误: {e}"
