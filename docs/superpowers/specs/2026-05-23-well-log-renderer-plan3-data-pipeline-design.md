# Well Log Renderer Plan 3 — QPainter Data Pipeline Design

**Parent spec:** `2026-05-22-well-log-renderer-rewrite-design.md`
**Depends on:** Plan 1 (core) + Plan 2 (track types + interaction)

## Goal

Create `build_qpainter_tracks(data: WellLogData) -> list[BaseTrack]` that converts a `WellLogData` object directly into QPainter track objects. This is the QPainter equivalent of `build_tracks_from_data()` (which produces ECharts JSON).

## Approach

New function, not an adapter. Build directly from `WellLogData` → `list[BaseTrack]`. The existing `build_tracks_from_data()` produces JSON dicts for ECharts — the QPainter path uses typed Python objects.

## Function Signature

```python
def build_qpainter_tracks(data: WellLogData) -> list[BaseTrack]:
    """Convert WellLogData into a list of QPainter track objects for WellLogCanvas."""
```

## Track Construction Rules

1. **DepthTrack** — always created, width=60
2. **CurveTrack** — one per curve in `data.curves`. Log scale if name in ("RT", "RXO"). Width=150.
3. **IntervalTrack** — for each non-empty interval list in `data.intervals`:
   - system → "System", width=80
   - series → "Series", width=80
   - formation → "Formation", width=80
   - member → "Member", width=80
   - lithology_desc → "Description", width=80
   - sequence → "Sequence", width=80
4. **LithologyTrack** — if `data.lithology` non-empty, width=80
5. **FaciesTrack** — if `data.intervals.facies` has any data, width=80 (single mode)
6. **SystemsTractTrack** — if `data.intervals.systems_tract` non-empty, width=60

## File Structure

```
packages/geoviz_well_log/geoviz_well_log/
├── qpainter_builder.py    # NEW: build_qpainter_tracks()
└── __init__.py            # MODIFY: export build_qpainter_tracks

tests/
└── test_qpainter_builder.py  # NEW
```

## Out of Scope

- WellLogPage integration (Plan 4)
- Track reordering / visibility toggle
- Merged curves (AC + GR overlay) — deferred to Plan 4
- AI prediction tracks — deferred
