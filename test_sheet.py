import pandas as pd
from pathlib import Path
path = Path("data/01-HZ19-1-1A井综合柱状图-2001-沉积室-地化室（无地化录井）-测井室-勘探室_2.xlsx")
excel_file = pd.ExcelFile(path)
for s in excel_file.sheet_names:
    print(f"Sheet: {s}")
    if "地层单位" in s or "砂层组" in s:
        df = pd.read_excel(path, sheet_name=s)
        print(f"Columns in {s}: {df.columns.tolist()}")
        print(df.head(2))
