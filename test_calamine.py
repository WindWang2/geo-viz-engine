import time
import pandas as pd
from pathlib import Path

path = Path("data/01-HZ19-1-1A井综合柱状图-2001-沉积室-地化室（无地化录井）-测井室-勘探室_2.xlsx")

# 1. Default (openpyxl)
start = time.perf_counter()
xls1 = pd.ExcelFile(path)
for sheet in xls1.sheet_names:
    if "测井曲线" in sheet or "地层" in sheet:
        df = pd.read_excel(xls1, sheet_name=sheet)
openpyxl_time = time.perf_counter() - start
print(f"Default (openpyxl) time: {openpyxl_time:.4f}s")

# 2. Calamine
start = time.perf_counter()
xls2 = pd.ExcelFile(path, engine="calamine")
for sheet in xls2.sheet_names:
    if "测井曲线" in sheet or "地层" in sheet:
        df = pd.read_excel(xls2, sheet_name=sheet)
calamine_time = time.perf_counter() - start
print(f"Calamine time: {calamine_time:.4f}s")

print(f"Speedup: {openpyxl_time / calamine_time:.1f}x")
