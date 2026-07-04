with open("/home/kevin/projects/geo-viz-engine/UI-REF/UI.html", "r", encoding="utf-8") as f:
    content = f.read()

# Let's print the last 12,000 characters of UI.html
print(content[-12000:])
