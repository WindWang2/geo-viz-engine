import pandas as pd
import os
from typing import Dict, List, Any, Optional

class WellDataService:
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            # Data directory is at project root/data
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
            self.data_dir = os.path.join(base_dir, "data")
        else:
            self.data_dir = os.path.abspath(data_dir)
        self._cache: Dict[str, Dict[str, pd.DataFrame]] = {}

    def _get_excel_path(self, well_name: str) -> str:
        """Get the expected Excel path for a well: {well_name}-laolong.xls"""
        # Try both naming patterns: wellName-laolong.xls and well_name-laolong.xls
        candidates = [
            os.path.join(self.data_dir, f"{well_name}-laolong.xls"),
            os.path.join(self.data_dir, f"{well_name.replace('-', '')}-laolong.xls"),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        # If no match, raise
        raise FileNotFoundError(
            f"Well data file not found for '{well_name}'. "
            f"Tried: {', '.join(candidates)}. "
            f"Place the XLS file in data directory with name: {well_name}-laolong.xls"
        )

    def _load_sheets(self, well_name: str) -> Dict[str, pd.DataFrame]:
        """Load sheets from the appropriate Excel file for this well (cached)."""
        if well_name not in self._cache:
            excel_path = self._get_excel_path(well_name)
            self._cache[well_name] = pd.read_excel(excel_path, sheet_name=None)
        return self._cache[well_name]

    def get_well_details(self, well_name: str) -> Dict[str, Any]:
        # Special case: 老龙1 uses the custom loader
        if well_name == '老龙1' or well_name == '老龙1井' or well_name.lower() == 'laolong1':
            from app.services.laolong1_loader import load_laolong1
            data = load_laolong1()
            # Convert WellLogData to WellDetailData format
            curves = []
            for c in data.curves:
                curves.append({
                    'name': c.name,
                    'unit': c.unit,
                    'data': c.data,
                    'depth': c.depth,
                })
            intervals = {
                'series': [{'top': i.top, 'bottom': i.bottom, 'name': i.name} for i in (data.intervals.series if data.intervals else [])],
                'system': [{'top': i.top, 'bottom': i.bottom, 'name': i.name} for i in (data.intervals.system if data.intervals else [])],
                'formation': [{'top': i.top, 'bottom': i.bottom, 'name': i.name} for i in (data.intervals.formation if data.intervals else [])],
                'member': [{'top': i.top, 'bottom': i.bottom, 'name': i.name} for i in (data.intervals.member if data.intervals else [])],
                'lithology': [{'top': i.top, 'bottom': i.bottom, 'name': i.name} for i in (data.intervals.lithology if data.intervals else [])],
                'systems_tract': [{'top': i.top, 'bottom': i.bottom, 'name': i.name} for i in (data.intervals.systems_tract if data.intervals else [])],
                'sequence': [{'top': i.top, 'bottom': i.bottom, 'name': i.name} for i in (data.intervals.sequence if data.intervals else [])],
                'facies': {
                    'phase': [{'top': i.top, 'bottom': i.bottom, 'name': i.name} for i in (data.intervals.facies.phase if data.intervals and data.intervals.facies else [])],
                    'sub_phase': [{'top': i.top, 'bottom': i.bottom, 'name': i.name} for i in (data.intervals.facies.sub_phase if data.intervals and data.intervals.facies else [])],
                    'micro_phase': [{'top': i.top, 'bottom': i.bottom, 'name': i.name} for i in (data.intervals.facies.micro_phase if data.intervals and data.intervals.facies else [])],
                },
            }
            return {
                'well_id': data.well_id,
                'well_name': data.well_name,
                'curves': curves,
                'intervals': intervals,
            }

        sheets = self._load_sheets(well_name)

        # 1. Metadata (simple for now)
        data = {
            "well_id": well_name, # Use name as ID for now
            "well_name": well_name,
            "curves": [],
            "intervals": {}
        }

        # 2. Process Curves
        curve_data = self._process_curves(sheets)
        data["curves"] = curve_data

        # 3. Process Intervals
        # Stratigraphy: Handle stacked tables in '地层系统'
        strat_df = sheets.get("地层系统")
        if strat_df is not None and not strat_df.empty:
            # The file we created puts all formations first then members
            # Split into groups based on empty rows
            empty_rows = strat_df[strat_df['层号'].isna()].index
            if len(empty_rows) > 0:
                first_empty = empty_rows[0]
                formations_df = strat_df.iloc[:first_empty]
                members_df = strat_df.iloc[first_empty+1:]
            else:
                formations_df = strat_df
                members_df = pd.DataFrame()

            data["intervals"]["series"] = []
            data["intervals"]["system"] = []
            data["intervals"]["formation"] = self._process_interval_sheet(formations_df, well_name, "层号")
            data["intervals"]["member"] = self._process_interval_sheet(members_df, well_name, "层号")
        else:
            data["intervals"]["series"] = []
            data["intervals"]["system"] = []
            data["intervals"]["formation"] = []
            data["intervals"]["member"] = []

        # Sequence: Handle stacked tables in '层序'
        seq_df = sheets.get("层序")
        if seq_df is not None and not seq_df.empty:
            # Table 1: Systems Tract (体系域 - HST/TST)
            data["intervals"]["systems_tract"] = self._process_interval_sheet(seq_df, well_name, "文本")
            # Table 2: Sequence (层序 - SQ1/SQ2)
            data["intervals"]["sequence"] = []
        else:
            data["intervals"]["systems_tract"] = []
            data["intervals"]["sequence"] = []

        data["intervals"]["lithology"] = self._process_interval_sheet(sheets.get("岩性剖面"), well_name, "岩性")
        # We also have lithology description in 岩性描述 sheet
        if data["intervals"]["lithology"] == [] and sheets.get("岩性描述") is not None:
            data["intervals"]["lithology"] = self._process_interval_sheet(sheets.get("岩性描述"), well_name, "岩性")

        # Facies (merge phase, sub-phase, micro-phase - empty for this well)
        data["intervals"]["facies"] = {
            "phase": self._process_interval_sheet(sheets.get("相"), well_name, "文本"),
            "sub_phase": self._process_interval_sheet(sheets.get("亚相"), well_name, "文本"),
            "micro_phase": self._process_interval_sheet(sheets.get("微相"), well_name, "文本")
        }

        return data

    def _process_curves(self, sheets: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        curves = []

        # GR (natural gamma ray)
        gr_sheet = sheets.get("GR")
        if gr_sheet is not None and not gr_sheet.empty:
            gr_sheet = gr_sheet.apply(pd.to_numeric, errors='coerce').dropna(subset=["深度", "GR"])
            if "深度" in gr_sheet.columns and "GR" in gr_sheet.columns:
                curves.append({
                    "name": "GR",
                    "unit": "API",
                    "data": gr_sheet["GR"].tolist(),
                    "depth": gr_sheet["深度"].tolist()
                })

        # Resistivity curves
        res_sheet = sheets.get("电阻率")
        if res_sheet is not None and not res_sheet.empty:
            res_sheet = res_sheet.apply(pd.to_numeric, errors='coerce').dropna(subset=["深度"])
            for col in ["R39AC", "R15PC", "R27PC", "R39PC"]:
                if col in res_sheet.columns and not res_sheet[col].isna().all():
                    curves.append({
                        "name": col,
                        "unit": "ohm.m",
                        "data": res_sheet[col].tolist(),
                        "depth": res_sheet["深度"].tolist()
                    })

        # Porosity, permeability, water saturation, RHOB, TNPH, PE
        poro_sheet = sheets.get("孔隙度")
        if poro_sheet is not None and not poro_sheet.empty:
            poro_sheet = poro_sheet.apply(pd.to_numeric, errors='coerce').dropna(subset=["深度"])
            curve_map = {
                "孔隙度": ("孔隙度", "v/v"),
                "渗透率": ("渗透率", "mD"),
                "含水饱和度": ("含水饱和度", "v/v"),
                "RHOB": ("RHOB", "g/cc"),
                "TNPH": ("TNPH", "v/v"),
                "PE": ("PE", "b/e"),
            }
            for col, (name, unit) in curve_map.items():
                if col in poro_sheet.columns and not poro_sheet[col].isna().all():
                    curves.append({
                        "name": name,
                        "unit": unit,
                        "data": poro_sheet[col].tolist(),
                        "depth": poro_sheet["深度"].tolist()
                    })

        # Other curves (CALI, BS)
        other_sheet = sheets.get("其他曲线")
        if other_sheet is not None and not other_sheet.empty:
            other_sheet = other_sheet.apply(pd.to_numeric, errors='coerce').dropna(subset=["深度"])
            for col in ["CALI", "BS"]:
                if col in other_sheet.columns and not other_sheet[col].isna().all():
                    curves.append({
                        "name": col,
                        "unit": "in",
                        "data": other_sheet[col].tolist(),
                        "depth": other_sheet["深度"].tolist()
                    })

        # For backwards compatibility, check original sheet names
        if "AC、GR" in sheets:
            ac_gr = sheets.get("AC、GR")
            if ac_gr is not None and not ac_gr.empty:
                ac_gr = ac_gr.apply(pd.to_numeric, errors='coerce').dropna()
                if "AC" in ac_gr.columns:
                    curves.append({
                        "name": "AC",
                        "unit": "us/ft",
                        "data": ac_gr["AC"].tolist(),
                        "depth": ac_gr["深度"].tolist()
                    })
                if "GR" in ac_gr.columns and not any(c["name"] == "GR" for c in curves):
                    curves.append({
                        "name": "GR",
                        "unit": "API",
                        "data": ac_gr["GR"].tolist(),
                        "depth": ac_gr["深度"].tolist()
                    })

        if "RT、RXO" in sheets:
            rt_rxo = sheets.get("RT、RXO")
            if rt_rxo is not None and not rt_rxo.empty:
                rt_rxo = rt_rxo.apply(pd.to_numeric, errors='coerce').dropna()
                if "RT" in rt_rxo.columns:
                    curves.append({
                        "name": "RT",
                        "unit": "ohm.m",
                        "data": rt_rxo["RT"].tolist(),
                        "depth": rt_rxo["深度"].tolist()
                    })
                if "RXO" in rt_rxo.columns:
                    curves.append({
                        "name": "RXO",
                        "unit": "ohm.m",
                        "data": rt_rxo["RXO"].tolist(),
                        "depth": rt_rxo["深度"].tolist()
                    })

        return curves

    def _process_interval_sheet(self, df: Optional[pd.DataFrame], well_name: str, text_col: str) -> List[Dict[str, Any]]:
        if df is None:
            return []
        if df.empty:
            return []
        if "顶深" not in df.columns or "底深" not in df.columns:
            return []

        # Basic cleaning
        df = df.copy()
        # Drop rows where '顶深' or '底深' is NaN or not numeric
        df["顶深"] = pd.to_numeric(df["顶深"], errors='coerce')
        df["底深"] = pd.to_numeric(df["底深"], errors='coerce')
        df = df.dropna(subset=["顶深", "底深"])

        if df.empty:
            return []

        # Filter by well name (if '井号' column exists)
        if "井号" in df.columns:
            df = df[df["井号"] == well_name]

        if df.empty:
            return []

        intervals = []
        for _, row in df.iterrows():
            name = ""
            if text_col in row:
                name = str(row[text_col]) if not pd.isna(row[text_col]) else ""
            intervals.append({
                "top": float(row["顶深"]),
                "bottom": float(row["底深"]),
                "name": name
            })
        return intervals
