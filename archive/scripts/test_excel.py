import pandas as pd
from pathlib import Path

path = Path("data/01-HZ19-1-1A井综合柱状图-2001-沉积室-地化室（无地化录井）-测井室-勘探室_2.xlsx")
excel_file = pd.ExcelFile(path)
for sheet in excel_file.sheet_names:
    print(f"Sheet: {sheet}")
    df = pd.read_excel(path, sheet_name=sheet)
    print(f"Columns: {df.columns.tolist()}")
    if "地层单位道" in sheet or "文本道" in sheet:
        print(df.head())
