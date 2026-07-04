# src/pages/cross_well/sidebar.py
"""Collapsible sidebar control panel for well correlation picking and overlays."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QRadioButton,
    QDoubleSpinBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QButtonGroup, QScrollArea, QFrame, QMessageBox, QGroupBox
)

class CrossWellSidebar(QWidget):
    """Sidebar panel for managing active horizon, snapping parameters, and curve overlays."""

    horizon_changed = Signal(str)
    curve_changed = Signal(str)
    snapping_changed = Signal(str, float)  # snap_type, snap_window_m
    curve_groups_changed = Signal(dict)    # curve_groups dict
    dtw_triggered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280)
        self.setStyleSheet(
            "CrossWellSidebar { background: #ffffff; border-left: 1px solid #e5eaf1; }"
        )

        self._available_curves: list[str] = []
        self._curve_groups: dict[str, list[str]] = {
            "AC/GR": ["AC", "GR"],
            "RT/RXO": ["RT", "RXO"]
        }

        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Title
        title_lbl = QLabel("层位对比控制面板")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a2433;")
        layout.addWidget(title_lbl)

        # Scroll Area for contents
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(16)

        # --- Group 1: Horizon Manager ---
        hz_group = QGroupBox("📂 层位管理")
        hz_group.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 1px solid #e5eaf1; border-radius: 8px; margin-top: 10px; padding: 12px 6px 6px 6px; background: #ffffff; }"
            "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 8px; padding: 0 3px; color: #1f66d4; }"
        )
        hz_layout = QVBoxLayout(hz_group)
        hz_layout.setSpacing(8)

        hz_combo_lbl = QLabel("当前激活层位：")
        hz_combo_lbl.setStyleSheet("font-size: 11px; color: #586878;")
        hz_layout.addWidget(hz_combo_lbl)

        hz_input_layout = QHBoxLayout()
        self._hz_combo = QComboBox()
        self._hz_combo.setEditable(True)
        self._hz_combo.setMinimumHeight(28)
        self._hz_combo.setStyleSheet(
            "QComboBox { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 2px 6px; font-size: 12px; }"
            "QComboBox::drop-down { border: none; }"
        )
        hz_input_layout.addWidget(self._hz_combo, 1)

        self._hz_add_btn = QPushButton("+")
        self._hz_add_btn.setFixedSize(28, 28)
        self._hz_add_btn.setStyleSheet(
            "QPushButton { background: #1f66d4; color: white; border: none; border-radius: 6px; font-weight: bold; font-size: 14px; }"
            "QPushButton:hover { background: #154ec2; }"
        )
        self._hz_add_btn.clicked.connect(self._on_add_horizon)
        hz_input_layout.addWidget(self._hz_add_btn)
        
        hz_layout.addLayout(hz_input_layout)
        self._hz_combo.currentTextChanged.connect(self._on_horizon_combo_changed)
        c_layout.addWidget(hz_group)

        # --- Group 2: Curve Snapping ---
        snap_group = QGroupBox("🎯 特征自动吸附")
        snap_group.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 1px solid #e5eaf1; border-radius: 8px; margin-top: 10px; padding: 12px 6px 6px 6px; background: #ffffff; }"
            "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 8px; padding: 0 3px; color: #1f66d4; }"
        )
        snap_layout = QVBoxLayout(snap_group)
        snap_layout.setSpacing(8)

        curve_lbl = QLabel("敏感测井曲线：")
        curve_lbl.setStyleSheet("font-size: 11px; color: #586878;")
        snap_layout.addWidget(curve_lbl)

        self._curve_combo = QComboBox()
        self._curve_combo.setMinimumHeight(28)
        self._curve_combo.setStyleSheet(
            "QComboBox { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 2px 6px; font-size: 12px; }"
        )
        self._curve_combo.currentTextChanged.connect(self._on_curve_combo_changed)
        snap_layout.addWidget(self._curve_combo)

        type_lbl = QLabel("吸附对齐特征值：")
        type_lbl.setStyleSheet("font-size: 11px; color: #586878; margin-top: 4px;")
        snap_layout.addWidget(type_lbl)

        # Radio button group
        self._snap_none_rdo = QRadioButton("无 (纯手动)")
        self._snap_max_rdo = QRadioButton("极大值 (Peak)")
        self._snap_min_rdo = QRadioButton("极小值 (Trough)")
        
        self._snap_none_rdo.setChecked(True)
        rdo_style = "QRadioButton { font-size: 11.5px; color: #1a2433; }"
        for rdo in [self._snap_none_rdo, self._snap_max_rdo, self._snap_min_rdo]:
            rdo.setStyleSheet(rdo_style)
            snap_layout.addWidget(rdo)

        self._snap_group = QButtonGroup(self)
        self._snap_group.addButton(self._snap_none_rdo)
        self._snap_group.addButton(self._snap_max_rdo)
        self._snap_group.addButton(self._snap_min_rdo)
        self._snap_group.buttonClicked.connect(self._on_snap_settings_changed)

        window_lbl = QLabel("搜索半径 (m)：")
        window_lbl.setStyleSheet("font-size: 11px; color: #586878; margin-top: 4px;")
        snap_layout.addWidget(window_lbl)

        self._window_spin = QDoubleSpinBox()
        self._window_spin.setRange(0.1, 10.0)
        self._window_spin.setValue(1.5)
        self._window_spin.setSingleStep(0.1)
        self._window_spin.setSuffix(" 米")
        self._window_spin.setMinimumHeight(28)
        self._window_spin.setStyleSheet(
            "QDoubleSpinBox { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 2px 6px; font-size: 12px; }"
        )
        self._window_spin.valueChanged.connect(self._on_snap_settings_changed)
        snap_layout.addWidget(self._window_spin)

        c_layout.addWidget(snap_group)

        # --- Group 3: Curve Overlay Manager ---
        overlay_group = QGroupBox("🔗 曲线合并与重叠")
        overlay_group.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 1px solid #e5eaf1; border-radius: 8px; margin-top: 10px; padding: 12px 6px 6px 6px; background: #ffffff; }"
            "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 8px; padding: 0 3px; color: #1f66d4; }"
        )
        overlay_layout = QVBoxLayout(overlay_group)
        overlay_layout.setSpacing(6)

        table_desc = QLabel("配置每条曲线的叠加目标：")
        table_desc.setStyleSheet("font-size: 11px; color: #586878;")
        overlay_layout.addWidget(table_desc)

        self._overlay_table = QTableWidget(0, 2)
        self._overlay_table.setHorizontalHeaderLabels(["曲线", "叠加目标"])
        self._overlay_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._overlay_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._overlay_table.verticalHeader().setVisible(False)
        self._overlay_table.setFixedHeight(160)
        self._overlay_table.setStyleSheet(
            "QTableWidget { border: 1px solid #e5eaf1; border-radius: 6px; font-size: 11.5px; background: #ffffff; }"
            "QHeaderView::section { background: #f1f4f9; border: none; padding: 4px; font-weight: bold; color: #586878; }"
        )
        overlay_layout.addWidget(self._overlay_table)
        c_layout.addWidget(overlay_group)

        # --- Group 4: DTW Auto-correlation ---
        dtw_group = QGroupBox("⚡ DTW 自动对比")
        dtw_group.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 1px solid #e5eaf1; border-radius: 8px; margin-top: 10px; padding: 12px 6px 6px 6px; background: #ffffff; }"
            "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 8px; padding: 0 3px; color: #1f66d4; }"
        )
        dtw_layout = QVBoxLayout(dtw_group)
        
        self._dtw_run_btn = QPushButton("一键传播 (DTW)")
        self._dtw_run_btn.setMinimumHeight(32)
        self._dtw_run_btn.setToolTip("用当前敏感曲线把手工拾取的层位传播至所有井")
        self._dtw_run_btn.setStyleSheet(
            "QPushButton { background: #1f66d4; color: white; border: none; border-radius: 6px; font-weight: bold; font-size: 12px; }"
            "QPushButton:hover { background: #154ec2; }"
        )
        self._dtw_run_btn.clicked.connect(self._on_dtw_run)
        dtw_layout.addWidget(self._dtw_run_btn)
        c_layout.addWidget(dtw_group)

        # Add spacers
        c_layout.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

    def set_available_curves(self, curves: list[str]):
        """Update curves checklist and dynamic group configurations."""
        self._available_curves = sorted(list(set(curves)))
        
        # Update snap curve dropdown
        self._curve_combo.blockSignals(True)
        current = self._curve_combo.currentText()
        self._curve_combo.clear()
        self._curve_combo.addItems(self._available_curves)
        if current in self._available_curves:
            self._curve_combo.setCurrentText(current)
        else:
            # Prefer GR, then AC, then first available
            gr_name = next((c for c in self._available_curves if c.upper() == "GR"), None)
            if gr_name:
                self._curve_combo.setCurrentText(gr_name)
            elif self._available_curves:
                self._curve_combo.setCurrentIndex(0)
        self._curve_combo.blockSignals(False)

        # Re-populate overlay table
        self._overlay_table.setRowCount(0)
        self._overlay_table.setRowCount(len(self._available_curves))
        
        for i, cname in enumerate(self._available_curves):
            # Column 0: Curve name
            name_item = QTableWidgetItem(cname)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._overlay_table.setItem(i, 0, name_item)

            # Column 1: Dropdown selector
            combo = QComboBox()
            combo.setMinimumHeight(24)
            combo.setStyleSheet("QComboBox { font-size: 11px; border: 1px solid #d3dbe6; border-radius: 4px; }")
            combo.addItem("独立显示")
            
            # Other curves that this curve can merge into
            others = [o for o in self._available_curves if o != cname]
            for o in others:
                combo.addItem(f"与 {o} 叠加")
                
            # Initial state mapping from self._curve_groups
            initial_merged_target = None
            for gname, items in self._curve_groups.items():
                if cname in items and len(items) > 1:
                    # Find other curves in this group
                    target = next((item for item in items if item != cname), None)
                    if target:
                        initial_merged_target = target
                        break
            
            if initial_merged_target:
                combo.setCurrentText(f"与 {initial_merged_target} 叠加")
            else:
                combo.setCurrentText("独立显示")

            combo.setProperty("curve_name", cname)
            combo.currentTextChanged.connect(self._on_table_combo_changed)
            self._overlay_table.setCellWidget(i, 1, combo)

    def set_horizons(self, horizons: list[str]):
        """Update the list of horizons in the dropdown."""
        self._hz_combo.blockSignals(True)
        current = self._hz_combo.currentText()
        self._hz_combo.clear()
        
        unique_hz = sorted(list(set(horizons)))
        self._hz_combo.addItems(unique_hz)
        
        if current:
            self._hz_combo.setEditText(current)
        elif unique_hz:
            self._hz_combo.setCurrentIndex(0)
        self._hz_combo.blockSignals(False)

    def _on_add_horizon(self):
        new_name = self._hz_combo.currentText().strip()
        if not new_name:
            return
        
        # Check if already exists in combo items
        all_items = [self._hz_combo.itemText(i) for i in range(self._hz_combo.count())]
        if new_name not in all_items:
            self._hz_combo.addItem(new_name)
            self._hz_combo.setCurrentText(new_name)
        self.horizon_changed.emit(new_name)

    def _on_horizon_combo_changed(self, text: str):
        self.horizon_changed.emit(text.strip())

    def _on_curve_combo_changed(self, text: str):
        self.curve_changed.emit(text.strip())

    def _on_snap_settings_changed(self, *_):
        snap_type = "none"
        if self._snap_max_rdo.isChecked():
            snap_type = "max"
        elif self._snap_min_rdo.isChecked():
            snap_type = "min"
        
        snap_window = self._window_spin.value()
        self.snapping_changed.emit(snap_type, snap_window)

    def _on_table_combo_changed(self, text: str):
        # Re-build self._curve_groups dynamically from table widgets
        new_groups: dict[str, list[str]] = {}
        
        # We build mapping of curve_name -> target
        relations: dict[str, str | None] = {}
        for i in range(self._overlay_table.rowCount()):
            combo = self._overlay_table.cellWidget(i, 1)
            if combo is None:
                continue
            cname = combo.property("curve_name")
            sel = combo.currentText()
            if sel.startswith("与 ") and sel.endswith(" 叠加"):
                target = sel[2:-3]
                relations[cname] = target
            else:
                relations[cname] = None

        # Build groupings. If A matches to B and B to A (or B matches to none)
        # We group them. To resolve transitive groupings:
        visited = set()
        for cname in self._available_curves:
            if cname in visited:
                continue
            
            group_members = [cname]
            visited.add(cname)
            
            # Follow target chain
            curr = cname
            while relations.get(curr) is not None:
                target = relations[curr]
                if target in visited:
                    if target not in group_members:
                        # Merge this chain into target's existing group
                        pass
                    break
                group_members.append(target)
                visited.add(target)
                curr = target
                
            # Filter unique and sort
            unique_members = sorted(list(set(group_members)))
            gname = "/".join(unique_members)
            new_groups[gname] = unique_members

        self._curve_groups = new_groups
        self.curve_groups_changed.emit(new_groups)

    def _on_dtw_run(self):
        self.dtw_triggered.emit()
