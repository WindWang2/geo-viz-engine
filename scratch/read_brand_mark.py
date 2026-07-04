with open("/home/kevin/projects/geo-viz-engine/UI-REF/UI.html", "r", encoding="utf-8") as f:
    content = f.read()

import re
matches = [m.start() for m in re.finditer(r"brand-mark", content)]
for idx, pos in enumerate(matches):
    print(f"\nMatch {idx+1} at position {pos}:")
    print(content[max(0, pos-50):pos+400])
