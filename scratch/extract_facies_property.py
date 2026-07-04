import json
import glob
from pathlib import Path

samples_dir = Path("/home/kevin/projects/geo-viz-engine/samples")

all_facies = set()
all_sub_facies = set()
all_micro_facies = set()

# Load facies
with open(samples_dir / "test_paleo_facies.geojson", "r", encoding="utf-8") as f:
    facies_data = json.load(f)
for feat in facies_data.get("features", []):
    f_val = feat["properties"].get("facies")
    if f_val:
        all_facies.add(f_val.strip())

# Load sub facies
with open(samples_dir / "test_paleo_sub_facies.geojson", "r", encoding="utf-8") as f:
    sub_data = json.load(f)
for feat in sub_data.get("features", []):
    f_val = feat["properties"].get("facies")
    if f_val:
        all_sub_facies.add(f_val.strip())

# Load micro facies
with open(samples_dir / "test_paleo_micro_facies.geojson", "r", encoding="utf-8") as f:
    micro_data = json.load(f)
for feat in micro_data.get("features", []):
    f_val = feat["properties"].get("facies")
    if f_val:
        all_micro_facies.add(f_val.strip())

print("=== FACIES (相) ===")
print(sorted(list(all_facies)))
print("\n=== SUB-FACIES (亚相) ===")
print(sorted(list(all_sub_facies)))
print("\n=== MICRO-FACIES (微相) ===")
print(sorted(list(all_micro_facies)))
