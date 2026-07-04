"""Wavelet generation (Ricker, Ormsby) and statistical extraction functions."""
from typing import Tuple
import numpy as np

def generate_ricker_wavelet(freq: float = 30.0, dt: float = 0.002, length: float = 0.1) -> Tuple[np.ndarray, np.ndarray]:
    """Generate Ricker wavelet with peak frequency `freq` (Hz) and sample rate `dt` (s)."""
    n_samples = int(length / dt)
    if n_samples % 2 == 0:
        n_samples += 1
    t = np.linspace(-length / 2, length / 2, n_samples)
    
    pi2_f2_t2 = (np.pi * freq * t) ** 2
    w = (1.0 - 2.0 * pi2_f2_t2) * np.exp(-pi2_f2_t2)
    
    # Normalize peak amplitude to 1.0
    if np.max(np.abs(w)) > 0:
        w = w / np.max(np.abs(w))
        
    return t, w

def generate_ormsby_wavelet(f1: float = 5.0, f2: float = 10.0, f3: float = 40.0, f4: float = 50.0, dt: float = 0.002, length: float = 0.1) -> Tuple[np.ndarray, np.ndarray]:
    """Generate Ormsby bandpass wavelet with corner frequencies f1-f2-f3-f4."""
    n_samples = int(length / dt)
    if n_samples % 2 == 0:
        n_samples += 1
    t = np.linspace(-length / 2, length / 2, n_samples)
    
    def _sinc_sq(f, t_arr):
        return (np.sin(np.pi * f * t_arr) / (np.pi * f * np.where(t_arr == 0, 1e-12, t_arr))) ** 2

    # Ormsby formula
    num = (np.pi * f4)**2 * _sinc_sq(f4, t) - (np.pi * f3)**2 * _sinc_sq(f3, t) - (np.pi * f2)**2 * _sinc_sq(f2, t) + (np.pi * f1)**2 * _sinc_sq(f1, t)
    den = (f4 - f3) * (f2 - f1)
    
    w = num / max(1e-6, den)
    if np.max(np.abs(w)) > 0:
        w = w / np.max(np.abs(w))
        
    return t, w

def extract_statistical_wavelet(seismic_data: np.ndarray, dt: float = 0.002, length: float = 0.1) -> Tuple[np.ndarray, np.ndarray]:
    """Extract zero-phase statistical wavelet from seismic trace data autocorrelation."""
    data = np.nan_to_num(np.asarray(seismic_data, dtype=np.float64))
    if len(data) == 0:
        return generate_ricker_wavelet(30.0, dt, length)

    autocorr = np.correlate(data, data, mode="full")
    n_samples = int(length / dt)
    if n_samples % 2 == 0:
        n_samples += 1

    mid = len(autocorr) // 2
    half = n_samples // 2
    w = autocorr[mid - half : mid + half + 1]

    # Apply Hanning window
    w = w * np.hanning(len(w))
    if np.max(np.abs(w)) > 0:
        w = w / np.max(np.abs(w))

    t = np.linspace(-length / 2, length / 2, len(w))
    return t, w
