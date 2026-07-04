import json
import base64
import gzip
import re
import os

def unpack_ui():
    ui_html_path = "/home/kevin/projects/geo-viz-engine/UI-REF/UI.html"
    output_dir = "/home/kevin/projects/geo-viz-engine/scratch/unpacked_ui"
    os.makedirs(output_dir, exist_ok=True)
    
    with open(ui_html_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Extract manifest
    manifest_match = re.search(r'<script type="__bundler/manifest">(.*?)</script>', content, re.DOTALL)
    if not manifest_match:
        print("Manifest not found")
        return
    manifest_json = manifest_match.group(1).strip()
    manifest = json.loads(manifest_json)
    
    # Extract template
    template_match = re.search(r'<script type="__bundler/template">(.*?)</script>', content, re.DOTALL)
    if not template_match:
        print("Template not found")
        return
    template_json = template_match.group(1).strip()
    template = json.loads(template_json)
    
    print(f"Found {len(manifest)} assets in manifest.")
    
    # Unpack and decompress assets
    unpacked_assets = {}
    for uuid, entry in manifest.items():
        data_base64 = entry["data"]
        compressed = entry["compressed"]
        mime = entry["mime"]
        
        data_bytes = base64.b64decode(data_base64)
        if compressed:
            try:
                data_bytes = gzip.decompress(data_bytes)
            except Exception as e:
                print(f"Failed to decompress {uuid}: {e}")
                
        # Determine file extension based on mime type
        ext = "txt"
        if "javascript" in mime:
            ext = "js"
        elif "css" in mime:
            ext = "css"
        elif "html" in mime:
            ext = "html"
        elif "svg" in mime:
            ext = "svg"
        elif "png" in mime:
            ext = "png"
            
        asset_filename = f"{uuid}.{ext}"
        asset_filepath = os.path.join(output_dir, asset_filename)
        with open(asset_filepath, "wb") as af:
            af.write(data_bytes)
            
        unpacked_assets[uuid] = {
            "path": asset_filepath,
            "mime": mime,
            "content": data_bytes.decode("utf-8", errors="ignore") if ext in ["js", "css", "html", "svg"] else None
        }
        print(f"Saved asset {uuid} ({mime}) to {asset_filename}")
        
    # Reconstruct the template
    reconstructed_html = template
    for uuid, asset_info in unpacked_assets.items():
        # In the template, we replace uuid with relative path or the asset content if appropriate, 
        # or we just keep it as a reference. Let's write the fully reconstructed html as well!
        if asset_info["content"] is not None and len(asset_info["content"]) < 1000000: # if it's not too huge
            # For CSS/JS, we can embed it, or link to it. Let's link to it.
            # But let's see what the UUID was used for in the template.
            # Usually, the template replaces the UUID with blob URL.
            # We can replace the UUID with the relative path to the unpacked asset!
            reconstructed_html = reconstructed_html.replace(uuid, f"./{uuid}.{ext}")
            
    reconstructed_html_path = os.path.join(output_dir, "index.html")
    with open(reconstructed_html_path, "w", encoding="utf-8") as rf:
        rf.write(reconstructed_html)
    print(f"Reconstructed HTML written to {reconstructed_html_path}")

if __name__ == "__main__":
    unpack_ui()
