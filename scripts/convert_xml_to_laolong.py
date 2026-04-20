"""Convert HZ25-10-1 well logging XML (Excel XML format) to LaoLong1-style XLS format."""
import xml.etree.ElementTree as ET
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional

NS = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}

def parse_xml(xml_path: str) -> Dict:
    """Parse the XML Excel file and extract all data."""
    worksheets: Dict[str, List[List[Optional[str]]]] = {}
    current_ws: Optional[str] = None
    current_rows: List[List[Optional[str]]] = []

    for event, elem in ET.iterparse(xml_path, events=('start', 'end')):
        if event == 'start' and elem.tag.endswith('Worksheet'):
            current_ws = elem.get('{urn:schemas-microsoft-com:office:spreadsheet}Name')
            current_rows = []
        elif event == 'end' and elem.tag.endswith('Worksheet'):
            if current_ws:
                worksheets[current_ws] = current_rows
            current_ws = None
        elif current_ws is not None and event == 'end' and elem.tag.endswith('Row'):
            row: List[Optional[str]] = []
            for cell in elem.findall('./ss:Cell/ss:Data', NS):
                row.append(cell.text if cell.text is not None else '')
            current_rows.append(row)

    return worksheets

def extract_curves(ws_data: List[List[Optional[str]]]) -> pd.DataFrame:
    """Extract curves data into a DataFrame."""
    # First row is header
    header = ws_data[0] if ws_data else []
    rows = ws_data[1:] if len(ws_data) > 1 else []

    # Convert to list of dicts
    data = []
    for row in rows:
        row_dict = {}
        for i, col_name in enumerate(header):
            if i >= len(row):
                row_dict[col_name] = None
            else:
                val = row[i]
                # Try to convert to float if numeric
                if val and val.strip():
                    try:
                        row_dict[col_name] = float(val)
                    except ValueError:
                        row_dict[col_name] = val
                else:
                    row_dict[col_name] = None
        data.append(row_dict)

    df = pd.DataFrame(data)
    # Drop rows where depth is None
    if '深度' in df.columns:
        df = df.dropna(subset=['深度'])
        # Sort by depth
        df = df.sort_values('深度').reset_index(drop=True)

    return df

def extract_intervals(ws_data: List[List[Optional[str]]],
                       top_col: str = '顶深',
                       bottom_col: str = '底深',
                       name_col: str = '岩性') -> List[Dict]:
    """Extract interval data (lithology, stratigraphy)."""
    if not ws_data or len(ws_data) < 2:
        return []

    header = ws_data[0]
    rows = ws_data[1:]

    # Find column indices
    col_idx = {name: i for i, name in enumerate(header)}
    if top_col not in col_idx or bottom_col not in col_idx:
        return []

    intervals = []
    for row in rows:
        try:
            if col_idx[top_col] >= len(row) or col_idx[bottom_col] >= len(row):
                continue
            top_val = row[col_idx[top_col]]
            bottom_val = row[col_idx[bottom_col]]
            if top_val is None or bottom_val is None or top_val == '' or bottom_val == '':
                continue
            top = float(top_val)
            bottom = float(bottom_val)
            name_val = ''
            if name_col in col_idx and col_idx[name_col] < len(row):
                name_val = row[col_idx[name_col]]
            name = str(name_val).strip() if name_val else ''
            if name:
                intervals.append({
                    'top': top,
                    'bottom': bottom,
                    'name': name
                })
        except (ValueError, TypeError, IndexError):
            continue

    return intervals

def extract_stratigraphy(ws_data: List[List[Optional[str]]]) -> Dict[str, List[Dict]]:
    """Extract stratigraphy by type (组 = formation, 段 = member)."""
    if not ws_data or len(ws_data) < 2:
        return {'formation': [], 'member': []}

    header = ws_data[0]
    rows = ws_data[1:]
    col_idx = {name: i for i, name in enumerate(header)}

    result = {'formation': [], 'member': []}

    for row in rows:
        try:
            if '道名' not in col_idx:
                continue
            if col_idx['道名'] >= len(row):
                continue
            dao_ming = row[col_idx['道名']]
            if '层号' not in col_idx or '顶深' not in col_idx or '底深' not in col_idx:
                continue
            if col_idx['层号'] >= len(row) or col_idx['顶深'] >= len(row) or col_idx['底深'] >= len(row):
                continue

            ceng_hao = row[col_idx['层号']]
            top_val = row[col_idx['顶深']]
            bottom_val = row[col_idx['底深']]

            if top_val is None or bottom_val is None or top_val == '' or bottom_val == '':
                continue

            top = float(top_val)
            bottom = float(bottom_val)
            name = str(ceng_hao).strip() if ceng_hao else ''

            if not name:
                continue

            interval = {'top': top, 'bottom': bottom, 'name': name}

            if dao_ming == '组':
                result['formation'].append(interval)
            elif dao_ming == '段':
                result['member'].append(interval)
        except (ValueError, TypeError, IndexError):
            continue

    return result

