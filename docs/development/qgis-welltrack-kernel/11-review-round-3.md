# 11 — Review round 4 (adversarial pre-build)

Reviewer: independent subagent, 2026-09-24, against commit `ebe9b70f` +
round-3 test fixes in flight. Mandate: make it crash/hang/render wrong with
realistic data and users.

## P0 findings

| # | Finding | Disposition |
|---|---|---|
| A-P0-1 | `private slots: scheduleRefresh()` declared, never defined → link error from moc vtable | FIXED: declaration removed (residue of an earlier refactor) |
| A-P0-2 | Same CMake closure trio as round 3 (Test component, Svg, SDK PRIVATE) | FIXED (see 10) |
| A-P0-3 | **Deterministic hang**: `Qgs2DXyPlot::calculateOptimisedIntervals` divides available mm by 30 and loops until labels fit; with plot ≤ ~16 px (small windows, squeezed tracks) available ≤ 0 → infinite loop, called every frame | FIXED: optimizer skipped below 16 px content width/height; plus the interval result is now cached per (model, generation, quantized window, size) so it no longer runs per frame at all |

## P1 findings

| # | Finding | Disposition |
|---|---|---|
| A-P1-4 | `for (v=start; v<=max; v+=step)` stalls when step < ULP(start) (ns-scale domains) | FIXED: all four stepping loops replaced by counted `forEachStep(start + i*step)` with caps |
| A-P1-5 | `applyDepthDomain` emitted after clamp even when the clamped result equals the current window (useless signals/repaints at full extent — root cause of the round-3 sync test failures) | FIXED: no-op check re-run post-clamp; semantic decision recorded: **synchronization delivers the requested window; canvases clamp to their own extent; identical result = no emission** |
| A-P1-6 | `cursorDepthChanged` NaN contract unimplemented: y outside content extrapolated finite depth | FIXED: notifyCursor clears (NaN) outside the content area |
| A-P1-7 | hit-test tolerance unbounded → public-API caller could trigger full-array scans per mouse move | FIXED: internal clamp to [1, 50] px, documented |
| A-P1-8 | interval optimizer ran every frame even on cache hits | FIXED: subsumed by A-P0-3 cache |

## P2 (accepted / noted)

- `localPos()` → `position()` (deprecated) — FIXED.
- Lifetime attack sequences (tool dtor vs canvas dtor, scene deleteLater,
  half-destructed paint, renderer `mLastModel` raw pointer) — reviewed and
  found safe; declaration-order requirement for stack tools documented in
  well_track_tools.h.
- Grid loops allocate QPolygonF per line — bounded (≤20000 guards); revisit
  only if perf table shows it.
- Cross-extent sync semantic documented in A-P1-5 disposition.
- Domain-boundary and license checks re-verified: no QGIS source copied, no
  business entities.

Verdict after fixes: **cleared for the controlled targeted build** (round-4
exit criteria: 0 open P0/P1).
