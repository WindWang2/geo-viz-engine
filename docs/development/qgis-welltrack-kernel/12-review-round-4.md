# 12 — Review round 4 (final pre-build sign-off + build-loop discipline)

Round 4 proper = the adversarial pass in 11. This file records the final
pre-build state, the build discipline, and the owner sign-off checklist
consumed by 13-final-build-evidence.md.

## Open P0/P1 at sign-off

None. All findings from rounds 1–4 (see 09/10/11) are fixed and verified
statically; each fix is committed with its round.

## Build-loop discipline (per prompt §12)

1. Configure **only the new package** (standalone mode, SDK injected via the
   paleo-workbench env contract) — no full geo-viz-engine configure, no QGIS
   rebuild.
2. Single targeted build `-j2` (retry loop for the known GCC 16.2.1 random
   ICE / ld signal-11 family; retrying is the documented mitigation).
3. Targeted `ctest` for the package's tests only, offscreen platform;
   first-run ctest flakes are re-run once before being believed.
4. One `welltrack_demo --offscreen` smoke render.
5. Any compile error → minimal fix → **one** verification build. No
   exploratory full rebuilds.

## Owner sign-off checklist (Definition of Done mapping)

| DoD item | Status |
|---|---|
| standalone C++ package | ✅ packages/geoviz-qgis-welltrack |
| QGIS-first implementation (no second framework) | ✅ reuse matrix 03 |
| reuse ledger complete | ✅ 04 (5 rows, 0 copies) |
| license/provenance gate | ✅ 04 + LICENSES/ |
| shared depth + multi-track + curves + bands + hit test | ✅ implemented |
| zoom/pan/tools reuse QGIS | ✅ QgsPlotToolPan as-is, QgsPlotToolZoom hooks, transient tools free |
| visible-range + LOD | ✅ binary slice + min/max envelope |
| public API independent of host app | ✅ no host deps (round-1 verified) |
| B-line usable via public API only | ✅ no domain entities |
| ≥4 review rounds | ✅ 09/10/11/12 |
| no mid-development build loops | ✅ first build happens after this sign-off |
| targeted build ≤ j6 | ⏳ next step (evidence in 13) |
| lifecycle/ownership review P0/P1 clean | ✅ |
| clear commits | ✅ docs / implementation / review fixes split |
| push branch + PR, no CI wait, no merge | ⏳ after 13/14 |
