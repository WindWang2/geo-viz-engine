import pandas as pd
import os
from typing import Dict, List, Any, Optional

class WellDataService:
    def __init__(self, excel_path: str = None):
        if excel_path is None:
            # Try to find the file relative to this script or project root
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
            excel_path = os.path.join(base_dir, "samples/demo.xls")
        
        self.excel_path = os.path.abspath(excel_path)
        self._all_sheets = None

    def _load_sheets(self):
        if self._all_sheets is None:
            self._all_sheets = pd.read_excel(self.excel_path, sheet_name=None)
        return self._all_sheets

    def get_well_details(self, well_name: str) -> Dict[str, Any]:
        sheets = self._load_sheets()
        
        # 1. Metadata (simple for now)
        data = {
            "well_id": well_name, # Use name as ID for now
            "well_name": well_name,
            "curves": [],
            "intervals": {}
        }

        # 2. Process Curves (AC, GR, RT, RXO)
        curve_data = self._process_curves(sheets)
        data["curves"] = curve_data
        
        # 3. Process Intervals
        # Stratigraphy: Handle stacked tables in '地层系统'
        strat_df = sheets.get("地层系统")
        if strat_df is not None:
            # Table 1: Series (系)
            data["intervals"]["series"] = self._process_interval_sheet(strat_df.iloc[0:2], well_name, "层号")
            # Table 2: System (统)
            data["intervals"]["system"] = self._process_interval_sheet(strat_df.iloc[2:5], well_name, "层号")
            # Table 3: Formation (组)
            data["intervals"]["formation"] = self._process_interval_sheet(strat_df.iloc[5:10], well_name, "层号")
            # Table 4: Member (段)
            data["intervals"]["member"] = self._process_interval_sheet(strat_df.iloc[10:], well_name, "文本")
        else:
            data["intervals"]["series"] = []
            data["intervals"]["system"] = []
            data["intervals"]["formation"] = []
            data["intervals"]["member"] = []
            
        # Sequence: Handle stacked tables in '层序'
        seq_df = sheets.get("层序")
        if seq_df is not None:
            # Table 1: Systems Tract (体系域 - HST/TST)
            data["intervals"]["systems_tract"] = self._process_interval_sheet(seq_df.iloc[0:5], well_name, "文本")
            # Table 2: Sequence (层序 - SQ1/SQ2)
            data["intervals"]["sequence"] = self._process_interval_sheet(seq_df.iloc[5:], well_name, "文本")
        else:
            data["intervals"]["systems_tract"] = []
            data["intervals"]["sequence"] = []
            
        data["intervals"]["lithology"] = self._process_interval_sheet(sheets.get("岩性剖面"), well_name, "岩性")
        
        # Facies (merge phase, sub-phase, micro-phase)
        data["intervals"]["facies"] = {
            "phase": self._process_interval_sheet(sheets.get("相"), well_name, "文本"),
            "sub_phase": self._process_interval_sheet(sheets.get("亚相"), well_name, "文本"),
            "micro_phase": self._process_interval_sheet(sheets.get("微相"), well_name, "文本")
        }

        return data

    def _process_curves(self, sheets: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        curves = []
        
        # Merge AC, GR
        ac_gr = sheets.get("AC、GR")
        if ac_gr is not None:
            # Clean data: ensure numeric
            ac_gr = ac_gr.apply(pd.to_numeric, errors='coerce').dropna()
            curves.append({
                "name": "AC",
                "unit": "us/ft", # Assumption
                "data": ac_gr["AC"].tolist(),
                "depth": ac_gr["深度"].tolist()
            })
            curves.append({
                "name": "GR",
                "unit": "API", # Assumption
                "data": ac_gr["GR"].tolist(),
                "depth": ac_gr["深度"].tolist()
            })

        # Merge RT, RXO
        rt_rxo = sheets.get("RT、RXO")
        if rt_rxo is not None:
            rt_rxo = rt_rxo.apply(pd.to_numeric, errors='coerce').dropna()
            curves.append({
                "name": "RT",
                "unit": "ohm.m", # Assumption
                "data": rt_rxo["RT"].tolist(),
                "depth": rt_rxo["深度"].tolist()
            })
            curves.append({
                "name": "RXO",
                "unit": "ohm.m", # Assumption
                "data": rt_rxo["RXO"].tolist(),
                "depth": rt_rxo["深度"].tolist()
            })
            
        return curves

    def _process_interval_sheet(self, df: Optional[pd.DataFrame], well_name: str, text_col: str) -> List[Dict[str, Any]]:
        if df is None:
            return []
        
        # Basic cleaning
        df = df.copy()
        # Drop rows where '顶深' or '底深' is NaN or not numeric
        df["顶深"] = pd.to_numeric(df["顶深"], errors='coerce')
        df["底深"] = pd.to_numeric(df["底深"], errors='coerce')
        df = df.dropna(subset=["顶深", "底深"])
        
        # Filter by well name (if '井号' column exists)
        if "井号" in df.columns:
            df = df[df["井号"] == well_name]
            
        intervals = []
        for _, row in df.iterrows():
            intervals.append({
                "top": float(row["顶深"]),
                "bottom": float(row["底深"]),
                "name": str(row[text_col]) if text_col in row else ""
            })
        return intervals
