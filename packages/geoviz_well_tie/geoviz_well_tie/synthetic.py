"""Reflectivity computation and synthetic seismogram generation."""

from __future__ import annotations

import numpy as np


def compute_reflectivity(
    sonic: np.ndarray,
    density: np.ndarray,
) -> np.ndarray:
    """Compute acoustic impedance and P-wave reflectivity from well logs.

    Reflectivity at interface *i*::

        R_i = (Z_{i+1} - Z_i) / (Z_{i+1} + Z_i)

    where ``Z = sonic^{-1} × density`` (acoustic impedance).

    Args:
        sonic: Sonic transit time in µs/m (slowness). Shape ``(N,)``.
        density: Bulk density in g/cm³. Shape ``(N,)``.

    Returns:
        ``(N-1,)`` float32 reflectivity series. First sample is at the
        first interface, last sample at the ``(N-2)``-th interface.
    """
    sonic = np.asarray(sonic, dtype=np.float64)
    density = np.asarray(density, dtype=np.float64)
    velocity = 1.0e6 / sonic  # µs/m → m/s
    impedance = velocity * density
    z_upper = impedance[:-1]
    z_lower = impedance[1:]
    denom = z_upper + z_lower
    denom = np.where(np.abs(denom) < 1e-12, 1e-12, denom)
    reflectivity = (z_lower - z_upper) / denom
    return reflectivity.astype(np.float32)


def generate_synthetic(
    reflectivity: np.ndarray,
    wavelet: np.ndarray,
) -> np.ndarray:
    """Convolve reflectivity with a wavelet to produce a synthetic seismogram.

    Args:
        reflectivity: ``(N,)`` reflectivity series from :func:`compute_reflectivity`.
        wavelet: ``(M,)`` wavelet from :func:`ricker_wavelet` or :func:`ormsby_wavelet`.

    Returns:
        ``(N,)`` float32 synthetic trace.
    """
    reflectivity = np.asarray(reflectivity, dtype=np.float64)
    wavelet = np.asarray(wavelet, dtype=np.float64)
    n_ref = len(reflectivity)
    if n_ref == 0:
        return np.empty(0, dtype=np.float32)
    # Ensure output length matches reflectivity by padding reflectivity when
    # the wavelet is longer.
    if len(wavelet) > n_ref:
        pad = len(wavelet) - n_ref
        padded = np.pad(reflectivity, pad)
        conv = np.convolve(padded, wavelet, mode="same")
        # Extract the centre portion matching original reflectivity positions
        start = pad
        synthetic = conv[start:start + n_ref]
    else:
        synthetic = np.convolve(reflectivity, wavelet, mode="same")
    return synthetic.astype(np.float32)


def generate_synthetic_twt(
    reflectivity: np.ndarray,
    wavelet_type: str = "ricker",
    dt_ms: float = 4.0,
    peak_freq: float = 25.0,
    *,
    f1: float = 5.0,
    f2: float = 10.0,
    f3: float = 40.0,
    f4: float = 50.0,
) -> np.ndarray:
    """Unit-safe wrapper: generate synthetic accepting *dt_ms* (milliseconds).

    Internally converts to seconds for wavelet generation, then convolves.

    Args:
        reflectivity: ``(N,)`` reflectivity series.
        wavelet_type: ``"ricker"`` or ``"ormsby"``.
        dt_ms: Sample interval in milliseconds.
        peak_freq: Peak frequency in Hz (Ricker only).
        f1..f4: Ormsby frequency parameters (Hz).

    Returns:
        ``(N,)`` float32 synthetic trace.
    """
    from .wavelet import ricker_wavelet, ormsby_wavelet

    dt_sec = dt_ms / 1000.0
    n_ref = len(reflectivity)
    # Force an odd wavelet length: with 'same'-mode convolution an even
    # length shifts the synthetic by one sample because the nominal centre
    # falls between samples (n_ref=40 used to peak one sample late, #117).
    n_wavelet = min(81, max(21, n_ref | 1))

    if wavelet_type == "ormsby":
        w = ormsby_wavelet(n_wavelet, dt=dt_sec, f1=f1, f2=f2, f3=f3, f4=f4)
    else:
        w = ricker_wavelet(n_wavelet, dt=dt_sec, peak_freq=peak_freq)

    return generate_synthetic(reflectivity, w)


