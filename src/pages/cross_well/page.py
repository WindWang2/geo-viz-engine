# src/pages/cross_well/page.py
"""Cross-well correlation page using CrossWellCanvas with picking workflow."""
from __future__ import annotations

from PySide6.QtCore import Qt, QObject, QThread, QEventLoop, Signal, QEvent
from PySide6.QtGui import QWheelEvent, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialog, QListWidget, QListWidgetItem, QAbstractItemView,
    QFileDialog, QMessageBox, QScrollArea,
)

from geoviz_well_log import build_qpainter_tracks
from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_cross_well import CrossWellCanvas, export_cross_well_report
from src.data.well_registry import list_wells, get_well_data
from src.utils.floating_progress import FloatingProgressOverlay
from src.pages.cross_well.sidebar import CrossWellSidebar



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
        from concurrent.futures import ThreadPoolExecutor
        
        def load_one(name):
            try:
                entry = get_well_data(name)
                if entry is None:
                    return name, None
                loader_fn, xls_path, config = entry
                data = loader_fn(xls_path, well_name=name)
                return name, data
            except Exception as e:
                print(f"[CrossWell] Failed to load {name}: {e}")
                return name, None

        # Load well data in parallel using a ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(4, len(self._well_names))) as executor:
            # Map futures back to names to preserve ordering
            future_to_name = {executor.submit(load_one, name): name for name in self._well_names}
            data_map = {}
            completed = 0
            
            import concurrent.futures
            for future in concurrent.futures.as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    _, data = future.result()
                    if data is not None:
                        data_map[name] = data
                except Exception as e:
                    print(f"[CrossWell] Failed to retrieve result for {name}: {e}")
                finally:
                    completed += 1
                    self.progress.emit(completed, name)

        # Preserve the original selection order of the wells
        result = []
        for name in self._well_names:
            if name in data_map:
                result.append((name, data_map[name]))
                
        self.finished.emit(result)


