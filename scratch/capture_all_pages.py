import os
import sys
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app import MainWindow

def capture_pages():
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Force high DPI scaling off for consistent capture sizes
    os.environ["QT_SCALE_FACTOR"] = "1"
    
    win = MainWindow()
    win.resize(1280, 800)
    win.show()
    
    # Allow some time for splash screen to complete (if any) or layout to settle
    QApplication.processEvents()
    time.sleep(0.5)
    
    output_dir = Path("/home/kevin/.gemini/antigravity-cli/brain/c233932d-7584-4a0b-83b6-86254318e98c")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Pages mapping
    page_names = {
        0: "0_map_page",
        1: "1_paleo_map_page",
        2: "2_well_log_page",
        3: "3_cross_well_page",
        4: "4_seismic_page",
        5: "5_plots_page",
        6: "6_data_page",
        7: "7_tools_page"
    }
    
    for index, name in page_names.items():
        print(f"Switching to page {index}: {name}...")
        win._switch_page(index)
        
        # Process events to allow repaint
        for _ in range(10):
            QApplication.processEvents()
            time.sleep(0.05)
            
        # Grab main window
        img = win.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)
        save_path = output_dir / f"{name}.png"
        img.save(str(save_path))
        print(f"Saved screenshot to {save_path}")

    print("All screenshots successfully captured!")
    win.close()

if __name__ == "__main__":
    capture_pages()
