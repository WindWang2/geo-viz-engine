"""Seismic attribute calculations (envelope, phase, frequency, RMS, etc.)."""
from __future__ import annotations

import numpy as np


def _analytic_signal(data: np.ndarray, axis: int = -1) -> np.ndarray:
    from scipy.signal import hilbert
    return hilbert(data, axis=axis)


def compute_envelope(data: np.ndarray, axis: int = -1) -> np.ndarray:
    """Envelope (instantaneous amplitude) via Hilbert transform."""
    return np.abs(_analytic_signal(data, axis)).astype(np.float32)


def compute_instantaneous_phase(data: np.ndarray, axis: int = -1) -> np.ndarray:
    """Instantaneous phase (radians, [-pi, pi]) via Hilbert transform."""
    return np.angle(_analytic_signal(data, axis)).astype(np.float32)


def compute_instantaneous_frequency(
    data: np.ndarray,
    sample_interval: float = 1.0,
    axis: int = -1,
) -> np.ndarray:
    """Instantaneous frequency via time-derivative of unwrapped phase.

    Args:
        data: Seismic amplitude array.
        sample_interval: Sample interval in the same unit as desired output
            (e.g. seconds → Hz, milliseconds → kHz).
        axis: Axis along which to compute (default: last / time).

    Returns:
        Frequency array (same shape). Edges are forward/backward diff.
    """
    phase = np.unwrap(np.angle(_analytic_signal(data, axis)), axis=axis)
    freq = np.gradient(phase, sample_interval, axis=axis) / (2 * np.pi)
    return freq.astype(np.float32)


def compute_rms_amplitude(
    data: np.ndarray,
    window: int = 21,
    axis: int = -1,
) -> np.ndarray:
    """Windowed RMS amplitude.

    Args:
        data: Seismic amplitude array.
        window: Half-window length (total window = 2*window+1 samples).
        axis: Axis along which to compute.

    Returns:
        RMS amplitude array (same shape, non-negative).
    """
    kernel = np.ones(2 * window + 1) / (2 * window + 1)
    # Expand kernel to match data dimensions for convolve
    for _ in range(data.ndim - 1):
        kernel = kernel[np.newaxis]
    # Move target axis to last position for uniform_filter-like behaviour
    data_sq = data.astype(np.float64) ** 2
    # Use uniform_filter1d via cumsum trick for speed
    from scipy.ndimage import uniform_filter1d
    mean_sq = uniform_filter1d(data_sq, size=2 * window + 1, axis=axis, mode="reflect")
    return np.sqrt(np.maximum(mean_sq, 0)).astype(np.float32)


def compute_sweetness(
    data: np.ndarray,
    sample_interval: float = 1.0,
    axis: int = -1,
) -> np.ndarray:
    """Sweetness attribute: envelope / sqrt(instantaneous frequency).

    Highlights high-amplitude, low-frequency zones (hydrocarbon indicators).
    Near-zero frequency values are clamped to avoid division issues.
    """
    env = compute_envelope(data, axis)
    freq = compute_instantaneous_frequency(data, sample_interval, axis)
    freq_safe = np.where(np.abs(freq) < 1e-6, 1e-6, np.abs(freq))
    return (env / np.sqrt(freq_safe)).astype(np.float32)


def compute_relative_impedance(data: np.ndarray, axis: int = -1) -> np.ndarray:
    """Relative acoustic impedance via running integration.

    Approximates impedance without full inversion. Assumes trace axis.
    """
    return np.cumsum(data, axis=axis).astype(np.float32)


