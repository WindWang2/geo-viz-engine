# Paleo Map Editing with Topology Preservation — Design Spec

**Date:** 2026-05-28
**Status:** Draft
**Scope:** Add full polygon editing capabilities to `geoviz-paleo-map` with hard topology constraints and hierarchy-aware parent recomputation.

---

## 1. Goals

- Enable users to edit paleogeographic map polygons: vertex editing, polygon create/delete/split/merge, attribute editing
- Maintain hard topology constraints — shared edges between adjacent polygons always move together, no gaps or overlaps
- Auto-recompute parent hierarchy boundaries (facies ← union of sub-facies) when children are edited
- Provide full undo/redo support
- Save edits back to GeoJSON (overwrite or save-as), plus export as SVG/PDF/PNG

## 2. Approach

**Shared-Vertex Topology Graph** — polygons reference shared `TopologyVertex` objects. Moving one vertex automatically updates all polygons that share it. Parent boundaries are recomputed via Shapely `unary_union` (debounced for performance). Shapely is used only for one-off geometry operations (parent union, split, merge), not per-frame rendering.

## 3. Data Model

New module: `topology.py`

### Core Types

```python
@dataclass
class TopologyVertex:
    x: float          # longitude (world coord)
    y: float          # latitude (world coord)
    id: int           # unique vertex ID

@dataclass
class TopologyEdge:
    v1: int           # vertex ID (canonicalized: min first)
    v2: int           # vertex ID

@dataclass
class RingRef:
    vertex_ids: list[int]    # ordered vertex IDs forming a closed ring

@dataclass
class FeatureRef:
    feature_id: str
    rings: list[RingRef]     # outer ring + holes
    level: str               # "facies" | "sub_facies" | "micro_facies"
    parent_id: str | None
    source_file: str | None  # for hierarchy-aware save
    properties: dict         # original GeoJSON properties (facies, name, boundary_type, etc.)
```

### TopologyModel

```python
class TopologyModel:
    _vertices: dict[int, TopologyVertex]          # all vertices by ID
    _features: dict[str, FeatureRef]              # feature geometry references
    _edge_index: dict[tuple[int,int], set[str]]   # edge → set of feature_ids sharing it
    _path_cache: dict[str, QPainterPath]          # feature_id → cached path (dirty tracking)
    _dirty_ids: set[str]                          # features needing path rebuild
    is_dirty: bool                                # unsaved changes flag
```

### Building the Graph (TopologyBuilder)

On load from GeoJSON:

1. Parse each feature's coordinate rings
2. Spatial deduplication: for each vertex, query a grid index for existing vertices within tolerance (1e-6 degrees ≈ 0.1m). Reuse existing vertex ID if within tolerance, otherwise create new `TopologyVertex`
3. Build `RingRef` per feature ring with deduplicated vertex IDs
4. Register edges: for each consecutive pair `(v_i, v_{i+1})` in a ring, canonicalize as `(min_id, max_id)`, add feature_id to `_edge_index[edge]`
5. Build initial `QPainterPath` cache per feature

## 4. Edit Mode

### Toggle

- Toolbar button "编辑模式" with pencil icon, or press `E` key
- `PaleoMapCanvas.edit_mode: bool` property + `edit_mode_changed = Signal(bool)` signal
- Entering edit mode: disable drag-pan (wheel zoom stays), enable selection and vertex handles
- Leaving edit mode: deselect all, hide handles, re-enable drag-pan

### Mouse Behavior in Edit Mode

| Action | Behavior |
|--------|----------|
| Click on polygon | Select it (highlight + show vertex handles) |
| Click on empty space | Deselect all |
| Drag on vertex handle | Move vertex (topology propagation) |
| Drag on polygon interior | Move entire polygon |
| Double-click on edge | Insert new vertex |
| Right-click on vertex | Context menu: delete vertex |
| Right-click on polygon | Context menu: edit attributes, delete, split, merge |
| Scroll wheel | Zoom (unchanged) |

### Selection Model

- Single selection (one polygon at a time)
- `PaleoMapCanvas.selection_changed = Signal(str)` — emits feature_id or empty string

### Cursor Management

| Context | Cursor |
|---------|--------|
| Default (edit mode) | Arrow |
| Over vertex handle | Crosshair |
| Over polygon interior (selected) | Open hand |
| Over polygon interior (not selected) | Pointing hand |
| During vertex drag | Closed hand |
| Over edge midpoint | Crosshair |

## 5. Editing Operations

Each operation is a discrete command with `execute()` and `undo()`.

### Vertex Move

- Drag handle → update `TopologyVertex(x, y)` → all `RingRef`s referencing that vertex reflect the change automatically
- Affected features detected via rings containing the vertex ID + `_edge_index` lookup
- Parent recomputation queued (debounced 150ms)

