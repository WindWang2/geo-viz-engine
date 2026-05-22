# Fix: QWebEngineView Black Screen on Windows

## Problem

All QWebEngineView pages (Map, PaleoMap, WellLog, CrossWell) show a black screen
on Windows 11 in both development and packaged (PyInstaller) modes. The seismic
3D page (pyqtgraph.opengl) renders correctly.

**Root cause**: OpenGL context conflict between pyqtgraph's `GLViewWidget`
(`QOpenGLWidget`) and Chromium's GPU process (`QWebEngineView`). On Windows,
Chromium and pyqtgraph compete for the GPU context. Two concrete bugs exacerbate
this:

1. **Wrong initialization order** — `WellLogPage` (QWebEngineView) is created
   before `SeismicPage` (pyqtgraph GLViewWidget), contradicting the code's own
   comment that the GL widget must grab the GPU context first.
2. **No Chromium flags set** — `QTWEBENGINE_CHROMIUM_FLAGS` is never configured,
   so Chromium defaults to hardware GPU compositing which conflicts with
   pyqtgraph's OpenGL context.

## Approach

Fix initialization order + set Chromium compositing flags. Minimal changes,
cross-platform compatible.

## Changes

### 1. `src/main.py` — Chromium flags + diagnostics

Set `QTWEBENGINE_CHROMIUM_FLAGS` before any Qt import on Windows:

```python
if sys.platform == "win32":
    _flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if "--disable-gpu-compositing" not in _flags:
        _flags += " --disable-gpu-compositing"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _flags.strip()
```

Add lightweight GPU diagnostics (stderr only, Windows only):

```python
if sys.platform == "win32":
    gpu_info = subprocess.run(
        ["wmic", "path", "win32_VideoController", "get", "name"],
        capture_output=True, text=True, timeout=5,
    ).stdout.strip()
    print(f"[GeoViz] GPU: {gpu_info}", file=sys.stderr)
    print(f"[GeoViz] Chromium flags: {os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '(none)')}", file=sys.stderr)
```

Existing `AA_ShareOpenGLContexts`, `setGraphicsApi(OpenGL)`, and
`CompatibilityProfile` settings remain unchanged.

### 2. `src/app.py` — Fix page creation order

Reorder page instantiation so all `QOpenGLWidget` (pyqtgraph) pages are created
before any `QWebEngineView` pages:

```
Before: WellLogPage → CrossWellPage → SeismicPage → MapPage → PaleoMapPage
After:  SeismicPage → MapPage → PaleoMapPage → WellLogPage → CrossWellPage
```

Update comments to reference pyqtgraph instead of stale VTK/PyVista.

### 3. Cleanup stale PyVista/VTK references

| File | Change |
|---|---|
| `pyproject.toml` | Remove `"pyvista>=0.43"` dependency |
| `packages/geoviz_seismic/pyproject.toml` | Remove pyvista dependency, update description |
| `packages/geoviz_seismic/__init__.py` | Update docstring: "PyVista 3D rendering" → "pyqtgraph OpenGL" |
| `scripts/build.py` | Remove `--hidden-import pyvistaqt` and `--hidden-import vtkmodules` |
| `CLAUDE.md` | Update all VTK/PyVista references to pyqtgraph + CuPy |

### 4. `CLAUDE.md` — Architecture description update

Replace all references to PyVista/VTK/pyvistaqt with the actual stack:
pyqtgraph.opengl (3D), CuPy (optional GPU compute), QPainter (2D profiles).

## Files Modified

- `src/main.py` — Chromium flags, diagnostics
- `src/app.py` — Page creation order, comment cleanup
- `pyproject.toml` — Remove pyvista dependency
- `packages/geoviz_seismic/pyproject.toml` — Remove pyvista dependency
- `packages/geoviz_seismic/__init__.py` — Update docstring
- `scripts/build.py` — Remove stale hidden imports
- `CLAUDE.md` — Architecture description accuracy

## Testing

- Verify on Windows 11 with integrated GPU (primary target)
- Verify on Windows 11 with discrete GPU
- Verify Linux/macOS still works (flags only applied on Windows)
- Verify MapLibre GL map renders correctly (WebGL)
- Verify well log chart renders correctly (ECharts SVG)
- Verify seismic 3D renders correctly (pyqtgraph OpenGL)
- Verify PyInstaller packaged build still works

## Out of Scope

- Process isolation for WebEngine (over-engineering for current need)
- Full software rendering fallback (`--disable-gpu` would hurt map performance)
- pyqtgraph upgrade or patching
