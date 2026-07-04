import json
import glob
from pathlib import Path

samples_dir = Path("/home/kevin/projects/geo-viz-engine/samples")
for path in sorted(samples_dir.glob("test_paleo_*.geojson")):
    print(f"File: {path.name}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    features = data.get("features", [])
    if features:
        print("  Sample properties keys:", list(features[0]["properties"].keys()))
        print("  Sample properties sample:", features[0]["properties"])
        # Print unique values of name/facies/type/class fields
        facies_set = set()
        for feat in features:
            props = feat["properties"]
            for key in ["facies", "name", "type", "class", "sub_facies", "micro_facies"]:
                if key in props:
                    val = props[key]
                    if val:
                        facies_set.add(val)
        print("  Unique names/facies/types/classes count:", len(facies_set))
        print("  Some values:", list(facies_set)[:10])
    print("-" * 40)
