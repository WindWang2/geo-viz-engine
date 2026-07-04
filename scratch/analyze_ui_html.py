import re

with open("/home/kevin/projects/geo-viz-engine/UI-REF/UI.html", "r", encoding="utf-8") as f:
    content = f.read()

print("File size:", len(content))

# Find all occurrences of svg tags
svgs = re.findall(r"<svg[^>]*>.*?</svg>", content, re.DOTALL | re.IGNORECASE)
print(f"Found {len(svgs)} SVG elements")
for i, svg in enumerate(svgs[:10]):
    print(f"\nSVG {i+1}:")
    print(svg[:500])

# Find any references to 'yellow', 'gold', 'amber', 'orange', 'w.svg', 'well.svg', 'logo'
keywords = ['yellow', 'gold', 'amber', 'orange', 'well.svg', 'logo', 'brand']
for kw in keywords:
    matches = [m.start() for m in re.finditer(kw, content, re.IGNORECASE)]
    print(f"Keyword '{kw}': found {len(matches)} occurrences")
    for pos in matches[:5]:
        start = max(0, pos - 100)
        end = min(len(content), pos + 100)
        print(f"  Context around {pos}: {repr(content[start:end])}")
