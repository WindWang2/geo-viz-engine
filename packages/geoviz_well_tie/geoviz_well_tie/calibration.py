"""Well-seismic calibration: time-depth conversion and alignment."""

from __future__ import annotations

import numpy as np


class WellTieCalibration:
    """Manages the well-seismic tie workflow.

    Provides time-depth conversion via checkshot tables and shift/stretch
    operations for aligning synthetic seismograms with real seismic data.

    Args:
        depths_m: Depth array in metres (MD or TVD). Ascending order is the
            canonical form; a strictly descending array (as found in merged
            LAS exports) is accepted and internally reversed, since
            :func:`numpy.interp` requires an increasing xp array and would
            otherwise produce garbage (#117).
        twt_ms: Two-way travel time array in milliseconds (same length as *depths_m*).
    """

    def __init__(self, depths_m: np.ndarray, twt_ms: np.ndarray):
        if len(depths_m) != len(twt_ms):
            raise ValueError(
                f"depths_m and twt_ms must have same length, "
                f"got {len(depths_m)} and {len(twt_ms)}"
            )
        self._depths = np.asarray(depths_m, dtype=np.float64)
        self._twt = np.asarray(twt_ms, dtype=np.float64)
        if len(self._depths) > 1 and self._depths[0] > self._depths[-1]:
            self._depths = self._depths[::-1].copy()
            self._twt = self._twt[::-1].copy()

    @property
    def depths(self) -> np.ndarray:
        return self._depths

    @property
    def twt(self) -> np.ndarray:
        return self._twt

    def depth_to_twt(self, depth: float | np.ndarray) -> float | np.ndarray:
        """Convert depth(s) to two-way travel time via interpolation."""
        result = np.interp(depth, self._depths, self._twt)
        return float(result) if np.ndim(result) == 0 else result

    def twt_to_depth(self, twt: float | np.ndarray) -> float | np.ndarray:
        """Convert two-way travel time to depth via interpolation."""
        result = np.interp(twt, self._twt, self._depths)
        return float(result) if np.ndim(result) == 0 else result

    def resample_to_twt(
        self,
        log_values: np.ndarray,
        dt_ms: float,
        t0_ms: float = 0.0,
    ) -> np.ndarray:
        """Resample a log from depth to TWT using the calibration curve.

        Args:
            log_values: Log values sampled at *self.depths*.
            dt_ms: Output sample interval in milliseconds.
            t0_ms: Start time for output (default 0).

        Returns:
            Resampled log values on a regular TWT grid.
        """
        log_values = np.asarray(log_values, dtype=np.float64)
        t_max = float(self._twt[-1])
        twt_out = np.arange(t0_ms, t_max + dt_ms, dt_ms, dtype=np.float64)
        depth_at_twt = np.interp(twt_out, self._twt, self._depths)
        return np.interp(depth_at_twt, self._depths, log_values).astype(np.float32)

    @classmethod
    def from_sonic(
        cls,
        depths_m: np.ndarray,
        sonic_us_m: np.ndarray,
    ) -> WellTieCalibration:
        """Create a calibration from sonic logs (integrated travel time).

        Non-finite depth/sonic samples are masked before integration (a NaN
        sonic interval would otherwise poison the cumulative TWT of every
        deeper sample, #117), and a strictly descending depth array is
        reversed so the integrated TWT comes out increasing from the
        wellhead instead of negative (#117).

        Args:
            depths_m: Depth array in metres.
            sonic_us_m: Sonic transit time in µs/m.

        Returns:
            New :class:`WellTieCalibration` with TWT derived from sonic.

        Raises:
            ValueError: If fewer than two finite depth/sonic samples remain
                after masking, or the input lengths differ.
        """
        depths = np.asarray(depths_m, dtype=np.float64)
        sonic = np.asarray(sonic_us_m, dtype=np.float64)
        if len(depths) != len(sonic):
            raise ValueError(
                f"depths_m and sonic_us_m must have same length, "
                f"got {len(depths)} and {len(sonic)}"
            )
        finite = np.isfinite(depths) & np.isfinite(sonic)
        depths = depths[finite]
        sonic = sonic[finite]
        if len(depths) < 2:
            raise ValueError(
                "from_sonic needs at least two finite depth/sonic samples, "
                f"got {len(depths)}"
            )
        if depths[0] > depths[-1]:
            depths = depths[::-1].copy()
            sonic = sonic[::-1].copy()
        dz = np.diff(depths)
        # Trapezoidal one-way time (µs) over each interval, then convert to
        # two-way travel time in milliseconds: OWT_µs * 2 / 1000 = TWT_ms.
        owt_us = dz * (sonic[:-1] + sonic[1:]) / 2.0
        twt = np.zeros_like(depths)
        twt[1:] = 2.0 * np.cumsum(owt_us) / 1000.0
        return cls(depths, twt)

    def to_td_pairs(self) -> dict[str, np.ndarray]:
        """Export T-D pairs as a dict for CSV serialization."""
        return {
            "depth_m": self._depths.copy(),
            "twt_ms": self._twt.copy(),
        }


def resample_to_seismic_grid(
    values: np.ndarray,
    src_twt: np.ndarray,
    dt_ms: float,
    t0_ms: float,
    n_samples: int,
) -> np.ndarray:
    """Resample trace values from an irregular TWT grid to the seismic volume's regular grid.

    Values outside the source TWT range are zero-filled.

    Args:
        values: Trace values sampled at *src_twt* positions.
        src_twt: Source TWT positions (may be irregular).
        dt_ms: Seismic volume sample interval in milliseconds.
        t0_ms: Seismic volume first sample time in milliseconds.
        n_samples: Number of output samples.

    Returns:
        ``(n_samples,)`` float32 resampled trace.
    """
    values = np.asarray(values, dtype=np.float64)
    src_twt = np.asarray(src_twt, dtype=np.float64)
    target_twt = np.arange(n_samples, dtype=np.float64) * dt_ms + t0_ms
    result = np.interp(target_twt, src_twt, values, left=0.0, right=0.0)
    return result.astype(np.float32)


def shift_depths(depths: np.ndarray, depth_shift: float) -> np.ndarray:
    """Apply a bulk depth offset to a depth axis.

    Promoted from ``paleo_workbench/viz/geomodel/well_seismic.py::
    WellSeismicTieCalibration.align_twt_depth``. Used after
    :func:`~geoviz_well_tie.auto_tie.correlate_synthetic_to_trace` has converted a
    sample lag into a physical depth offset, to slide the log depth axis onto the
    seismic. Returns a new array; the input is not modified.

    Args:
        depths: Depth axis (any unit).
        depth_shift: Offset added to every sample, in the same unit as ``depths``.

    Returns:
        Shifted depth axis, same shape as ``depths``.
    """
    return np.asarray(depths) + depth_shift
