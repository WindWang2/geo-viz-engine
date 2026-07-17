"""GUI-independent cooperative cancellation primitives for long-running jobs."""

from __future__ import annotations

from threading import Event


class JobCancelled(RuntimeError):
    """Raised at a cooperative cancellation checkpoint."""


class CancellationToken:
    """Thread-safe cancellation state shared by host and engine calculation."""

    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise JobCancelled("job cancelled")
