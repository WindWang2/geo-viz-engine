"""Global QSS stylesheet for Azurite Design System."""

GLOBAL_STYLESHEET = """
    QWidget { background: #faf9f5; color: #1a2433; font-family: "Microsoft YaHei", "Segoe UI", sans-serif; }

    QGroupBox {
        border: 1px solid #e5eaf1;
        border-radius: 12px;
        margin-top: 12px;
        padding-top: 16px;
        font-weight: bold;
        background: #ffffff;
    }
    QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #1f66d4; }

    QPushButton {
        background: #ffffff;
        border: 1px solid #d3dbe6;
        border-radius: 8px;
        padding: 6px 12px;
        color: #1a2433;
        font-weight: 500;
    }
    QPushButton:hover { background: #f1f4f9; border-color: #1f66d4; color: #1f66d4; }
    QPushButton:pressed { background: #e9effa; }
    QPushButton:checked { background: #1f66d4; color: #ffffff; border-color: #1f66d4; }

    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
        background: #ffffff;
        border: 1px solid #d3dbe6;
        border-radius: 6px;
        padding: 4px 8px;
        min-height: 24px;
        color: #1a2433;
    }
    QLineEdit:focus, QComboBox:focus { border-color: #1f66d4; }

    QTableWidget {
        background: #ffffff;
        gridline-color: #f1f4f9;
        border: 1px solid #d3dbe6;
        border-radius: 12px;
    }
    QHeaderView::section {
        background: #fafbfd;
        border: none;
        border-right: 1px solid #e5eaf1;
        border-bottom: 1px solid #e5eaf1;
        padding: 6px;
        font-weight: bold;
        color: #586878;
    }

    QScrollBar:vertical { background: #faf9f5; width: 8px; margin: 0px; }
    QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 4px; min-height: 20px; }
    QScrollBar::handle:vertical:hover { background: #94a3b8; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

    QScrollBar:horizontal { background: #faf9f5; height: 8px; margin: 0px; }
    QScrollBar::handle:horizontal { background: #cbd5e1; border-radius: 4px; min-width: 20px; }
    QScrollBar::handle:horizontal:hover { background: #94a3b8; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }

    QScrollArea { border: none; background: transparent; }
"""
