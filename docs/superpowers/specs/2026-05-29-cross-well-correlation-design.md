# Cross-Well Correlation Panel — Design Spec

**Date:** 2026-05-29  
**Status:** Approved  
**Branch target:** feat/cross-well-correlation  
**Version:** v0.8.0  

---

## Problem Statement

GeoViz Engine's CrossWellPage displays correlated well logs using QPainter (via `geoviz_well_log.CrossWellWidget`), but provides no professional picking workflow — no formation tops database, no manual horizon picking with undo/redo, no DTW auto-correlation, and no seismic tie. Geological engineers who currently pay for Petrel or Kingdom to do simple multi-well correlation have no open-source, native-desktop alternative.

GeoViz Engine is already the right architecture (PySide6 desktop, QPainter-based pages) for the geoscience community. The gap to fill: a professional picking workflow layered on top of the existing QPainter cross-well renderer, delivered as a new `geoviz-cross-well` package that composes `geoviz_well_log.WellLogCanvas` for rendering and adds formation tops, horizon picks, DTW auto-correlation, and seismic tie.

## EUREKA

**Everyone builds geo tools for Python/Jupyter users (welly, striplog, bruges).** But geological engineers — especially in Chinese oil industry workflows — use Qt desktop apps and don't write code. No open-source tool has a native-feeling, click-to-pick correlation panel with formation tops + DTW auto-correlation. GeoViz Engine is uniquely positioned to own this.

---

## Scope (v0.8.0)

### In Scope

1. **CrossWell Canvas (composition)** — new `CrossWellCanvas` composes `geoviz_well_log.WellLogCanvas` for rendering
   - Multi-well layout: each well gets a track column (depth ruler + selected curves) — handled by WellLogCanvas
   - Zoom/pan on depth axis (synchronized via QPainterSyncManager) — handled by existing ZoomPanHandler
   - Picking overlay: transparent widget on top of CrossWellWidget for pick placement and correlation ties
   - Correlation ties: draggable bezier curves connecting picked horizons across wells
   - Style: light theme consistent with existing CrossWellPage (D9)

2. **Formation Tops Database**
   - Load tops from CSV (`well_name, formation_name, depth_m`)
   - Tops shown as horizontal dashed lines with labels on each well's depth track
   - Click a top to select/delete; drag to adjust depth
   - Save/export tops to CSV

3. **Manual Horizon Picking**
   - Click on a log curve to place a pick at a depth
   - Connect picks across wells with a rubber-band correlation tie line
   - Picks colored by formation group
   - Undo/redo stack (QUndoStack, consistent with PaleoMapPage edit commands)

4. **DTW Auto-Correlation (enhancement layer)**
   - On demand: "Auto-correlate from [reference well]" button
   - Algorithm: Dynamic Time Warping on GR curve (primary), resistivity optional
   - Output: suggested picks shown as ghost lines, user accepts/rejects each
   - Confidence bands shown around suggestions (width = DTW cost)

