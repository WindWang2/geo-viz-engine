from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QScrollArea
from PySide6.QtCore import Qt
import pyqtgraph as pg

from src.data.models import WellLogData, CurveData, IntervalItem
from src.renderers.well_log.config import (
    ChartConfig, TrackType, TrackConfig, CurveTrackConfig,
    IntervalTrackConfig, TextTrackConfig, SystemsTractTrackConfig,
)
from src.renderers.well_log.tracks.base import TrackWidget
from src.renderers.well_log.tracks.curve_track import CurveTrack
from src.renderers.well_log.tracks.interval_track import IntervalTrack
from src.renderers.well_log.tracks.depth_track import DepthTrack
from src.renderers.well_log.tracks.text_track import TextTrack
from src.renderers.well_log.tracks.systems_tract_track import SystemsTractTrack
from src.renderers.well_log.modules import CompositeModule, LayoutCoordinator


class ChartEngine(QWidget):
    def __init__(self, data: WellLogData, config: ChartConfig, parent=None):
        super().__init__(parent)
        self._data = data
        self._config = config
        self._tracks: list[TrackWidget] = []
        self._pyqt_tracks: list = []  # CurveTrack | DepthTrack
        self._master_viewbox: pg.ViewBox | None = None
        self._coordinator: LayoutCoordinator | None = None
        self._scroll: QScrollArea | None = None
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)  # allows horizontal fill of viewport
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._container = QWidget()
        layout = QHBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        top_depth = self._data.top_depth
        bottom_depth = self._data.bottom_depth

        for track_cfg in self._config.tracks:
            track = self._create_track(track_cfg, top_depth, bottom_depth)
            if track is None:
                continue
            self._tracks.append(track)
            layout.addWidget(track, 0, Qt.AlignmentFlag.AlignTop)

        self._link_depth_axes()

        # ── Wrap paired curves (AC+GR, RT+RXO) into CompositeModules ──
        curve_map: dict[str, any] = {}
        for t in self._tracks:
            if hasattr(t, '_curves'):
                for c in t._curves:
                    curve_map[c.name.upper()] = t

        pair_labels = [("AC", "GR"), ("RT", "RXO")]
        composite_list: list = []
        paired_keys: set = set()

        for a_name, b_name in pair_labels:
            t_a = curve_map.get(a_name.upper())
            t_b = curve_map.get(b_name.upper())
            if t_a and t_b and t_a is not t_b:
                cm = CompositeModule(label=f"{a_name}/{b_name}", children=[t_a, t_b], width_override=t_a.config.width)
                composite_list.append(cm)
                paired_keys.update([a_name.upper(), b_name.upper()])

        # Rebuild all_mods: composites first, then non-paired singletons
        final_mods: list = []
        for cm in composite_list:
            final_mods.append(cm)
        for t in self._tracks:
            if hasattr(t, '_curves'):
                if t._curves[0].name.upper() not in paired_keys:
                    final_mods.append(t)
            else:
                final_mods.append(t)

        # Wire LayoutCoordinator
        self._coordinator = LayoutCoordinator(
            master_vb=self._master_viewbox,
            modules=final_mods,
            viewport_height=400,  # placeholder, will be overwritten on first layout
        )
        self._master_viewbox.sigYRangeChanged.connect(self._coordinator.on_master_range_changed)
        self._coordinator.fit_to_viewport()
        self._scroll = scroll
        layout.addStretch()
        scroll.setWidget(self._container)
        outer.addWidget(scroll)

    def _create_track(self, cfg: TrackConfig,
                      top_depth: float, bottom_depth: float) -> TrackWidget | None:
        hh = self._config.header_height

        if cfg.type == TrackType.DEPTH:
            track = DepthTrack(cfg, top_depth, bottom_depth, hh, self)
            self._pyqt_tracks.append(track)
            return track

        if cfg.type == TrackType.CURVES:
            if not isinstance(cfg, CurveTrackConfig):
                return None
            curves = self._resolve_curves(cfg.curve_names)
            if not curves:
                return None
            track = CurveTrack(cfg, curves, hh, self)
            self._pyqt_tracks.append(track)
            return track

        if cfg.type == TrackType.INTERVAL:
            if not isinstance(cfg, IntervalTrackConfig):
                return None
            intervals = self._resolve_intervals(cfg.data_key, cfg.facies_level)
            if intervals is None:
                return None
            return IntervalTrack(cfg, intervals, top_depth, bottom_depth, hh, self)

        if cfg.type == TrackType.TEXT:
            if not isinstance(cfg, TextTrackConfig):
                return None
            intervals = self._resolve_intervals(cfg.data_key)
            if intervals is None:
                return None
            return TextTrack(cfg, intervals, top_depth, bottom_depth, hh, self)

        if cfg.type == TrackType.SYSTEMS_TRACT:
            if not isinstance(cfg, SystemsTractTrackConfig):
                return None
            intervals = self._resolve_intervals(cfg.data_key)
            if intervals is None:
                return None
            return SystemsTractTrack(cfg, intervals, top_depth, bottom_depth, hh, self)

        return None

    def _resolve_curves(self, curve_names: list[str]) -> list[CurveData]:
        result = []
        for name in curve_names:
            for c in self._data.curves:
                if c.name.upper() == name.upper():
                    result.append(c)
                    break
        return result

    def _resolve_intervals(self, data_key: str,
                           facies_level: str | None = None) -> list[IntervalItem] | None:
        if self._data.intervals is None:
            return None
        intervals = self._data.intervals
        if data_key == "facies" and facies_level:
            return getattr(intervals.facies, facies_level, None)
        return getattr(intervals, data_key, None)

    def _link_depth_axes(self):
        if not self._pyqt_tracks:
            return

        self._master_viewbox = self._pyqt_tracks[0].view_box

        for track in self._pyqt_tracks[1:]:
            track.view_box.setYLink(self._master_viewbox)

        self._master_viewbox.sigYRangeChanged.connect(self._on_depth_range_changed)

    def _on_depth_range_changed(self, viewbox, range_tuple):
        top, bottom = range_tuple[0], range_tuple[1]
        for track in self._tracks:
            if not isinstance(track, (CurveTrack, DepthTrack)):
                track.set_depth_range(top, bottom)

    def export(self, file_path: str):
        """Render all tracks to a PNG file at full chart resolution."""
        pix = self._container.grab()
        pix.save(file_path, "PNG")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._coordinator and self._scroll:
            vp_h = self._scroll.viewport().height()
            if vp_h > 0:
                self._coordinator.on_resize(vp_h)
