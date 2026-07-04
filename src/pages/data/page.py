from pathlib import Path
from datetime import datetime
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QTableWidget, QTableWidgetItem, QLabel, QGroupBox, QMessageBox,
    QFrame, QLineEdit, QHeaderView, QSplitter, QTextEdit, QInputDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from src.data.cache import DataCache
from src.data.well_registry import list_wells, get_well_data


class DataPage(QWidget):
    def _get_ui_icon(self, name: str) -> QIcon:
        """Resolve icon from project resources."""
        from src.utils.paths import get_resources_dir
        path = get_resources_dir() / "icons" / "ui" / name
        if path.exists():
            return QIcon(str(path))
        return QIcon()

    def __init__(self, cache: DataCache, main_window=None):
        super().__init__()
        self.cache = cache
        self._main_window = main_window
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # 1. Project Management section (Preserved for tests)
        self.proj_group = QGroupBox(" 工程项目管理")
        self.proj_group.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #1a2433; }"
        )
        proj_layout = QHBoxLayout(self.proj_group)
        proj_layout.setContentsMargins(12, 12, 12, 12)
        proj_layout.setSpacing(10)

        self._project_meta_label = QLabel("工程: 未加载")
        self._project_meta_label.setStyleSheet("font-weight: bold; color: #1f66d4; font-size: 13px; border: none;")

        self._new_proj_btn = QPushButton(" 新建工程")
        self._new_proj_btn.setIcon(self._get_ui_icon("plus.svg"))
        self._new_proj_btn.clicked.connect(self._on_new_project)

        self._open_proj_btn = QPushButton(" 打开工程")
        self._open_proj_btn.setIcon(self._get_ui_icon("upload.svg"))
        self._open_proj_btn.clicked.connect(self._on_open_project)

        self._save_proj_btn = QPushButton(" 保存工程")
        self._save_proj_btn.setIcon(self._get_ui_icon("check.svg"))
        self._save_proj_btn.clicked.connect(self._on_save_project)

        self._save_as_proj_btn = QPushButton(" 另存工程")
        self._save_as_proj_btn.setIcon(self._get_ui_icon("export.svg"))
        self._save_as_proj_btn.clicked.connect(self._on_save_as_project)

        btn_style = (
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 5px 12px; color: #1a2433; }"
            "QPushButton:hover { background: #f1f4f9; }"
        )
        for btn in [self._new_proj_btn, self._open_proj_btn, self._save_proj_btn, self._save_as_proj_btn]:
            btn.setStyleSheet(btn_style)
            proj_layout.addWidget(btn)

        proj_layout.insertWidget(0, self._project_meta_label)
        proj_layout.insertStretch(1)
        main_layout.addWidget(self.proj_group)

        # 2. High-Fidelity Top Import Header
        self._top_hdr = QFrame()
        self._top_hdr.setStyleSheet(
            "QFrame { background: #ffffff; border: 1px solid #e5eaf1; border-radius: 8px; }"
        )
        hdr_layout = QHBoxLayout(self._top_hdr)
        hdr_layout.setContentsMargins(12, 12, 12, 12)
        hdr_layout.setSpacing(12)

        self._import_data_btn = QPushButton(" 导入数据")
        self._import_data_btn.setIcon(self._get_ui_icon("plus.svg"))
        self._import_data_btn.clicked.connect(self._on_import_data)
        self._import_data_btn.setStyleSheet(
            "QPushButton { background: #1f66d4; color: #ffffff; font-weight: bold; border-radius: 6px; padding: 6px 14px; border: none; }"
            "QPushButton:hover { background: #1a54b2; }"
        )
        hdr_layout.addWidget(self._import_data_btn)

        self._import_excel_btn = QPushButton(" 导入 Excel")
        self._import_excel_btn.setIcon(self._get_ui_icon("table.svg"))
        self._import_excel_btn.clicked.connect(lambda: self._import_file("Excel (*.xlsx *.xls)"))

        self._import_las_btn = QPushButton(" 导入 LAS")
        self._import_las_btn.setIcon(self._get_ui_icon("doc.svg"))
        self._import_las_btn.clicked.connect(lambda: self._import_file("LAS (*.las)"))

        self._import_segy_btn = QPushButton(" 导入 SEGY")
        self._import_segy_btn.setIcon(self._get_ui_icon("upload.svg"))
        self._import_segy_btn.clicked.connect(lambda: self._import_file("SEGY (*.sgy *.segy)"))

        sub_btn_style = (
            "QPushButton { background: #ffffff; border: 1px solid #d3dbe6; border-radius: 6px; padding: 6px 12px; color: #586878; }"
            "QPushButton:hover { background: #f1f4f9; color: #1f66d4; border-color: #1f66d4; }"
        )
        for btn in [self._import_excel_btn, self._import_las_btn, self._import_segy_btn]:
            btn.setStyleSheet(sub_btn_style)
            hdr_layout.addWidget(btn)

        hdr_layout.addStretch()

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 搜索表格...")
        self._search_input.setFixedWidth(180)
        self._search_input.setStyleSheet(
            "QLineEdit { background: #fafbfd; border: 1px solid #d3dbe6; border-radius: 6px; padding: 5px 10px; color: #1a2433; }"
            "QLineEdit:focus { border: 1px solid #1f66d4; background: #ffffff; }"
        )
        self._search_input.textChanged.connect(self._filter_table)
        hdr_layout.addWidget(self._search_input)

        main_layout.addWidget(self._top_hdr)

        # 3. High-Fidelity KPI Cards Section (dynamic values)
        self._kpi_container = QFrame()
        self._kpi_container.setStyleSheet("border: none; background: transparent;")
        kpi_layout = QHBoxLayout(self._kpi_container)
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.setSpacing(12)

        kpi_defs = [
            ("注册井数", "— 口", "registered_wells", "#1f66d4"),
            ("缓存占用", "— MB", "cache_size", "#2ca36b"),
            ("数据格式", "—", "data_format", "#805ad5"),
            ("引擎速度", "—", "engine_speed", "#ef4444")
        ]

        self._kpi_value_labels: dict[str, QLabel] = {}
        for title, value, obj_name, color in kpi_defs:
            card = QFrame(self._kpi_container)
            card.setObjectName(obj_name)
            card.setStyleSheet(
                "QFrame { background: #ffffff; border: 1px solid #e5eaf1; border-radius: 8px; }"
                "QFrame:hover { border-color: " + color + "; }"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 12, 12, 12)
            card_layout.setSpacing(4)

            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("color: #586878; font-size: 11px; font-weight: 500; border: none; background: transparent;")
            lbl_val = QLabel(value)
            lbl_val.setStyleSheet("color: " + color + "; font-size: 18px; font-weight: bold; border: none; background: transparent;")

            card_layout.addWidget(lbl_title)
            card_layout.addWidget(lbl_val)
            kpi_layout.addWidget(card)
            self._kpi_value_labels[obj_name] = lbl_val

        main_layout.addWidget(self._kpi_container)

        # 4. Modern Table View + slide-out Detail Panel
        table_group = QGroupBox(" 井位数据列表")
        table_group.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #1a2433; }"
        )
        table_layout = QVBoxLayout(table_group)
        table_layout.setContentsMargins(12, 16, 12, 12)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: #e5eaf1; }")

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["井名", "纬度", "经度", ""])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 36)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(
            "QTableWidget { border: 1px solid #e5eaf1; background: #ffffff; alternate-background-color: #fafbfd; gridline-color: #e5eaf1; color: #1a2433; }"
            "QHeaderView::section { background-color: #fafbfd; color: #586878; font-weight: bold; border: none; border-bottom: 1px solid #e5eaf1; padding: 6px; }"
            "QTableWidget::item { padding: 6px; }"
            "QTableWidget::item:selected { background: #e9effa; color: #1f66d4; }"
        )
        self.table.setAlternatingRowColors(True)
        splitter.addWidget(self.table)

        # WellDetailPanel — slide-out side panel
        self._detail_panel = self._build_detail_panel()
        self._detail_panel.hide()
        splitter.addWidget(self._detail_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        table_layout.addWidget(splitter)
        main_layout.addWidget(table_group, 1)

        self._load_well_table()
        self.refresh_kpis()

    def _build_detail_panel(self) -> QFrame:
        """Build the WellDetailPanel side-out frame."""
        panel = QFrame()
        panel.setObjectName("wellDetailPanel")
        panel.setMinimumWidth(280)
        panel.setStyleSheet(
            "#wellDetailPanel { background: #fafbfd; border-left: 1px solid #e5eaf1; }"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Header row
        hdr = QHBoxLayout()
        self._detail_name_label = QLabel("井位详情")
        self._detail_name_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #1a2433;")
        hdr.addWidget(self._detail_name_label)
        hdr.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { border: none; color: #92a0b0; }"
            "QPushButton:hover { background: #f1f4f9; border-radius: 6px; }"
        )
        close_btn.clicked.connect(self._hide_well_detail)
        hdr.addWidget(close_btn)
        layout.addLayout(hdr)

        # Metadata JSON viewer
        self._detail_meta_view = QTextEdit()
        self._detail_meta_view.setReadOnly(True)
        self._detail_meta_view.setStyleSheet(
            "QTextEdit { background: #ffffff; border: 1px solid #e5eaf1; border-radius: 8px;"
            " padding: 8px; font-family: monospace; font-size: 11px; color: #1a2433; }"
        )
        layout.addWidget(self._detail_meta_view, 1)

        # Rename + delete actions
        actions = QHBoxLayout()
        self._detail_rename_btn = QPushButton(" 重命名")
        self._detail_rename_btn.setStyleSheet(
            "QPushButton { background: #ffffff; color: #1f66d4; border: 1px solid #1f66d4;"
            " border-radius: 6px; padding: 6px 12px; font-weight: 600; }"
            "QPushButton:hover { background: #e9effa; }"
        )
        self._detail_delete_btn = QPushButton(" 删除")
        self._detail_delete_btn.setStyleSheet(
            "QPushButton { background: #ffffff; color: #ef4444; border: 1px solid #ef4444;"
            " border-radius: 6px; padding: 6px 12px; font-weight: 600; }"
            "QPushButton:hover { background: #fef2f2; }"
        )
        actions.addWidget(self._detail_rename_btn)
        actions.addWidget(self._detail_delete_btn)
        actions.addStretch()
        layout.addLayout(actions)

        # Wire detail panel action buttons
        self._detail_rename_btn.clicked.connect(self._on_rename_well)
        self._detail_delete_btn.clicked.connect(self._on_delete_well)

        return panel

    def refresh_kpis(self):
        """Recompute KPI values from the live cache state."""
        from src.utils.paths import get_data_dir
        try:
            wells = self.cache.get_well_coordinates(get_data_dir() / "well_coordinates.json")
            self._kpi_value_labels["registered_wells"].setText(f"{len(wells)} 口")
        except Exception:
            self._kpi_value_labels["registered_wells"].setText("0 口")

        # Cache size: walk ~/.cache/geoviz
        cache_root = Path.home() / ".cache" / "geoviz"
        total = 0
        if cache_root.exists():
            for dirpath, _dirs, files in os.walk(cache_root):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(dirpath, f))
                    except OSError:
                        pass
        mb = total / (1024 * 1024)
        if mb >= 1024:
            self._kpi_value_labels["cache_size"].setText(f"{mb / 1024:.2f} GB")
        else:
            self._kpi_value_labels["cache_size"].setText(f"{mb:.1f} MB")

        self._kpi_value_labels["data_format"].setText("LAS/SEGY")
        self._kpi_value_labels["engine_speed"].setText("Calamine")

    def _show_well_detail(self, well_name: str):
        """Populate and reveal the side-out detail panel for a well."""
        import json
        self._current_detail_well = well_name
        self._detail_name_label.setText(f"井位详情 · {well_name}")
        from src.utils.paths import get_data_dir
        meta = {"name": well_name, "source": "well_coordinates.json"}
        try:
            wells = self.cache.get_well_coordinates(get_data_dir() / "well_coordinates.json")
            for w in wells:
                if w.name == well_name:
                    meta.update({
                        "latitude": w.latitude,
                        "longitude": w.longitude,
                    })
                    break
        except Exception:
            pass
        self._detail_meta_view.setPlainText(json.dumps(meta, indent=2, ensure_ascii=False))
        self._detail_panel.show()

    def _hide_well_detail(self):
        self._detail_panel.hide()

    def _get_main_window(self):
        """Return the MainWindow reference injected at construction."""
        if self._main_window is not None:
            return self._main_window
        curr = self.parent()
        while curr is not None:
            if curr.__class__.__name__ == "MainWindow":
                return curr
            curr = curr.parent()
        return None

    def update_project_display(self):
        """Update the metadata label to reflect current project state."""
        win = self._get_main_window()
        if win and win.current_project:
            name = win.current_project.meta.name
            path_str = getattr(win, "current_project_path", None)
            if path_str:
                self._project_meta_label.setText(f"工程: {name} ({Path(path_str).name})")
            else:
                self._project_meta_label.setText(f"工程: {name} (未保存)")
        else:
            self._project_meta_label.setText("工程: 未加载")

    def _on_new_project(self):
        """Handle new project button clicks."""
        from src.data.project import ProjectSchema, ProjectMeta

        win = self._get_main_window()
        if not win:
            return

        now_str = datetime.now().isoformat()
        meta = ProjectMeta(
            name="新工程",
            version="0.8.0",
            created_at=now_str,
            updated_at=now_str
        )
        project_data = ProjectSchema(meta=meta)
        win.current_project_path = None
        win.sync_from_project(project_data)
        self.update_project_display()

    def _on_open_project(self):
        """Handle open project button clicks with file selection dialogue."""
        win = self._get_main_window()
        if not win:
            return

        path, _ = QFileDialog.getOpenFileName(self, "打开工程文件", "", "GeoViz Project (*.gvz)")
        if path:
            from src.data.project import ProjectManager
            try:
                manager = ProjectManager(path)
                project_data = manager.load_project()
                win.current_project_path = path
                win.sync_from_project(project_data)
                self.update_project_display()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"加载工程失败: {e}")

    def _on_save_project(self):
        """Save the current project to its active path or delegate to save as."""
        win = self._get_main_window()
        if not win:
            return

        path = getattr(win, "current_project_path", None)
        if path:
            from src.data.project import ProjectManager
            try:
                project_data = win.sync_to_project()
                manager = ProjectManager(path)
                manager.save_project(project_data)
                self.update_project_display()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"保存工程失败: {e}")
        else:
            self._on_save_as_project()

    def _on_save_as_project(self):
        """Save the current project to a new specified path."""
        win = self._get_main_window()
        if not win:
            return

        path, _ = QFileDialog.getSaveFileName(self, "另存工程文件", "", "GeoViz Project (*.gvz)")
        if path:
            from src.data.project import ProjectManager
            try:
                project_data = win.sync_to_project()
                manager = ProjectManager(path)
                manager.save_project(project_data)
                win.current_project_path = path
                self.update_project_display()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"保存工程失败: {e}")

    def _import_file(self, filter_str: str):
        path, _ = QFileDialog.getOpenFileName(self, "选择数据文件", "", filter_str)
        if path:
            self._load_imported_file(path, filter_str)

    def _on_import_data(self):
        """Generic import — show format chooser then file dialog."""
        path, _ = QFileDialog.getOpenFileName(
            self, "导入数据文件", "",
            "All Supported (*.xlsx *.xls *.las *.sgy *.segy *.json);;Excel (*.xlsx *.xls);;LAS (*.las);;SEGY (*.sgy *.segy);;JSON (*.json)"
        )
        if path:
            ext = Path(path).suffix.lower()
            if ext in (".xlsx", ".xls"):
                self._load_imported_file(path, "Excel (*.xlsx *.xls)")
            elif ext == ".las":
                self._load_imported_file(path, "LAS (*.las)")
            elif ext in (".sgy", ".segy"):
                self._load_imported_file(path, "SEGY (*.sgy *.segy)")
            elif ext == ".json":
                self._load_imported_file(path, "JSON (*.json)")

    def _load_imported_file(self, path: str, filter_str: str):
        """Load an imported file into the cache and refresh display."""
        try:
            p = Path(path)
            if "Excel" in filter_str:
                from src.data.loaders import load_well_log_from_excel
                load_well_log_from_excel(p)
                self.cache.catalog.register_well_file(p.stem, p)
            self.cache.put_file(path)
            self._load_well_table()
            self.refresh_kpis()
            QMessageBox.information(self, "导入完成", f"文件已成功导入:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"无法加载文件:\n{path}\n\n{e}")

    def _on_rename_well(self):
        """Rename the currently selected well in the detail panel."""
        well_name = getattr(self, "_current_detail_well", None)
        if not well_name:
            return
        new_name, ok = QInputDialog.getText(self, "重命名井位", "新名称:", text=well_name)
        if ok and new_name and new_name != well_name:
            self.cache.rename_well(well_name, new_name)
            self._load_well_table()
            self.refresh_kpis()
            self._hide_well_detail()

    def _on_delete_well(self):
        """Delete the currently selected well after confirmation."""
        well_name = getattr(self, "_current_detail_well", None)
        if not well_name:
            return
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除井位 '{well_name}' 吗？\n此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.cache.remove_well(well_name)
            self._load_well_table()
            self.refresh_kpis()
            self._hide_well_detail()

    def _load_well_table(self):
        from src.utils.paths import get_data_dir
        well_coords_file = get_data_dir() / "well_coordinates.json"
        wells = self.cache.get_well_coordinates(well_coords_file)
        self.table.setRowCount(len(wells))
        for i, w in enumerate(wells):
            self.table.setItem(i, 0, QTableWidgetItem(w.name))
            self.table.setItem(i, 1, QTableWidgetItem(f"{w.latitude:.6f}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{w.longitude:.6f}"))
            # Arrow button for detail panel
            arrow_btn = QPushButton("›")
            arrow_btn.setFixedSize(28, 28)
            arrow_btn.setStyleSheet(
                "QPushButton { border: none; color: #92a0b0; font-size: 16px; font-weight: bold; }"
                "QPushButton:hover { color: #1f66d4; background: #e9effa; border-radius: 6px; }"
            )
            arrow_btn.clicked.connect(lambda checked=False, name=w.name: self._show_well_detail(name))
            self.table.setCellWidget(i, 3, arrow_btn)

    def _filter_table(self, text):
        for i in range(self.table.rowCount()):
            match = False
            for j in range(self.table.columnCount()):
                item = self.table.item(i, j)
                if item and text.lower() in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(i, not match)
