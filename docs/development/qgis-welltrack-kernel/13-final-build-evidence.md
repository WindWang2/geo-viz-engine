# 13 — Final targeted build & test evidence

Date: 2026-09-24. Host: Arch Linux, GCC 16.2.1, Qt 6.11.2 (system), Ninja
not used — Unix Makefiles, `-j2` throughout (hard cap ≤ j6 honored; no
parallel agents building simultaneously).

## Configure

Standalone configure of **only** `packages/geoviz-qgis-welltrack` (build dir
`build-qwt` inside the worktree, git-excluded), SDK injected via the
paleo-workbench environment contract (`PALEO_QGIS_SOURCE_DIR` /
`PALEO_QGIS_SDK_DIR` / `PALEO_QGIS_BUILD_DIR` / `PWB_QGIS_DEPS_PREFIX`).
Configure succeeded on the first attempt (`/tmp/qwt-configure.log`); no QGIS
rebuild, no full geo-viz-engine configure/build at any point.

## Compile loop (bounded, per prompt §12 discipline)

| Attempt | Failure | Fix (minimal) |
|---|---|---|
| 1 | bare `#include "axis_spec.h"` in src/ (public headers live under `include/geoviz/qgis_welltrack/`) | qualified includes in all src TUs |
| 2 | QGIS core headers pull `QDomDocument` → Qt6::Xml missing from the core-only closure | SdkCore closure = Core+Gui+Xml+Svg |
| 3 | QGIS 4.2 headers require defaulted `operator==` → **C++20**; `nsecElapsed` typo; const `axis.style()` pointer | `CMAKE_CXX_STANDARD 20`; `nsecsElapsed`; const fix |
| 4 | `qgsapplication.h` needs QtWidgets in the QGIS-app test group | full SDK interface linked for APP tests |
| 5 | AUTOMOC never scanned public headers in `include/` → undefined `staticMetaObject` | Q_OBJECT public headers added as target sources |
| 6 | `crs()` returns `QgsCoordinateReferenceSystem` by value → incomplete type in consumers | include added to the public canvas header |
| 7 | example missing `welltrack_renderer.h` include | added |

All were interface/plumbing issues; **zero changes to kernel math, LOD, or
interaction logic came out of the compiler** — the review-first design held.

Final build: **48/48 targets, exit 0** (`-j2`, no ICE encountered).

## Tests — ctest 13/13 PASS

```
100% tests passed out of 13   (Total Test time = 3.7 s)
```

Groups: 7 pure-logic suites (depth domain, curve view, axis transform,
visible slice, envelope oracle, track layout, hit testing) + QGIS-app
renderer suite (pixel probes incl. NaN-gap no-bridging, BetweenSeries fill,
marker line, band fill, two-curve colors, SVG export, idempotence) + 5 GUI
suites (canvas lifecycle ×50 open/close, navigation incl. wheel anchor and
Ctrl-fine zoom and IncreasingUp, gesture-level tools incl. transient
mid-button pan, synchronizer, perf).

Two verification iterations were needed after the first ctest run (4 fails →
root causes: default 0..1 domain wrongly treated as "explicit", no-op guard
ignored orientation changes, one test-side wheel-delivery path + one
hit-probe geometry expectation) — all four fixed and re-run green.

## Offscreen demo smoke

`welltrack_demo --offscreen /tmp/qwt-demo.png` → exit 0, valid
900×700 RGBA PNG. (One demo-side bug found and fixed here: the offscreen
path forgot `DemoWell::make()` — empty buffers, not a kernel issue.)

## Performance evidence (measured, no FPS claims)

test_perf table — 4 curve tracks × 4 curves (16 series), 900×700 logical px,
offscreen, RelWithDebInfo, single-threaded render path:

| samples/curve | prep µs (first render) | paint µs | envelope pts | raw samples in slices |
|---:|---:|---:|---:|---:|
| 1e4  | 120 984 | 6 795 | 21 056 | 160 000 |
| 1e5  |  31 373 | 4 508 | 21 056 | 1 600 000 |
| 1e6  | 118 010 | 5 937 | 21 056 | 16 000 000 |

Reading:

- Envelope output is **constant ≈ 2 points per pixel-row per curve**
  (2 × 700 × 16 = 22 400; 21 056 observed) independent of sample count —
  paint time stays ~5–7 ms from 1e4 to **1e6** samples per curve. The LOD
  goal (paint cost O(viewport), not O(n)) is demonstrated, not assumed.
- Prep scales with the visible slice (O(n) scan): 1.6e7 samples in 118 ms ≈
  1.35e8 samples/s envelope construction single-threaded; cached
  re-render prep is asserted cheaper (test pins `prep2 <= prep1`).
- envelopeBound: 1e5 samples → 1 600 points (bins=800), far under the
  4×bins cap.

Residual, honestly: the layout + axis-label pass runs per frame (documented
v1 degradation in 07); interval optimization is cached; grid loop allocations
are bounded but not pooled.
