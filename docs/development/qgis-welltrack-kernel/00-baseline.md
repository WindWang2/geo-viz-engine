# 00 — Baseline (Prompt A: QGIS-native well-track plot kernel)

Date: 2026-09-24. Branch `feat/qgis-plot-welltrack-kernel`, worktree
`geo-viz-engine-wt-qgis-welltrack` (sibling of the `geo-viz-engine` submodule
checkout inside the paleo-workbench `main` worktree).

## Repository state at branch point

- Upstream: https://github.com/WindWang2/geo-viz-engine
- `origin/main` SHA: `0f89b9ed35c34bd1933b075eda620dd955098608`
  ("Merge pull request #153 from WindWang2/zcode/issue-zero-convergence")
- Open PRs: none.
- Most recent merged PR: #153 (2026-09-22, coherence GPU fallback / FillType /
  well-name collisions / GBK CSVs / sonic guard / fence validation).
- Open issues: #148 (ADR seismic slice layout — unrelated to this line).
- Relevant recent commits: `5949fef6` (facade exports QPainter track renderer),
  `5362da12` (well-log min-max sampling duplicate index fix), `5b0aa075`
  (hover info triple-paint fix), `427277d3` (coal.svg pattern), `ad8b031d`
  (cross-well depth alignment #114).
- geo-viz-engine license: MIT (see `LICENSE`). This matters for §5 license gate.

## Environment facts (locked, from paleo-workbench actual build)

| Fact | Value | Evidence |
|---|---|---|
| QGIS version | **4.2.0** | `third_party/qgis/CMakeLists.txt:67-69` (CPACK 4.2.0) |
| QGIS upstream | tag `final-4_2_0`, commit `ca5812c8b8e39b59695a3b0206fc5f3206eda0a9` | `third_party/qgis/UPSTREAM.md` |
| QGIS fork snapshot | `192422c60` ("cpp-migration-plan-v1-568-g192422c60") | `git -C third_party/qgis describe` |
| QGIS license | **GPL-2.0-or-later** | `third_party/qgis/UPSTREAM.md`, `COPYING` |
| Qt | system Qt 6.11.2 (`/usr`, pacman qt6-base 6.11.2-3) | host; `PwbQgisSdk.cmake` pins single-Qt policy |
| QGIS SDK libs | `main/native/qgis_render_bridge/build/qgis-vendor/output/lib/libqgis_{core,gui,analysis}.so` (4.2.0) | read-only vendored install tree |
| QGIS headers | consumed from `third_party/qgis/src/{core,gui,analysis}` + vendor build generated headers (`qgsconfig.h` at build root) | `cmake/PwbQgisSdk.cmake` |
| Existing import targets | `PwbQgis::Core/Gui/Analysis`, `PwbQgis::Sdk` (INTERFACE closure) | `cmake/PwbQgisSdk.cmake` |
| Compiler | GCC 16.2.1 (system); known random ICE under load — retry loop + `<=j6` policy | host memory note |
| QgsApplication init recipe | `setPrefixPath(SDK output)+init()+initQgis()`, process-wide exactly-once guard | `native/qgis_render_bridge/src/map_stack_service.cpp:1453-1459` |

## Scope of this line (A) vs the parallel line (B)

A owns: QGIS plot research, QGIS canvas/item/tool adaptation, generic track
viewport substrate, generic curve rendering, generic interval/band primitives,
coordinate transforms, hit testing, LOD/render performance, Qt/QGIS lifecycle.

B owns (`packages/geoviz-well-track-native/`, does not exist yet at branch
point): well/curve/track domain model, MD/TVD/TVDSS/TWT semantics, tops,
lithology meanings, product widget, config persistence, host adapters.

This package must not contain domain entities (`WellId`, `HorizonId`,
`Lithology`, `Facies`, `PaleoProject`, `WellRepository`, ...).

## Process constraints honored

- No modifications on `main`; worktree is a sibling directory, not inside any
  tracked checkout path of the submodule.
- Review-first: ≥4 review rounds before any build; single controlled targeted
  build at the end (`-j2`/`-j4`, hard cap `-j6`), no QGIS rebuild, no
  full-repo rebuild loops.
- Baseline `packages/geoviz_well_log` (Python/QPainter) is **not** removed or
  modified; it is the behavior reference and test-oracle candidate.
