from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QTableWidget, QTableWidgetItem, QLabel, QGroupBox,
)
from PySide6.QtCore import Qt

from src.data.cache import DataCache


class DataPage(QWidget):
    def __init__(self, cache: DataCache):
        super().__init__()
        self.cache = cache
        layout = QVBoxLayout(self)

        # Import section
        import_group = QGroupBox("数据导入")
        import_layout = QHBoxLayout(import_group)

        import_excel = QPushButton("导入 Excel (.xlsx)")
        import_excel.clicked.connect(lambda: self._import_file("Excel (*.xlsx *.xls)"))
        import_las = QPushButton("导入 LAS (.las)")
        import_las.clicked.connect(lambda: self._import_file("LAS (*.las)"))
        import_segy = QPushButton("导入 SEGY (.sgy)")
        import_segy.clicked.connect(lambda: self._import_file("SEGY (*.sgy *.segy)"))

        import_layout.addWidget(import_excel)
        import_layout.addWidget(import_las)
        import_layout.addWidget(import_segy)
        layout.addWidget(import_group)

        # Well coordinates table
        table_group = QGroupBox("井位坐标")
        table_layout = QVBoxLayout(table_group)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["井名", "纬度", "经度"])
        table_layout.addWidget(self.table)
        layout.addWidget(table_group)

        self._load_well_table()

    def _import_file(self, filter_str: str):
        path, _ = QFileDialog.getOpenFileName(self, "选择数据文件", "", filter_str)
        if path:
            pass  # Will be implemented with actual loaders

    def _load_well_table(self):
        well_coords_file = Path(__file__).parent.parent.parent / "data" / "well_coordinates.json"
        wells = self.cache.get_well_coordinates(well_coords_file)
        self.table.setRowCount(len(wells))
        for i, w in enumerate(wells):
            self.table.setItem(i, 0, QTableWidgetItem(w.name))
            self.table.setItem(i, 1, QTableWidgetItem(f"{w.latitude:.6f}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{w.longitude:.6f}"))
