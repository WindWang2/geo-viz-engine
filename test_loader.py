import sys
from pathlib import Path
from src.data.loaders import load_well_log_from_excel

path = Path("data/01-HZ19-1-1A井综合柱状图-2001-沉积室-地化室（无地化录井）-测井室-勘探室_2.xlsx")
log_data = load_well_log_from_excel(path)

print("--- Formation ---")
for f in log_data.intervals.formation[:10]:
    print(f)
print("... total:", len(log_data.intervals.formation))