DEFAULT_SONIC_CLIP = (10.0, 1000.0)
DEFAULT_WAVELET_HALF_LENGTH_S = 0.064


def _interpolate_nan(values: np.ndarray) -> np.ndarray:
    """Fill NaN gaps by linear interpolation over the sample index.

    Edge NaNs (no valid neighbour on one side) take the nearest finite
    value. An all-NaN array is returned unchanged — there is nothing to
    interpolate from, and the caller's downstream NaNs remain visible.
    """
    values = np.asarray(values, dtype=np.float64)
    good = np.isfinite(values)
    if good.all() or not good.any():
        return values
    idx = np.arange(len(values))
    return np.interp(idx, idx[good], values[good])


def synthetic_from_logs(
    sonic: np.ndarray,
    density: np.ndarray,
    *,
    wavelet_freq: float = 30.0,
    dt_s: float = 0.002,
    half_length_s: float = DEFAULT_WAVELET_HALF_LENGTH_S,
    sonic_clip: tuple[float, float] | None = DEFAULT_SONIC_CLIP,
) -> np.ndarray:
    """One-call sonic+density → Ricker synthetic seismogram.

    Convenience composition of :func:`compute_reflectivity`,
    :func:`~geoviz_well_tie.wavelet.ricker_wavelet` and :func:`generate_synthetic`,
    promoted from ``paleo_workbench/viz/geomodel/well_seismic.py::
    WellSeismicTieCalibration.compute_synthetic``.

    Args:
        sonic: Sonic transit time in µs/m (slowness). Shape ``(N,)``.
        density: Bulk density in g/cm³, aligned with ``sonic``.
        wavelet_freq: Ricker peak frequency in Hz.
        dt_s: Sample interval in **seconds** (the rest of this package mostly
            speaks milliseconds).
        half_length_s: Ricker half-length in seconds; the wavelet spans
            ``[-half_length_s, +half_length_s]``.
        sonic_clip: ``(min, max)`` µs/m clamp applied before the velocity
            reciprocal, guarding against zero/negative sonic samples. Pass
            ``None`` to disable.

    NaN handling: NaN samples in *sonic* or *density* are filled by linear
    interpolation over the sample index before impedance computation (edge
    NaNs take the nearest finite value). Without this, a single NaN log
    sample poisons the two reflectivity interfaces it touches and — after
    convolution — the entire wavelet aperture around them (#117). Inputs
    that are entirely NaN still yield an all-NaN synthetic.

    Returns:
        ``(N-1,)`` float32 synthetic trace, or an empty array when fewer than two
        log samples are supplied.
    """
    from .wavelet import ricker_wavelet

    sonic = np.asarray(sonic, dtype=np.float64)
    density = np.asarray(density, dtype=np.float64)
    if len(sonic) <= 1:
        return np.empty(0, dtype=np.float32)

    if sonic_clip is not None:
        sonic = np.clip(sonic, sonic_clip[0], sonic_clip[1])

    sonic = _interpolate_nan(sonic)
    density = _interpolate_nan(density)

    reflectivity = compute_reflectivity(sonic, density)
    # |1 keeps the aperture odd so 'same'-mode convolution stays zero-phase
    # for any half_length_s/dt_s combination (#117).
    n_wavelet = (int(round(2.0 * half_length_s / dt_s)) + 1) | 1
    wavelet = ricker_wavelet(n_wavelet, dt=dt_s, peak_freq=wavelet_freq)
    return generate_synthetic(reflectivity, wavelet)
