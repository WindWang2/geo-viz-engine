# geoviz-qgis-welltrack — QGIS-native well-track plotting kernel

A standalone C++17 package providing a high-performance well-track / log-curve
plotting substrate on top of the **QGIS 4.2 SDK** (the same vendored SDK
paleo-workbench consumes). It is the A-line deliverable of the QGIS plot
kernel initiative: see `docs/development/qgis-welltrack-kernel/` in the
repository root for the full design record (source inventory, reuse matrix,
license gate, rendering/perf contracts, review rounds, build evidence).

## What it is (and is not)

- **Is**: shared numeric depth viewport, N track columns with per-track value
  axes (linear/log10), curve rendering (line/markers/fill-to-baseline/
  fill-between), generic depth bands / marker lines / text anchors,
  coordinate transforms, hit testing, extrema-preserving LOD for 1e4–1e6
  samples, and a `QgsPlotCanvas`-based interactive canvas with QGIS plot
  tools (pan, marquee depth-zoom, cursor readout, transient tools) plus
  multi-canvas depth synchronization.
- **Is not**: a well/lithology/facies domain model. No `WellId`, no MD/TVD
  semantics, no persistence, no Python. The B-line package
  (`geoviz-well-track-native`, separate) maps domain objects onto these
  primitives through this public API only.

QGIS-first policy: everything QGIS's public plot API offers is *used*, not
reimplemented — canvas event plumbing, tool lifecycle, rubber band,
`QgsPlotAxis` styling, `calculateOptimisedIntervals`, `QgsTextRenderer`,
`QgsLineSymbol` grids. The six genuine public-API gaps (depth-axis
inversion, multi-column layout, shared viewport, plot↔pixel transforms,
big-sample LOD, vertical zoom tool) are implemented here on top of the
documented extension points (`QgsPlotCanvas` virtuals, `QgsPlotToolZoom`
constrain hooks) — the same route QGIS itself uses for the elevation profile
canvas. **No QGIS source code is copied** (license gate:
`docs/…/04-license-provenance.md`; linking `libqgis_*.so` is GPL-2.0+ at
binary distribution time — see `LICENSES/QGIS-LINKING.md`).

## Targets

| CMake target | Contents |
|---|---|
| `GeoViz::QgisWellTrackCore` | data views, LOD, layout, renderer, hit testing (Qt Core/Gui + QGIS core) |
| `GeoViz::QgisWellTrack` | `WellTrackCanvas`, tools, crosshair, synchronizer (adds Qt Widgets + QGIS gui) |

## Consuming

```cmake
# geo-viz-engine / paleo-workbench build:
add_subdirectory(packages/geoviz-qgis-welltrack)
target_link_libraries(my_host PRIVATE GeoViz::QgisWellTrack)
```

Standalone configure (SDK located via cache vars or the same-named
environment variables paleo-workbench uses):

```bash
cmake -S packages/geoviz-qgis-welltrack -B build-qwt \
  -DPALEO_QGIS_SOURCE_DIR=/path/to/qgis-src \
  -DPALEO_QGIS_SDK_DIR=/path/to/qgis-install/output \
  -DPALEO_QGIS_BUILD_DIR=/path/to/qgis-build \
  -DGEOVIZ_QWT_BUILD_TESTS=ON -DGEOVIZ_QWT_BUILD_EXAMPLES=ON
cmake --build build-qwt -j4
ctest --test-dir build-qwt --output-on-failure
```

If the parent project already imported `PwbQgis::Sdk` (paleo-workbench), it
is reused automatically — one Qt ABI, one QGIS SDK per process.

## Minimal host usage

```cpp
#include "geoviz/qgis_welltrack/well_track_canvas.h"
#include "geoviz/qgis_welltrack/well_track_tools.h"

using namespace geoviz::qgis_welltrack;

// Buffers must outlive every model snapshot that views them.
auto model = WellTrackModel::create();
auto *track = model->appendTrack( QStringLiteral( "GR" ) ).get();
track->axis.minimum = 0.0;
track->axis.maximum = 150.0;
CurveSpec gr;
gr.id = 1;
gr.label = QStringLiteral( "GR" );
gr.data = makeDoubleView( depths /*const double* */, values, count);
track->curves.push_back( gr );

auto *canvas = new WellTrackCanvas( parent );
canvas->setModel( model );       // auto-fits depth extent
canvas->fitDepth();
canvas->setTool( new WellTrackCursorTool( canvas ) );   // or QgsPlotToolPan / WellTrackDepthZoomTool
QObject::connect( canvas, &WellTrackCanvas::cursorDepthChanged, [] ( double d ) { /* readout */ } );

WellTrackSynchronizer sync;      // optional: keep canvases depth-locked
sync.addCanvas( canvasA );
sync.addCanvas( canvasB );
```

Headless export uses the same render path as the screen:

```cpp
QSvgGenerator generator; /* ... */
QPainter painter( &generator );
WellTrackRenderer renderer;
renderer.render( &painter, QRectF( 0, 0, 900, 700 ), *model, canvas->depthDomain() );
```

## Data contract (performance-critical)

`CurveSeriesView` borrows memory (packed double/float arrays or strided
struct members). Depths must be **non-decreasing**; NaN depths are a caller
bug (`validateDepthMonotonic` audits at load time). NaN *values* are legal
gaps. The kernel never copies sample arrays: keep the buffers alive as long
as the model snapshot referencing them.

## Layout

```
include/geoviz/qgis_welltrack/   public headers (core + gui)
src/                             core implementation
src/gui/                         canvas/scene item/tools/synchronizer (+ private scene item header)
tests/                           QtTest suites (pure, QGIS-app, GUI groups)
examples/welltrack_demo/         interactive + --offscreen smoke
LICENSES/                        QGIS linking notes
```

## Status

See `docs/development/qgis-welltrack-kernel/09..14` for review rounds and
targeted build evidence. Baseline Python stack (`packages/geoviz_well_log`)
remains untouched; it is the behavior reference and test oracle.
