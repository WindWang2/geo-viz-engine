# 10 — Review round 3 (tests)

Reviewer: independent subagent, 2026-09-24, against commit `ebe9b70f` +
in-flight fixes. Contract: 08-test-plan.md.

## Findings and dispositions

| # | Sev | Finding | Disposition |
|---|---|---|---|
| T-P0-1 | won't compile | test_canvas_tools called protected constrain/click hooks directly | FIXED: tests rewritten gesture-level (viewport press/move/release; marquee equivalence asserted through the resulting depth window) |
| T-P0-2 | always fail | pan tests started from full-extent fit → clamp no-ops → zero delta | FIXED: `prepare*()` zooms to a sub-window first |
| T-P0-3 | always fail | wheel zoom threshold arithmetic wrong (1 step ≠ ×0.75) | FIXED: 240 delta + span < before/1.4 assertion |
| T-P0-4 | always fail | 4/6 hit-test probes used guessed x instead of axis mapping | FIXED: probes compute x via `axis.xForValue` |
| T-P0-5 | always fail | indexOrderEmission exercised the pass-through path (n below threshold) | FIXED: 100 samples/1 bin (binned path); added reversed argmin/argmax case |
| T-P0-6 | always fail | synchronizer tests ignored clamp semantics / no-op guard | FIXED: same-extent canvases; sub-window zooms; noPingPong counts 1+1 |
| T-P0-7 | configure/compile | Qt6 Test component missing; Qt6::Svg missing for test_renderer; SDK closure PRIVATE → GUI tests can't see qgsplotcanvas.h | FIXED: Test component added; Svg linked; SDK interface PUBLIC on gui target |
| T-P1 | flaky | "paint may not have happened" before reading lastLayout | FIXED: `QTRY_VERIFY(!lastLayout().tracks.empty())` in all prepare helpers |
| T-P2 | quality | DPR-sensitive width assert; gap-probe margin vs line width; prepare returned canvas by value; visible-slice oracle end-scan bug | FIXED (batch) |

## Coverage deltas vs 08-test-plan (added this round)

- twoCurvesDistinctColors, BetweenSeries fill pixel probe, marker line probe
  (test_renderer)
- zoomToRect inverted-rect no-op; wheel Ctrl fine zoom; IncreasingUp
  orientation navigation; transient middle-button pan smoke (navigation/tools)
- cursor NaN contract when hovering the header band (tools)

## Accepted residual gaps (documented, not blocking)

- Hi-DPI render path has no automated probe (requires QT_SCALE_FACTOR runs;
  code path verified against upstream elevation pattern; DPR-aware grab width
  assert added where cheap).
- Log-axis rendering covered indirectly (demo model log track renders in
  canvas grab); no dedicated log-gridline pixel probe.
- Depth-ruler label rendering verified only through composite grabs.

Verdict after fixes: tests executable and pinned to the plan; cleared to
round 4.