def compute_spectral_decomposition(
    data: np.ndarray,
    freq_bands: list[tuple[float, float]],
    sample_interval: float = 1.0,
    axis: int = -1,
) -> np.ndarray:
    """Spectral decomposition via STFT bandpass filter bank.

    Decomposes seismic data into frequency-band energy volumes using
    short-time Fourier transform. Each band produces an envelope-like
    attribute representing energy in that frequency range.

    Args:
        data: 2-D seismic amplitude array (n_samples x n_traces).
        freq_bands: List of (low_freq, high_freq) tuples in Hz.
            E.g. [(10, 20), (20, 40), (40, 60)] for three bands.
        sample_interval: Sample interval in seconds.
        axis: Time/sample axis (default: last).

    Returns:
        3-D array of shape (n_bands, n_samples, n_traces) with float32
        envelope energy per band.
    """
    from scipy.signal import stft, istft

    data = np.asarray(data, dtype=np.float32)
    n_bands = len(freq_bands)

    # STFT parameters — window of ~200ms for decent freq resolution
    nperseg = min(64, data.shape[axis])
    noverlap = nperseg // 2

    # Work along the time axis
    data_ax = np.moveaxis(data, axis, -1)
    orig_shape = data_ax.shape
    flat = data_ax.reshape(-1, orig_shape[-1])

    f, t_stft, Zxx = stft(flat, fs=1.0 / sample_interval, nperseg=nperseg,
                           noverlap=noverlap, axis=-1)

    result = np.zeros((n_bands, *data.shape), dtype=np.float32)

    for i, (flo, fhi) in enumerate(freq_bands):
        mask = (f >= flo) & (f <= fhi)
        if not np.any(mask):
            continue
        Zxx_band = np.zeros_like(Zxx)
        # Zxx shape: (n_traces, n_freqs, n_time_frames); mask applies to axis 1
        Zxx_band[:, mask, :] = Zxx[:, mask, :]
        _, reconstructed = istft(Zxx_band, fs=1.0 / sample_interval,
                                 nperseg=nperseg, noverlap=noverlap)
        # Trim/pad to match original length
        n_samples = orig_shape[-1]
        if reconstructed.shape[-1] > n_samples:
            reconstructed = reconstructed[:, :n_samples]
        elif reconstructed.shape[-1] < n_samples:
            pad = np.zeros((*reconstructed.shape[:-1], n_samples - reconstructed.shape[-1]))
            reconstructed = np.concatenate([reconstructed, pad], axis=-1)
        # Compute envelope of band-limited signal
        env = np.abs(_analytic_signal(
            np.moveaxis(reconstructed.reshape(orig_shape), -1, axis), axis=axis
        ))
        result[i] = env.astype(np.float32)

    return result


def _power_iteration_c3(traces, n_iter: int = 30):
    """Power iteration for λ_max / trace(C) coherence.

    Works with both NumPy and CuPy arrays — dispatches via the array's
    module (traces.__class__).

    Default is 30 iterations: 10 left a measurable bias on noisy windows
    (max |Δ| ≈ 0.07 vs the exact eigenvalue on adversarial re-measurement;
    ~0.09 on synthetic noise), while 30 converges to machine-visual parity
    at linear cost (#845).
    """
    xp = traces.__class__.__module__.split(".")[0]
    if xp == "cupy":
        import cupy as cp

        xp = cp
    else:
        xp = np

    v = xp.ones((traces.shape[0], traces.shape[1], 1), dtype=xp.float32)
    Tt = traces.transpose(0, 2, 1)
    for _ in range(n_iter):
        v = traces @ (Tt @ v)
        v = v / xp.maximum(xp.linalg.norm(v, axis=-2, keepdims=True), 1e-10)

    lambda_max = xp.sum((Tt @ v) ** 2, axis=(1, 2))
    total_energy = xp.sum(traces ** 2, axis=(1, 2))
    return xp.where(total_energy > 0, lambda_max / total_energy, 1.0)


