import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QGroupBox, QLineEdit
)
from PySide6.QtCore import Qt

from scripts.convert_xml_to_laolong import convert_to_laolong_xls

class ToolsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Title
        title = QLabel("工具箱")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2d3748;")
        layout.addWidget(title)

        # Tool 1: XML to Excel Converter
        xml_converter_group = QGroupBox("测井 XML 转 Excel (LaoLong 格式)")
        xml_layout = QVBoxLayout(xml_converter_group)

        # Input row
        in_layout = QHBoxLayout()
        self.in_xml_path = QLineEdit()
        self.in_xml_path.setPlaceholderText("选择输入的 XML 文件...")
        self.in_xml_path.setReadOnly(True)
        in_btn = QPushButton("浏览...")
        in_btn.clicked.connect(self._select_input_xml)
        in_layout.addWidget(QLabel("输入 XML:"))
        in_layout.addWidget(self.in_xml_path)
        in_layout.addWidget(in_btn)
        xml_layout.addLayout(in_layout)

        # Output row
        out_layout = QHBoxLayout()
        self.out_xls_path = QLineEdit()
        self.out_xls_path.setPlaceholderText("选择输出的 Excel 文件路径...")
        out_btn = QPushButton("浏览...")
        out_btn.clicked.connect(self._select_output_xls)
        out_layout.addWidget(QLabel("输出 Excel:"))
        out_layout.addWidget(self.out_xls_path)
        out_layout.addWidget(out_btn)
        xml_layout.addLayout(out_layout)

        # Action row
        action_layout = QHBoxLayout()
        self.run_btn = QPushButton("执行转换")
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #3182ce;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #2b6cb0;
            }
            QPushButton:disabled {
                background-color: #a0aec0;
            }
        """)
        self.run_btn.clicked.connect(self._run_conversion)
        action_layout.addStretch()
        action_layout.addWidget(self.run_btn)
        xml_layout.addLayout(action_layout)

        layout.addWidget(xml_converter_group)
        layout.addStretch()

    def _select_input_xml(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 XML 文件", "", "XML Files (*.xml)")
        if path:
            self.in_xml_path.setText(path)
            # Auto-suggest output path
            out_path = str(Path(path).with_suffix(".xls"))
            self.out_xls_path.setText(out_path)

    def _select_output_xls(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存为 Excel 文件", self.out_xls_path.text(), "Excel Files (*.xls *.xlsx)")
        if path:
            self.out_xls_path.setText(path)

    def _run_conversion(self):
        in_path = self.in_xml_path.text()
        out_path = self.out_xls_path.text()

        if not in_path or not out_path:
            QMessageBox.warning(self, "缺少参数", "请指定输入和输出文件路径。")
            return

        if not os.path.exists(in_path):
            QMessageBox.critical(self, "文件不存在", "指定的输入 XML 文件不存在。")
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("转换中...")
        
        try:
            # Run the conversion synchronously (can move to QThread if it takes too long)
            convert_to_laolong_xls(in_path, out_path)
            QMessageBox.information(self, "转换成功", f"文件已成功转换为 LaoLong 格式 Excel。\n输出路径: {out_path}")
        except Exception as e:
            QMessageBox.critical(self, "转换失败", f"转换过程中发生错误:\n{str(e)}")
        finally:
            self.run_btn.setEnabled(True)
            self.run_btn.setText("执行转换")
