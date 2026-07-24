"""WellSeismicJointWidget — thin facade over geoviz_seismic.Renderer3D."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from .scene import WellSeismicScene

logger = logging.getLogger(__name__)


class WellSeismicJointWidget(QWidget):
    """Compose seismic orthogonal 3D slices with joint-scene well overlays.

    Slice rendering is delegated to ``geoviz_seismic.Renderer3D`` (facade);
    well trajectories come from :class:`WellSeismicScene`.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene: WellSeismicScene | None = None
        self._renderer = None
        self._status = QLabel("井震联合场景未加载")
        self._status.setStyleSheet("color: #64748b; padding: 4px 8px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        try:
            from geoviz_seismic.renderer_3d import Renderer3D

            self._renderer = Renderer3D(self)
            layout.addWidget(self._renderer, 1)
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("Renderer3D unavailable: %s", exc)
            self._renderer = None
            layout.addWidget(
                QLabel(f"地震三维渲染不可用: {exc}"),
                1,
            )

        layout.addWidget(self._status, 0)

    @property
    def scene(self) -> WellSeismicScene | None:
        return self._scene

    @property
    def renderer(self):
        """Underlying Renderer3D instance (may be None if import failed)."""
        return self._renderer

    def set_scene(self, scene: WellSeismicScene) -> None:
        """Bind a scene and push volume + well trajectories into the facade."""
        self._scene = scene
        self._sync_from_scene()

    def _sync_from_scene(self) -> None:
        scene = self._scene
        if scene is None:
            self._status.setText("井震联合场景未加载")
            return

        vol = scene.volume_access
        n_wells = len(scene.well_trajectories())
        domain = scene.vertical_domain.value

        if self._renderer is not None and vol is not None:
            data = self._dense_volume_array(vol)
            if data is not None:
                try:
                    self._renderer.load_volume(np.asarray(data, dtype=np.float32))
                except Exception as exc:
                    logger.warning("load_volume failed: %s", exc)
                    self._status.setText(f"体加载失败: {exc}")
                    return
            else:
                logger.info(
                    "VolumeAccess has no dense array; orthogonal slices stay on injectable scene API"
                )

        self._overlay_wells()
        survey = scene.survey
        survey_txt = (
            f"IL {survey.iline_start}–{survey.iline_start + (survey.n_inlines - 1) * survey.iline_step}, "
            f"XL {survey.xline_start}–{survey.xline_start + (survey.n_crosslines - 1) * survey.xline_step}"
            if survey
            else "no survey"
        )
        self._status.setText(
            f"域={domain} · wells={n_wells} · {survey_txt}"
        )

    def _overlay_wells(self) -> None:
        """Draw well polylines into the Renderer3D view when available."""
        scene = self._scene
        if scene is None or self._renderer is None:
            return
        view = getattr(self._renderer, "_view", None)
        if view is None:
            return

        # Remove previous well items if we stored them
        prev = getattr(self, "_well_items", None)
        if prev:
            for item in prev:
                try:
                    view.removeItem(item)
                except Exception:
                    pass
        self._well_items = []

        try:
            import pyqtgraph.opengl as gl
        except Exception:
            return

        for traj in scene.well_trajectories().values():
            pts = traj.points
            if pts.size == 0:
                continue
            # Renderer3D index space is roughly (il_idx, xl_idx, sample).
            # Map world XY via survey when present; Z(ms) → sample via dt.
            pos = self._world_to_render_coords(pts)
            if pos is None or len(pos) == 0:
                continue
            color = (0.2, 0.9, 0.4, 1.0) if traj.has_td else (0.9, 0.7, 0.2, 1.0)
            item = gl.GLLinePlotItem(
                pos=pos,
                color=color,
                width=2,
                antialias=True,
            )
            view.addItem(item)
            self._well_items.append(item)
            # Wellhead marker
            scatter = gl.GLScatterPlotItem(
                pos=pos[:1],
                color=color,
                size=8,
            )
            view.addItem(scatter)
            self._well_items.append(scatter)

    @staticmethod
    def _dense_volume_array(vol) -> np.ndarray | None:
        """Return a dense (il, xl, sample) array when the access can provide one.

        ``InMemoryVolumeAccess`` exposes ``.data``. Pure slice-only backends
        return None — the scene API remains the sampling seam for those.
        """
        data = getattr(vol, "data", None)
        if data is not None:
            return np.asarray(data)
        return None

    def _world_to_render_coords(self, points: np.ndarray) -> np.ndarray | None:
        scene = self._scene
        if scene is None or scene.survey is None:
            # Fallback: treat x,y,z as already in render-ish space
            return np.asarray(points, dtype=np.float32)

        survey = scene.survey
        out = np.zeros((len(points), 3), dtype=np.float32)
        for i, (x, y, z) in enumerate(points):
            il, xl = survey.xy_to_il_xl(float(x), float(y))
            il_idx = (il - survey.iline_start) / (survey.iline_step or 1)
            xl_idx = (xl - survey.xline_start) / (survey.xline_step or 1)
            if survey.dt_ms and survey.dt_ms > 0:
                t_idx = (float(z) - survey.t0_ms) / survey.dt_ms
            else:
                t_idx = float(z)
            out[i] = (il_idx, xl_idx, t_idx)
        return out
