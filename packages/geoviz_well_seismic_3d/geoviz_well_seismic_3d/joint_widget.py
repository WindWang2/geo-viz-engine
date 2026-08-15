"""WellSeismicJointWidget — thin facade over geoviz_seismic.Renderer3D."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .color_scales import (
    GR_COLOR_SCALES,
    MISSING_GR_RGBA,
    colorize_gr,
)
from .models import JointWellId

if TYPE_CHECKING:
    from .scene import WellSeismicScene

logger = logging.getLogger(__name__)

# Workbench seismic scale keys → Renderer3D LUT names (kept consistent with
# color_scales.SEISMIC_COLOR_SCALES used by the 2D fence profile).
_RENDER_CMAP = {
    "blue-white-red": "seismic",
    "red-white-blue": "seismic_r",
    "gray": "gray",
}


@dataclass(frozen=True)
class WellOverlaySpec:
    """Render-ready independent line segments for one GR-colored well."""

    id: JointWellId
    positions: np.ndarray
    colors: np.ndarray
    head_position: np.ndarray
    head_color: tuple[float, float, float, float]
    width_px: int


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
        # Volume identity last uploaded to the renderer (skip redundant
        # whole-volume GPU re-uploads on colour/fence/domain refreshes).
        self._last_volume_key = None
        self._cmap_applied = False
        self._gr_legend: QLabel | None = None
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
            self._set_default_render_mode()
            set_controls_visible = getattr(
                self._renderer, "set_slice_controls_visible", None
            )
            if callable(set_controls_visible):
                set_controls_visible(False)
            layout.addWidget(self._renderer, 1)
            self._gr_legend = QLabel(self._renderer)
            self._gr_legend.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            self._gr_legend.setFixedSize(92, 150)
            self._gr_legend.show()
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

    @property
    def gr_legend_title(self) -> str:
        return "GR (API)"

    def well_overlay_specs(self) -> dict[JointWellId, WellOverlaySpec]:
        """Return the exact GR segment colors and widths used by the 3D overlay."""
        scene = self._scene
        if scene is None:
            return {}
        value_range = scene.gr_value_range() or (0.0, 1.0)
        settings = scene.display_settings
        specs: dict[JointWellId, WellOverlaySpec] = {}
        for well_id, track in scene.gr_well_trajectories(
            visible_only=True
        ).items():
            pos = self._traj_to_render(track.points)
            rgba = colorize_gr(
                track.gr_values,
                value_range=value_range,
                color_scale=settings.gr_color_scale,
            ).astype(np.float32) / 255.0
            segment_pos = np.empty(
                (max(len(pos) - 1, 0) * 2, 3), dtype=np.float32
            )
            segment_colors = np.empty(
                (len(segment_pos), 4), dtype=np.float32
            )
            for index in range(max(len(pos) - 1, 0)):
                segment_pos[index * 2 : index * 2 + 2] = pos[
                    index : index + 2
                ]
                values = track.gr_values[index : index + 2]
                if np.all(np.isfinite(values)):
                    segment_colors[index * 2 : index * 2 + 2] = rgba[
                        index : index + 2
                    ]
                else:
                    segment_colors[index * 2 : index * 2 + 2] = (
                        np.asarray(MISSING_GR_RGBA, dtype=np.float32)
                        / 255.0
                    )
            head = (
                tuple(float(value) for value in rgba[0])
                if len(rgba)
                else tuple(value / 255.0 for value in MISSING_GR_RGBA)
            )
            specs[well_id] = WellOverlaySpec(
                id=well_id,
                positions=segment_pos,
                colors=segment_colors,
                head_position=(
                    pos[0]
                    if len(pos)
                    else np.zeros(3, dtype=np.float32)
                ),
                head_color=head,
                width_px=settings.well_width_px,
            )
        return specs

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
                self.set_well_trajectories(
                    scene.well_trajectories(visible_only=True)
                )
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

    def _set_default_render_mode(self) -> None:
        """Keep the joint workspace in orthogonal-slice mode by default."""
        renderer = self._renderer
        if renderer is None:
            return
        set_mode = getattr(renderer, "set_render_mode", None)
        if callable(set_mode):
            set_mode("planes")

    def set_well_trajectories(self, trajectories: dict) -> None:
        """Public: replace wells with GR-colored, outlined trajectory segments."""
        self._clear_items(self._well_items)
        if self._renderer is None or self._gl is None or self._scene is None:
            return
        view = self._view()
        if view is None:
            return
        allowed = set(trajectories)
        for well_id, spec in self.well_overlay_specs().items():
            if well_id not in allowed:
                continue
            if len(spec.positions):
                outline = self._gl.GLLinePlotItem(
                    pos=spec.positions,
                    color=(0.06, 0.09, 0.16, 1.0),
                    width=spec.width_px + 2,
                    mode="lines",
                    antialias=True,
                )
                view.addItem(outline)
                self._well_items.append(outline)
                line = self._gl.GLLinePlotItem(
                    pos=spec.positions,
                    color=spec.colors,
                    width=spec.width_px,
                    mode="lines",
                    antialias=True,
                )
                view.addItem(line)
                self._well_items.append(line)
            scatter = self._gl.GLScatterPlotItem(
                pos=np.asarray([spec.head_position], dtype=np.float32),
                color=spec.head_color,
                size=spec.width_px + 7,
            )
            view.addItem(scatter)
            self._well_items.append(scatter)
        self._update_gr_legend()

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
        """Compatibility: move IL/XL and only the active Time slice."""
        scene = self._scene
        if scene is not None and scene.registration is not None:
            try:
                scene.set_orthogonal_slice_indices(
                    inline_index=int(il),
                    crossline_index=int(xl),
                )
                scene.move_active_time_slice_to_sample(int(sample))
                self.sync_orthogonal_slices()
                return
            except Exception:
                logger.debug(
                    "scene slice-state update failed", exc_info=True
                )
        r = self._renderer
        if r is None:
            return
        apply_all = getattr(r, "apply_slice_positions", None)
        if callable(apply_all):
            try:
                apply_all(int(il), int(xl), int(sample), rebuild=True)
                return
            except Exception:
                logger.debug("apply_slice_positions failed", exc_info=True)
        # Fallback: set_position_external per axis + force rebuild
        for name, val in (("inline", il), ("crossline", xl), ("time", sample)):
            ext = getattr(r, "set_position_external", None)
            if callable(ext):
                try:
                    ext(name, int(val))
                    continue
                except Exception:
                    pass
        rebuild = getattr(r, "_update_slice_planes", None)
        if callable(rebuild):
            try:
                rebuild()
            except Exception:
                pass

    def set_active_time_sample(self, sample: int) -> None:
        """Move ActiveTimeSlice without changing IL or XL."""
        scene = self._scene
        if scene is None:
            return
        try:
            scene.move_active_time_slice_to_sample(int(sample))
            self.sync_orthogonal_slices()
        except Exception:
            logger.debug("active Time slice update failed", exc_info=True)

    def sync_orthogonal_slices(self) -> None:
        """Render the scene-owned orthogonal slice state."""
        scene = self._scene
        renderer = self._renderer
        if scene is None or renderer is None:
            return
        render_state = scene.orthogonal_slice_render_state()
        if render_state is None:
            return
        il, xl, times, active, opacity = render_state
        set_all = getattr(renderer, "set_orthogonal_slices", None)
        if callable(set_all):
            set_all(
                il,
                xl,
                times,
                active_time=active,
                time_opacity=opacity,
                time_enabled=scene.vertical_domain.value == "time",
            )
            return
        renderer.apply_slice_positions(il, xl, active, rebuild=True)

    def set_camera_pose(
        self,
        *,
        distance: float = 250.0,
        elevation: float = 30.0,
        azimuth: float = 45.0,
    ) -> None:
        """Public camera pose for host align-view (no private _view digs)."""
        r = self._renderer
        if r is None:
            return
        method = getattr(r, "set_camera_pose", None)
        if callable(method):
            try:
                method(distance=distance, elevation=elevation, azimuth=azimuth)
                return
            except Exception:
                pass
        # Last resort only inside this widget
        view = self._view()
        if view is not None:
            try:
                view.setCameraPosition(
                    distance=float(distance),
                    elevation=float(elevation),
                    azimuth=float(azimuth),
                )
            except Exception:
                pass

    def _view(self):
        """Access GL view only inside this widget (not for hosts)."""
        if self._renderer is None:
            return None
        return getattr(self._renderer, "_view", None)

    def _update_gr_legend(self) -> None:
        if self._gr_legend is None or self._scene is None:
            return
        settings = self._scene.display_settings
        value_range = self._scene.gr_value_range()
        pix = QPixmap(self._gr_legend.size())
        pix.fill(QColor(15, 23, 42, 224))
        painter = QPainter(pix)
        painter.setPen(QColor(226, 232, 240))
        painter.drawText(8, 17, self.gr_legend_title)
        top, bottom, left = 28, 128, 10
        gradient = QLinearGradient(
            float(left), float(bottom), float(left), float(top)
        )
        stops = GR_COLOR_SCALES.get(
            settings.gr_color_scale, GR_COLOR_SCALES["viridis"]
        )
        for index, color in enumerate(stops):
            gradient.setColorAt(
                index / max(len(stops) - 1, 1), QColor(*color)
            )
        painter.fillRect(
            QRectF(left, top, 14, bottom - top), QBrush(gradient)
        )
        painter.setPen(QColor(148, 163, 184))
        painter.drawRect(QRectF(left, top, 14, bottom - top))
        painter.setPen(QColor(226, 232, 240))
        if value_range is None:
            painter.drawText(29, 42, "无数据")
        else:
            painter.drawText(29, 38, f"{value_range[1]:.3g}")
            painter.drawText(29, 128, f"{value_range[0]:.3g}")
        painter.end()
        self._gr_legend.setPixmap(pix)
        self._position_gr_legend()

    def _position_gr_legend(self) -> None:
        if self._gr_legend is None or self._renderer is None:
            return
        self._gr_legend.move(
            max(self._renderer.width() - self._gr_legend.width() - 8, 0),
            8,
        )
        self._gr_legend.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._position_gr_legend()

    def _sync_from_scene(self) -> None:
        scene = self._scene
        if scene is None:
            self._status.setText("井震联合场景未加载")
            return

        vol = scene.volume_access
        data = getattr(vol, "data", None) if vol is not None else None
        if self._renderer is not None:
            if vol is None or data is None:
                # Volume detached (project switch / empty state): drop the
                # stale GL brick and planes instead of leaving the previous
                # dataset on screen while the scene says "not loaded".
                if getattr(self._renderer, "_loaded", False):
                    try:
                        self._renderer.clear()
                    except Exception:
                        logger.debug("renderer clear failed", exc_info=True)
                self._last_volume_key = None
            else:
                volume_key = (
                    getattr(vol, "source_id", None),
                    getattr(vol, "lod_level", None),
                    id(data),
                    tuple(int(x) for x in data.shape),
                )
                if volume_key != getattr(self, "_last_volume_key", None):
                    try:
                        self._set_default_render_mode()
                        # Progressive LOD upgrades must not reset the camera.
                        already = bool(getattr(self._renderer, "_loaded", False))
                        load_kw = {}
                        try:
                            # Keyword supported on Stage-7 renderer; ignore if older.
                            import inspect

                            if "preserve_camera" in inspect.signature(
                                self._renderer.load_volume
                            ).parameters:
                                load_kw["preserve_camera"] = already
                        except Exception:
                            pass
                        self._renderer.load_volume(
                            np.asarray(data, dtype=np.float32), **load_kw
                        )
                        self._last_volume_key = volume_key
                        self.sync_orthogonal_slices()
                    except Exception as exc:
                        logger.warning("load_volume failed: %s", exc)
                else:
                    # Same brick: only re-apply slice positions (cheap,
                    # differential) — domain/fence/colour changes must not
                    # re-upload the whole volume texture.
                    self.sync_orthogonal_slices()
            # Wire the scene's seismic colour scale into the 3D renderer so
            # the 2D profile and the 3D planes share one LUT source.
            cmap = _RENDER_CMAP.get(
                scene.display_settings.seismic_color_scale, "seismic"
            )
            try:
                if (
                    getattr(self._renderer, "_cmap_name", None) != cmap
                    or not getattr(self, "_cmap_applied", False)
                ):
                    self._renderer.set_colormap(cmap)
                    self._cmap_applied = True
            except Exception:
                logger.debug("set_colormap failed", exc_info=True)

        self.set_well_trajectories(
            scene.well_trajectories(visible_only=True)
        )
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
                self.set_active_time_sample(idx[2])

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
        visible_wells = len(scene.well_trajectories(visible_only=True))
        total_wells = len(scene.well_trajectories())
        self._status.setText(
            f"域={scene.vertical_domain.value} · wells={visible_wells}/{total_wells} "
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
                    self.set_active_time_sample(idx[2])
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
        # Place curtain columns at the SAME arc-length stations the amplitude
        # strip was extracted at (extract_fence_strip samples by arc length);
        # a vertex-fraction parameterization misplaces columns whenever the
        # fence polyline has uneven segment lengths.
        n_a = ext.amplitude.shape[0]
        seg = np.diff(verts_xy, axis=0)
        seg_len = np.linalg.norm(seg, axis=1)
        cum = np.concatenate([[0.0], np.cumsum(seg_len)])
        total = float(cum[-1]) or 1.0
        targets = np.clip(
            np.asarray(ext.arc_length_m, dtype=np.float64), 0.0, total
        )
        j_idx = np.clip(
            np.searchsorted(cum, targets, side="right") - 1, 0, n - 2
        )
        local = (targets - cum[j_idx]) / np.where(
            seg_len[j_idx] > 1e-12, seg_len[j_idx], 1.0
        )
        xy_rows = verts_xy[j_idx] + local[:, None] * (
            verts_xy[j_idx + 1] - verts_xy[j_idx]
        )
        verts = []
        faces = []
        for i in range(n_a):
            xy = xy_rows[i]
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
