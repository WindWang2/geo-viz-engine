from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QTableWidget, QTableWidgetItem, QLabel, QGroupBox, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from src.data.cache import DataCache


class DataPage(QWidget):
    def _get_ui_icon(self, name: str) -> QIcon:
        """Resolve icon from project resources."""
        from src.utils.paths import get_resources_dir
        path = get_resources_dir() / "icons" / "ui" / name
        if path.exists():
            return QIcon(str(path))
        return QIcon()

    def __init__(self, cache: DataCache):
        super().__init__()
        self.cache = cache
        layout = QVBoxLayout(self)

        # 1. Project Management section (Phase 15 - Phase 3)
        proj_group = QGroupBox(" 工程项目管理")
        proj_layout = QHBoxLayout(proj_group)

        self._project_meta_label = QLabel("工程: 未加载")
        self._project_meta_label.setStyleSheet("font-weight: bold; color: #1f66d4; font-size: 13px;")

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

        proj_layout.addWidget(self._project_meta_label)
        proj_layout.addStretch()
        proj_layout.addWidget(self._new_proj_btn)
        proj_layout.addWidget(self._open_proj_btn)
        proj_layout.addWidget(self._save_proj_btn)
        proj_layout.addWidget(self._save_as_proj_btn)

        layout.addWidget(proj_group)

        # 2. Import section
        import_group = QGroupBox(" 数据导入")
        import_layout = QHBoxLayout(import_group)

        import_excel = QPushButton(" 导入 Excel")
        import_excel.setIcon(self._get_ui_icon("table.svg"))
        import_excel.clicked.connect(lambda: self._import_file("Excel (*.xlsx *.xls)"))
        
        import_las = QPushButton(" 导入 LAS")
        import_las.setIcon(self._get_ui_icon("doc.svg"))
        import_las.clicked.connect(lambda: self._import_file("LAS (*.las)"))
        
        import_segy = QPushButton(" 导入 SEGY")
        import_segy.setIcon(self._get_ui_icon("upload.svg"))
        import_segy.clicked.connect(lambda: self._import_file("SEGY (*.sgy *.segy)"))

        import_layout.addWidget(import_excel)
        import_layout.addWidget(import_las)
        import_layout.addWidget(import_segy)
        layout.addWidget(import_group)

        # 3. Well coordinates table
        table_group = QGroupBox(" 井位坐标")
        table_layout = QVBoxLayout(table_group)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["井名", "纬度", "经度"])
        table_layout.addWidget(self.table)
        layout.addWidget(table_group)

        self._load_well_table()

    def _get_main_window(self):
        """Traverse widget hierarchy to find the top-level MainWindow instance."""
        curr = self
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
        from datetime import datetime

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
            pass  # Will be implemented with actual loaders

    def _load_well_table(self):
        from src.utils.paths import get_data_dir
        well_coords_file = get_data_dir() / "well_coordinates.json"
        wells = self.cache.get_well_coordinates(well_coords_file)
        self.table.setRowCount(len(wells))
        for i, w in enumerate(wells):
            self.table.setItem(i, 0, QTableWidgetItem(w.name))
            self.table.setItem(i, 1, QTableWidgetItem(f"{w.latitude:.6f}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{w.longitude:.6f}"))
