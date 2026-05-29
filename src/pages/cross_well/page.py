# src/pages/cross_well/page.py
"""Cross-well correlation page using CrossWellCanvas with picking workflow."""
from __future__ import annotations

from PySide6.QtCore import Qt, QObject, QThread, Signal, QEvent
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialog, QListWidget, QListWidgetItem, QAbstractItemView,
    QFileDialog, QMessageBox, QScrollArea,
)

from geoviz_well_log import build_qpainter_tracks
from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_cross_well import CrossWellCanvas
from src.data.well_registry import list_wells, get_well_data
from src.utils.floating_progress import FloatingProgressOverlay


class _WellSelectDialog(QDialog):
    """Multi-select dialog for choosing wells to compare."""

    def __init__(self, well_names: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择对比井")
        self.setMinimumSize(300, 400)

        layout = QVBoxLayout(self)

        label = QLabel("勾选要对比的井号：")
        label.setStyleSheet("font-weight: bold; padding: 8px;")
        layout.addWidget(label)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for name in sorted(well_names):
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._list.addItem(item)
        layout.addWidget(self._list)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        ok_btn = QPushButton("确定")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def get_selected(self) -> list[str]:
        selected = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected


_REQUIRED_LABELS = {"深度", "岩性"}
_MAX_OPTIONAL = 3


class _TrackSelectDialog(QDialog):
    """Dialog for selecting which tracks to show per well (max 5)."""

    def __init__(self, all_labels: list[str], selected: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择井道")
        self.setMinimumSize(300, 400)

        layout = QVBoxLayout(self)

        hint = QLabel("深度和岩性固定显示，最多再选3个井道：")
        hint.setStyleSheet("font-weight: bold; padding: 8px;")
        layout.addWidget(hint)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for label in all_labels:
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if label in _REQUIRED_LABELS:
                item.setCheckState(Qt.CheckState.Checked)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                item.setForeground(Qt.GlobalColor.gray)
            else:
                is_checked = label in selected
                item.setCheckState(
                    Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
                )
            self._list.addItem(item)

        self._list.itemChanged.connect(self._enforce_limit)
        layout.addWidget(self._list)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        ok_btn = QPushButton("确定")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def _enforce_limit(self, changed: QListWidgetItem):
        checked = sum(
            1 for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.CheckState.Checked
            and self._list.item(i).text() not in _REQUIRED_LABELS
        )
        if checked > _MAX_OPTIONAL:
            changed.setCheckState(Qt.CheckState.Unchecked)

    def get_selected(self) -> list[str]:
        selected = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected


class _WellLoadWorker(QObject):
    """Background worker that loads well data."""

    progress = Signal(int, str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, well_names: list[str], parent=None):
        super().__init__(parent)
        self._well_names = well_names

    def run(self):
        result = []
        for i, name in enumerate(self._well_names):
            try:
                entry = get_well_data(name)
                if entry is None:
                    continue
                loader_fn, xls_path, config = entry
                data = loader_fn(xls_path, well_name=name)
                result.append((name, data))
                self.progress.emit(i, name)
            except Exception as e:
                print(f"[CrossWell] Failed to load {name}: {e}")
        self.finished.emit(result)


class CrossWellPage(QWidget):
    """Cross-well correlation page with grouped toolbar and picking workflow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._selected_labels: list[str] | None = None
        self._well_data_cache: dict[str, object] = {}
        self._all_track_labels: list[str] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Toolbar ---
        self._toolbar = QWidget()
        self._toolbar.setStyleSheet(
            "background: #f7fafc; border-bottom: 1px solid #e2e8f0;"
        )
        tb = QHBoxLayout(self._toolbar)
        tb.setContentsMargins(12, 6, 12, 6)

        title = QLabel("连井对比")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a202c;")
        tb.addWidget(title)
        tb.addSpacing(12)

        # Data group
        self._add_btn = self._make_btn("添加井")
        self._add_btn.clicked.connect(self._on_add_wells)
        tb.addWidget(self._add_btn)

        self._clear_btn = QPushButton("清除")
        self._clear_btn.setFixedHeight(28)
        self._clear_btn.setStyleSheet("""
            QPushButton {
                background: #fed7d7; color: #9b2c2c;
                border: 1px solid #feb2b2; border-radius: 4px;
                padding: 0 12px; font-size: 13px;
            }
            QPushButton:hover { background: #fc8181; color: white; }
        """)
        self._clear_btn.clicked.connect(self._on_clear)
        tb.addWidget(self._clear_btn)

        self._sep(tb)

        # View group
        self._track_btn = self._make_btn("选择井道")
        self._track_btn.clicked.connect(self._on_select_tracks)
        tb.addWidget(self._track_btn)

        self._domain_btn = self._make_btn("域: MD")
        self._domain_btn.setCheckable(True)
        self._domain_btn.clicked.connect(self._on_toggle_domain)
        tb.addWidget(self._domain_btn)

        self._sep(tb)

        # Correlate group
        self._pick_btn = QPushButton("手动拾取")
        self._pick_btn.setFixedHeight(28)
        self._pick_btn.setCheckable(True)
        self._pick_btn.setStyleSheet(self._btn_style())
        self._pick_btn.clicked.connect(self._on_toggle_pick)
        tb.addWidget(self._pick_btn)

        self._auto_btn = self._make_btn("自动连井")
        self._auto_btn.clicked.connect(self._on_auto_link)
        tb.addWidget(self._auto_btn)

        self._tops_btn = self._make_btn("导入层位")
        self._tops_btn.clicked.connect(self._on_load_tops)
        tb.addWidget(self._tops_btn)

        tb.addStretch()

        # Export group
        self._export_btn = QPushButton("导出")
        self._export_btn.setFixedHeight(28)
        self._export_btn.setStyleSheet("""
            QPushButton {
                background: #3182ce; color: white;
                border: none; border-radius: 4px;
                padding: 0 12px; font-size: 13px;
            }
            QPushButton:hover { background: #2b6cb0; }
            QPushButton:pressed { background: #2c5282; }
        """)
        self._export_btn.clicked.connect(self._on_export)
        tb.addWidget(self._export_btn)

        outer.addWidget(self._toolbar)

        # --- Progress ---
        self._progress = FloatingProgressOverlay(self)
        outer.addWidget(self._progress)

        # --- Status bar ---
        self._status = QLabel()
        self._status.setStyleSheet(
            "background: #f7fafc; border-top: 1px solid #e2e8f0; "
            "padding: 4px 12px; font-size: 12px; color: #4a5568;"
        )
        self._update_status()
        outer.addWidget(self._status)

        # --- CrossWellCanvas ---
        self._canvas = CrossWellCanvas()
        self._cross_well = self._canvas.widget  # underlying CrossWellWidget
        outer.addWidget(self._canvas, 1)
        self._scroll = None

        # --- Empty state ---
        self._placeholder = QWidget()
        ph_layout = QVBoxLayout(self._placeholder)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_title = QLabel("连井对比")
        ph_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1a202c;")
        ph_sub = QLabel("点击「添加井」选择要对比的井号")
        ph_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_sub.setStyleSheet("font-size: 14px; color: #718096; margin-top: 8px;")
        ph_cta = QPushButton("添加井")
        ph_cta.setFixedSize(120, 36)
        ph_cta.setStyleSheet("""
            QPushButton {
                background: #3182ce; color: white;
                border: none; border-radius: 6px;
                font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background: #2b6cb0; }
        """)
        ph_cta.clicked.connect(self._on_add_wells)
        ph_layout.addWidget(ph_title)
        ph_layout.addWidget(ph_sub)
        ph_layout.addSpacing(16)
        cta_box = QHBoxLayout()
        cta_box.addStretch()
        cta_box.addWidget(ph_cta)
        cta_box.addStretch()
        ph_layout.addLayout(cta_box)
        self._placeholder.setStyleSheet(
            "background: #f7fafc; border: 2px dashed #cbd5e1; border-radius: 12px;"
        )
        self._cross_well._container_layout.insertWidget(0, self._placeholder)

    def showEvent(self, event):
        super().showEvent(event)
        if self._scroll is None:
            layout = self.layout()
            layout.removeWidget(self._canvas)
            self._scroll = QScrollArea()
            self._scroll.setWidgetResizable(True)
            self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._scroll.setStyleSheet("QScrollArea { background: #ffffff; border: none; }")
            layout.insertWidget(layout.count() - 1, self._scroll, 1)
            self._scroll.show()
            self._scroll.setWidget(self._canvas)
            self._canvas.show()
            self._scroll.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is not None and event is not None and event.type() == QEvent.Type.Wheel and self._scroll is not None:
            viewport = self._scroll.viewport()
            if obj is viewport:
                pos = event.position().toPoint()
                for canvas in self._cross_well._canvases:
                    canvas_pos = canvas.mapFrom(viewport, pos)
                    if canvas.rect().contains(canvas_pos):
                        canvas_global = event.globalPosition().toPoint() - event.position().toPoint() + canvas_pos
                        new_event = QWheelEvent(
                            canvas_pos, canvas_global,
                            event.pixelDelta(), event.angleDelta(),
                            event.buttons(), event.modifiers(),
                            event.phase(), event.inverted(),
                        )
                        from PySide6.QtWidgets import QApplication
                        QApplication.sendEvent(canvas, new_event)
                        return True
        return super().eventFilter(obj, event)

    @property
    def canvas_count(self) -> int:
        return self._cross_well.canvas_count

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Z:
                self._canvas.picks_model.undo()
                return
            elif event.key() == Qt.Key.Key_Y:
                self._canvas.picks_model.redo()
                return
        if event.key() == Qt.Key.Key_Escape:
            if self._canvas.pick_mode:
                self.canvas.pick_mode = False
                self._pick_btn.setChecked(False)
                self._pick_btn.setStyleSheet(self._btn_style())
                return
        super().keyPressEvent(event)

    # --- Helpers ---

    @staticmethod
    def _btn_style() -> str:
        return """
            QPushButton {
                background: #edf2f7; color: #1e293b;
                border: 1px solid #cbd5e1; border-radius: 4px;
                padding: 0 12px; font-size: 13px;
            }
            QPushButton:hover { background: #e2e8f0; }
        """

    def _make_btn(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(28)
        btn.setStyleSheet(self._btn_style())
        return btn

    @staticmethod
    def _sep(layout: QHBoxLayout):
        sep = QLabel("|")
        sep.setStyleSheet("color: #cbd5e1; font-size: 16px;")
        layout.addWidget(sep)

    def _update_status(self):
        parts = []
        n = self._cross_well.canvas_count if hasattr(self, '_cross_well') else 0
        parts.append(f"{n} wells" if n else "no wells")
        if hasattr(self, '_canvas') and self._canvas.pick_mode:
            parts.append("PICK MODE")
        self._status.setText("  |  ".join(parts) if parts else "")

    # --- Actions ---

    def _on_add_wells(self):
        available = list_wells()
        if not available:
            QMessageBox.information(self, "添加井", "没有可用的井数据。")
            return
        dialog = _WellSelectDialog(available, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = dialog.get_selected()
        if not selected:
            return
        self._load_wells(selected)

    def _load_wells(self, well_names: list[str]):
        self._placeholder.setVisible(False)
        self._add_btn.setEnabled(False)
        self._progress.show_progress("正在加载井数据...")

        self._thread = QThread()
        self._worker = _WellLoadWorker(well_names)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_load_finished)
        self._worker.error.connect(self._on_load_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def _on_load_finished(self, results: list):
        self._add_btn.setEnabled(True)
        for well_name, data in results:
            self._well_data_cache[well_name] = data
            all_tracks = build_qpainter_tracks(data)
            all_labels = [t.label for t in all_tracks]

            if self._selected_labels is None:
                self._all_track_labels = all_labels
                self._selected_labels = self._default_labels(all_labels)

            filtered = self._filter_tracks(all_tracks, self._selected_labels)
            canvas = WellLogCanvas()
            canvas.set_tracks(filtered)
            self._cross_well.add_canvas(canvas, well_name)

            if data.intervals and data.intervals.formation:
                self._cross_well.set_formation_data(well_name, data.intervals.formation)

        self._update_status()

    @staticmethod
    def _default_labels(all_labels: list[str]) -> list[str]:
        selected = [l for l in all_labels if l in _REQUIRED_LABELS]
        optional = [l for l in all_labels if l not in _REQUIRED_LABELS]
        selected.extend(optional[:_MAX_OPTIONAL])
        return selected

    def _on_load_error(self, msg: str):
        self._add_btn.setEnabled(True)
        self._placeholder.setVisible(True)
        self._progress.hide_progress()
        QMessageBox.warning(self, "加载失败", msg)

    def _on_thread_finished(self):
        self._progress.hide_progress()

    @staticmethod
    def _filter_tracks(tracks, labels: list[str]):
        label_set = set(labels)
        ordered = []
        for t in tracks:
            if t.label in label_set:
                ordered.append(t)
        label_order = {l: i for i, l in enumerate(labels)}
        ordered.sort(key=lambda t: label_order.get(t.label, 999))
        return ordered

    def _on_select_tracks(self):
        if not self._all_track_labels:
            return
        dialog = _TrackSelectDialog(
            self._all_track_labels,
            self._selected_labels or [],
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = dialog.get_selected()
        if not selected:
            return
        self._selected_labels = selected
        self._rebuild_canvases()

    def _rebuild_canvases(self):
        for canvas, well_name in zip(
            self._cross_well._canvases, self._cross_well._well_names
        ):
            if well_name not in self._well_data_cache:
                continue
            data = self._well_data_cache[well_name]
            all_tracks = build_qpainter_tracks(data)
            filtered = self._filter_tracks(all_tracks, self._selected_labels)
            canvas.set_tracks(filtered)
            canvas.update()

    def _on_auto_link(self):
        self._cross_well.auto_link()

    def _on_toggle_pick(self):
        active = self._pick_btn.isChecked()
        self._canvas.pick_mode = active
        if active:
            self._pick_btn.setStyleSheet(
                self._btn_style() + "QPushButton { background: #fef3c7; border-color: #f59e0b; }"
            )
        else:
            self._pick_btn.setStyleSheet(self._btn_style())
        self._update_status()

    def _on_toggle_domain(self):
        checked = self._domain_btn.isChecked()
        domain = "TWT" if checked else "MD"
        self._domain_btn.setText(f"域: {domain}")
        self._canvas._overlay.set_depth_domain(domain)

    def _on_load_tops(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入层位数据", "",
            "CSV 文件 (*.csv);;所有文件 (*)",
        )
        if not path:
            return
        self._canvas.tops_model.load_csv(path)

    def _on_clear(self):
        self._cross_well.clear_all()
        self._canvas.picks_model.clear()
        self._canvas.tops_model.clear()
        self._well_data_cache.clear()
        self._all_track_labels = []
        self._selected_labels = None
        self._placeholder.setVisible(True)
        self._pick_btn.setChecked(False)
        self._pick_btn.setStyleSheet(self._btn_style())
        self._update_status()

    def _on_export(self):
        if self._cross_well.canvas_count == 0:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出连井对比图", "cross_well",
            "SVG 矢量 (*.svg);;PDF 矢量 (*.pdf);;PNG 位图 (*.png)",
        )
        if not path:
            return
        lower = path.lower()
        if lower.endswith(".pdf"):
            fmt = "pdf"
        elif lower.endswith(".png"):
            fmt = "png"
        else:
            if not lower.endswith(".svg"):
                path += ".svg"
            fmt = "svg"
        self._cross_well.export_composite(path, fmt=fmt)

    def contextMenuEvent(self, event):
        from PySide6.QtWidgets import QMenu

        pos = event.pos()
        target_canvas = None
        for canvas in self._cross_well._canvases:
            canvas_pos = canvas.mapTo(self, canvas.rect().topLeft())
            canvas_rect = canvas.rect().translated(canvas_pos)
            if canvas_rect.contains(pos):
                target_canvas = canvas
                break

        if target_canvas is None:
            return

        menu = QMenu(self)
        well_name = target_canvas.tracks[0].label if target_canvas.tracks else "unknown"
        menu.addAction(f"── {well_name} ──").setEnabled(False)

        for i, track in enumerate(target_canvas.tracks):
            action = menu.addAction(track.label)
            action.setCheckable(True)
            action.setChecked(getattr(track, "_visible", True))
            action.toggled.connect(
                lambda checked, idx=i: self._cross_well.set_track_visible(
                    target_canvas, idx, checked
                )
            )

        menu.exec(event.globalPos())