5. **Seismic Tie (basic)**
   - Load checkshot CSV (`depth_m, twt_ms`) per well
   - Convert LAS depth log to TWT using T-D curve
   - Show dual axis (depth + time) on each well track
   - Does not display seismic section (that's SeismicPage scope)

### Out of Scope (v0.8.0)

- Migrating WellLogPage from ECharts (stays as-is)
- 3D visualization of picks
- Automatic wavelet extraction or synthetic seismograms
- Direct connection to SeismicPage's OpenGL volume

---

## Architecture

### Package: `geoviz-cross-well` (new, in `packages/`)

```
packages/geoviz_cross_well/
├── geoviz_cross_well/
│   ├── __init__.py
│   ├── canvas.py              # CrossWellCanvas — composes CrossWellWidget + picking layers
│   ├── tops_model.py          # FormationTopsModel — tops database + I/O
│   ├── picks_model.py         # HorizonPicksModel — pick data + undo/redo
│   ├── correlation_layer.py   # CorrelationLayer — bezier tie lines between picks
│   ├── dtw_engine.py          # DTWEngine — DTW correlation algorithm
│   └── seismic_tie.py         # SeismicTie — checkshot T-D conversion
├── tests/
│   ├── test_tops_model.py
│   ├── test_picks_model.py
│   ├── test_dtw_engine.py
│   └── test_cross_well_canvas.py
└── pyproject.toml
```

**Composition:** `CrossWellCanvas` wraps `geoviz_well_log.CrossWellWidget` for multi-well layout and `geoviz_well_log.WellLogCanvas` for per-well track/curve rendering. No track.py, curve_layer.py, or viewport.py — those are handled by geoviz_well_log. The new package only adds picking-specific modules.

### Modified Files

| File | Change |
|------|--------|
| `src/pages/cross_well_page.py` | Replace ECharts + QWebEngineView with CrossWellCanvas |
| `src/app.py` | Update import |
| `pyproject.toml` (root) | Add `geoviz-cross-well` to workspace dependencies |

---

## Data Model

### CrossWellViewport
```python
@dataclass
class CrossWellViewport:
    wells: list[str]          # ordered well names
    depth_min: float          # metres (TVDSS or MD)
    depth_max: float
    depth_domain: str         # "MD" | "TVDSS" | "TWT"
    width: int                # pixels
    height: int

    @property
    def depth_scale(self) -> float:
        """px per metre"""
        return self.height / (self.depth_max - self.depth_min)

    def world_to_y(self, depth: float) -> float:
        return (depth - self.depth_min) * self.depth_scale

    def y_to_world(self, y: float) -> float:
        return self.depth_min + y / self.depth_scale
```

Note: Depth range and zoom/pan are primarily managed by `WellLogCanvas.set_depth_range()` and `ZoomPanHandler`. CrossWellViewport is used by the picking overlay layers to convert depth positions to pixel coordinates on the overlay widget.

### FormationTopsModel
```python
@dataclass
class FormationTop:
    well_name: str
    formation_name: str
    depth_m: float
    color: str               # hex string (e.g. "#f59e0b"), auto-assigned from palette; convert to QColor at render time (D10)

class FormationTopsModel:
    def load_csv(self, path: str) -> None: ...
    def save_csv(self, path: str) -> None: ...
    def tops_for_well(self, well: str) -> list[FormationTop]: ...
    def add_top(self, top: FormationTop) -> None: ...       # emits tops_changed
    def delete_top(self, well: str, formation: str) -> None: ...
    tops_changed = Signal()
```

### HorizonPicksModel
```python
@dataclass
class HorizonPick:
    pick_id: str             # uuid4
    formation_name: str
    well_depths: list[tuple[str, float | None]]   # [(well_name, depth_m or None)] — ordered, None = absent/eroded (impl note 6)
    source: str              # "manual" | "dtw"
    confidence: dict[str, float]    # well_name → [0..1] (DTW picks only)

class HorizonPicksModel:
    def add_pick(self, formation: str, well: str, depth: float) -> str: ...
    def connect_picks(self, pick_id: str, well: str, depth: float) -> None: ...
    def delete_pick(self, pick_id: str) -> None: ...
    def picks_changed = Signal()
    
    # Undo stack integration
    undo_manager: UndoManager   # QUndoStack wrapper, same as PaleoMapPage
```

---

## Rendering Architecture

### Layout

```
┌─────────────────────────────────────────────────────────┐
│  WELL A          WELL B          WELL C                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐           │
│  │depth│ GR │   │depth│ GR │   │depth│ GR │           │
│  │─────┼────│   │─────┼────│   │─────┼────│           │
│  │1000m│    │   │1050m│    │   │1020m│    │           │
│  │  ───┤    │   │  ───┤    │   │  ───┤    │           │← formation top (dashed)
│  │     │    │   │     │    │   │     │    │           │
│  │  ●══╪════╪═══╪══●══╪════╪═══╪══●  │    │           │← correlation tie (bezier)
│  │     │    │   │     │    │   │     │    │           │
│  └──────────┘   └──────────┘   └──────────┘           │
└─────────────────────────────────────────────────────────┘
```

### Rendering Pipeline (per frame)

```
CrossWellCanvas.paintEvent(self)
  ├── CrossWellWidget.paintEvent()               # delegated — WellLogCanvas renders tracks/curves
  ├── PickingOverlay.paintEvent()                # transparent overlay on top
  │   ├── TopLayer.paint(painter)                # formation top dashes + labels per well
  │   ├── CorrelationLayer.paint(painter)        # bezier ties + pick dots
  │   └── SelectionLayer.paint(painter)          # hover/selected highlights
```

Note: Track rendering, depth rulers, log curves, and zoom/pan are handled by `geoviz_well_log.WellLogCanvas` — not reimplemented here.

### Curve Rendering (delegated to geoviz_well_log)

Log curves are rendered by `geoviz_well_log.WellLogCanvas` — no reimplementation needed. Fill styles and curve rendering follow the existing geoviz_well_log conventions.

Fill between curve and track edge (for reference when styling picking overlay):
- GR: filled left (shale side)
- RHOB/NPHI: filled right
- Fill alpha = 0.35, curve pen width = 1.5px cosmetic

### Correlation Ties

Each tie is a cubic bezier with:
- Control points at 1/3 and 2/3 of the horizontal span
- Pen: 2px, color from formation palette
- Hover: highlight + tooltip showing depth diff
- DTW suggestion: dashed pen, ghost opacity until accepted

---

## DTW Engine

### Algorithm

```python
def correlate(
    ref_well: str,
    target_wells: list[str],
    curve_name: str,          # "GR" default
    depth_window: float,      # ±N metres search window
    formation_name: str,
) -> dict[str, DTWResult]:
```

**DTW cost metric:** Symmetric DTW with Sakoe-Chiba band (radius = depth_window converted to samples). Uses `scipy.spatial.distance.cdist` for distance matrix, then standard DP traceback.

**Output per target well:**
- `suggested_depth: float` — best-match depth
- `cost: float` — normalized DTW cost [0..1]
- `confidence: float = 1.0 - cost` — shown as pick width band

**Dependency:** `scipy` (already in pyproject.toml via seismic page).

---

## Seismic Tie

### Checkshot Loader

```python
@dataclass
class CheckshotTable:
    well_name: str
    depths_m: np.ndarray    # MD or TVDSS
    twt_ms: np.ndarray      # two-way time milliseconds

def interpolate_twt(self, depth: float) -> float:
    """Linear interpolation from T-D table."""
    return np.interp(depth, self.depths_m, self.twt_ms)
```

### Dual-Axis Mode

When `CrossWellViewport.depth_domain == "TWT"`, the depth ruler shows time (ms) and all picks/tops are displayed in TWT. Formation tops loaded in MD are converted via per-well checkshot table.

---

## Interaction Design

| Action | Result |
|--------|--------|
| Click on log curve | Place a manual pick at that depth |
| Shift+click | Add to existing horizon (connects picks across wells) |
| Right-click pick | Context: Delete, Rename formation |
| Drag pick | Adjust depth (updates bezier tie live) |
| Ctrl+Z / Ctrl+Y | Undo/Redo picks |
| Click formation top line | Select (shows depth in status bar) |
| Drag formation top | Adjust depth |
| "Auto-correlate" button | Run DTW from selected reference well |
| Click ghost pick | Accept DTW suggestion |
| Escape | Reject/cancel current pick action |
| Scroll wheel | Zoom depth axis (all wells synchronized) |
| Middle-drag | Pan depth axis |

---

## File I/O

### Formation Tops CSV format
```csv
well_name,formation_name,depth_m
WELL-A,Jurassic,1250.0
WELL-A,Triassic,1800.0
WELL-B,Jurassic,1280.0
```

### Horizon Picks JSON format (save/load session)
```json
{
  "picks": [
    {
      "pick_id": "uuid",
      "formation_name": "Jurassic",
      "well_depths": [["WELL-A", 1250.0], ["WELL-B", 1280.0], ["WELL-C", null]],
      "source": "manual"
    }
  ]
}
```

---

## Tests

| Test | Coverage |
|------|----------|
| `test_tops_model.py` | CSV load/save, tops_for_well, add/delete |
| `test_picks_model.py` | add/connect/delete, undo/redo, signal emission |
| `test_dtw_engine.py` | identical curves → cost 0, shifted curve → correct offset, Sakoe-Chiba band |
| `test_seismic_tie.py` | T-D interpolation, out-of-range clamp |
| `test_cross_well_canvas.py` | paintEvent smoke test, viewport world↔y, pick placement via mouse event |

---

## Security Notes (from prior learnings)

- **pickle-cache-rce** (confidence 9/10): Do NOT use pickle for caching picks or tops. Use JSON only.
- **plaintext-http-api** (confidence 9/10): No network calls in this module. All I/O is local file-based.

---

## Milestones

| Milestone | Content | Estimated CC time |
|-----------|---------|-------------------|
| M1 | CrossWellCanvas composition wrapper + event filter for pick mode (no picking logic) | ~1h |
| M2 | FormationTopsModel + tops rendering + CSV I/O | ~1h |
| M3 | HorizonPicksModel + manual picking + PicksUndoManager (new, QUndoStack pattern) | ~2h |
| M4 | CorrelationLayer bezier ties | ~1h |
| M5 | DTWEngine + ghost picks + accept/reject UI | ~2h |
| M6 | SeismicTie checkshot loader + dual-axis mode | ~1.5h |
| M7 | Full test suite + integration with CrossWellPage | ~1.5h |

**Total estimated CC time: ~11 hours**  
**Human review time: ~2-3 hours** (test a real LAS + checkshot dataset)

---

## Open Questions

1. Should tops colors be user-overridable or always auto-assigned from a geologic palette?
2. Does DTW need to handle MD vs TVDSS mismatch between wells, or can we require the user to pre-convert?
3. ~~Should `geoviz-cross-well` be a new separate package (like `geoviz-well-log`) or integrated into the main `src/` tree?~~ **RESOLVED: New separate package.**

---

## Design Review Decisions (2026-05-29)

### Resolved Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| D1 | Toolbar layout | **Grouped toolbar** with 4 clusters: Data (Add/Clear), View (Tracks/Depth Range/Scale/Domain), Correlate (Pick/Auto-Correlate/Accept), Export | Geological engineers need clear workflow stages |
| D2 | Well column sizing | **Equal split + horizontal scroll** | Consistent with existing QScrollArea pattern; readable curves at any well count |
| D3 | Canvas visual hierarchy | **Ties-first**: ties > picks > tops > curves > ruler | Correlation ties ARE the product; curves are context |
| D4 | Empty state | **Rich empty state** with icon, title, subtitle, CTA button | First-time user onboarding; not just "no data" text |
| D5 | DTW accept/reject UI | **Click to accept** (ghost→solid), **right-click to reject** (disappears), Escape rejects all remaining, summary toast | Direct canvas manipulation; fast workflow |
| D6 | Pick mode vs navigate | **Toggle button** in Correlate group. Cursor crosshair in pick mode. Status bar indicator | Matches existing 手动连井 pattern; discoverable |
| D7 | First-use guidance | **Hint overlay** after first well load, auto-dismisses after 5s or toolbar interaction | Protects the "aha moment" — first pick |
| D8 | Connect picks gesture | **Shift+click** to add to active horizon | Precise depth control; works for non-adjacent wells |
| D9 | Theme | **Light theme** (consistent with existing CrossWellPage) | User continuity; ties use high-saturation colors for contrast |
| D10 | Model Qt coupling | **Hex string** for color in data model, convert to QColor at render time | Headless-testable models; consistent with payload_builder pattern |
| D11 | Window resize behavior | **Fixed depth scale, reflow columns** | User's zoom is deliberate; respect it on resize |
| D12 | Existing file migration | **Retire both** page.py and scene_page.py. New geoviz_cross_well package owns the page. | Clean architecture; no stale code confusion |
| D13 | Save guard | **Dirty tracking** + confirm dialog on Clear/page switch/window close. '*' in title bar. | Professional tool must protect unsaved work |

### Theme & Color Notes

- Canvas background: light (`#f7fafc` or similar), consistent with existing CrossWellPage
- Toolbar: light (`#f7fafc`, `border-bottom: 1px solid #e2e8f0`), matching existing pattern
- Correlation ties: high-saturation warm colors (orange/red) to pop against light background
- Curve fills: muted at alpha 0.35, darker pen colors for readability
- Formation tops: dashed lines, warm palette auto-assigned per formation name

### Page Chrome Specification

```
┌─────────────────────────────────────────────────────────────────────┐
│ TOOLBAR:  [Data] Add | Clear │ [View] Tracks | Range | Scale |    │
│          Domain │ [Correlate] Pick | Auto-Correlate │ [Export] │
├─────────────────────────────────────────────────────────────────────┤
│ CANVAS:   [Well A col] [Well B col] [Well C col] ...              │
│           ┌─────────┐  ┌─────────┐  ┌─────────┐                  │
│           │depth|GR │  │depth|GR │  │depth|GR │                  │
│           └─────────┘  └─────────┘  └─────────┘                  │
├─────────────────────────────────────────────────────────────────────┤
│ STATUS:   "深度: 1250.0 m | 3 wells | MD | PICK MODE"            │
└─────────────────────────────────────────────────────────────────────┘
```

### Empty State

Rich placeholder widget with:
- Icon/illustration (well log correlation visual)
- Title: "连井对比"
- Subtitle: "点击「添加井」选择要对比的井号"
- Primary CTA button: "添加井"

### Hint Overlay (first use)

Semi-transparent overlay shown after first well load:
- Text: "点击工具栏的「手动拾取」按钮，然后在曲线上点击开始地层对比"
- Auto-dismisses after 5 seconds or on any toolbar interaction
- Only shown once (track in QSettings)

### Implementation Notes (deferred decisions)

1. **Well ordering**: Default alphabetical, with drag-to-reorder as future enhancement
2. **Curve color table**: GR=#2D6A4F, RHOB=#E63946, NPHI=#457B9D, SP=#6C757D (follow standard geo conventions)
3. **Depth ruler ticks**: Major every 100m, minor every 25m. At zoom >5px/m switch to 10m/2m. Label format: "XXXX.X m"
4. **DTW async**: Run in QThread worker with progress signal and cancel support (same pattern as _WellLoadWorker)
5. **Single-well state**: Correlate buttons disabled. Manual picking still functional (picks stored without ties)
6. **HorizonPick ordering**: Use `list[tuple[str, float | None]]` instead of `dict[str, float]` to preserve well order and support gaps (eroded/absent horizons)
7. **Checkshot-missing wells**: Show MD only with warning badge in depth ruler header

---

## CEO Review Decisions (2026-05-29)

### Premises Challenged

| # | Premise | Verdict |
|---|---------|---------|
| P1 | GeoViz Engine is the right architecture (PySide6, QPainter) | **Confirmed** |
| P2 | No open-source Qt tool has click-to-pick correlation + formation tops + DTW | **Confirmed** |
| P3 | Geological engineers pay for Petrel/Kingdom for simple correlation | **Confirmed** |
| P4 | "Replace the current ECharts renderer" | **FAILED** — CrossWellPage already uses QPainter via geoviz_well_log |
| P5 | Everyone builds geo tools for Python/Jupyter users | **Confirmed** |

### Resolved Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| CD1 | Problem Statement | **REWRITE** — scope is adding picking workflow to existing QPainter renderer, not replacing ECharts | Critical premise failure (P4) |
| CD2 | Package architecture | **New package COMPOSES geoviz_well_log** — reuse WellLogCanvas + CrossWellWidget, add only picking modules | No duplication (removes track.py, curve_layer.py, viewport.py); clean rendering-vs-picking boundary |
| CD3 | Scope | **Keep all 7 milestones** (tops, picks, ties, DTW, seismic tie) | Full scope per user preference |

### Architecture Impact

With composition (CD2), the new package is leaner:

- **Removed files:** track.py, curve_layer.py, viewport.py (handled by geoviz_well_log)
- **Kept files:** canvas.py, tops_model.py, picks_model.py, correlation_layer.py, dtw_engine.py, seismic_tie.py
- **Cross-package dependency:** geoviz-cross-well imports geoviz-well-log (feature, not bug — enforces boundary)

---

## GSTACK DESIGN DOC

- **Session:** office-hours 2026-05-29
- **Mode:** builder (open source / geoscience community)
- **Eureka:** native QPainter well log correlation + formation tops + DTW — nobody has built this in open source
- **Premises confirmed:** 4/5 (P4 "replace ECharts" FAILED — already QPainter)
- **Next step:** `/autoplan` → CEO+Eng+Design review → implementation plan

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | issues_open | premise P4 failed, 3 decisions (CD1-CD3) |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open | 5 issues, 0 critical gaps, 5 tasks (T1-T5) |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | issues_open | score: 4/10 → 7/10, 13 decisions |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |
| Outside Voice | Claude subagent | Independent plan challenge | 1 | issues_found | 5 findings (backend mismatch, QOpenGLWidget, UndoManager, underscore, duplication) |

UNRESOLVED: 3 deferred implementation notes (well ordering, curve color table, DTW async)
VERDICT: design + CEO + eng review completed — all critical issues resolved, ready for implementation
