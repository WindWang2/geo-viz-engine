# geoviz-common

Shared canvas utilities for `geoviz-map` and `geoviz-paleo-map`.

- `PaintScheduler` — debounced repaint scheduling (~60fps).
- `BaseLayerPixmapCache` — per-layer 2x-viewport `QPixmap` buffer with pan
  headroom; subclasses supply `_make_buf_viewport` for their viewport type.
- `BaseScreenPathCache` — zoom-keyed screen-space `QPainterPath` cache with
  scale/center validation; `geoviz_paleo_map` extends it with RDP LOD paths.
- `BaseViewport` — shared world↔screen mapping geometry (scale/projection
  left to each package's viewport subclass).
- `BaseZoomPanHandler` — drag pan + cursor-anchored wheel zoom.
- `CollisionDetector` — spatial-hash label-collision grid (shared verbatim).
