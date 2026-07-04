import sys
try:
    import pypdf
except ImportError:
    print("pypdf is not installed. Run with 'uv run --with pypdf python scratch/analyze_pdf.py'")
    sys.exit(1)

pdf_path = "/home/kevin/projects/geo-viz-engine/勘探管理图件图册编制规范.pdf"
reader = pypdf.PdfReader(pdf_path)
print(f"Total pages: {len(reader.pages)}")

keywords = ["沉积相图式", "岩石图式", "附录O", "附录M", "潮坪", "陆棚", "三角洲", "碳酸盐台地", "蒸发盐", "蒸发岩"]

results = {kw: [] for kw in keywords}

# Scan pages for keywords
for page_num in range(len(reader.pages)):
    text = reader.pages[page_num].extract_text()
    if not text:
        continue
    for kw in keywords:
        if kw in text:
            results[kw].append(page_num + 1)  # 1-based page index

for kw, pages in results.items():
    print(f"Keyword '{kw}' found on pages: {pages[:20]} (total: {len(pages)})")