def compute_coherence_c3(
    data: np.ndarray,
    win_il: int = 5,
    win_xl: int = 5,
    win_t: int = 5,
    use_gpu: bool = False,
) -> np.ndarray:
    """C3 eigenstructure coherence (Marfurt et al., 1998).

    Computes coherence from the ratio of the largest eigenvalue to the
    trace of the covariance matrix built from a 3-D analysis window.
    Uses power iteration for efficiency — avoids full eigendecomposition
    and never materialises the full covariance matrix.

    Args:
        data: 3-D seismic amplitude array (n_il, n_xl, n_samples), or 2-D
            (n_xl, n_samples) treated as a single inline.
        win_il: Half-window in inline direction (total = 2*win_il+1).
        win_xl: Half-window in crossline direction (total = 2*win_xl+1).
        win_t: Half-window in time direction (total = 2*win_t+1).
        use_gpu: If True and CuPy is available, offloads the power-iteration
            step to the GPU per-chunk for significant speed-up on large
            volumes.

    Returns:
        Coherence array (same shape as input) with values in [0, 1].
    """
    from numpy.lib.stride_tricks import sliding_window_view

    try:
        import cupy as cp

        _has_cupy = True
    except Exception:
        _has_cupy = False

    gpu_active = use_gpu and _has_cupy

    data = np.asarray(data, dtype=np.float32)
    was_2d = data.ndim == 2
    if was_2d:
        data = data[np.newaxis, :, :]

    n_il, n_xl, n_t = data.shape
    result = np.ones(data.shape, dtype=np.float32)

    wil = min(2 * win_il + 1, n_il)
    wxl = min(2 * win_xl + 1, n_xl)
    wt = min(2 * win_t + 1, n_t)
    # Force odd window sizes for symmetric padding
    if wil % 2 == 0:
        wil -= 1
    if wxl % 2 == 0:
        wxl -= 1
    if wt % 2 == 0:
        wt -= 1
    n_traces = wil * wxl

    # Pad with reflect mode at boundaries
    pad_il, pad_xl, pad_t = (wil - 1) // 2, (wxl - 1) // 2, (wt - 1) // 2
    padded = np.pad(
        data,
        ((pad_il, pad_il), (pad_xl, pad_xl), (pad_t, pad_t)),
        mode="reflect",
    )

    # Adaptive chunk size — target ~100 MB for traces array
    max_bytes = 100_000_000
    positions = max(1, max_bytes // (n_traces * wt * 4))
    chunk_xl = max(1, min(n_xl, positions // n_t))

    n_power_iter = 30

    for il in range(n_il):
        strip = padded[il : il + wil, :, :]

        for xl0 in range(0, n_xl, chunk_xl):
            xl1 = min(xl0 + chunk_xl, n_xl)
            cxl = xl1 - xl0

            xl_end = xl0 + cxl + wxl - 1
            chunk = strip[:, xl0:xl_end, :]

            # sliding_window_view: (wil, cxl, n_t, wxl, wt)
            swv = sliding_window_view(chunk, (wxl, wt), axis=(1, 2))
            traces = np.ascontiguousarray(swv.transpose(1, 2, 0, 3, 4))
            traces = traces.reshape(cxl * n_t, n_traces, wt)

            if gpu_active:
                traces_gpu = cp.asarray(traces)
                coh = _power_iteration_c3(traces_gpu, n_power_iter)
                coh = cp.asnumpy(coh).astype(np.float32)
            else:
                coh = _power_iteration_c3(traces, n_power_iter)
                coh = coh.astype(np.float32)

            result[il, xl0:xl1, :] = coh.reshape(cxl, n_t)

    if was_2d:
        result = result[0]
    return result


def fuse_rgb(
    attr_r: np.ndarray,
    attr_g: np.ndarray,
    attr_b: np.ndarray,
    clip_pct: float = 99.0,
) -> np.ndarray:
    """Fuse three attribute arrays into an RGB image.

    Each attribute is independently percentile-clipped to [0, 1] and
    scaled to [0, 255] uint8. The three channels are stacked into an
    (H, W, 3) uint8 array.

    Args:
        attr_r: Red channel attribute (2-D float32).
        attr_g: Green channel attribute (2-D float32).
        attr_b: Blue channel attribute (2-D float32).
        clip_pct: Percentile for clipping (default 99.0).

    Returns:
        (H, W, 3) uint8 RGB image.
    """
    def _normalize(a: np.ndarray) -> np.ndarray:
        lo = np.nanpercentile(a, 100.0 - clip_pct)
        hi = np.nanpercentile(a, clip_pct)
        if hi <= lo:
            hi = np.nanmax(a)
            lo = np.nanmin(a)
        if hi <= lo:
            return np.zeros_like(a, dtype=np.float32)
        return np.clip((a - lo) / (hi - lo), 0.0, 1.0)

    r = (_normalize(attr_r) * 255).astype(np.uint8)
    g = (_normalize(attr_g) * 255).astype(np.uint8)
    b = (_normalize(attr_b) * 255).astype(np.uint8)
    return np.stack([r, g, b], axis=-1)


def blend_rgba(
    r_channel: np.ndarray,
    g_channel: np.ndarray,
    b_channel: np.ndarray,
    *,
    alpha: float = 0.85,
) -> np.ndarray:
    """Blend three attribute arrays into a float32 RGBA array with a constant alpha.

    Promoted from ``paleo_workbench/viz/geomodel/well_seismic.py::RGBAttributeFusion``.
    Unlike :func:`fuse_rgb` (percentile-clipped uint8, meant for 2-D image display),
    this keeps float32 in ``[0, 1]`` and appends an alpha channel — the form the
    ``pyqtgraph.opengl`` per-vertex / per-face ``colors=`` arguments expect.

    Normalization is plain min-max per channel with no percentile clipping, so a
    single outlier compresses the rest of that channel. Prefer :func:`fuse_rgb` when
    robust scaling matters.

    Args:
        r_channel: Attribute mapped to red. Any shape.
        g_channel: Attribute mapped to green, same shape as ``r_channel``.
        b_channel: Attribute mapped to blue, same shape as ``r_channel``.
        alpha: Constant opacity written to the A channel.

    Returns:
        ``(..., 4)`` float32 array, one RGBA tuple per input element.
    """
    def _minmax(arr: np.ndarray) -> np.ndarray:
        arr = np.asarray(arr, dtype=np.float32)
        lo, hi = np.min(arr), np.max(arr)
        if hi - lo < 1e-8:
            return np.zeros_like(arr, dtype=np.float32)
        return (arr - lo) / (hi - lo)

    r = _minmax(r_channel)
    g = _minmax(g_channel)
    b = _minmax(b_channel)
    a = np.full_like(r, fill_value=alpha, dtype=np.float32)
    return np.stack([r, g, b, a], axis=-1)


def compute_dip(
    data: np.ndarray,
    axis_il: int = 0,
    axis_xl: int = 1,
    axis_t: int = 2,
    dt: float = 1.0,
    dx_il: float = 1.0,
    dx_xl: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute apparent dip angles (radians) along inline and crossline.

    Uses central differences for the spatial gradients and the vertical
    (time) gradient.  The apparent dip is ``atan(∂x/∂t)``.

    ``dt`` / ``dx_il`` / ``dx_xl`` convert the per-index gradients into
    physical units (e.g. seconds per sample and meters per trace). Left at
    their defaults of 1.0 the result is an INDEX-unit gradient ratio — a
    plane with slope s has dip ``atan(s)`` regardless of how many meters
    or milliseconds an index spans, so the numbers are not physical angles
    (#845). Pass real spacings to get true radians: a plane with spatial
    slope ``s`` then has dip ``atan(s * dt / dx)``.

    Args:
        data: 3-D seismic amplitude (n_il, n_xl, n_t) or 2-D (n_xl, n_t).
        axis_il: Axis index for the inline direction.
        axis_xl: Axis index for the crossline direction.
        axis_t: Axis index for the time/sample direction.
        dt: Time sample interval in the time axis unit (per index).
        dx_il: Inline spacing in the same unit as ``dt`` per inline index.
        dx_xl: Crossline spacing in the same unit as ``dt`` per crossline index.

    Returns:
        (dip_il, dip_xl) arrays with the same shape as *data* and dtype
        float32.  Values are in ``[-π/2, π/2]``; physical radians only when
        the spacing arguments match the data's real sampling.
    """
    data = np.asarray(data, dtype=np.float32)
    was_2d = data.ndim == 2
    if was_2d:
        # 2-D data convention: (n_xl, n_t). Only xl and t gradients exist.
        grad_xl = np.gradient(data, dx_xl, axis=0)
        grad_t = np.gradient(data, dt, axis=1)
        gt_safe = np.where(np.abs(grad_t) < 1e-10, 1e-10, grad_t)
        dip_il = np.zeros_like(data)
        dip_xl = np.arctan(grad_xl / gt_safe).astype(np.float32)
        return dip_il, dip_xl

    # Central differences, with index spans converted to physical units
    grad_il = np.gradient(data, dx_il, axis=axis_il)
    grad_xl = np.gradient(data, dx_xl, axis=axis_xl)
    grad_t = np.gradient(data, dt, axis=axis_t)

    # Avoid division by zero — tiny vertical gradient is treated as flat
    gt_safe = np.where(np.abs(grad_t) < 1e-10, 1e-10, grad_t)
    dip_il = np.arctan(grad_il / gt_safe).astype(np.float32)
    dip_xl = np.arctan(grad_xl / gt_safe).astype(np.float32)
    return dip_il, dip_xl


def compute_azimuth(
    dip_il: np.ndarray,
    dip_xl: np.ndarray,
) -> np.ndarray:
    """Structural azimuth from inline / crossline dip components.

    Azimuth is measured clockwise from the inline axis, in radians,
    range ``[0, 2π)``.
    """
    az = np.arctan2(dip_xl, dip_il)
    az = np.where(az < 0, az + 2 * np.pi, az)
    return az.astype(np.float32)


def _compute_slope(data, xp=np):
    """Return inline/crossline slope (grad_spatial / grad_time) arrays.

    Operates with the array module ``xp`` (numpy or cupy) — the caller is
    responsible for placing *data* on the matching device.
    """
    if data.ndim == 2:
        grad_xl = xp.gradient(data, axis=0)
        grad_t = xp.gradient(data, axis=1)
        gt_safe = xp.where(xp.abs(grad_t) < 1e-10, 1e-10, grad_t)
        slope_il = xp.zeros_like(data)
        slope_xl = grad_xl / gt_safe
        return slope_il.astype(xp.float32), slope_xl.astype(xp.float32)

    grad_il = xp.gradient(data, axis=0)
    grad_xl = xp.gradient(data, axis=1)
    grad_t = xp.gradient(data, axis=2)
    gt_safe = xp.where(xp.abs(grad_t) < 1e-10, 1e-10, grad_t)
    slope_il = (grad_il / gt_safe).astype(xp.float32)
    slope_xl = (grad_xl / gt_safe).astype(xp.float32)
    return slope_il, slope_xl


def compute_curvature(
    data: np.ndarray,
    kind: str = "mean",
    *,
    win_il: int = 3,
    win_xl: int = 3,
    win_t: int = 3,
    use_gpu: bool = False,
) -> np.ndarray:
    """Volume curvature via the slope-gradient (second-derivative) method.

    Computes curvature attributes useful for fracture prediction and
    structural interpretation.  The algorithm:

    1. Compute inline / crossline slope (spatial_grad / time_grad).
    2. Smooth the slope fields with a local mean (noise suppression).
    3. Compute second-order spatial gradients of the smoothed slope.
    4. Derive Gaussian, mean, max, min, dip, or strike curvature.

    Args:
        data: 3-D seismic amplitude or 2-D slice.
        kind: One of ``"gaussian"``, ``"mean"``, ``"max"``, ``"min"``,
            ``"dip"``, ``"strike"``.
        win_il: Half-window for inline smoothing (total = 2*win_il+1).
        win_xl: Half-window for crossline smoothing.
        win_t: Half-window for time smoothing.
        use_gpu: If True and CuPy available, offloads to GPU per-chunk.

    Returns:
        Curvature array (same shape as input, float32).
    """
    try:
        import cupy as cp
        from cupyx.scipy.ndimage import uniform_filter as cp_uniform_filter

        _has_cupy = True
    except Exception:
        _has_cupy = False

    gpu_active = use_gpu and _has_cupy

    if gpu_active:
        xp = cp
        uniform_filter = cp_uniform_filter
        data_x = cp.asarray(data, dtype=cp.float32)
    else:
        from scipy.ndimage import uniform_filter as np_uniform_filter

        xp = np
        uniform_filter = np_uniform_filter
        data_x = np.asarray(data, dtype=np.float32)

    # 1. Slope (not dip angle — curvature needs linear slope for constant 2nd deriv)
    slope_il, slope_xl = _compute_slope(data_x, xp=xp)

    # 2. Smooth slope
    if data_x.ndim == 2:
        size_xl = 2 * win_xl + 1
        size_t = 2 * win_t + 1
        # 2-D slices are (n_xl, n_t) — window sizes must follow axis order.
        slope_il = uniform_filter(slope_il, size=(size_xl, size_t), mode="reflect")
        slope_xl = uniform_filter(slope_xl, size=(size_xl, size_t), mode="reflect")
        # 3. Second derivatives — 2-D slices are (n_xl, n_t), so the
        # crossline derivative runs along axis 0 (axis 1 in the 3-D path).
        d2_il = xp.gradient(xp.gradient(slope_il, axis=0), axis=0)
        d2_xl = xp.gradient(xp.gradient(slope_xl, axis=0), axis=0)
        d2_il_xl = xp.gradient(xp.gradient(slope_il, axis=1), axis=0)
    else:
        size_il = 2 * win_il + 1
        size_xl = 2 * win_xl + 1
        size_t = 2 * win_t + 1
        slope_il = uniform_filter(slope_il, size=(size_il, size_xl, size_t), mode="reflect")
        slope_xl = uniform_filter(slope_xl, size=(size_il, size_xl, size_t), mode="reflect")
        # 3. Second derivatives
        d2_il = xp.gradient(xp.gradient(slope_il, axis=0), axis=0)
        d2_xl = xp.gradient(xp.gradient(slope_xl, axis=1), axis=1)
        d2_il_xl = xp.gradient(xp.gradient(slope_il, axis=1), axis=0)

    # 4. Curvature formulas
    if kind == "gaussian":
        result = d2_il * d2_xl - d2_il_xl ** 2
    elif kind == "mean":
        result = (d2_il + d2_xl) / 2.0
    elif kind == "max":
        half_sum = (d2_il + d2_xl) / 2.0
        diff_term = ((d2_il - d2_xl) / 2.0) ** 2 + d2_il_xl ** 2
        result = half_sum + xp.sqrt(xp.maximum(diff_term, 0.0))
    elif kind == "min":
        half_sum = (d2_il + d2_xl) / 2.0
        diff_term = ((d2_il - d2_xl) / 2.0) ** 2 + d2_il_xl ** 2
        result = half_sum - xp.sqrt(xp.maximum(diff_term, 0.0))
    elif kind == "dip":
        result = d2_il
    elif kind == "strike":
        result = d2_xl
    else:
        raise ValueError(f"Unknown curvature kind: {kind!r}")

    if gpu_active:
        return cp.asnumpy(result).astype(np.float32)
    return result.astype(np.float32)
