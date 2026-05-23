# Well Log Renderer Plan 4 — WellLogPage Integration Design

**Parent spec:** `2026-05-22-well-log-renderer-rewrite-design.md`
**Depends on:** Plan 3 (data pipeline)

## Goal

Wire the QPainter renderer into WellLogPage so users can view well logs with native rendering instead of ECharts.

## Approach

Add a toggle button in the toolbar to switch between ECharts (ChartEngine) and QPainter (WellLogCanvas) rendering. Both share the same data loading path. When QPainter is selected, `build_qpainter_tracks()` produces track objects and `WellLogCanvas` renders them.

## Changes to WellLogPage

1. **Toolbar toggle**: Add a QPushButton/QComboBox "Renderer: ECharts / QPainter" in the toolbar area
2. **QPainter widget**: Create a QScrollArea containing WellLogCanvas. Show/hide based on renderer selection.
3. **Data loading**: When QPainter is active, call `build_qpainter_tracks(data)` → `canvas.set_tracks(tracks)` → `canvas.set_depth_range(data.top_depth, data.bottom_depth)`
4. **ZoomPanHandler**: Attach to canvas on creation, set full range
5. **Export**: Use `qpainter_export_svg/pdf/png` when QPainter is active
6. **Track control panel**: Disable track reordering/merge/split when QPainter is active (Phase 2 feature)

## File Structure

```
src/pages/well_log/
├── page.py              # MODIFY: add toggle, QPainter path
└── qpainter_widget.py   # NEW: QScrollArea + WellLogCanvas + ZoomPanHandler wrapper

tests/
└── test_qpainter_widget.py  # NEW
```

## Out of Scope

- Removing ECharts backend (preserved for backward compatibility)
- Cross-well page migration
- Track reordering/merge/split in QPainter mode
