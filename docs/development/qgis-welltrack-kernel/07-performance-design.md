# 07 — Performance design

Audit-first note: the mechanisms below are *ported as behavior* from the
proven Python stack (`geoviz_well_log` renderer) plus what QGIS source review
showed is missing there; nothing is speculative. Evidence obligations live in
08-test-plan.

## Target scale

| Scenario | Expectation |
|---|---|
| 1e4 samples / curve, 8 curves, 4 tracks | interactive pan/zoom, prep < 2 ms/curve typical |
| 1e5 samples / curve | same, LOD bound ≈ O(content height), not O(n) |
| 1e6 samples / curve | usable: slice + envelope stay linear-in-slice; full-file scans forbidden per frame |
| multi-canvas sync (4 canvases) | no cascade repaints (no-op guard + blockSignals discipline) |

## Mechanism 1 — visible-range slicing (O(log n) per frame)

`visibleSlice` = two `std::upper_bound`/`lower_bound` binary searches over the
monotonic depth array + ±5% margin (margin prevents gap-flicker at edges,
reference: `curve_track.py:170-181`). Contract: depths non-decreasing; NaN
depths rejected by `validateDepthMonotonic` (returns first bad index; host
responsibility, debug-asserted).

## Mechanism 2 — extrema-preserving envelope (O(slice) per frame)

Per screen depth-row bin (bins = contentRect.height()), emit the bin's min
and max sample **in original index order**, plus a trailing break flag for
bins containing non-finite values (gap contract — polylines never bridge).
This is the min/max envelope the prompt asks to *prove* against alternatives:

- vs raw: 1e6→~2×height points; visual extrema preserved exactly per bin.
- vs LTTB: LTTB minimizes triangle area for general x-y charts; on monotone
  depth tracks it can *drop* a bin's extreme excursion when the shape is
  locally triangular — wrong invariant for log curves (extrema are the
  signal). LTTB remains in `geoviz_plots` for cross-plots; not used here.
- vs point-decimation (every k-th): aliasing destroys spikes. Rejected.
- Tests pin the invariant: for random walks (incl. NaN injection), per-bin
  envelope min/max equals brute-force slice min/max, and the global max/min
  of the visible window is always present in the envelope output.

Small-n fast path: `sliceCount <= max(2*bins, 64)` → pass-through raw samples
(no envelope allocation).

## Mechanism 3 — quantized caches (bounded, explicit invalidation)

| Cache | Key | Invalidated by |
|---|---|---|
| layout | (size, visibility/width set, model generation) | any of key inputs |
| envelope (per curve) | (model identity, model generation, track id, series id, bins, quantized depth window with quantum = span/bins) | key change; single-slot per curve (current viewport only — **no history, no unbounded growth**) |
| axis label layout | (axis config generation, width) | key change |
| scene item pixmap | (model gen, depth window, size, dpr, style) | `refresh()`/any input change |

v1 implementation note (honest degradation, reviewed in round 1/2): the
envelope cache and scene-item pixmap are implemented as specified; layout
and axis-label layout are recomputed each frame (measured cheap relative to
envelope building; the perf table in 13 quantifies it). Buffer-content
changes without a `touch()` produce stale envelopes by contract — the host
must bump the model (documented in track_model.h).

Depth-window quantization (quantum = span/bins) means pan within a bin
re-renders from the same envelope — the reference trick that makes dragging
cheap. All caches hold *one* slot per entity (current view); memory is bounded
by ~Σ curves × O(height) points.

## Mechanism 4 — paint hygiene

- One `QPainterPath`/`QPolygonF` per curve per frame, subpath breaks instead
  of path rebuilds; no per-sample `QPainter` state changes.
- No per-sample QObject/allocations; envelope output reuses caller-provided
  `std::vector` (steady-state zero-alloc after warmup).
- Grid lines batched per symbol config; text via `QgsTextFormat` batched
  through `QgsRenderContext` (upstream pattern).
- Cursor/crosshair on separate item → content cache not invalidated by hover.

## Threading

LOD pre-warm (`visibleSlice`+`buildEnvelope`) is pure data and may run on a
worker against an immutable snapshot; GUI painting stays on the main thread
(Qt/QGIS constraint). v1 exposes the functions thread-safe; the canvas itself
uses them synchronously (worker pipeline is B-line integration work, hook
documented).

## Measurement discipline (no fake FPS)

`RenderStats` reports measured prep/paint µs (QElapsedTimer), sample counts,
envelope points. The perf test prints a table for 1e4/1e5/1e6 and asserts
only *sanity* bounds (envelope ≤ 4×bins×curves; full render of 1e6×4 curves
< 5 s headless) so CI can't flake on wall-clock; real numbers go into
13-final-build-evidence.md.
