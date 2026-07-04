import sys
import pypdf

pdf_path = "/home/kevin/projects/geo-viz-engine/勘探管理图件图册编制规范.pdf"
reader = pypdf.PdfReader(pdf_path)

has_text = 0
for i in range(len(reader.pages)):
    text = reader.pages[i].extract_text()
    if text and text.strip():
        has_text += 1
        if has_text <= 5:
            print(f"Page {i+1} has text (first 100 chars): {repr(text.strip()[:100])}")

print(f"Total pages with text: {has_text} / {len(reader.pages)}")
