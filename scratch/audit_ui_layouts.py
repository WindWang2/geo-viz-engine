import os
import sys
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QCheckBox, QRadioButton, QWidget
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QFontMetrics

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app import MainWindow

def find_all_visible_widgets(parent: QWidget) -> list[QWidget]:
    widgets = []
    for child in parent.findChildren(QWidget):
        if child.isVisible() and child.width() > 0 and child.height() > 0:
            widgets.append(child)
    return widgets

def check_truncation(w: QWidget) -> str | None:
    text = ""
    is_label = isinstance(w, QLabel)
    is_btn = isinstance(w, QPushButton)
    is_checkbox = isinstance(w, QCheckBox)
    is_radio = isinstance(w, QRadioButton)
    
    if is_label:
        text = w.text()
    elif is_btn:
        text = w.text()
    elif is_checkbox:
        text = w.text()
    elif is_radio:
        text = w.text()
        
    if not text or not text.strip():
        return None
        
    # Skip rich text HTML for simple text metrics estimation
    if "<" in text and ">" in text:
        # Simple HTML tag stripper
        import re
        text_clean = re.sub(r'<[^>]+>', '', text)
    else:
        text_clean = text
        
    fm = QFontMetrics(w.font())
    text_width = fm.horizontalAdvance(text_clean)
    text_height = fm.height()
    
    w_width = w.width()
    w_height = w.height()
    
    # Standard margins and icon offsets
    padding_x = 0
    if is_btn:
        padding_x += 16  # standard padding
        if not w.icon().isNull():
            padding_x += w.iconSize().width() + 6
    elif is_checkbox or is_radio:
        padding_x += 24  # indicator box + spacing
        
    available_width = w_width - padding_x
    
    # Check horizontal truncation
    if available_width < text_width:
        # Check if it's a wrapping label
        if is_label and w.wordWrap():
            # If height is large enough to fit wrapped text, it's fine
            approx_lines = (text_width // max(1, available_width)) + 1
            required_height = approx_lines * text_height
            if w_height < required_height:
                return f"Word-wrapped label height too small: {w_height}px < {required_height}px needed for approx {approx_lines} lines. text='{text}'"
        else:
            return f"Horizontal text truncation: visible width {w_width}px (avail {available_width}px) < text width {text_width}px. text='{text}'"
            
    # Check vertical truncation
    if w_height < text_height - 2:
        return f"Vertical text truncation: visible height {w_height}px < text height {text_height}px. text='{text}'"
        
    return None

def check_overlaps(widgets: list[QWidget]) -> list[str]:
    overlaps = []
    # Map widgets to their global geometries
    geoms = []
    for w in widgets:
        g_pos = w.mapToGlobal(QPoint(0, 0))
        rect = QRect(g_pos.x(), g_pos.y(), w.width(), w.height())
        geoms.append((w, rect))
        
    n = len(geoms)
    for i in range(n):
        w1, r1 = geoms[i]
        for j in range(i + 1, n):
            w2, r2 = geoms[j]
            
            # Skip if one is parent of the other or vice versa
            if w1.isAncestorOf(w2) or w2.isAncestorOf(w1):
                continue
                
            # Skip if they have different parents and are in separate stacked layout components
            # (Double check if they are actually both visible and active simultaneously)
            if not r1.intersects(r2):
                continue
                
            # Intersecting geometry detected!
            # Filter out background panels overlapping with their children (though ancestor check handles most)
            # or layouts containing backgrounds
            overlap_area = r1.intersected(r2)
            # If the intersection is substantial and neither is a container overlay or background
            if overlap_area.width() > 5 and overlap_area.height() > 5:
                # Check class names
                n1 = w1.metaObject().className()
                n2 = w2.metaObject().className()
                # Containers or custom frames might hold elements, but standard components shouldn't overlap
                exempt = ["QFrame", "QGroupBox", "QWidget", "QStackedWidget", "QSplitter", "QScrollArea", "QViewport", "QOpenGLWidget"]
                if n1 in exempt or n2 in exempt:
                    continue
                # Also check parent structures
                overlaps.append(f"Overlap: {n1} (rect={r1.getRect()}, text={getattr(w1, 'text', lambda: '')()}) and {n2} (rect={r2.getRect()}, text={getattr(w2, 'text', lambda: '')()}) intersect by {overlap_area.width()}x{overlap_area.height()}px")
                
    return overlaps

def audit_all_pages():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_SCALE_FACTOR"] = "1"
    
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.resize(1280, 820)
    win.show()
    
    QApplication.processEvents()
    time.sleep(0.5)
    
    page_names = {
        0: "0_MapPage",
        1: "1_PaleoMapPage",
        2: "2_WellLogPage",
        3: "3_CrossWellPage",
        4: "4_SeismicPage",
        5: "5_PlotsPage",
        6: "6_DataPage",
        7: "7_ToolsPage"
    }
    
    report = []
    
    for index, name in page_names.items():
        print(f"\n================ Auditing Page {index}: {name} ================")
        try:
            win._switch_page(index)
            
            # Settle layout
            for _ in range(5):
                QApplication.processEvents()
                time.sleep(0.05)
                
            widgets = find_all_visible_widgets(win)
            print(f"Found {len(widgets)} visible active widgets.")
            
            # 1. Check truncations
            truncations = []
            for w in widgets:
                trunc = check_truncation(w)
                if trunc:
                    cls_name = w.metaObject().className()
                    truncations.append(f"  - [{cls_name}] {trunc}")
                    
            # 2. Check overlaps
            overlaps = []
            # Filter known overlays/canvases/backings that are structurally intended to overlay
            filtered_widgets = []
            for w in widgets:
                cls_name = w.metaObject().className()
                obj_name = w.objectName()
                text = getattr(w, 'text', lambda: '')()
                # Skip known background panels, viewport wrappers or overlays
                if cls_name in ["PickingOverlay", "ConnectionOverlay", "DepthRuler"]:
                    continue
                if "Canvas" in cls_name or "MapCanvas" in cls_name or "WellLogCanvas" in cls_name:
                    continue
                # If it's a map zoom/ruler floating button or overlay panel, ignore overlap with MapCanvas
                filtered_widgets.append(w)
                
            overlaps = check_overlaps(filtered_widgets)
            
            if truncations:
                print(f"Found {len(truncations)} potential text truncations:")
                for t in truncations:
                    print(t)
                    report.append(f"Page {name} - Truncation: {t}")
            else:
                print("No text truncations detected!")
                
            if overlaps:
                print(f"Found {len(overlaps)} potential sibling overlaps:")
                for o in overlaps:
                    print(f"  - {o}")
                    report.append(f"Page {name} - Overlap: {o}")
            else:
                print("No layout overlaps detected!")
        except Exception as ex:
            print(f"Failed to audit page {name} due to: {ex}")
            report.append(f"Page {name} - Failed to audit: {ex}")
            
    print("\n================ AUDIT SUMMARY ================")
    if not report:
        print("PERFECT! No pixel-level layout truncations or overlaps found on all pages!")
    else:
        print(f"Found {len(report)} items needing review:")
        for item in report:
            print(item)
            
    win.close()

if __name__ == "__main__":
    audit_all_pages()