### Insert Vertex

- Double-click on edge → split edge by inserting new `TopologyVertex` between `v1` and `v2` in the ring's `vertex_ids`
- If edge is shared: insertion propagates to both polygons' rings

### Delete Vertex

- Right-click → "删除节点"
- Minimum ring size: 4 vertices (3 + closing). Refuse if ring would shrink below 4
- If vertex is shared: remove from all shared rings. Refuse if any ring would go below minimum

### Polygon Move

- Drag polygon interior → translate all vertices of all rings by delta
- Shared vertices move with it → adjacent polygons follow (topology preserved)

### Polygon Create

- Click-to-place: each click adds a vertex, double-click or Enter to close
- User assigns: facies name, level, parent (if hierarchy), boundary_type
- New vertices and edges register in topology model
- Snapping to existing edges during drawing detects shared vertices
- If the new polygon doesn't snap to any existing edge, it is standalone (no shared topology). It can still be adjacent to other polygons but has its own independent vertices. Shared topology can be established later by dragging its vertices onto existing edges (which triggers re-snap and vertex deduplication)

### Polygon Delete

- Right-click → "删除多边形"
- Remove feature, clean up orphan vertices/edges
- Parent recomputation triggered

### Polygon Split

- User draws a line across the polygon (click start, click end)
- Split polygon into two halves, each gets a new feature ID
- User assigns facies name to the new polygon
- Implementation: Shapely `split()` as one-off utility

### Polygon Merge

- Select polygon, right-click → "合并到..." → click adjacent polygon
- Union of two polygons, result keeps target's attributes
- Implementation: Shapely `union()` as one-off utility

### Attribute Edit

- Right-click → "编辑属性" → dialog with: facies name, display name, level, boundary_type, parent
- Changing parent triggers hierarchy re-link

## 6. Topology Engine

### Real-Time Propagation

```
move_vertex(vertex_id, new_x, new_y) → list[affected_feature_ids]
```

1. Update `TopologyVertex(x, y)`
2. Find all features whose rings contain `vertex_id` → mark paths dirty
3. Find edges containing `vertex_id` → find all features sharing those edges → mark dirty
4. Return affected feature_ids

O(1) for vertex update, O(k) for propagation (k = number of adjacent features, typically 2-3).

### Parent Union Recomputation

```
recompute_parent(child_feature_id) → updated parent geometry
```

1. Find all siblings (features with same `parent_id`)
2. Convert siblings' current topology rings to Shapely `Polygon` objects
3. Compute `unary_union(siblings)` → `Polygon` or `MultiPolygon`
4. Convert result back to topology rings (deduplicate vertices)
5. Update parent `FeatureRef.rings`, mark parent path dirty

**Performance:** Debounce 150ms after last vertex move. Show parent boundary as dashed "pending" line during debounce. Cache Shapely objects for siblings.

### Topology Validation (Optional)

After edits, optionally check:
- No two features overlap (intersection area > tolerance)
- Siblings tile parent with no gaps
- Emit `topology_warning = Signal(str)` if violations found

## 7. Rendering in Edit Mode

### EditOverlayLayer (new PaleoLayer)

Paints on top of all existing layers when `edit_mode` is active:

