import json
import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
import math

from src.data.models import (
    CurveData, FaciesData, IntervalItem, LineStyle, WellCoordinates, WellIntervals, WellLogData,
)

_SENTINEL_VALUES = {-9999, -999.25, -9999.0}

def load_well_coordinates(path: Path) -> list[WellCoordinates]:
    if not path.exists(): return []
    with open(path) as f: raw = json.load(f)
    items = raw.get("wells", []) if isinstance(raw, dict) else raw
    return [WellCoordinates(**{**w, "name": w.get("well_name", w.get("name"))}) for w in items]

def parse_xml_facies(path: Path) -> WellIntervals:
    """Extract facies and sequence from the professional XML sidecar."""
    ns = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
    tree = ET.parse(str(path))
    root = tree.getroot()
    ivs = WellIntervals()
    for ws in root.findall("ss:Worksheet", ns):
        ws_name = ws.get("{urn:schemas-microsoft-com:office:spreadsheet}Name", "")
        table = ws.find("ss:Table", ns)
        if table is None: continue
        rows = table.findall("ss:Row", ns)
        if "文本道" in ws_name:
            for row in rows[1:]:
                cells = row.findall("ss:Cell", ns)
                vals = []
                ci = 0
                for c in cells:
                    ia = c.get("{urn:schemas-microsoft-com:office:spreadsheet}Index")
                    if ia: ci = int(ia) - 1
                    while len(vals) < ci: vals.append(None)
                    de = c.find("ss:Data", ns)
                    vals.append(de.text if de is not None else None)
                    ci += 1
                if len(vals) < 10: continue
                t, n, t1, b1 = vals[1], vals[9], vals[3], vals[6]
                if not t1 or not b1 or not n: continue
                item = IntervalItem(top=float(t1), bottom=float(b1), name=str(n))
                if "微相" in t: ivs.facies.micro_phase.append(item)
                elif "亚相" in t: ivs.facies.sub_phase.append(item)
                elif "沉积相" in t or t == "相": ivs.facies.phase.append(item)
        elif "砂层组道" in ws_name:
             for row in rows[1:]:
                cells = [c.find("ss:Data", ns).text for c in row.findall("ss:Cell", ns) if c.find("ss:Data", ns) is not None]
                if len(cells) < 6: continue
                if "ZJ" in str(cells[2]): ivs.sequence.append(IntervalItem(top=float(cells[3]), bottom=float(cells[6]), name=str(cells[2])))
    return ivs

