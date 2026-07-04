# src/pages/cross_well/scene_page.py
"""Cross-well comparison page using QGraphicsScene/View canvas."""
from __future__ import annotations

from PySide6.QtCore import Qt, QObject, QThread, Signal, QPointF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDoubleSpinBox, QDialog, QListWidget, QListWidgetItem,
    QAbstractItemView, QFileDialog, QMessageBox, QFormLayout,
    QMenu,
)

from geoviz_well_log import build_qpainter_tracks
from geoviz_well_log.scene import CrossWellScene, CrossWellView
from src.data.well_registry import list_wells, get_well_data
from src.utils.floating_progress import FloatingProgressOverlay


# Reuse dialogs from page.py (import directly to avoid circular deps)
class _WellSelectDialog(QDialog):
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
                item.setForeground(QColor("#718096"))
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


class _DepthRangeDialog(QDialog):
    """Dialog for setting per-well or global depth range."""

    def __init__(self, well_name: str | None, current_top: float,
                 current_bottom: float, parent=None):
        super().__init__(parent)
        title = f"设置深度范围 — {well_name}" if well_name else "设置统一深度范围"
        self.setWindowTitle(title)
        self.setMinimumWidth(280)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._top_spin = QDoubleSpinBox()
        self._top_spin.setRange(0, 99999)
        self._top_spin.setDecimals(1)
        self._top_spin.setSuffix(" m")
        self._top_spin.setValue(current_top)
        form.addRow("顶部深度:", self._top_spin)

        self._bottom_spin = QDoubleSpinBox()
        self._bottom_spin.setRange(0, 99999)
        self._bottom_spin.setDecimals(1)
        self._bottom_spin.setSuffix(" m")
        self._bottom_spin.setValue(current_bottom)
        form.addRow("底部深度:", self._bottom_spin)

        layout.addLayout(form)

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

    def get_range(self) -> tuple[float, float]:
        return self._top_spin.value(), self._bottom_spin.value()


class _WellLoadWorker(QObject):
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
                    print(f"[CrossWell] Skipping {name}: not found in registry")
                    continue
                loader_fn, xls_path, config = entry
                data = loader_fn(xls_path, well_name=name)
                result.append((name, data))
                self.progress.emit(i, name)
            except Exception as e:
                print(f"[CrossWell] Failed to load {name}: {e}")
                continue
        self.finished.emit(result)


