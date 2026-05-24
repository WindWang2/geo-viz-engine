"""Seismic attribute calculations (envelope, instantaneous phase, etc.)."""
from __future__ import annotations

import numpy as np


def compute_envelope(data: np.ndarray, axis: int = -1) -> np.ndarray:
    """Compute envelope (instantaneous amplitude) via Hilbert transform.

    Uses ``scipy.signal.hilbert`` along the specified axis and returns
    the absolute value of the analytic signal.

    Args:
        data: Seismic amplitude array (any dimensionality).
        axis: Axis along which to compute the Hilbert transform
              (default: last axis, typically time).

    Returns:
        Envelope array with the same shape as *data*.
    """
    from scipy.signal import hilbert

    analytic = hilbert(data, axis=axis)
    return np.abs(analytic).astype(np.float32)


def compute_instantaneous_phase(data: np.ndarray, axis: int = -1) -> np.ndarray:
    """Compute instantaneous phase via Hilbert transform.

    Args:
        data: Seismic amplitude array.
        axis: Axis along which to compute the Hilbert transform.

    Returns:
        Phase array (radians, wrapped to [-pi, pi]) with the same shape.
    """
    from scipy.signal import hilbert

    analytic = hilbert(data, axis=axis)
    return np.angle(analytic).astype(np.float32)