- **Vertex handles**: circles at each vertex of selected polygon
  - Default: 6px radius, white fill + dark border (#2d3748, 2px)
  - Hovered: blue fill (#3182ce)
  - Dragging: blue fill, 8px radius
- **Edge highlight**: when mouse is near an edge (within 8px screen), draw edge segment in blue
- **Shared vertex indicator**: small colored ring around handle when vertex is shared by multiple features

### FaciesPolygonsLayer Modifications

- Add `selected_id: str | None` field
- Selected polygon: lighter/more saturated brush, 3px outer glow stroke (alpha=60)
- Non-selected polygons in edit mode: reduced opacity (alpha=180)
- `rebuild_dirty_paths(feature_ids: set[str])` — rebuild only changed paths from topology coordinates
- Path building switches between GeoJSON source (view mode) and TopologyModel (edit mode)

## 8. Undo/Redo System

### Command Pattern

```python
class EditCommand(ABC):
    def execute(self, model: TopologyModel) -> None: ...
    def undo(self, model: TopologyModel) -> None: ...
```

### Command Types

| Command | Stores | execute() | undo() |
|---------|--------|-----------|--------|
| `MoveVertexCmd` | vertex_id, old_pos, new_pos | set new_pos | restore old_pos |
| `MovePolygonCmd` | feature_id, delta, old_positions | translate | restore |
| `InsertVertexCmd` | vertex_id, edge, ring_index | insert + create | remove + delete |
| `DeleteVertexCmd` | vertex_id, edge, ring_index | remove | insert back |
| `CreatePolygonCmd` | feature_ref, vertices | add | remove |
| `DeletePolygonCmd` | feature_ref, vertices (snapshot) | remove | restore |
| `SplitPolygonCmd` | original_id, new_id, geometries | replace with two | restore original |
| `MergePolygonCmd` | kept_id, removed_id, geometries | replace with union | restore both |
| `EditAttributesCmd` | feature_id, old_attrs, new_attrs | set new | restore old |
| `RecomputeParentCmd` | parent_id, old_rings, new_rings | set new | restore old |

### Composite Commands

Vertex drag = `[MoveVertexCmd, RecomputeParentCmd]`. Single Ctrl+Z undoes both.

### UndoManager

```python
class UndoManager:
    _undo_stack: list[EditCommand]   # max 100
    _redo_stack: list[EditCommand]
    
    def execute(self, cmd, model): ...   # run + push to undo, clear redo
    def undo(self, model): ...           # pop undo → run undo → push redo
    def redo(self, model): ...           # pop redo → run execute → push undo
    def clear(self): ...
```

Keyboard: `Ctrl+Z` undo, `Ctrl+Y` / `Ctrl+Shift+Z` redo.

## 9. Save & Export

### Save to GeoJSON

Walk `_features` in TopologyModel → reconstruct coordinate arrays from `RingRef.vertex_ids` → lookup `(x, y)` → build GeoJSON Feature with original properties → write FeatureCollection.

- **Save** (`Ctrl+S`): overwrite current file. Hierarchy mode saves each level to its respective source file
- **Save As** (`Ctrl+Shift+S`): prompt for new path, write full collection
- Dirty tracking: `TopologyModel.is_dirty` set on edit, reset on save. Prompt on period switch if dirty

### Export as Image

Reuse `geoviz-well-log` export pattern:
- SVG: `QSvgGenerator` → `canvas.render(painter)`
- PDF: `QPrinter` → `canvas.render(painter)`
- PNG: `canvas.grab()`

### Hierarchy-Aware Save

`FeatureRef.source_file` tracks origin. Save distributes features back to source files. "Save As" writes everything to a single file.

## 10. New Files

```
packages/geoviz_paleo_map/
  topology.py          ~300 lines  -- TopologyModel, TopologyVertex, TopologyEdge, RingRef, TopologyBuilder
  edit_engine.py       ~250 lines  -- EditEngine (selection, drag logic, operation dispatch)
  edit_commands.py     ~200 lines  -- EditCommand subclasses, UndoManager, CompositeCommand
  edit_overlay.py      ~150 lines  -- EditOverlayLayer (vertex handles, edge highlights, cursors)
  export.py            ~80 lines   -- SVG/PDF/PNG export dialog
```

## 11. Modified Files

| File | Changes |
|------|---------|
| `canvas.py` | edit_mode property/signal, EditEngine, EditOverlayLayer in layer stack, keyboard shortcuts, TopologyModel lifecycle |
| `facies_polygons.py` | selected_id field, selection highlight, rebuild_dirty_paths(), path from TopologyModel |
| `zoom_pan.py` | Disable drag-pan when edit_mode=True |
| `hierarchy.py` | Expose get_children(parent_id) |
| `__init__.py` | Export TopologyModel, EditEngine, UndoManager |

Page-level (`src/pages/paleo_map/page.py`):
- Edit mode toggle button in toolbar
- Save/export buttons visible in edit mode
- Selection → properties panel
- Topology warning → status bar

## 12. Dependencies

- **shapely** — already used by PaleoDataLoader for CSV/WKT. Used for parent union, split, merge (one-off operations only, not per-frame)
- No new external dependencies

## 13. Performance Characteristics

- **View mode**: completely unaffected. Existing paint path untouched. TopologyModel only built on period switch.
- **Vertex drag**: O(1) vertex update + O(k) propagation (k ≈ 2-3 adjacent features). Path rebuild is O(1) per affected feature.
- **Parent recompute**: debounced 150ms. Shapely unary_union on 2-10 sibling polygons is <5ms.
- **Quadtree rebuild**: only dirty paths are rebuilt, not the entire spatial index.
- **Undo/redo**: O(1) per operation (stack push/pop + vertex position restore).

## 14. Open Questions

- Polygon split: exact algorithm for user-drawn cut line → two polygons. Shapely `split()` may produce MultiPolygon if the line doesn't fully cross. Need fallback UX.
- Multi-select: deferred to future version. Single selection simplifies the first implementation significantly.
- Vertex snapping during polygon creation: how aggressively to snap to existing edges. Tolerance in screen pixels vs world coordinates.
