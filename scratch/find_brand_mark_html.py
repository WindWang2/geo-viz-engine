with open("/home/kevin/projects/geo-viz-engine/UI-REF/UI.html", "r", encoding="utf-8") as f:
    content = f.read()

# Let's search for "brand-mark" in the HTML/JS content, ignoring the CSS stylesheet matches
import re
for m in re.finditer(r"brand-mark", content):
    pos = m.start()
    if pos < 8000000: # Usually the HTML/JS is in the first part, CSS at the end
        print(f"HTML/JS Match at position {pos}:")
        print(content[pos-100:pos+300])
