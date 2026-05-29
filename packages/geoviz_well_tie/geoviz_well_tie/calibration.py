"""Well-seismic calibration: time-depth conversion and alignment."""

from __future__ import annotations

import numpy as np


class WellTieCalibration:
    """Manages the well-seismic tie workflow.

    Provides time-depth conversion via checkshot tables and shift/stretch
    operations for aligning synthetic seismograms with real seismic data.

    Args:
        depths_m: Depth array in metres (MD or TVD).
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

    @property
    def depths(self) -> np.ndarray:
        return self._depths

    @property
    def twt(self) -> np.ndarray:
        return self._twt

    def depth_to_twt(self, depth: float | np.ndarray) -> float | np.ndarray:
        """Convert depth(s) to two-way travel time via interpolation."""
        return float(np.interp(depth, self._depths, self._twt))

    def twt_to_depth(self, twt: float | np.ndarray) -> float | np.ndarray:
        """Convert two-way travel time to depth via interpolation."""
        return float(np.interp(twt, self._twt, self._depths))

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

        Args:
            depths_m: Depth array in metres.
            sonic_us_m: Sonic transit time in µs/m.

        Returns:
            New :class:`WellTieCalibration` with TWT derived from sonic.
        """
        depths = np.asarray(depths_m, dtype=np.float64)
        sonic = np.asarray(sonic_us_m, dtype=np.float64)
        dz = np.diff(depths)
        dt = dz * (sonic[:-1] + sonic[1:]) / 2.0  # trapezoidal integration
        twt = np.zeros_like(depths)
        twt[1:] = np.cumsum(dt) / 1000.0  # µs → ms
        return cls(depths, twt)