def load_well_log_laolong1(path: Path, well_name: str | None = None) -> WellLogData:
    import pandas as pd
    
    excel_file = pd.ExcelFile(path)
    sheet_names = excel_file.sheet_names

    def read_interval_sheet(df):
        items = []
        if df is None or df.empty: return items
        cols = df.columns.tolist()
        top_col, bot_col, name_col = None, None, None
        for c in cols:
            c_str = str(c).strip()
            if "顶深" in c_str or "top" in c_str.lower(): top_col = c
            elif "底深" in c_str or "bot" in c_str.lower() or "bottom" in c_str.lower(): bot_col = c
            elif "岩性" in c_str or "文本" in c_str or "name" in c_str.lower() or "相" in c_str or "层号" in c_str: name_col = c
        if top_col is None or bot_col is None:
            if len(cols) >= 3:
                top_col, bot_col, name_col = cols[1], cols[2], cols[0]
        if top_col and bot_col:
            for _, r in df.iterrows():
                try:
                    t, b = float(r[top_col]), float(r[bot_col])
                    if math.isnan(t) or math.isnan(b): continue
                    n = str(r[name_col]) if name_col and not pd.isna(r[name_col]) else ""
                    items.append(IntervalItem(top=t, bottom=b, name=n.strip()))
                except (ValueError, TypeError): continue
        return items

    curves = []
    
    # 1. AC and GR
    if "AC、GR" in sheet_names:
        df = pd.read_excel(path, sheet_name="AC、GR")
        curves.append(CurveData(name="AC", depth=df["深度"].tolist(), values=[(float(v) if v not in _SENTINEL_VALUES else float('nan')) for v in df["AC"].tolist()], color="#1d4ed8", display_range=(40, 100), line_style=LineStyle.SOLID))
        curves.append(CurveData(name="GR", depth=df["深度"].tolist(), values=[(float(v) if v not in _SENTINEL_VALUES else float('nan')) for v in df["GR"].tolist()], color="#15803d", display_range=(0, 150)))
    else:
        if "GR" in sheet_names:
            df = pd.read_excel(path, sheet_name="GR")
            curves.append(CurveData(name="GR", depth=df.iloc[:, 0].tolist(), values=[(float(v) if v not in _SENTINEL_VALUES else float('nan')) for v in df.iloc[:, 1].tolist()], color="#15803d", display_range=(0, 150)))
        if "其他曲线" in sheet_names:
            df = pd.read_excel(path, sheet_name="其他曲线")
            curves.append(CurveData(name="AC", depth=df.iloc[:, 0].tolist(), values=[(float(v) if v not in _SENTINEL_VALUES else float('nan')) for v in df.iloc[:, 1].tolist()], color="#1d4ed8", display_range=(40, 100), line_style=LineStyle.SOLID))

    # 2. RT and RXO
    if "RT、RXO" in sheet_names:
        df = pd.read_excel(path, sheet_name="RT、RXO")
        curves.append(CurveData(name="RT", depth=df["深度"].tolist(), values=[(float(v) if v not in _SENTINEL_VALUES else float('nan')) for v in df["RT"].tolist()], color="#b91c1c", display_range=(0.1, 1000), line_style=LineStyle.SOLID))
        curves.append(CurveData(name="RXO", depth=df["深度"].tolist(), values=[(float(v) if v not in _SENTINEL_VALUES else float('nan')) for v in df["RXO"].tolist()], color="#ea580c", display_range=(0.1, 1000), line_style=LineStyle.DASHED))
    elif "电阻率" in sheet_names:
        df = pd.read_excel(path, sheet_name="电阻率")
        curves.append(CurveData(name="RT", depth=df.iloc[:, 0].tolist(), values=[(float(v) if v not in _SENTINEL_VALUES else float('nan')) for v in df.iloc[:, 1].tolist()], color="#b91c1c", display_range=(0.1, 1000), line_style=LineStyle.SOLID))
        curves.append(CurveData(name="RXO", depth=df.iloc[:, 0].tolist(), values=[(float(v) if v not in _SENTINEL_VALUES else float('nan')) for v in df.iloc[:, 2].tolist()], color="#ea580c", display_range=(0.1, 1000), line_style=LineStyle.DASHED))

    # 3. Intervals
    series = []
    system_intervals = []
    formation = []
    
    if "地层系统" in sheet_names:
        df = pd.read_excel(path, sheet_name="地层系统")
        cols = [str(c).strip() for c in df.columns]
        if "井号" in cols or (not df.empty and len(df.columns) > 0 and any(isinstance(val, str) and "井号" in val for val in df.iloc[:, 0].dropna())):
            all_rows = [df.columns.tolist()] + df.values.tolist()
            block = 0
            for row in all_rows:
                if not row or len(row) < 4: continue
                if str(row[0]).strip() == "井号":
                    block += 1
                    continue
                if block > 3 or pd.isna(row[0]) or pd.isna(row[2]) or pd.isna(row[3]):
                    continue
                try:
                    item = IntervalItem(
                        top=float(row[2]), bottom=float(row[3]),
                        name=str(row[1]).strip(),
                    )
                    if block == 1: series.append(item)
                    elif block == 2: system_intervals.append(item)
                    elif block == 3: formation.append(item)
                except (ValueError, TypeError): continue
        else:
            formation = read_interval_sheet(df)

    lithology = []
    if "岩性剖面" in sheet_names:
        lithology = read_interval_sheet(pd.read_excel(path, sheet_name="岩性剖面"))

    lithology_desc = []
    if "岩性描述" in sheet_names:
        lithology_desc = read_interval_sheet(pd.read_excel(path, sheet_name="岩性描述"))

    micro_phase = []
    if "微相" in sheet_names:
        micro_phase = read_interval_sheet(pd.read_excel(path, sheet_name="微相"))

    sub_phase = []
    if "亚相" in sheet_names:
        sub_phase = read_interval_sheet(pd.read_excel(path, sheet_name="亚相"))

    phase = []
    if "相" in sheet_names:
        phase = read_interval_sheet(pd.read_excel(path, sheet_name="相"))

    systems_tract = []
    sequence = []
    
    if "层序" in sheet_names:
        df = pd.read_excel(path, sheet_name="层序")
        cols = [str(c).strip() for c in df.columns]
        if "井号" in cols or (not df.empty and len(df.columns) > 0 and any(isinstance(val, str) and "井号" in val for val in df.iloc[:, 0].dropna())):
            all_rows = [df.columns.tolist()] + df.values.tolist()
            block = 0
            for row in all_rows:
                if not row or len(row) < 6: continue
                if str(row[0]).strip() == "井号":
                    block += 1
                    continue
                if pd.isna(row[0]) or pd.isna(row[2]) or pd.isna(row[3]):
                    continue
                try:
                    item = IntervalItem(
                        top=float(row[2]), bottom=float(row[3]),
                        name=str(row[5]).strip(),
                    )
                    if block == 1: systems_tract.append(item)
                    elif block == 2: sequence.append(item)
                except (ValueError, TypeError): continue
        else:
            sequence = read_interval_sheet(df)

    intervals = WellIntervals(
        series=series,
        system=system_intervals,
        formation=formation,
        lithology=lithology,
        lithology_desc=lithology_desc,
        systems_tract=systems_tract,
        sequence=sequence,
        facies=FaciesData(
            phase=phase,
            sub_phase=sub_phase,
            micro_phase=micro_phase,
        ),
    )

    # Merge with professional XML data if any exists
    xml_files = sorted(list(path.parent.glob("*.xml")), key=lambda x: len(x.name))
    if xml_files and not phase:
        try:
            xml_ivs = parse_xml_facies(xml_files[0])
            if xml_ivs.facies.phase: intervals.facies = xml_ivs.facies
            if xml_ivs.sequence: intervals.sequence = xml_ivs.sequence
        except Exception: pass

    all_depths = [d for c in curves for d in c.depth if d == d]
    if not all_depths and intervals.lithology:
        all_depths = [iv.top for iv in intervals.lithology] + [iv.bottom for iv in intervals.lithology]
    
    top_d, bot_d = (min(all_depths), max(all_depths)) if all_depths else (0, 1000)

    return WellLogData(
        well_name=well_name or "HZ25-10-1",
        top_depth=top_d,
        bottom_depth=bot_d,
        curves=curves,
        intervals=intervals
    )

