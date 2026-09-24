# 04 — License provenance gate

## The two licenses in play

| Artifact | License | Evidence |
|---|---|---|
| geo-viz-engine (this repository) | MIT | `LICENSE` at repo root |
| QGIS source snapshot (incl. everything under `src/core/plot`, `src/gui/plot`) | **GPL-2.0-or-later** | `third_party/qgis/UPSTREAM.md`, `third_party/qgis/COPYING` |
| Qt 6.11.2 (system) | LGPL-3.0 / GPL-2+ (GPL modules unused) | distro package |

## Gate decision (frozen before any code was written)

**Mode: zero QGIS source copying. All QGIS consumption is by linking against
the prebuilt SDK shared libraries through their public C++ headers
(`libqgis_core.so.4.2.0`, `libqgis_gui.so.4.2.0`), exactly as the host
project already does via `PwbQgis::Sdk`.**

Rationale:

1. QGIS is GPL-2.0+. Copying even "minimal necessary" upstream source files
   (e.g. reworking `Qgs2DXyPlot::render` for a depth-inverted axis) would
   import GPL-2.0+ code into an MIT repository. The only lawful way to do
   that is to keep those files GPL with their upstream headers intact —
   which changes the licensing surface of this package beyond what the
   MIT repo license declares.
2. The prompt's license gate instructs exactly this fallback: if the license
   boundary is unsuitable for copying, stop the copy plan and compose
   through the public API instead.
3. Investigation (docs 02/03) showed copying is **not necessary**: the six
   real gaps (depth inversion, multi-column layout, shared viewport,
   transforms/hit-test, LOD, vertical zoom tool) are all expressible by
   subclassing public classes and implementing public virtuals — the same
   route QGIS itself uses for the elevation profile canvas. Nothing needs
   upstream function bodies.

## Reuse ledger (complete — one line per QGIS artifact consumed)

| # | Upstream artifact | Version | Reuse mode | Local destination | Modifications |
|---|---|---|---|---|---|
| 1 | `libqgis_core.so` | 4.2.0 (SDK build of final-4_2_0 @ ca5812c8) | dynamic link, public API | `GeoViz::QgisWellTrackCore` links `PwbQgis::Core`-equivalent imported target | none to QGIS |
| 2 | `libqgis_gui.so` | 4.2.0 | dynamic link, public API | `GeoViz::QgisWellTrack` (gui lib) links gui target | none |
| 3 | QGIS public headers `qgsplot*.h`, `qgsplotcanvas*.h`, `qgsplottool*.h`, `qgsplotrubberband.h`, `qgsplotmouseevent.h`, `qgsplottransienttools.h` | snapshot 192422c60 | include (compile-time) only | consumed via include closure; never vendored into this repo | none |
| 4 | `QgsPlotDefaultSettings` factories | 4.2.0 API call | runtime call for default symbols | `src/axis_styling.cpp` | none |
| 5 | Upstream *design* of `QgsElevationProfileCanvas` (canvas virtuals, DPR image cache, z-order conventions) | 4.2.0 | **idea/reference only** — no code copied; our implementations are written from the documented public contracts in 02 | `src/gui/*` | n/a |

**Count of QGIS source files copied into this package: 0.**
If a future change ever needs one, it must be added to this ledger first,
keep its upstream copyright header, and be marked GPL-2.0-or-later in
`LICENSES/`.

## Distribution implications (flagged, not decided here)

- Object/binary distribution of anything linking `libqgis_*.so` combines
  GPL-2.0+ code with this package's code. Under GPL-2.0+ §2/§5 the *combined
  work* obligations are triggered at distribution time; the paleo-workbench
  host already accepts exactly this posture for its existing
  `qgis_render_bridge` native module, and this package adds no new category
  of obligation (same two libraries, same linkage mode).
- Internal use / no distribution: no obligation.
- This package's own source files remain MIT (repo license); the package
  documents (README + `LICENSES/QGIS-LINKING.md`) that building it requires
  the QGIS SDK and that distributed binaries inherit GPL terms from QGIS.
- No legal conclusion is made here; the engineering gate is simply: **no GPL
  text may enter the repo through this package.**

## Qt

System Qt 6.11.2 LGPL is consumed identically to every other Qt module in the
repo (dynamic link). No Qt source is copied.
