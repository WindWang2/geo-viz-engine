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
    """Compose seismic orthogonal 3D slices with joint-scene overlays.

    Public overlay API: ``set_well_trajectories``, ``set_fence_curtains``,
    ``set_probe_marker``, ``set_slice_indices`` — hosts must not touch private
    Renderer3D ``_view``.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene: WellSeismicScene | None = None
        self._renderer = None
        self._gl = None
        self._well_items: list = []
        self._curtain_items: list = []
        self._probe_item = None
        self._status = QLabel("井震联合场景未加载")
        self._status.setStyleSheet("color: #64748b; padding: 4px 8px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        try:
            from geoviz_seismic.renderer_3d import Renderer3D
            import pyqtgraph.opengl as gl

            self._gl = gl
            self._renderer = Renderer3D(self)
            layout.addWidget(self._renderer, 1)
        except Exception as exc:  # pragma: no cover
            logger.warning("Renderer3D unavailable: %s", exc)
            self._renderer = None
            layout.addWidget(QLabel(f"地震三维渲染不可用: {exc}"), 1)

        try:
            from .profile_2d import FenceProfile2D

            self._profile = FenceProfile2D(self)
            self._profile.probe_changed.connect(self._on_profile_probe)
            layout.addWidget(self._profile, 0)
        except Exception:
            self._profile = None

        layout.addWidget(self._status, 0)

    @property
    def scene(self) -> WellSeismicScene | None:
        return self._scene

    @property
    def renderer(self):
        return self._renderer

    @property
    def profile_widget(self):
        """Public access to the fence 2D profile (may be reparented by hosts)."""
        return getattr(self, "_profile", None)

    def take_profile_widget(self):
        """Detach fence 2D profile for embedding in a separate host panel."""
        profile = getattr(self, "_profile", None)
        self._profile = None
        return profile

    def slice_indices(self) -> tuple[int, int, int] | None:
        """Current orthogonal slice indices (il, xl, sample) if renderer is ready."""
        r = self._renderer
        if r is None:
            return None
        get_pos = getattr(r, "get_slice_positions", None)
        if callable(get_pos):
            try:
                return tuple(int(x) for x in get_pos())  # type: ignore[return-value]
            except Exception:
                pass
        try:
            return (
                int(getattr(r, "_il_pos", 0) or 0),
                int(getattr(r, "_xl_pos", 0) or 0),
                int(getattr(r, "_t_pos", 0) or 0),
            )
        except Exception:
            return None

    def set_layer_visibility(
        self,
        *,
        wells: bool = True,
        fences: bool = True,
        volume: bool = True,
    ) -> None:
        """Show/hide joint layers independently (volume off must not hide wells/fences)."""
        scene = self._scene
        if scene is not None:
            for f in scene.fences:
                f.visible = bool(fences)
        # Keep the Renderer3D widget visible so overlays stay; only hide planes.
        if self._renderer is not None:
            try:
                self._renderer.setVisible(True)
            except Exception:
                pass
            set_planes = getattr(self._renderer, "set_planes_visible", None)
            if callable(set_planes):
                try:
                    set_planes(bool(volume))
                except Exception:
                    pass
            else:
                # Fallback: hide known plane attributes without hiding widget
                for attr in ("_img_il", "_img_xl", "_img_t", "_line_il", "_line_xl", "_line_t"):
                    item = getattr(self._renderer, attr, None)
                    if item is None:
                        continue
                    try:
                        item.setVisible(bool(volume))
                    except Exception:
                        pass
        # Rebuild overlays according to flags
        if scene is not None:
            if wells:
                self.set_well_trajectories(scene.well_trajectories())
            else:
                self.set_well_trajectories({})
            if fences:
                ext = scene.extract_active_fence()
                self.set_fence_curtains([ext] if ext is not None else [])
            else:
                self.set_fence_curtains([])
        for item in self._well_items:
            try:
                item.setVisible(bool(wells))
            except Exception:
                pass
        for item in self._curtain_items:
            try:
                item.setVisible(bool(fences))
            except Exception:
                pass

    def set_scene(self, scene: WellSeismicScene) -> None:
        self._scene = scene
        self._sync_from_scene()

    def set_well_trajectories(self, trajectories: dict) -> None:
        """Public: replace well polylines from trajectory map name→WellTrajectory3D."""
        self._clear_items(self._well_items)
        if self._renderer is None or self._gl is None or self._scene is None:
            return
        view = self._view()
        if view is None:
            return
        for traj in trajectories.values():
            pts = traj.points
            if pts.size == 0:
                continue
            pos = self._traj_to_render(pts)
            color = (0.2, 0.9, 0.4, 1.0) if traj.has_td else (0.9, 0.7, 0.2, 1.0)
            line = self._gl.GLLinePlotItem(pos=pos, color=color, width=2, antialias=True)
            view.addItem(line)
            self._well_items.append(line)
            scatter = self._gl.GLScatterPlotItem(pos=pos[:1], color=color, size=8)
            view.addItem(scatter)
            self._well_items.append(scatter)

    def set_fence_curtains(self, extractions: list) -> None:
        """Public: draw fence curtains from FenceExtraction list (or active only)."""
        self._clear_items(self._curtain_items)
        if self._renderer is None or self._gl is None or self._scene is None:
            return
        view = self._view()
        if view is None:
            return
        scene = self._scene
        for ext in extractions:
            fence = None
            for f in scene.fences:
                if f.id == ext.fence_id:
                    fence = f
                    break
            if fence is None or not fence.visible:
                continue
            mesh = self._curtain_mesh(fence.vertices_xy, ext)
            if mesh is not None:
                view.addItem(mesh)
                self._curtain_items.append(mesh)

    def set_probe_marker(self, xyz_render: tuple[float, float, float] | None) -> None:
        if self._probe_item is not None and self._view() is not None:
            try:
                self._view().removeItem(self._probe_item)
            except Exception:
                pass
            self._probe_item = None
        if xyz_render is None or self._gl is None or self._view() is None:
            return
        pos = np.array([xyz_render], dtype=np.float32)
        self._probe_item = self._gl.GLScatterPlotItem(
            pos=pos, color=(1.0, 0.3, 0.2, 1.0), size=12
        )
        self._view().addItem(self._probe_item)

    def set_slice_indices(self, il: int, xl: int, sample: int) -> None:
        """Drive orthogonal slices via Renderer3D public API when available."""
        r = self._renderer
        if r is None:
            return
        for name, val in (("inline", il), ("crossline", xl), ("time", sample)):
            method = getattr(r, "set_slice", None) or getattr(r, "set_slice_position", None)
            if callable(method):
                try:
                    method(name, int(val))
                    continue
                except Exception:
                    pass
            # Fallback: sliders if present
            slider = {
                "inline": getattr(r, "_il_slider", None),
                "crossline": getattr(r, "_xl_slider", None),
                "time": getattr(r, "_t_slider", None),
            }.get(name)
            if slider is not None:
                try:
                    slider.setValue(int(val))
                except Exception:
                    pass

    def _view(self):
        """Access GL view only inside this widget (not for hosts)."""
        if self._renderer is None:
            return None
        return getattr(self._renderer, "_view", None)

    def _sync_from_scene(self) -> None:
        scene = self._scene
        if scene is None:
            self._status.setText("井震联合场景未加载")
            return

        vol = scene.volume_access
        if self._renderer is not None and vol is not None:
            data = getattr(vol, "data", None)
            if data is not None:
                try:
                    self._renderer.load_volume(np.asarray(data, dtype=np.float32))
                except Exception as exc:
                    logger.warning("load_volume failed: %s", exc)

        self.set_well_trajectories(scene.well_trajectories())
        ext = scene.extract_active_fence()
        curtains = []
        if ext is not None:
            curtains.append(ext)
        for f in scene.fences:
            if f.id != scene.active_fence_id and f.visible:
                # non-active: still extract if cached later; skip heavy for MVP
                pass
        self.set_fence_curtains(curtains)

        if self._profile is not None:
            self._profile.set_scene(scene)

        if scene.probe is not None:
            p = scene.probe
            self.set_probe_marker(scene.world_to_render_xyz(p.x, p.y, p.z))
            idx = scene.probe_slice_indices()
            if idx is not None:
                self.set_slice_indices(*idx)

        survey = scene.survey
        survey_txt = (
            f"IL {survey.iline_start}+{survey.n_inlines} · XL {survey.xline_start}+{survey.n_crosslines}"
            if survey
            else "no survey"
        )
        reg = scene.registration
        reg_txt = (
            f" · vol={reg.n_inline}x{reg.n_crossline}x{reg.n_sample}"
            if reg
            else ""
        )
        preview = " · preview" if scene.preview_mode else ""
        self._status.setText(
            f"域={scene.vertical_domain.value} · wells={len(scene.well_trajectories())} "
            f"· fences={len(scene.fences)} · {survey_txt}{reg_txt}{preview}"
        )

    def _on_profile_probe(self, s_m: float, z: float) -> None:
        if self._scene is None:
            return
        try:
            self._scene.set_probe(s_m, z)
            p = self._scene.probe
            if p is not None:
                self.set_probe_marker(self._scene.world_to_render_xyz(p.x, p.y, p.z))
                idx = self._scene.probe_slice_indices()
                if idx is not None:
                    self.set_slice_indices(*idx)
        except Exception as exc:
            logger.debug("probe failed: %s", exc)

    def _traj_to_render(self, points: np.ndarray) -> np.ndarray:
        scene = self._scene
        out = np.zeros((len(points), 3), dtype=np.float32)
        if scene is None:
            return np.asarray(points, dtype=np.float32)
        for i, (x, y, z) in enumerate(points):
            out[i] = scene.world_to_render_xyz(float(x), float(y), float(z))
        return out

    def _curtain_mesh(self, vertices_xy: np.ndarray, ext):
        """Build a simple textured-ish mesh strip along fence in render space."""
        if self._gl is None or self._scene is None:
            return None
        try:
            from pyqtgraph.opengl import MeshData, GLMeshItem
        except Exception:
            return None
        verts_xy = np.asarray(vertices_xy, dtype=np.float64)
        n = len(verts_xy)
        nt = ext.amplitude.shape[1]
        # sample a few vertical levels
        n_v = min(32, nt)
        t_idx = np.linspace(0, nt - 1, n_v)
        z_vals = np.interp(t_idx, np.arange(nt), ext.sample_axis)
        # resample path to match along samples of extract
        n_a = ext.amplitude.shape[0]
        # use extract arc points
        verts = []
        faces = []
        for i in range(n_a):
            # position along polyline by arc fraction
            frac = i / max(n_a - 1, 1)
            # approximate XY by linear along original verts
            # better: use same parameterization as extract — place via fence verts
            idx_f = frac * (n - 1)
            j = int(idx_f)
            j = min(j, n - 2)
            local = idx_f - j
            xy = verts_xy[j] * (1 - local) + verts_xy[j + 1] * local
            for k, z in enumerate(z_vals):
                rx, ry, rz = self._scene.world_to_render_xyz(float(xy[0]), float(xy[1]), float(z))
                verts.append([rx, ry, rz])
        verts = np.asarray(verts, dtype=np.float32)
        for i in range(n_a - 1):
            for k in range(n_v - 1):
                a = i * n_v + k
                b = a + 1
                c = (i + 1) * n_v + k
                d = c + 1
                faces.append([a, c, b])
                faces.append([b, c, d])
        faces = np.asarray(faces, dtype=np.uint32)
        md = MeshData(vertexes=verts, faces=faces)
        item = GLMeshItem(
            meshdata=md,
            smooth=False,
            color=(0.3, 0.5, 0.9, 0.55),
            shader="balloon",
            glOptions="translucent",
        )
        return item

    def _clear_items(self, items: list) -> None:
        view = self._view()
        if view is None:
            items.clear()
            return
        for it in items:
            try:
                view.removeItem(it)
            except Exception:
                pass
        items.clear()