class _DTWPropagateWorker(QObject):
    """Background worker that runs DTW propagation off the UI thread.

    The page collects the per-well curve arrays on the UI thread and hands
    them here, so the worker never touches widgets or the picks model.
    """

    progress = Signal(int, str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        work_items: list[tuple[str, float, str]],
        wells: list[str],
        curve_data: dict[str, tuple],
        parent=None,
    ):
        super().__init__(parent)
        self._work_items = work_items
        self._wells = list(wells)
        self._curve_data = curve_data

    def run(self):
        try:
            from geoviz_cross_well.dtw_engine import DTWEngine
            engine = DTWEngine()
            results: list[tuple[str, float, str]] = []
            completed = 0
            total = len(self._work_items) * max(0, len(self._wells) - 1)
            for ref_well, ref_depth, formation in self._work_items:
                ref_data = self._curve_data.get(ref_well)
                for target_well in self._wells:
                    if target_well == ref_well:
                        continue
                    completed += 1
                    if ref_data is not None:
                        tgt_data = self._curve_data.get(target_well)
                        if tgt_data is not None:
                            ref_depths, ref_values = ref_data
                            tgt_depths, tgt_values = tgt_data
                            result = engine.correlate(
                                ref_values, ref_depths,
                                tgt_values, tgt_depths,
                                ref_depth=ref_depth,
                            )
                            # Infeasible alignments (band/NaN) must not
                            # fabricate ghost picks (#539).
                            if result.feasible:
                                results.append((target_well, result.suggested_depth, formation))
                    self.progress.emit(completed, f"DTW 传播中... ({completed}/{total})")
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class CrossWellPage(QWidget):
    """Cross-well correlation page with grouped toolbar and picking workflow."""

    def _get_ui_icon(self, name: str) -> QIcon:
        """Resolve icon from project resources."""
        from src.utils.paths import get_resources_dir
        path = get_resources_dir() / "icons" / "ui" / name
        if path.exists():
            return QIcon(str(path))
        return QIcon()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._dtw_thread = None
        self._dtw_worker = None
        self._dtw_running = False
        self._selected_labels: list[str] | None = None
        self._well_data_cache: dict[str, object] = {}
        self._all_track_labels: list[str] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        # --- Toolbar ---
        self._toolbar = QWidget()
        self._toolbar.setStyleSheet(
            "background: #faf9f5; border-bottom: 1px solid #e5eaf1;"
        )
        tb = QHBoxLayout(self._toolbar)
        tb.setContentsMargins(10, 8, 10, 8)
        tb.setSpacing(5)

        # Well properties dynamic label (Shortened to fit layout)
        self._well_props_lbl = QLabel("0 口井")
        self._well_props_lbl.setToolTip("PCA 自动排井")
        self._well_props_lbl.setStyleSheet("font-size: 12px; color: #586878; font-weight: 600; min-width: 45px;")
        tb.addWidget(self._well_props_lbl)
        tb.addSpacing(2)

        # Segmented buttons (Pick, Link, Browse)
        self._pick_seg = QPushButton("拾取")
        self._pick_seg.setCheckable(True)
        self._link_seg = QPushButton("连接")
        self._link_seg.setCheckable(True)
        self._browse_seg = QPushButton("浏览")
        self._browse_seg.setCheckable(True)
        self._browse_seg.setChecked(True)

        seg_style = (
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 4px; padding: 4px 8px; font-size: 11.5px; color: #586878; }"
            "QPushButton:hover { background: #f1f4f9; }"
            "QPushButton:checked { background: #e9effa; border-color: #1f66d4; color: #1f66d4; font-weight: bold; }"
        )
        for btn in [self._pick_seg, self._link_seg, self._browse_seg]:
            btn.setStyleSheet(seg_style)

        from PySide6.QtWidgets import QButtonGroup
        self._mode_btn_group = QButtonGroup(self)
        self._mode_btn_group.addButton(self._pick_seg)
        self._mode_btn_group.addButton(self._link_seg)
        self._mode_btn_group.addButton(self._browse_seg)
        self._mode_btn_group.setExclusive(True)

        tb.addWidget(self._pick_seg)
        tb.addWidget(self._link_seg)
        tb.addWidget(self._browse_seg)

        # Aliases for compatibility
        self._pick_btn = self._pick_seg
        self._manual_link_btn = self._link_seg

        self._pick_seg.clicked.connect(self._on_toggle_pick)
        self._link_seg.clicked.connect(self._on_toggle_manual_link)
        self._browse_seg.clicked.connect(self._on_browse_mode)

        self._sep(tb)

        # Data group
        self._add_btn = self._make_btn(" 添加", "plus.svg")
        self._add_btn.setToolTip("打开井选择对话框，加载多口井并显示在画布上")
        self._add_btn.clicked.connect(self._on_add_wells)
        self._add_btn.setStyleSheet(
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 4px 8px; color: #1a2433; }"
            "QPushButton:hover { background: #f1f4f9; }"
        )
        tb.addWidget(self._add_btn)

        self._clear_btn = QPushButton(" 清除")
        self._clear_btn.setIcon(self._get_ui_icon("undo.svg"))
        self._clear_btn.setFixedHeight(28)
        self._clear_btn.setToolTip("清除所有井和拾取数据，回到初始状态")
        self._clear_btn.clicked.connect(self._on_clear)
        self._clear_btn.setStyleSheet(
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 4px 8px; color: #1a2433; }"
            "QPushButton:hover { background: #f1f4f9; }"
        )
        tb.addWidget(self._clear_btn)

        self._sep(tb)

        # View group
        self._track_btn = self._make_btn(" 井道", "table.svg")
        self._track_btn.setToolTip("勾选要显示的井道（深度/岩性固定，最多再选3个）")
        self._track_btn.clicked.connect(self._on_select_tracks)
        self._track_btn.setStyleSheet(
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 4px 8px; color: #1a2433; }"
            "QPushButton:hover { background: #f1f4f9; }"
        )
        tb.addWidget(self._track_btn)

        self._domain_btn = self._make_btn(" 域: MD", "globe.svg")
        self._domain_btn.setCheckable(True)
        self._domain_btn.setToolTip("切换深度域：MD（测量深度）↔ TWT（双程旅行时，需先导入井震标定）")
        self._domain_btn.clicked.connect(self._on_toggle_domain)
        self._domain_btn.setStyleSheet(
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 4px 8px; color: #1a2433; }"
            "QPushButton:hover { background: #f1f4f9; }"
            "QPushButton:checked { background: #e9effa; border-color: #1f66d4; color: #1f66d4; font-weight: bold; }"
        )
        tb.addWidget(self._domain_btn)

        self._sep(tb)

        # Correlate group
        self._auto_btn = self._make_btn(" 自动", "share.svg")
        self._auto_btn.setToolTip("按层位名匹配相邻井（如「万山组」），无名时不会连接")
        self._auto_btn.clicked.connect(self._on_auto_link)
        self._auto_btn.setStyleSheet(
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 4px 8px; color: #1a2433; }"
            "QPushButton:hover { background: #f1f4f9; }"
        )
        tb.addWidget(self._auto_btn)

        self._dtw_btn = self._make_btn("DTW", "search.svg")
        self._dtw_btn.setToolTip(
            "用 DTW 把当前已有的层位点从一口井传播 to 所有其他井（产生灰色 ghost 点，左键确认 / 右键拒绝）"
        )
        self._dtw_btn.clicked.connect(self._on_dtw_propagate)
        self._dtw_btn.setStyleSheet(
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 4px 8px; color: #1a2433; }"
            "QPushButton:hover { background: #f1f4f9; }"
        )
        tb.addWidget(self._dtw_btn)
        
        # DTW Auto Contrast alias for TDD
        self._dtw_auto_btn = self._dtw_btn

        self._tops_btn = self._make_btn(" 导入", "upload.svg")
        self._tops_btn.setToolTip("从 CSV 文件导入层位顶界数据（well, formation, depth_m）")
        self._tops_btn.clicked.connect(self._on_load_tops)
        self._tops_btn.setStyleSheet(
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 4px 8px; color: #1a2433; }"
            "QPushButton:hover { background: #f1f4f9; }"
        )
        tb.addWidget(self._tops_btn)

        tb.addStretch()

        # Export group: Ultra-wide SVG
        self._export_btn = self._make_btn(" 导出", "export.svg")
        self._export_btn.clicked.connect(self._on_export)
        self._export_btn.setStyleSheet(
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 4px 8px; color: #1a2433; }"
            "QPushButton:hover { background: #f1f4f9; }"
        )
        tb.addWidget(self._export_btn)
        
        self._svg_wide_btn = self._export_btn

        outer.addWidget(self._toolbar)

        # --- Progress ---
        self._progress = FloatingProgressOverlay(self)
        outer.addWidget(self._progress)

        # --- Status bar ---
        self._status = QLabel()
        self._status.setStyleSheet(
            "background: #faf9f5; border-top: 1px solid #e2e8f0; "
            "padding: 6px 12px; font-size: 12px; color: #586878;"
        )
        self._update_status()
        outer.addWidget(self._status)

        # --- CrossWellCanvas & Sidebar ---
        self._canvas = CrossWellCanvas()
        self._cross_well = self._canvas.widget  # underlying CrossWellWidget
        self._canvas.picks_model.picks_changed.connect(self._update_status)
        
        self._sidebar = CrossWellSidebar(self)
        self._sidebar_collapsed = False
        
        self._toggle_sidebar_btn = QPushButton("▶")
        self._toggle_sidebar_btn.setFixedWidth(12)
        self._toggle_sidebar_btn.setStyleSheet(
            "QPushButton { background: #faf9f5; border-left: 1px solid #e5eaf1; border-right: 1px solid #e5eaf1; color: #586878; font-size: 10px; font-weight: bold; border-radius: 0; padding: 0; }"
            "QPushButton:hover { background: #f1f4f9; color: #1f66d4; }"
        )
        self._toggle_sidebar_btn.clicked.connect(self._toggle_sidebar)

        self._mid_widget = QWidget()
        self._mid_layout = QHBoxLayout(self._mid_widget)
        self._mid_layout.setContentsMargins(0, 0, 0, 0)
        self._mid_layout.setSpacing(0)
        
        self._mid_layout.addWidget(self._canvas, 1)
        self._mid_layout.addWidget(self._toggle_sidebar_btn)
        self._mid_layout.addWidget(self._sidebar)
        
        outer.addWidget(self._mid_widget, 1)
        self._scroll = None

        # Connect sidebar signals
        self._sidebar.horizon_changed.connect(self._on_sidebar_horizon_changed)
        self._sidebar.curve_changed.connect(self._on_sidebar_curve_changed)
        self._sidebar.snapping_changed.connect(self._on_sidebar_snapping_changed)
        self._sidebar.curve_groups_changed.connect(self._on_sidebar_curve_groups_changed)
        self._sidebar.dtw_triggered.connect(self._on_dtw_propagate)

        # --- Empty state ---
        self._placeholder = QWidget()
        ph_layout = QVBoxLayout(self._placeholder)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_title = QLabel(" 连井对比")
        ph_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1f66d4;")
        ph_sub = QLabel("点击「添加井」选择要对比的井号")
        ph_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_sub.setStyleSheet("font-size: 14px; color: #586878; margin-top: 8px;")
        ph_cta = QPushButton(" 添加井")
        ph_cta.setIcon(self._get_ui_icon("plus.svg"))
        ph_cta.setFixedSize(140, 40)
        ph_cta.clicked.connect(self._on_add_wells)
        ph_layout.addWidget(ph_title)
        ph_layout.addWidget(ph_sub)
        ph_layout.addSpacing(20)
        cta_box = QHBoxLayout()
        cta_box.addStretch()
        cta_box.addWidget(ph_cta)
        cta_box.addStretch()
        ph_layout.addLayout(cta_box)
        self._placeholder.setStyleSheet(
            "background: #faf9f5; border: 2px dashed #586878; border-radius: 12px;"
        )
        self._cross_well._container_layout.insertWidget(0, self._placeholder)

    def showEvent(self, event):
        super().showEvent(event)
        if self._scroll is None:
            self._mid_layout.removeWidget(self._canvas)
            self._scroll = QScrollArea()
            self._scroll.setWidgetResizable(True)
            self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._scroll.setStyleSheet("QScrollArea { background: #ffffff; border: none; }")
            self._mid_layout.insertWidget(0, self._scroll, 1)
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
                self._canvas.pick_mode = False
                self._pick_btn.setChecked(False)
                return
        super().keyPressEvent(event)

    # --- Helpers ---

    def _make_btn(self, text: str, icon_name: str | None = None) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(28)
        if icon_name:
            btn.setIcon(self._get_ui_icon(icon_name))
        return btn

    @staticmethod
    def _sep(layout: QHBoxLayout):
        sep = QLabel("|")
        sep.setStyleSheet("color: #cbd5e1; font-size: 16px;")
        layout.addWidget(sep)

    def _update_status(self):
        parts = []
        n = self._cross_well.canvas_count if hasattr(self, '_cross_well') else 0
        self._well_props_lbl.setText(f"{n} 口井" if n else "0 口井")
        parts.append(f"{n} 口井" if n else "无井数据")
        if hasattr(self, '_canvas'):
            picks_n = len(self._canvas.picks_model.all_picks())
            if picks_n:
                parts.append(f"{picks_n} 个层位点")
            if self._canvas.pick_mode:
                parts.append(
                    "拾取模式: 左键添加 · Shift+左键连接 · 右键删除 · Ctrl+Z 撤销 · Esc 退出"
                )
            elif hasattr(self, '_cross_well') and self._cross_well._manual_link_active:
                parts.append(
                    "连井模式: 请依次左键点击相邻两口井中的砂体或小层进行对比连线"
                )
        self._status.setText("  |  ".join(parts) if parts else "")

    # --- Actions ---

    def load_planned_section(self, well_names: list[str]):
        """Plan a contiguous well section path from geographic coordinates and load them."""
        from src.data.cache import DataCache
        from src.utils.paths import get_data_dir
        from geoviz_cross_well.auto_section_planner import plan_section
        
        # Load coordinate dictionary
        coords_file = get_data_dir() / "well_coordinates.json"
        cache = DataCache()
        all_coords = cache.get_well_coordinates(coords_file)
        
        # Filter coordinates for selected wells
        selected_coords = [c for c in all_coords if c.name in well_names]
        
        if len(selected_coords) > 1:
            # Sort wells along the first principal component (PCA) for logical geographic flow
            sorted_coords = plan_section(selected_coords, method="pca")
            sorted_names = [c.name for c in sorted_coords]
        else:
            sorted_names = list(well_names)
            
        # Clear existing section and load new sorted wells
        self._on_clear()
        self._load_wells(sorted_names)

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
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_load_finished)
        self._worker.error.connect(self._on_load_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def _on_worker_progress(self, completed: int, well_name: str):
        """Update progress overlay during well loading."""
        self._progress.update_progress(completed, f"正在加载 {well_name} ({completed})")

    def _on_load_finished(self, results: list):
        self._add_btn.setEnabled(True)
        merge_list = []
        for label, names in self._canvas.curve_groups.items():
            merge_list.append((names, label))

        for well_name, data in results:
            self._well_data_cache[well_name] = data
            all_tracks = build_qpainter_tracks(data, merge_groups=merge_list)
            all_labels = [t.label for t in all_tracks]

            if self._selected_labels is None:
                self._all_track_labels = all_labels
                self._selected_labels = self._default_labels(all_labels)

            # Smart filter
            filtered = []
            for t in all_tracks:
                if t.label in self._selected_labels:
                    filtered.append(t)
                else:
                    parts = t.label.split("/")
                    if any(p in self._selected_labels for p in parts):
                        filtered.append(t)

            canvas = WellLogCanvas()
            canvas.set_tracks(filtered)
            self._cross_well.add_canvas(canvas, well_name)

            if data.intervals and data.intervals.formation:
                self._cross_well.set_formation_data(well_name, data.intervals.formation)

        # Update available curves in the sidebar
        curves = set()
        for d in self._well_data_cache.values():
            for c in d.curves:
                curves.add(c.name)
        self._sidebar.set_available_curves(list(curves))

        # Update horizons in the sidebar
        horizons = set()
        for p in self._canvas.picks_model.all_picks():
            horizons.add(p.formation_name)
        for d in self._well_data_cache.values():
            if d.intervals and d.intervals.formation:
                for item in d.intervals.formation:
                    horizons.add(item.name)
        if not horizons:
            horizons.add("Horizon-1")
        self._sidebar.set_horizons(list(horizons))

        # Sync active state from sidebar
        self._canvas.active_formation = self._sidebar._hz_combo.currentText().strip()
        self._canvas.active_curve = self._sidebar._curve_combo.currentText().strip()
        snap_type = "none"
        if self._sidebar._snap_max_rdo.isChecked():
            snap_type = "max"
        elif self._sidebar._snap_min_rdo.isChecked():
            snap_type = "min"
        self._canvas.snap_type = snap_type
        self._canvas.snap_window_m = self._sidebar._window_spin.value()

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
        merge_list = []
        for label, names in self._canvas.curve_groups.items():
            merge_list.append((names, label))

        for canvas, well_name in zip(
            self._cross_well._canvases, self._cross_well._well_names
        ):
            if well_name not in self._well_data_cache:
                continue
            data = self._well_data_cache[well_name]
            all_tracks = build_qpainter_tracks(data, merge_groups=merge_list)
            
            # Smart filter
            filtered = []
            for t in all_tracks:
                if self._selected_labels is None:
                    filtered.append(t)
                elif t.label in self._selected_labels:
                    filtered.append(t)
                else:
                    parts = t.label.split("/")
                    if any(p in self._selected_labels for p in parts):
                        filtered.append(t)

            canvas.set_tracks(filtered)
            canvas.update()


    def _on_auto_link(self):
        self._cross_well.auto_link()

    def _on_dtw_propagate(self):
        """Propagate every existing manual pick to all other wells via DTW.

        The DTW computation runs in a background ``_DTWPropagateWorker`` so the
        UI thread is never blocked and no ``processEvents()`` re-entrancy is
        needed; the resulting ghost picks are backfilled on the UI thread once
        the worker finishes.
        """
        if self._cross_well.canvas_count < 2:
            QMessageBox.information(
                self, "DTW 传播",
                "至少需要 2 口井才能进行 DTW 传播。",
            )
            return
        manual_picks = [
            p for p in self._canvas.picks_model.all_picks() if p.source == "manual"
        ]
        if not manual_picks:
            QMessageBox.information(
                self, "DTW 传播",
                "请先在某口井上手动拾取一个层位点，然后再用 DTW 传播到其他井。",
            )
            return
        if self._dtw_running:
            return  # a previous run is still in progress

        # Collect per-well curve arrays on the UI thread; the worker only ever
        # sees plain numpy arrays, never widgets or the picks model.
        wells = self._cross_well._well_names
        canvases = self._cross_well._canvases
        curve_data: dict[str, tuple] = {}
        for canvas, well_name in zip(canvases, wells):
            data = self._canvas._extract_curve(canvas)
            if data is not None:
                curve_data[well_name] = data

        # One anchor well per pick (the first connected well with a depth).
        work_items: list[tuple[str, float, str]] = []
        for pick in manual_picks:
            for well in pick.connected_wells():
                depth = pick.depth_for_well(well)
                if depth is None:
                    continue
                work_items.append((well, depth, pick.formation_name))
                break  # one anchor per pick is enough

        # Estimate total work = picks × other-well count for a single linear bar.
        total_steps = len(work_items) * max(0, len(wells) - 1)
        self._set_dtw_running(True)
        self._progress.show_progress("DTW 传播中...", maximum=max(1, total_steps))

        self._dtw_thread = QThread()
        self._dtw_worker = _DTWPropagateWorker(work_items, wells, curve_data)
        self._dtw_worker.moveToThread(self._dtw_thread)

        self._dtw_thread.started.connect(self._dtw_worker.run)
        self._dtw_worker.progress.connect(self._on_dtw_progress)
        self._dtw_worker.finished.connect(self._on_dtw_finished)
        self._dtw_worker.error.connect(self._on_dtw_error)
        self._dtw_worker.finished.connect(self._dtw_thread.quit)
        self._dtw_worker.error.connect(self._dtw_thread.quit)
        self._dtw_worker.finished.connect(self._dtw_worker.deleteLater)
        self._dtw_worker.error.connect(self._dtw_worker.deleteLater)
        self._dtw_thread.finished.connect(self._dtw_thread.deleteLater)
        self._dtw_thread.finished.connect(self._on_dtw_thread_finished)

        # Wait for the worker inside a nested event loop so the DTW compute
        # stays off the UI thread while progress/backfill run on it; this
        # replaces the old per-step QApplication.processEvents() re-entrancy.
        loop = QEventLoop(self)
        self._dtw_worker.finished.connect(loop.quit)
        self._dtw_worker.error.connect(loop.quit)
        self._dtw_thread.start()
        try:
            loop.exec()
        finally:
            loop.deleteLater()

    def _on_dtw_progress(self, completed: int, msg: str):
        """Update the progress overlay while the DTW worker runs."""
        self._progress.update_progress(completed, msg)

    def _on_dtw_finished(self, results: list):
        """Backfill the computed DTW ghost picks and restore the UI."""
        created_total = 0
        for well, depth, formation in results:
            self._canvas.picks_model.add_pick(formation, well, depth, source="dtw")
            created_total += 1
        self._set_dtw_running(False)
        self._progress.hide_progress()
        QMessageBox.information(
            self, "DTW 传播完成",
            f"已生成 {created_total} 个 DTW 候选点（灰色 ghost）。"
            f"\n左键点击确认为正式拾取，右键点击拒绝。",
        )
        self._update_status()

    def _on_dtw_error(self, msg: str):
        """Report a worker failure and restore the UI."""
        self._set_dtw_running(False)
        self._progress.hide_progress()
        QMessageBox.warning(self, "DTW 传播失败", msg)

    def _on_dtw_thread_finished(self):
        self._progress.hide_progress()

    def _set_dtw_running(self, running: bool):
        """Disable actions that must not run concurrently with DTW."""
        self._dtw_running = bool(running)
        for btn in (self._dtw_btn, self._add_btn, self._clear_btn):
            btn.setEnabled(not running)

    def _on_browse_mode(self):
        # Uncheck pick mode if it was active
        if self._pick_btn.isChecked():
            self._pick_btn.setChecked(False)
            self._canvas.pick_mode = False
        # Uncheck manual link if it was active
        if self._manual_link_btn.isChecked():
            self._manual_link_btn.setChecked(False)
            self._cross_well.toggle_manual_link()
        self._update_status()

    def _on_toggle_pick(self):
        active = self._pick_btn.isChecked()
        self._canvas.pick_mode = active
        if active:
            if self._manual_link_btn.isChecked():
                self._manual_link_btn.setChecked(False)
                self._on_toggle_manual_link()
            self._pick_seg.setChecked(True)
        self._update_status()

    def _on_toggle_manual_link(self):
        active = self._manual_link_btn.isChecked()
        self._cross_well.toggle_manual_link()
        if active:
            if self._pick_btn.isChecked():
                self._pick_btn.setChecked(False)
                self._on_toggle_pick()
            self._link_seg.setChecked(True)
        self._update_status()

    def _on_toggle_domain(self):
        checked = self._domain_btn.isChecked()
        domain = "TWT" if checked else "MD"
        self._domain_btn.setText(f" 域: {domain}")
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
        self._manual_link_btn.setChecked(False)
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

        # Ask the user for the report title
        from PySide6.QtWidgets import QInputDialog
        title, ok = QInputDialog.getText(
            self, "输入报告标题", "请输入导出的报告图件标题：",
            text="连井对比剖面图"
        )
        if not ok or not title.strip():
            title = "连井对比剖面图"

        try:
            export_cross_well_report(
                self._canvas,
                path,
                format=fmt,
                title=title,
                page_size="A4",
                orientation="landscape",
                include_legend=True,
                include_grid_frame=True,
            )
            QMessageBox.information(self, "导出成功", f"连井对比报告已成功导出至：\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出过程中发生错误：\n{str(e)}")

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

    def _toggle_sidebar(self):
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        self._sidebar_collapsed = not self._sidebar_collapsed
        target_w = 0 if self._sidebar_collapsed else 280
        
        self._sidebar_anim = QPropertyAnimation(self._sidebar, b"maximumWidth")
        self._sidebar_anim.setDuration(200)
        self._sidebar_anim.setStartValue(self._sidebar.width())
        self._sidebar_anim.setEndValue(target_w)
        self._sidebar_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._sidebar_anim.start()
        
        self._toggle_sidebar_btn.setText("◀" if self._sidebar_collapsed else "▶")

    def _on_sidebar_horizon_changed(self, name: str):
        self._canvas.active_formation = name

    def cleanup(self):
        """Stop well-loading / DTW threads when leaving this page."""
        for attr in ("_thread", "_dtw_thread"):
            thread = getattr(self, attr, None)
            if thread is not None:
                try:
                    if thread.isRunning():
                        thread.quit()
                        thread.wait(1500)
                except RuntimeError:
                    pass
                setattr(self, attr, None)
        self._worker = None
        self._dtw_worker = None

    def export_project_picks(self):
        from src.data.project import ProjectPick

        picks = []
        if hasattr(self, "_canvas"):
            for hp in self._canvas.picks_model.all_picks():
                for well, depth in hp.well_depths:
                    if depth is not None:
                        picks.append(
                            ProjectPick(
                                well_name=well,
                                depth=depth,
                                formation=hp.formation_name,
                                pick_group=hp.pick_id,
                            )
                        )
        return picks

    def export_project_correlations(self):
        return []

    def import_project_picks(self, picks, correlations=None):
        from geoviz_cross_well.picks_model import HorizonPick

        if not hasattr(self, "_canvas") or not picks:
            return
        grouped: dict[str, HorizonPick] = {}
        for p in picks:
            gid = p.pick_group or f"{p.formation}:{p.well_name}"
            if gid not in grouped:
                grouped[gid] = HorizonPick(
                    pick_id=gid if p.pick_group else HorizonPick.new_id(),
                    formation_name=p.formation,
                    well_depths=[],
                    source="manual",
                )
            grouped[gid].set_depth(p.well_name, p.depth)
        self._canvas.picks_model.clear()
        for pick in grouped.values():
            self._canvas.picks_model._picks[pick.pick_id] = pick
        self._canvas.picks_model.picks_changed.emit()
        self._update_status()

    def _on_sidebar_curve_changed(self, curve_name: str):
        self._canvas.active_curve = curve_name

    def _on_sidebar_snapping_changed(self, snap_type: str, snap_window: float):
        self._canvas.snap_type = snap_type
        self._canvas.snap_window_m = snap_window

    def _on_sidebar_curve_groups_changed(self, new_groups: dict):
        self._canvas.curve_groups = new_groups
        self._rebuild_canvases()

