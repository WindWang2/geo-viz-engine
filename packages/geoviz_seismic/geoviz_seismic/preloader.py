"""SeismicPreloadManager -- Drag velocity prediction & async preloading queue."""
from __future__ import annotations

from enum import IntEnum
import threading
import time
from typing import Any


class PreloadPriority(IntEnum):
    P0_IMMEDIATE = 0
    P1_DIRECTIONAL = 1
    P2_SYMMETRIC = 2


class CancellationToken:
    """Token to signal cancellation of obsolete preloading tasks."""

    def __init__(self, generation: int, manager: SeismicPreloadManager):
        self.generation = generation
        self._manager = manager

    def is_cancelled(self) -> bool:
        return self._manager.current_generation != self.generation


class DragTracker:
    """Tracks slice slider movement timestamps to calculate velocity and direction."""

    def __init__(self):
        self.last_pos: int = 0
        self.last_time: float = time.monotonic()
        self.velocity: float = 0.0

    def update(self, pos: int, timestamp: float | None = None) -> float:
        now = timestamp if timestamp is not None else time.monotonic()
        dt = now - self.last_time
        if dt > 1e-4:
            self.velocity = (pos - self.last_pos) / dt
        self.last_pos = pos
        self.last_time = now
        return self.velocity

    def is_moving_positive(self) -> bool:
        return self.velocity > 0.0


class SeismicPreloadManager:
    """Manages generation tokens and priority queues for async slice preloading."""

    def __init__(self):
        self._lock = threading.Lock()
        self.current_generation: int = 0

    def next_generation(self) -> CancellationToken:
        with self._lock:
            self.current_generation += 1
            return CancellationToken(self.current_generation, self)
