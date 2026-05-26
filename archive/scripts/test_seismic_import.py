import sys
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
try:
    from src.pages.seismic import SeismicPage
    page = SeismicPage()
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
