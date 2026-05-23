from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .track_base import BaseTrack


class LayoutCoordinator:
    """Synchronizes depth range across all tracks in a canvas."""

    def __init__(self, tracks: list[BaseTrack] | None = None):
        self._tracks: list[BaseTrack] = tracks or []

    @property
    def tracks(self) -> list[BaseTrack]:
        return self._tracks

    def add_track(self, track: BaseTrack):
        self._tracks.append(track)

    def remove_track(self, track: BaseTrack):
        self._tracks.remove(track)

    @property
    def total_width(self) -> int:
        return sum(t.width for t in self._tracks if getattr(t, '_visible', True))

    def set_depth_range(self, top: float, bottom: float):
        for track in self._tracks:
            track.set_depth_range(top, bottom)