class CrossWellScenePage(QWidget):
    """Cross-well comparison page using QGraphicsScene/View canvas."""

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

        self._add_btn = QPushButton("添加井")
        self._add_btn.setFixedHeight(28)
        self._add_btn.setStyleSheet(self._btn_style())
        self._add_btn.clicked.connect(self._on_add_wells)
        tb.addWidget(self._add_btn)

        self._track_btn = QPushButton("选择井道")
        self._track_btn.setFixedHeight(28)
        self._track_btn.setStyleSheet(self._btn_style())
        self._track_btn.clicked.connect(self._on_select_tracks)
        tb.addWidget(self._track_btn)

        self._auto_link_btn = QPushButton("自动连井")
        self._auto_link_btn.setFixedHeight(28)
        self._auto_link_btn.setStyleSheet(self._btn_style())
        self._auto_link_btn.clicked.connect(self._on_auto_link)
        tb.addWidget(self._auto_link_btn)

        self._manual_link_btn = QPushButton("手动连井")
        self._manual_link_btn.setFixedHeight(28)
        self._manual_link_btn.setCheckable(True)
        self._manual_link_btn.setStyleSheet(self._btn_style())
        self._manual_link_btn.clicked.connect(self._on_toggle_manual_link)
        tb.addWidget(self._manual_link_btn)

        # Depth scale control
        tb.addSpacing(8)
        scale_label = QLabel("比例尺:")
        scale_label.setStyleSheet("font-size: 12px; color: #4a5568;")
        tb.addWidget(scale_label)

        self._scale_spin = QDoubleSpinBox()
        self._scale_spin.setRange(0.05, 20.0)
        self._scale_spin.setSingleStep(0.1)
        self._scale_spin.setDecimals(2)
        self._scale_spin.setValue(0.8)
        self._scale_spin.setSuffix(" px/m")
        self._scale_spin.setFixedHeight(28)
        self._scale_spin.setFixedWidth(100)
        self._scale_spin.setStyleSheet("""
            QDoubleSpinBox {
                border: 1px solid #cbd5e1; border-radius: 4px;
                padding: 0 6px; font-size: 12px; background: white;
            }
        """)
        self._scale_spin.valueChanged.connect(self._on_scale_changed)
        tb.addWidget(self._scale_spin)

        self._depth_range_btn = QPushButton("深度范围")
        self._depth_range_btn.setFixedHeight(28)
        self._depth_range_btn.setStyleSheet(self._btn_style())
        self._depth_range_btn.clicked.connect(self._on_global_depth_range)
        tb.addWidget(self._depth_range_btn)

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

        tb.addStretch()

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

        # --- Scene + View ---
        self._scene = CrossWellScene()
        self._view = CrossWellView(self._scene)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._on_view_context_menu)
        outer.addWidget(self._view, 1)

        # --- Placeholder ---
        self._placeholder = QLabel("点击\"添加井\"开始对比")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(
            "font-size: 18px; color: #718096; background: #f7fafc;"
            "border: 2px dashed #cbd5e1; border-radius: 12px; padding: 40px;"
        )
        self._placeholder.setMinimumSize(300, 200)
        self._placeholder.setVisible(True)
        self._placeholder.setParent(self)

        # Install scene event filter for manual linking
        self._scene.installEventFilter(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._placeholder.isVisible():
            self._placeholder.setGeometry(self._view.geometry())

    def eventFilter(self, obj, event):
        if obj is self._scene and event.type() == event.Type.GraphicsSceneMousePress:
            from PySide6.QtWidgets import QGraphicsSceneMouseEvent
            if isinstance(event, QGraphicsSceneMouseEvent):
                if self._scene.manual_link_mode():
                    from geoviz_well_log.scene.well_item import WellItem
                    item = self._scene.itemAt(event.scenePos(), self._view.transform())
                    target = item
                    while target and not isinstance(target, WellItem):
                        target = target.parentItem()
                    if target:
                        local_pos = target.mapFromScene(event.scenePos())
                        self._scene.handle_well_click(target.well_name, local_pos)
        return super().eventFilter(obj, event)

    @property
    def canvas_count(self) -> int:
        return self._scene.well_count()

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

            formation = None
            if data.intervals and data.intervals.formation:
                formation = data.intervals.formation

            self._scene.add_well(well_name, filtered, formation_data=formation)

        # Set unified depth range covering all loaded wells
        if results:
            tops = [data.top_depth for _, data in results]
            bottoms = [data.bottom_depth for _, data in results]
            self._scene.set_all_well_depth_range(min(tops), max(bottoms))

        self._view.fit_scene()

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
        self._rebuild_wells()

    def _rebuild_wells(self):
        for well_name in list(self._well_data_cache.keys()):
            data = self._well_data_cache[well_name]
            all_tracks = build_qpainter_tracks(data)
            filtered = self._filter_tracks(all_tracks, self._selected_labels)
            self._scene.update_well_tracks(well_name, filtered)

    def _on_auto_link(self):
        self._scene.auto_link()

    def _on_toggle_manual_link(self):
        active = not self._scene.manual_link_mode()
        self._scene.set_manual_link_mode(active)
        if active:
            self._manual_link_btn.setStyleSheet(
                self._btn_style() + "QPushButton { background: #fef3c7; border-color: #f59e0b; }"
            )
        else:
            self._manual_link_btn.setStyleSheet(self._btn_style())

    # --- Depth scale ---

    def _on_scale_changed(self, value: float):
        self._scene.set_depth_scale(value)

    # --- Depth range ---

    def _on_global_depth_range(self):
        wells = self._scene.wells()
        if not wells:
            return
        tops = [w.depth_top for w in wells]
        bottoms = [w.depth_bottom for w in wells]
        dialog = _DepthRangeDialog(None, min(tops), max(bottoms), parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        top, bottom = dialog.get_range()
        if top >= bottom:
            return
        self._scene.set_all_well_depth_range(top, bottom)

    def _on_per_well_depth_range(self, well_name: str):
        item = self._scene.well_by_name(well_name)
        if item is None:
            return
        dialog = _DepthRangeDialog(
            well_name, item.depth_top, item.depth_bottom, parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        top, bottom = dialog.get_range()
        if top >= bottom:
            return
        self._scene.set_well_depth_range(well_name, top, bottom)

    # --- Context menu ---

    def _on_view_context_menu(self, pos):
        scene_pos = self._view.mapToScene(pos)
        from geoviz_well_log.scene.well_item import WellItem
        from geoviz_well_log.scene.depth_ruler_item import DepthRulerItem
        from geoviz_well_log.scene.annotation_item import AnnotationItem
        item = self._scene.itemAt(scene_pos, self._view.transform())
        target = item
        while target and not isinstance(target, WellItem):
            target = target.parentItem()

        if target is None:
            # Click on empty scene area — offer annotation placement
            if isinstance(item, (DepthRulerItem, AnnotationItem, type(None))):
                if isinstance(item, AnnotationItem):
                    return  # let AnnotationItem handle its own menu
                menu = QMenu(self)
                ann_action = menu.addAction("添加标注...")
                action = menu.exec(self._view.mapToGlobal(pos))
                if action == ann_action:
                    depth = (scene_pos.y() - 28) / self._scene.depth_scale() + self._scene._ruler._depth_top
                    from PySide6.QtWidgets import QInputDialog
                    text, ok = QInputDialog.getText(self, "标注", "输入标注文字:")
                    if ok and text.strip():
                        self._scene.add_annotation(text.strip(), scene_pos.x(), depth)
            return

        menu = QMenu(self)
        well_name = target.well_name
        range_action = menu.addAction(f"设置 {well_name} 深度范围")
        menu.addSeparator()
        reset_action = menu.addAction("重置为数据范围")

        action = menu.exec(self._view.mapToGlobal(pos))
        if action == range_action:
            self._on_per_well_depth_range(well_name)
        elif action == reset_action:
            self._reset_well_to_data_range(well_name)

    def _reset_well_to_data_range(self, well_name: str):
        data = self._well_data_cache.get(well_name)
        if data is None:
            return
        self._scene.set_well_depth_range(well_name, data.top_depth, data.bottom_depth)

    # --- Clear / Export ---

    def _on_clear(self):
        self._scene.clear_all()
        self._well_data_cache.clear()
        self._all_track_labels = []
        self._selected_labels = None
        self._placeholder.setVisible(True)
        self._manual_link_btn.setChecked(False)
        self._manual_link_btn.setStyleSheet(self._btn_style())

    def _on_export(self):
        if self._scene.well_count() == 0:
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
        self._scene.export_to_file(path, fmt=fmt)
