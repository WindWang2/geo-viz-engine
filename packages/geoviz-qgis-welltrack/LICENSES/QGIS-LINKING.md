# QGIS linking notes for geoviz-qgis-welltrack

This package contains **no QGIS source code**. It links the prebuilt QGIS
4.2.0 SDK (`libqgis_core.so`, `libqgis_gui.so`) through public headers only.

- QGIS upstream: https://github.com/qgis/QGIS, tag `final-4_2_0`
  (commit `ca5812c8b8e39b59695a3b0206fc5f3206eda0a9`), license
  **GPL-2.0-or-later**.
- This package's own sources are MIT (repository `LICENSE`).
- Distributing a binary that links QGIS combines GPL-2.0+ code with this
  package: GPL obligations attach to the combined work at distribution time.
  The paleo-workbench host already accepts this posture for its existing
  native QGIS bridge; this package adds no new linkage category.
- Full gate record: `docs/development/qgis-welltrack-kernel/04-license-provenance.md`.

If anyone ever needs to *copy* QGIS source into this tree: stop, update the
gate doc first, keep the upstream copyright headers, and mark the files
GPL-2.0-or-later — they may not carry the repository MIT header.