def convert_to_laolong_xls(xml_path: str, output_xls_path: str):
    """Convert XML to LaoLong1-style XLS file."""
    print(f"Parsing XML: {xml_path}")
    worksheets = parse_xml(xml_path)

    print(f"Found worksheets: {list(worksheets.keys())}")

    # Extract curves
    curves_df = extract_curves(worksheets.get('测井曲线-HZ25-10-1井', []))
    print(f"Curves: {len(curves_df)} rows, columns: {list(curves_df.columns)}")
    print(f"Depth range: {curves_df['深度'].min():.2f} - {curves_df['深度'].max():.2f}")

    # Extract lithology
    lithology_intervals = extract_intervals(worksheets.get('岩性道', []),
                                           top_col='顶深', bottom_col='底深', name_col='岩性')
    print(f"Lithology intervals: {len(lithology_intervals)}")

    # Extract stratigraphy
    strat = extract_stratigraphy(worksheets.get('地层单位道', []))
    print(f"Stratigraphy - formations: {len(strat['formation'])}, members: {len(strat['member'])}")

    # Create Excel writer
    with pd.ExcelWriter(output_xls_path, engine='openpyxl') as writer:

        # --- Split curves into sheets matching LaoLong1 format ---
        # Sheet 1: GR (we'll put GR here, similar to AC+GR in LaoLong1)
        if '深度' in curves_df.columns and 'GR' in curves_df.columns:
            gr_df = curves_df[['深度', 'GR']].dropna(subset=['GR'])
            gr_df.columns = ['深度', 'GR']
            gr_df.to_excel(writer, sheet_name='GR', index=False)
            print(f"Wrote GR sheet: {len(gr_df)} rows")

        # Sheet 2: Resistivity curves (R39AC, R15PC, R27PC, R39PC)
        resis_cols = ['深度']
        resis_cols.extend([col for col in ['R39AC', 'R15PC', 'R27PC', 'R39PC'] if col in curves_df.columns])
        if len(resis_cols) > 1:
            resis_df = curves_df[resis_cols].dropna(subset=resis_cols[1:], how='all')
            resis_df.to_excel(writer, sheet_name='电阻率', index=False)
            print(f"Wrote 电阻率 sheet: {len(resis_df)} rows, curves: {resis_cols[1:]}")

        # Sheet 3: Porosity, density, neutron, PE
        poro_cols = ['深度']
        poro_cols.extend([col for col in ['孔隙度', '渗透率', '含水饱和度', 'RHOB', 'TNPH', 'PE'] if col in curves_df.columns])
        if len(poro_cols) > 1:
            poro_df = curves_df[poro_cols].dropna(subset=poro_cols[1:], how='all')
            poro_df.to_excel(writer, sheet_name='孔隙度', index=False)
            print(f"Wrote 孔隙度 sheet: {len(poro_df)} rows")

        # Other curves (CALI, BS) go to extra sheet
        other_cols = ['深度']
        other_cols.extend([col for col in ['CALI', 'BS'] if col in curves_df.columns])
        if len(other_cols) > 1:
            other_df = curves_df[other_cols].dropna(subset=other_cols[1:], how='all')
            other_df.to_excel(writer, sheet_name='其他曲线', index=False)
            print(f"Wrote 其他曲线 sheet: {len(other_df)} rows")

        # --- Stratigraphy system sheet ---
        # Format matches LaoLong1: 层号 | 顶深 | 底深 in groups
        # We group by: 1. series (empty - none), 2. system (empty - none), 3. formation (组), 4. member (段)
        strat_rows = []
        # Formations (组)
        for f in strat['formation']:
            strat_rows.append({'层号': f['name'], '顶深': f['top'], '底深': f['bottom'], '文本': f['name']})
        # Empty separator row
        if strat_rows:
            strat_rows.append({'层号': None, '顶深': None, '底深': None, '文本': None})
        # Members (段)
        for m in strat['member']:
            strat_rows.append({'层号': m['name'], '顶深': m['top'], '底深': m['bottom'], '文本': m['name']})

        if strat_rows:
            strat_df = pd.DataFrame(strat_rows)
            strat_df.to_excel(writer, sheet_name='地层系统', index=False)
            print(f"Wrote 地层系统 sheet: {len(strat_rows)} rows")

        # --- Lithology profile ---
        litho_rows = []
        for litho in lithology_intervals:
            litho_rows.append({
                '岩性': litho['name'],
                '顶深': litho['top'],
                '底深': litho['bottom'],
                '文本': litho['name']
            })
        if litho_rows:
            litho_df = pd.DataFrame(litho_rows)
            litho_df.to_excel(writer, sheet_name='岩性剖面', index=False)
            print(f"Wrote 岩性剖面 sheet: {len(litho_rows)} rows")

        # --- Lithology description (same as lithology for now) ---
        if litho_rows:
            desc_df = pd.DataFrame(litho_rows)
            desc_df.to_excel(writer, sheet_name='岩性描述', index=False)

        # --- Create empty sheets for facies/sequence that we don't have data for ---
        # Still include them for compatibility with loader
        pd.DataFrame().to_excel(writer, sheet_name='微相', index=False)
        pd.DataFrame().to_excel(writer, sheet_name='亚相', index=False)
        pd.DataFrame().to_excel(writer, sheet_name='相', index=False)
        pd.DataFrame().to_excel(writer, sheet_name='层序', index=False)

    print(f"\nConversion complete! Output saved to: {output_xls_path}")
    return output_xls_path

if __name__ == '__main__':
    xml_path = '/home/kevin/projects/geo-viz-engine/data/25-HZ25-10-1井单井综合柱状图-2019-沉积室-勘探室-无地化录井-测井.xml'
    output_path = '/home/kevin/projects/geo-viz-engine/data/HZ25-10-1-laolong.xls'
    convert_to_laolong_xls(xml_path, output_path)
