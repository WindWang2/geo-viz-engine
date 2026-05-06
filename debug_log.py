import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from src.pages.cross_well_page import CrossWellPage

app = QApplication(sys.argv)
page = CrossWellPage()
page.show()
page.add_well("HZ21-1-18")
page.add_well("HZ21-1-1")

def check_cache():
    print("----- DEBUG CACHE & GEOMETRY -----")
    print(f"Links count: {len(page.links)}")
    for link in page.links[:3]:
        print(f"Link: {link}")
    app.quit()

def do_link():
    print("Triggering auto_link...")
    page._auto_link()
    QTimer.singleShot(2000, check_cache) # wait for js

QTimer.singleShot(2000, do_link)
app.exec()
