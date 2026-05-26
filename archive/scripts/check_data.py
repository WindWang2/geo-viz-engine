from pathlib import Path
from src.data.loaders import load_well_log_from_excel

path = Path("data/01-HZ19-1-1A井综合柱状图-2001-沉积室-地化室（无地化录井）-测井室-勘探室_2.xlsx")
log_data = load_well_log_from_excel(path)

print("--- Stratigraphic Framework (Members/Sequences) ---")
if log_data.intervals.sequence:
    for s in log_data.intervals.sequence[:10]:
        print(f"Sequence: {s}")
elif log_data.intervals.member:
    for s in log_data.intervals.member[:10]:
        print(f"Member: {s}")
else:
    print("No Member or Sequence data found.")
    
print("\n--- Formation ---")
if log_data.intervals.formation:
    for f in log_data.intervals.formation[:10]:
        print(f"Formation: {f}")
else:
    print("No Formation data found.")

