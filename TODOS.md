# TODOS

## [seismic] Wire up slice type combo box

**What:** `_on_slice_type_changed` in `SeismicView` is currently `pass`. The combo box should trigger an immediate slice read when the user selects Inline/Crossline/Time.

**Why:** The dropdown is visible and interactive but does nothing — misleading UI. Users expect selecting "Crossline" to show a crossline profile at the current position.

**How:** Read the current position from the active 3D plane widget for the selected slice type, convert to actual inline/crossline number, read from loader/cache, and update profile widget.

**Depends on:** SeismicView fully implemented (Task 11+).

**Context:** Added during eng review of seismic module plan. The plane widgets already handle interactive slice selection; this combo is for explicit type switching without dragging.
