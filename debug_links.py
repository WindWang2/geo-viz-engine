import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from src.pages.cross_well_page import CrossWellPage

app = QApplication(sys.argv)
page = CrossWellPage()
page.add_well("HZ19-1-1A")
page.add_well("XJ24-3-1AX")

def check_cache():
    print("Links count:", len(page.links))
    print("Cache size:", len(page.overlay._depth_cache))
    for k, v in page.overlay._depth_cache.items():
        print(f"Cache entry: {k[0]._well_name}, {k[1]} -> {v}")
    
    # Try to simulate paintEvent logic
    for link in page.links:
        src_engine = next((e for e in page.engines if e._well_name == link.source_well), None)
        tgt_engine = next((e for e in page.engines if e._well_name == link.target_well), None)
        
        parts_s = link.source_interval_id.split('_')
        parts_t = link.target_interval_id.split('_')
        s_top, s_bot = round(float(parts_s[0]), 2), round(float(parts_s[1]), 2)
        t_top, t_bot = round(float(parts_t[0]), 2), round(float(parts_t[1]), 2)
        
        y_s_top = page.overlay._depth_cache.get((src_engine, s_top))
        y_s_bot = page.overlay._depth_cache.get((src_engine, s_bot))
        y_t_top = page.overlay._depth_cache.get((tgt_engine, t_top))
        y_t_bot = page.overlay._depth_cache.get((tgt_engine, t_bot))
        
        print(f"Link {link.source_interval_id} -> {link.target_interval_id}")
        print(f"  y_s_top: {y_s_top}, y_s_bot: {y_s_bot}")
        print(f"  y_t_top: {y_t_top}, y_t_bot: {y_t_bot}")
        
    app.quit()

def do_link():
    print("Doing auto link...")
    page._auto_link()
    QTimer.singleShot(2000, check_cache) # Wait 2s for JS callbacks

QTimer.singleShot(2000, do_link) # Wait 2s for initial load
app.exec()