def load_well_log_converted(path: Path, well_name: str | None = None) -> WellLogData:
    import pandas as pd
    import numpy as np
    import math

    def get_display_range(vals):
        valid = [v for v in vals if v == v and not math.isinf(v)]
        if not valid:
            return (0, 100)
        mn, mx = min(valid), max(valid)
        if mn == mx:
            mn -= 10
            mx += 10
        return (float(mn), float(mx))

    from src.renderers.well_log.configs.laolong1 import LITHOLOGY_MAPPING, FACIES_MAPPING
    
    def get_pattern_and_color(name, is_facies=False):
        if not name: return "", "#ffffff"
        mapping = FACIES_MAPPING if is_facies else LITHOLOGY_MAPPING
        
        pat = ""
        for k in sorted(mapping.patterns.keys(), key=len, reverse=True):
            if k in name:
                pat = mapping.patterns[k]
                break
                
        col = "#ffffff"
        for k in sorted(mapping.colors.keys(), key=len, reverse=True):
            if k in name:
                col = mapping.colors[k]
                break
                
        return pat, col

    excel_file = pd.ExcelFile(path)
    sheet_names = excel_file.sheet_names

    curves = []
    series = []
    system = []
    formation = []
    member = []
    lithology = []
    lithology_desc = []
    systems_tract = []
    sequence = []
    phase = []
    sub_phase = []
    micro_phase = []
    
    custom_tracks = []
    
    # 1. Depth Track
    custom_tracks.append({"type": "DepthTrack", "name": "深度", "width": 6})

    # 2. Process Curve Sheets
    for s in sheet_names:
        if "测井曲线" in s or "离散曲线" in s:
            try:
                df = pd.read_excel(path, sheet_name=s)
                if df.empty:
                    continue
                cols = df.columns.tolist()
                
                depth_col = None
                for c in cols:
                    if str(c).strip() == "深度":
                        depth_col = c
                        break
                if not depth_col:
                    for c in cols:
                        if "depth" in str(c).lower():
                            depth_col = c
                            break
                    if not depth_col:
                        depth_col = cols[1] if len(cols) > 1 else cols[0]
                        
                depths = [float(x) for x in df[depth_col].tolist()]
                
                for c in cols:
                    c_str = str(c).strip()
                    if c == depth_col or c_str in ("井号", "TVD", "TVDSS", "道名", "道"):
                        continue
                        
                    vals = []
                    for x in df[c].tolist():
                        try:
                            if pd.isna(x) or x in _SENTINEL_VALUES:
                                vals.append(float('nan'))
                            else:
                                vals.append(float(x))
                        except (ValueError, TypeError):
                            vals.append(float('nan'))
                            
                    if not any(v == v for v in vals):
                        continue
                        
                    color = "#15803d"
                    if "GR" in c_str.upper(): color = "#15803d"
                    elif "AC" in c_str.upper() or "DT" in c_str.upper(): color = "#1d4ed8"
                    elif "RT" in c_str.upper() or "RD" in c_str.upper() or "LLD" in c_str.upper(): color = "#b91c1c"
                    elif "RXO" in c_str.upper() or "RS" in c_str.upper() or "LLS" in c_str.upper(): color = "#ea580c"
                    elif "CAL" in c_str.upper(): color = "#d97706"
                    
                    rng = get_display_range(vals)
                    curves.append(CurveData(
                        name=c_str, depth=depths, values=vals,
                        color=color, display_range=rng
                    ))
                    
                    curve_data = [[d, (v if not math.isnan(v) else None)] for d, v in zip(depths, vals)]
                    custom_tracks.append({
                        "type": "CurveTrack",
                        "name": c_str,
                        "width": 14,
                        "series": [{
                            "name": c_str,
                            "color": color,
                            "lineStyle": "solid",
                            "rangeLabel": f"{rng[0]} - {rng[1]}",
                            "data": curve_data
                        }]
                    })
            except Exception as e:
                print(f"Error processing sheet {s}: {e}")
                
    # Helper to read child interval sheets
    def read_child_sheet(df, default_name):
        items_dict = {}
        if df is None or df.empty:
            return items_dict
        cols = df.columns.tolist()
        
        top_col, bot_col, name_col, track_col = None, None, None, None
        
        for c in cols:
            if "道名" in str(c).strip():
                track_col = c
                break

        # 1. Precise match for top/bottom
        for c in cols:
            c_str = str(c).strip()
            if c_str in ("顶深", "顶界", "top"): top_col = c
            elif c_str in ("底深", "底界", "bottom"): bot_col = c
            
        # 2. Substring match for top/bottom (avoid TVD)
        if not top_col or not bot_col:
            for c in cols:
                c_str = str(c).strip().lower()
                if "tvd" in c_str: continue
                if not top_col and ("顶" in c_str or "top" in c_str): top_col = c
                elif not bot_col and ("底" in c_str or "bot" in c_str): bot_col = c

        # 3. Fallback to just "深" or "depth"
        if not top_col or not bot_col:
            for c in cols:
                c_str = str(c).strip().lower()
                if "tvd" in c_str: continue
                if "深" in c_str or "depth" in c_str:
                    if not top_col: top_col = c
                    elif not bot_col and c != top_col: bot_col = c

        # 4. Determine name column
        for k in ("文本", "层号", "层名", "岩性", "名称", "name", "相类型", "说明", "取心", "符号"):
            for c in cols:
                if str(c).strip() == k:
                    if c != top_col and c != bot_col and c != track_col:
                        name_col = c
                        break
            if name_col:
                break
                    
        if not name_col:
            for c in cols:
                c_str = str(c).strip()
                if any(k in c_str for k in ("岩性", "文本", "层", "相", "名", "name", "符号")):
                    if c != top_col and c != bot_col and c != track_col and "井号" not in c_str:
                        name_col = c
                        break
                        
        if not name_col:
            for c in cols:
                if c != top_col and c != bot_col and c != track_col and "井号" not in str(c):
                    name_col = c
                    break
                    
        if not top_col and bot_col:
            top_col = bot_col
        elif not bot_col and top_col:
            bot_col = top_col

        if top_col and bot_col:
            for _, r in df.iterrows():
                try:
                    t, b = float(r[top_col]), float(r[bot_col])
                    if math.isnan(t) or math.isnan(b):
                        continue
                    n = str(r[name_col]) if name_col and not pd.isna(r[name_col]) else ""
                    tn = str(r[track_col]).strip() if track_col and not pd.isna(r[track_col]) else default_name
                    if not tn: tn = default_name
                    
                    if tn not in items_dict:
                        items_dict[tn] = []
                    items_dict[tn].append(IntervalItem(top=t, bottom=b, name=n.strip()))
                except (ValueError, TypeError):
                    continue
        return items_dict

    for s in sheet_names:
        if "测井曲线" in s or "离散曲线" in s or "坐标" in s:
            continue
            
        try:
            df = pd.read_excel(path, sheet_name=s)
            if df.empty:
                continue
                
            items_dict = read_child_sheet(df, s)
            if not items_dict:
                continue
                
            for tn, items in items_dict.items():
                if not items:
                    continue
                    
                if "岩性道" in tn or "岩性" in tn or "岩性" in s:
                    lithology.extend(items)
                elif "砂层" in tn or "砂层" in s:
                    sequence.extend(items)
                elif "段" in tn:
                    member.extend(items)
                elif "地层单位" in tn or "组" in tn:
                    formation.extend(items)
                elif "油层" in tn or "油层" in s:
                    series.extend(items)
                elif "微相" in tn:
                    micro_phase.extend(items)
                elif "亚相" in tn:
                    sub_phase.extend(items)
                elif "相" in tn:
                    phase.extend(items)
                elif "解释分层" in tn or "解释" in s:
                    system.extend(items)
                elif "储量单元" in tn or "标准层" in s:
                    systems_tract.extend(items)
                else:
                    lithology_desc.extend(items)
                    
                apply_pattern = "岩性" in tn or "相" in tn or "岩性" in s or "相" in s
                track_type = "LithologyTrack" if "岩性" in tn or "岩性" in s else "IntervalTrack"
                
                # Apply grouping and renaming
                display_name = tn
                parent_group = ""
                
                if "相" in tn or "相" in s:
                    if "测试" not in tn and "结论" not in tn:
                        parent_group = "沉积相"
                        display_name = tn.replace("沉积", "") # 沉积相->相, 沉积亚相->亚相
                        
                if "单位" in s or tn in ("系", "统", "组", "段", "底层系统", "地层系统"):
                    parent_group = "地层系统"

                track = {
                    "type": track_type,
                    "name": display_name,
                    "width": 12 if "描述" in tn or "结论" in tn else 8,
                    "textOrientation": "vertical" if any(k in tn for k in ("组", "段", "相", "界")) else "horizontal",
                    "data": []
                }
                
                is_facies = parent_group == "沉积相"
                for i in items:
                    pat, col = "", "#ffffff"
                    if apply_pattern:
                        pat, col = get_pattern_and_color(i.name, is_facies)
                        
                    if track_type == "LithologyTrack" and col == "#ffffff":
                        col = "#cbd5e0"
                    elif col == "#ffffff" and is_facies:
                        col = "#ecfeff" # fallback for facies

                    track["data"].append({
                        "top": i.top,
                        "bottom": i.bottom,
                        "name": i.name,
                        "color": col,
                        "lithology": pat
                    })
                
                if parent_group:
                    track["parentGroup"] = parent_group
                    track["group"] = parent_group
                
                custom_tracks.append(track)
        except Exception as e:
            print(f"Error processing child sheet {s}: {e}")
            
    intervals = WellIntervals(
        series=series,
        system=system,
        formation=formation,
        member=member,
        lithology=lithology,
        lithology_desc=lithology_desc,
        systems_tract=systems_tract,
        sequence=sequence,
        facies=FaciesData(
            phase=phase,
            sub_phase=sub_phase,
            micro_phase=micro_phase,
        ),
    )
    
    all_depths = [d for c in curves for d in c.depth if d == d]
    if not all_depths and intervals.lithology:
        all_depths = [iv.top for iv in intervals.lithology] + [iv.bottom for iv in intervals.lithology]
        
    top_d, bot_d = (min(all_depths), max(all_depths)) if all_depths else (0, 1000)

    return WellLogData(
        well_name=well_name or "NewWell",
        top_depth=top_d,
        bottom_depth=bot_d,
        curves=curves,
        intervals=intervals,
        custom_tracks=custom_tracks
    )

def load_well_log_from_excel(path: Path, well_name: str | None = None, xml_path: Path | None = None) -> WellLogData:
    import pandas as pd
    excel_file = pd.ExcelFile(path)
    sheet_names = excel_file.sheet_names
    
    if any("测井曲线" in s or "离散曲线" in s or "岩性道" in s or "地层单位" in s for s in sheet_names):
        return load_well_log_converted(path, well_name)
    else:
        return load_well_log_laolong1(path, well_name)



