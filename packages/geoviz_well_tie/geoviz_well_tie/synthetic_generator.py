"""Impedance, Reflectivity, and Synthetic Seismogram Generator."""
import numpy as np

def compute_impedance(sonic: np.ndarray, density: np.ndarray) -> np.ndarray:
    """Compute Acoustic Impedance AI = Vp * RHOB from sonic (us/m) and density (g/cm3)."""
    sonic_clean = np.asarray(sonic, dtype=np.float64)
    density_clean = np.asarray(density, dtype=np.float64)
    
    # Avoid zero or negative sonic
    sonic_clean = np.maximum(100.0, sonic_clean)
    vp = 1e6 / sonic_clean  # m/s
    return vp * density_clean

def compute_reflectivity(impedance: np.ndarray) -> np.ndarray:
    """Compute Reflectivity series RC = (AI[i+1] - AI[i]) / (AI[i+1] + AI[i])."""
    ai = np.asarray(impedance, dtype=np.float64)
    if len(ai) < 2:
        return np.array([], dtype=np.float64)
        
    ai_num = ai[1:] - ai[:-1]
    ai_den = np.maximum(1e-6, ai[1:] + ai[:-1])
    return ai_num / ai_den

def generate_synthetic_seismogram(sonic: np.ndarray, density: np.ndarray, wavelet: np.ndarray) -> np.ndarray:
    """Generate 1D synthetic seismogram by convolving reflectivity series with wavelet."""
    ai = compute_impedance(sonic, density)
    rc = compute_reflectivity(ai)
    if len(rc) == 0:
        return np.array([], dtype=np.float64)
        
    synthetic = np.convolve(rc, wavelet, mode="same")
    return synthetic
