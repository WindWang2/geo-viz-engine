"""Frame-budget LOD policy and direction-aware prefetch for slice browsing (#1082).

The interaction contract:

    user drags a slice slider
      → frame budget (default 16 ms) decides the served LOD
      → reads that blow the budget coarsen the level (up to max_lod)
      → interaction stops for IDLE_MS (250 ms)
      → async refine one level finer, repeat until lod0 replaces the view
        without flicker (finer result simply overwrites the panel)

``LodPolicy`` is a pure, clock-injectable state machine (headless-testable).
``DirectionalPrefetcher`` follows the slider's movement direction at the
CURRENT lod; a new position/generation supersedes any in-flight batch.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable

DEFAULT_FRAME_BUDGET_MS = 16.0
DEFAULT_IDLE_MS = 250.0


class LodPolicy:
    """Decides which LOD level serves the next interactive read.

    Tracks read latencies per lod level; a level whose (smoothed) latency
    exceeds the frame budget is demoted during interaction. When interaction
    goes quiet for ``idle_ms``, the policy steps one level finer per tick
    until lod 0 (idle refinement — the panel replaces coarse frames without
    flicker because finer results arrive later and overwrite).
    """

    def __init__(
        self,
        *,
        max_lod: int = 4,
        frame_budget_ms: float = DEFAULT_FRAME_BUDGET_MS,
        idle_ms: float = DEFAULT_IDLE_MS,
        clock: Callable[[], float] = time.monotonic,
        smoothing: float = 0.3,
    ):
        self.max_lod = max_lod
        self.frame_budget_ms = float(frame_budget_ms)
        self.idle_ms = float(idle_ms)
        self._clock = clock
        self._alpha = smoothing
        self._current = 0
        self._interacting = False
        self._last_activity = self._clock()
        # Smoothed read+render latency per lod level (ms).
        self._latency_ms: dict[int, float] = {}
        self._recent_frames: deque[float] = deque(maxlen=8)

    # ------------------------------------------------------------ state --
    @property
    def current_lod(self) -> int:
        return self._current

    def begin_interaction(self) -> None:
        self._interacting = True
        self._last_activity = self._clock()

    def end_interaction(self) -> None:
        self._interacting = False
        self._last_activity = self._clock()

    def touch(self) -> None:
        """Any user-driven request counts as activity (drag continuation)."""
        self._last_activity = self._clock()

    def record_read(self, lod: int, elapsed_ms: float) -> None:
        prev = self._latency_ms.get(lod)
        self._latency_ms[lod] = (
            elapsed_ms if prev is None else prev + self._alpha * (elapsed_ms - prev)
        )

    def record_frame(self, elapsed_ms: float) -> None:
        self._recent_frames.append(float(elapsed_ms))

    def smoothed_frame_ms(self) -> float | None:
        if not self._recent_frames:
            return None
        return sum(self._recent_frames) / len(self._recent_frames)

    # ------------------------------------------------------------ policy --
    def select_lod(self) -> int:
        """LOD for the next interactive read (called after begin/touch)."""
        if self._interacting:
            # Demote while the CURRENT level keeps blowing the budget.
            lat = self._latency_ms.get(self._current)
            if lat is not None and lat > self.frame_budget_ms:
                self._current = min(self._current + 1, self.max_lod)
        return self._current

    def idle_refine_ready(self) -> bool:
        """True when the quiet window elapsed and a finer level exists."""
        if self._interacting:
            return False
        if self._current == 0:
            return False
        return (self._clock() - self._last_activity) >= self.idle_ms / 1000.0

    def refine_step(self) -> int | None:
        """Consume one idle-refine step; returns the refined lod or None."""
        if not self.idle_refine_ready():
            return None
        self._current = max(0, self._current - 1)
        self._last_activity = self._clock()  # one step per quiet window
        return self._current

    def reset(self) -> None:
        self._current = 0
        self._interacting = False
        self._last_activity = self._clock()
        self._latency_ms.clear()
        self._recent_frames.clear()


class DirectionalPrefetcher:
    """Background prefetch that follows slider movement at the current LOD.

    Production rules (#1082 / #1080 prototype promotion):
    - direction = sign of the latest position delta; ahead only in that
      direction (no wasted -side reads);
    - a new ``update`` supersedes any in-flight batch (generation counter);
    - runs on its own daemon thread: it never blocks the interactive read
      path and never occupies more than one background read at a time.
    """

    def __init__(
        self,
        read_fn: Callable[[int, int], None],
        *,
        ahead: int = 4,
        max_lod: int = 4,
    ):
        self._read_fn = read_fn
        self.ahead = int(ahead)
        self.max_lod = int(max_lod)
        self._lock = threading.Lock()
        self._generation = 0
        self._thread: threading.Thread | None = None
        self._last_position: int | None = None
        self._direction = 1

    def update(self, position: int, *, lod: int = 0) -> None:
        """Record a new interactive position; queue a directional batch.

        The FIRST position only establishes the baseline (movement direction
        is unknown yet, so any "ahead" guess would waste half its reads).
        """
        position = int(position)
        lod = max(0, min(int(lod), self.max_lod))
        with self._lock:
            if self._last_position is None:
                self._last_position = position
                self._generation += 1  # invalidate any prior batch
                return
            delta = position - self._last_position
            if delta:
                self._direction = 1 if delta > 0 else -1
            self._last_position = position
            self._generation += 1
            gen = self._generation
            batch = [
                position + self._direction * k for k in range(1, self.ahead + 1)
            ]
        if self._thread is not None and self._thread.is_alive():
            return  # superseded batches stop themselves via the generation
        self._thread = threading.Thread(target=self._work, args=(gen, batch, lod), daemon=True)
        self._thread.start()

    def _work(self, generation: int, batch: list[int], lod: int) -> None:
        for pos in batch:
            with self._lock:
                if generation != self._generation:
                    return
            try:
                self._read_fn(pos, lod)
            except Exception:
                return  # out-of-range or read failure ends the batch quietly

    def cancel(self) -> None:
        with self._lock:
            self._generation += 1
