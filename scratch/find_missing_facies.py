import json
import re
from pathlib import Path

# Load FACIES_PATTERNS from packages/geoviz_paleo_map/geoviz_paleo_map/style.py
style_path = Path("/home/kevin/projects/geo-viz-engine/packages/geoviz_paleo_map/geoviz_paleo_map/style.py")
with open(style_path, "r", encoding="utf-8") as f:
    style_content = f.read()

# Match all keys inside FACIES_PATTERNS
pattern_keys = re.findall(r'"([^"]+)"\s*:\s*"[^"]+"', style_content)
pattern_keys_set = set(pattern_keys)

# Load FACIES_COLORS from packages/geoviz_well_log/geoviz_well_log/pattern_map.py
pattern_map_path = Path("/home/kevin/projects/geo-viz-engine/packages/geoviz_well_log/geoviz_well_log/pattern_map.py")
with open(pattern_map_path, "r", encoding="utf-8") as f:
    pattern_map_content = f.read()

color_keys = re.findall(r'"([^"]+)"\s*:\s*"#[0-9a-fA-F]+"', pattern_map_content)
color_keys_set = set(color_keys)

# Extract facies, sub-facies, and micro-facies from GeoJSONs
samples_dir = Path("/home/kevin/projects/geo-viz-engine/samples")
all_facies = set()
for path in samples_dir.glob("test_paleo_*.geojson"):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for feat in data.get("features", []):
        f_val = feat["properties"].get("facies")
        if f_val:
            all_facies.add(f_val.strip())

print(f"Total unique facies/sub-facies/micro-facies names in GeoJSONs: {len(all_facies)}")
print("Names missing from FACIES_PATTERNS:")
missing_patterns = all_facies - pattern_keys_set
print(sorted(list(missing_patterns)))

print("\nNames missing from FACIES_COLORS:")
missing_colors = all_facies - color_keys_set
print(sorted(list(missing_colors)))
