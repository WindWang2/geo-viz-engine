"""Cross-correlation auto-tie, lag shift, and residual calculation engine."""
from typing import Tuple
import numpy as np

def compute_cross_correlation(s1: np.ndarray, s2: np.ndarray) -> Tuple[float, int]:
    """Compute peak cross-correlation coefficient R and best lag shift (samples)."""
    a = np.nan_to_num(np.asarray(s1, dtype=np.float64))
    b = np.nan_to_num(np.asarray(s2, dtype=np.float64))
    
    n = min(len(a), len(b))
    if n == 0:
        return 0.0, 0
        
    a = a[:n]
    b = b[:n]
    
    std_a = np.std(a)
    std_b = np.std(b)
    if std_a == 0 or std_b == 0:
        return 0.0, 0

    corr = np.correlate(a - np.mean(a), b - np.mean(b), mode="full")
    norm = n * std_a * std_b
    corr_norm = corr / max(1e-6, norm)
    
    max_idx = int(np.argmax(corr_norm))
    lag = max_idx - (n - 1)
    max_r = float(corr_norm[max_idx])
    
    return max_r, lag

def evaluate_tie_quality(synthetic: np.ndarray, seismic: np.ndarray) -> Tuple[float, int, np.ndarray]:
    """Evaluate well-seismic tie quality. Returns (R, lag_shift, amplitude_residual)."""
    max_r, lag = compute_cross_correlation(synthetic, seismic)
    
    n = min(len(synthetic), len(seismic))
    syn_crop = synthetic[:n]
    seis_crop = seismic[:n]
    
    residual = np.abs(syn_crop - seis_crop)
    return max_r, lag, residual
