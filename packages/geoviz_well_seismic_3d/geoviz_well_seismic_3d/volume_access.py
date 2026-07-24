"""Injectable volume access for joint-scene slicing (LOD/async backends later)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class VolumeAccess(Protocol):
    """Minimal volume handle: shape + orthogonal slices.

    Later tickets may add async fence sampling and brick/pyramid LOD behind
    this protocol without changing WellSeismicScene consumers.
    """

    @property
    def shape(self) -> tuple[int, int, int]:
        """(n_inline, n_crossline, n_sample)."""
        ...

    def slice_inline(self, il_index: int) -> np.ndarray:
        """2-D slice at inline index → shape (n_crossline, n_sample)."""
        ...

    def slice_crossline(self, xl_index: int) -> np.ndarray:
        """2-D slice at crossline index → shape (n_inline, n_sample)."""
        ...

    def slice_time(self, sample_index: int) -> np.ndarray:
        """2-D horizontal slice → shape (n_inline, n_crossline)."""
        ...


class InMemoryVolumeAccess:
    """CPU ndarray volume for tests and small demos."""

    def __init__(self, data: np.ndarray) -> None:
        arr = np.asarray(data)
        if arr.ndim != 3:
            raise ValueError("volume data must be 3-D (il, xl, sample)")
        self._data = arr

    @property
    def shape(self) -> tuple[int, int, int]:
        ni, nx, nt = self._data.shape
        return int(ni), int(nx), int(nt)

    @property
    def data(self) -> np.ndarray:
        return self._data

    def slice_inline(self, il_index: int) -> np.ndarray:
        return np.asarray(self._data[il_index, :, :])

    def slice_crossline(self, xl_index: int) -> np.ndarray:
        return np.asarray(self._data[:, xl_index, :])

    def slice_time(self, sample_index: int) -> np.ndarray:
        return np.asarray(self._data[:, :, sample_index])
