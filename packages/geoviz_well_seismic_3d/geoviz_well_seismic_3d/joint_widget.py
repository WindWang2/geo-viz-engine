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
        self._pierce_items: list = []
        self._probe_item = None
        # Volume identity last uploaded to the renderer (skip redundant
        # whole-volume GPU re-uploads on colour/fence/domain refreshes).
        self._last_volume_key = None
        self._cmap_applied = False
        self._overlay_specs_token = None
        self._overlay_specs_cached = None
        self._gr_legend: QLabel | None = None
        self._name_chips: list[QLabel] = []
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
            self._name_chips = []
            layout.addWidget(QLabel(f"地震三维渲染不可用: {exc}"), 1)

        try:
            from .time_map_2d import TimeSliceMap2D

            self._time_map = TimeSliceMap2D(self)
            self._time_map.well_clicked.connect(self._on_time_map_well)
            layout.addWidget(self._time_map, 0)
        except Exception:
            self._time_map = None

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
        tracks = scene.gr_well_trajectories(visible_only=True)
        token = (
            id(scene),
            scene.vertical_domain,
            value_range,
            settings.gr_color_scale,
            settings.well_width_px,
            tuple(
                (
                    well_id,
                    track.points.shape,
                    track.gr_values.shape,
                    float(track.points[0, 0]) if len(track.points) else 0.0,
                    float(track.points[-1, 2]) if len(track.points) else 0.0,
                    float(np.nansum(track.gr_values[:: max(1, len(track.gr_values) // 8)]))
                    if len(track.gr_values)
                    else 0.0,
                )
                for well_id, track in tracks.items()
            ),
        )
        if (
            self._overlay_specs_token == token
            and self._overlay_specs_cached is not None
        ):
            return self._overlay_specs_cached
        specs: dict[JointWellId, WellOverlaySpec] = {}
        missing = np.asarray(MISSING_GR_RGBA, dtype=np.float32) / 255.0
        for well_id, track in tracks.items():
            pos = self._traj_to_render(track.points)
            rgba = colorize_gr(
                track.gr_values,
                value_range=value_range,
                color_scale=settings.gr_color_scale,
            ).astype(np.float32) / 255.0
            n_seg = max(len(pos) - 1, 0)
            if n_seg == 0:
                segment_pos = np.empty((0, 3), dtype=np.float32)
                segment_colors = np.empty((0, 4), dtype=np.float32)
            else:
                segment_pos = np.empty((n_seg * 2, 3), dtype=np.float32)
                segment_pos[0::2] = pos[:-1]
                segment_pos[1::2] = pos[1:]
                finite = np.isfinite(track.gr_values)
                both = finite[:-1] & finite[1:]
                col0 = np.where(both[:, None], rgba[:-1], missing)
                col1 = np.where(both[:, None], rgba[1:], missing)
                segment_colors = np.empty((n_seg * 2, 4), dtype=np.float32)
                segment_colors[0::2] = col0
                segment_colors[1::2] = col1
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
        self._overlay_specs_token = token
        self._overlay_specs_cached = specs
        return specs

    def take_profile_widget(self):
        """Detach fence 2D profile for embedding in a separate host panel.

        The widget keeps its ``_profile`` reference so scene sync still
        refreshes the (now reparented) strip.
        """
        return getattr(self, "_profile", None)

    def take_time_map_widget(self):
        """Detach ActiveTimeSlice map for embedding in a host panel.

        Keep ``_time_map`` so load/slider sync still paints the map.
        """
        return getattr(self, "_time_map", None)

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

    def set_seismic_render_mode(self, mode: str) -> None:
        """Switch the 3D host between orthogonal planes and volume fill."""
        renderer = self._renderer
        if renderer is None:
            return
        kind = "volume" if str(mode).lower().startswith("vol") else "planes"
        set_mode = getattr(renderer, "set_render_mode", None)
        if callable(set_mode):
            set_mode(kind)
        if kind == "planes":
            set_planes = getattr(renderer, "set_planes_visible", None)
            if callable(set_planes):
                set_planes(True)
        self._discard_well_name_chips()

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
            mode = str(getattr(self._renderer, "_mode", "planes") or "planes")
            if mode == "volume":
                visual = getattr(self._renderer, "_volume_visual", None)
                if visual is not None:
                    try:
                        visual.setVisible(bool(volume))
                    except Exception:
                        pass
                set_planes = getattr(self._renderer, "set_planes_visible", None)
                if callable(set_planes):
                    try:
                        set_planes(False)
                    except Exception:
                        pass
            else:
                set_planes = getattr(self._renderer, "set_planes_visible", None)
                if callable(set_planes):
                    try:
                        set_planes(bool(volume))
                    except Exception:
                        pass
                else:
                    for attr in (
                        "_img_il",
                        "_img_xl",
                        "_img_t",
                        "_line_il",
                        "_line_xl",
                        "_line_t",
                    ):
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
                self.set_time_pierce_overlays()
            else:
                self.set_well_trajectories({})
                if not hasattr(self, "_pierce_items") or self._pierce_items is None:
                    self._pierce_items = []
                self._clear_items(self._pierce_items)
                self._discard_well_name_chips()
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
        self._overlay_specs_token = None
        self._overlay_specs_cached = None
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
        presentations = {
            item.id: item.display_name
            for item in self._scene.well_presentations()
        }
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
            # QLabel children of QOpenGLWidget never composite into the GLES
            # FBO; GLTextItem paints during paintGL so well-head names show.
            name = presentations.get(well_id, str(well_id).split(":")[-1])
            try:
                text_item = self._gl.GLTextItem(
                    pos=np.asarray(spec.head_position, dtype=np.float32),
                    text=str(name),
                    color=(253, 224, 71, 255),
                )
                view.addItem(text_item)
                self._well_items.append(text_item)
            except Exception:
                logger.debug("well-head GLTextItem failed", exc_info=True)
        self._update_gr_legend()
        self._discard_well_name_chips()

    def set_fence_curtains(self, extractions: list) -> None:
        """Public: draw fence curtains from FenceExtraction list (or active only).

        Rebuilding the meshes is expensive (~25ms for a 128-column fence) and
        depends only on (fence geometry, extraction, domain) — the scene's
        extract cache already returns the SAME FenceExtraction object for
        unchanged state, so identity-keyed skipping keeps colour/well-width
        refreshes from re-triangulating the curtains every tick.
        """
        key = tuple(
            (ext.fence_id, id(ext), tuple(ext.amplitude.shape))
            for ext in extractions
        )
        if key == getattr(self, "_last_curtain_key", None):
            return
        self._clear_items(self._curtain_items)
        self._last_curtain_key = key
        # Hold references so id() of the cached extractions cannot be reused
        # by a new array while it is part of the key.
        self._last_curtains_ref = list(extractions)
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
        azimuth: float = -45.0,
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

    def _discard_well_name_chips(self) -> None:
        """Drop leftover QLabel well-name chips (GLTextItem is the only label)."""
        chips = getattr(self, "_name_chips", None) or []
        for chip in chips:
            chip.hide()
            chip.setParent(None)
            chip.deleteLater()
        self._name_chips = []

    def _sync_well_name_chips(self) -> None:
        self._discard_well_name_chips()

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
                        data_arr = np.asarray(data, dtype=np.float32)
                        from geoviz_seismic.renderer_3d import compute_balanced_spacing

                        load_kw["spacing"] = compute_balanced_spacing(data_arr.shape)
                        self._renderer.load_volume(data_arr, **load_kw)
                        self._apply_survey_mapping()
                        self._last_volume_key = volume_key
                        # Prevent id() recycling: keep the uploaded array
                        # alive so a cache-evicted re-read cannot alias the
                        # same id and falsely match the key.
                        self._last_volume_ref = data
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
        self.set_time_pierce_overlays()
        ext = scene.extract_active_fence()
        curtains = []
        if ext is not None:
            curtains.append(ext)
        for f in scene.fences:
            if f.id != scene.active_fence_id and f.visible:
                # non-active: still extract if cached later; skip heavy for MVP
                pass
        self.set_fence_curtains(curtains)

        time_map = getattr(self, "_time_map", None)
        if time_map is not None:
            time_map.set_scene(scene)
        profile = getattr(self, "_profile", None)
        if profile is not None:
            profile.set_scene(scene)

        if scene.probe is not None:
            p = scene.probe
            self.set_probe_marker(self._index_xyz_to_world(
                scene.world_to_render_xyz(p.x, p.y, p.z)
            ))
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

    def _on_time_map_well(self, well_id: str) -> None:
        scene = self._scene
        if scene is None:
            return
        try:
            added = scene.append_fence_well(well_id)
        except ValueError as exc:
            self._status.setText(str(exc))
            return
        if added:
            self._sync_from_scene()

    def set_time_pierce_overlays(self) -> None:
        """Pierce points, names and floor polyline on ActiveTimeSlice."""
        if not hasattr(self, "_pierce_items") or self._pierce_items is None:
            self._pierce_items = []
        self._clear_items(self._pierce_items)
        scene = self._scene
        if scene is None or getattr(self, "_gl", None) is None or self._view() is None:
            return
        view = self._view()
        pierces = scene.pierce_points_on_active_time()
        if not pierces:
            return
        gl_pts = []
        for pierce in pierces:
            world = self._index_xyz_to_world(
                scene.world_to_render_xyz(pierce.x, pierce.y, pierce.z)
            )
            gl_pts.append((pierce, np.asarray(world, dtype=np.float32)))
        pos = np.vstack([p[1] for p in gl_pts])
        scatter = self._gl.GLScatterPlotItem(
            pos=pos,
            color=(0.98, 0.80, 0.08, 1.0),
            size=11,
        )
        view.addItem(scatter)
        self._pierce_items.append(scatter)
        order = list(scene.fence_well_ids)
        by_id = {pierce.well_id: world for pierce, world in gl_pts}
        line = [by_id[wid] for wid in order if wid in by_id]
        if len(line) >= 2:
            path = np.vstack(line)
            item = self._gl.GLLinePlotItem(
                pos=path,
                color=(0.13, 0.83, 0.93, 1.0),
                width=2,
                antialias=True,
            )
            view.addItem(item)
            self._pierce_items.append(item)

    def _on_profile_probe(self, s_m: float, z: float) -> None:
        if self._scene is None:
            return
        try:
            self._scene.set_probe(s_m, z)
            p = self._scene.probe
            if p is not None:
                self.set_probe_marker(self._index_xyz_to_world(
                    self._scene.world_to_render_xyz(p.x, p.y, p.z)
                ))
                idx = self._scene.probe_slice_indices()
                if idx is not None:
                    self.set_active_time_sample(idx[2])
        except Exception as exc:
            logger.debug("probe failed: %s", exc)

    def _traj_to_render(self, points: np.ndarray) -> np.ndarray:
        scene = self._scene
        if scene is None:
            idx = np.asarray(points, dtype=np.float32)
        else:
            idx = scene.world_to_render_xyz_array(points)
        return self._index_xyz_to_world(idx)

    def _apply_survey_mapping(self) -> None:
        """Push TWT / downsample mapping so 3D Z ticks match 2D Time (ms)."""
        renderer = self._renderer
        scene = self._scene
        if renderer is None or scene is None:
            return
        survey = scene.survey
        if survey is None:
            return
        vol = scene.volume_access
        strides = getattr(vol, "strides", None) or (1, 1, 1)
        set_map = getattr(renderer, "set_survey_mapping", None)
        if not callable(set_map):
            return
        try:
            set_map(
                t0_ms=float(getattr(survey, "t0_ms", 0.0) or 0.0),
                dt_ms=float(getattr(survey, "dt_ms", 0.0) or 0.0) or None,
                ds_factor=tuple(max(1, int(x)) for x in strides),
            )
        except Exception:
            logger.debug("set_survey_mapping failed", exc_info=True)

    def _index_xyz_to_world(self, idx_xyz) -> np.ndarray:
        """Volume indices (il, xl, sample) → Renderer3D world (time-down).

        ``world_to_render_xyz`` stays in sample-index space for scene math.
        GL overlays must use the same Z as slice planes: sample 0 at the
        top of the box.
        """
        pts = np.asarray(idx_xyz, dtype=np.float64)
        if pts.size == 0:
            return np.zeros((0, 3), dtype=np.float32)
        scalar = pts.ndim == 1
        if scalar:
            pts = pts.reshape(1, 3)
        si, sx, st = 1.0, 1.0, 1.0
        nt = None
        renderer = getattr(self, "_renderer", None)
        if renderer is not None:
            spacing = getattr(renderer, "_volume_spacing", None)
            if spacing is not None and len(spacing) >= 3:
                si, sx, st = float(spacing[0]), float(spacing[1]), float(spacing[2])
            vol = getattr(renderer, "_volume_data_cpu", None)
            if vol is not None:
                nt = int(vol.shape[2])
        out = np.empty((pts.shape[0], 3), dtype=np.float32)
        out[:, 0] = pts[:, 0] * si
        out[:, 1] = pts[:, 1] * sx
        if nt is not None:
            from geoviz_seismic.renderer_3d import sample_to_z

            out[:, 2] = sample_to_z(pts[:, 2], nt, st)
        else:
            out[:, 2] = pts[:, 2] * st
        if scalar:
            return out[0]
        return out

    def _curtain_mesh(self, vertices_xy: np.ndarray, ext):
        """Amplitude-coloured curtain strip along fence (#51).

        沿折线按等弧长重采样（与 extract_fence_strip 共用同一参数化，避免
        非等长线段上顶点索引分数错位），振幅经 ColormapManager 的 seismic
        色表映射为每顶点颜色，保留整体半透明。
        """
        if self._gl is None or self._scene is None:
            return None
        try:
            from pyqtgraph.opengl import MeshData, GLMeshItem
        except Exception:
            return None
        from geoviz_seismic.colormap import ColormapManager

        from .fence import sample_fence_polyline

        nt = ext.amplitude.shape[1]
        n_a = ext.amplitude.shape[0]
        # sample a few vertical levels
        n_v = min(32, nt)
        t_idx = np.linspace(0, nt - 1, n_v)
        z_vals = np.interp(t_idx, np.arange(nt), ext.sample_axis)
        # 等弧长重采样，沿向索引与 2D VD / extract_fence_strip 完全一致
        samples_xy = sample_fence_polyline(vertices_xy, n_a)
        verts = []
        for i, xy in enumerate(samples_xy):
            for k, z in enumerate(z_vals):
                rx, ry, rz = self._scene.world_to_render_xyz(
                    float(xy[0]), float(xy[1]), float(z)
                )
                verts.append([rx, ry, rz])
        verts = self._index_xyz_to_world(np.asarray(verts, dtype=np.float64))
        faces = []
        for i in range(n_a - 1):
            for k in range(n_v - 1):
                a = i * n_v + k
                b = a + 1
                c = (i + 1) * n_v + k
                d = c + 1
                faces.append([a, c, b])
                faces.append([b, c, d])
        faces = np.asarray(faces, dtype=np.uint32)
        # 振幅 → seismic 色表 → 每顶点 RGBA（GLMeshItem 支持 vertexColors）
        amp = ext.amplitude
        finite = np.isfinite(amp)
        if not np.any(finite):
            # 全缺失数据：退化为原固定半透明蓝
            colors = np.full(
                (n_a * n_v, 4), (0.3, 0.5, 0.9, 0.55), dtype=np.float32
            )
        else:
            rgba = ColormapManager.apply_colormap(
                amp, name=ColormapManager.SEISMIC
            )
            v_idx = t_idx.astype(int)
            colors = (
                rgba[:, v_idx, :].reshape(n_a * n_v, 4).astype(np.float32)
                / 255.0
            )
            # 无振幅数据处镂空，其余保留整体半透明
            mask = finite[:, v_idx].reshape(n_a * n_v)
            colors[:, 3] = np.where(mask, 0.55, 0.0)
        md = MeshData(vertexes=verts, faces=faces, vertexColors=colors)
        item = GLMeshItem(
            meshdata=md,
            smooth=False,
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
