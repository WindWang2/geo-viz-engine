"""GPU computation operations powered by CuPy (fallback to NumPy)."""
from __future__ import annotations

import logging
import numpy as np

logger = logging.getLogger(__name__)

try:
    import cupy as cp
    _CUPY_AVAILABLE = True
    # Verify functional context
    try:
        _ = cp.cuda.Device().id
    except Exception:
        logger.warning("CuPy imported but no active CUDA device detected. Falling back to CPU mode.")
        _CUPY_AVAILABLE = False
except ImportError:
    cp = None
    _CUPY_AVAILABLE = False


def is_gpu_available() -> bool:
    """Check if CuPy and a functional CUDA device are available."""
    return _CUPY_AVAILABLE


def to_gpu(arr: np.ndarray) -> cp.ndarray | np.ndarray:
    """Safely transfer a NumPy array to the GPU if available."""
    if not _CUPY_AVAILABLE or arr is None:
        return arr
    if isinstance(arr, cp.ndarray):
        return arr
    return cp.asarray(arr)


def to_cpu(arr: cp.ndarray | np.ndarray) -> np.ndarray:
    """Safely transfer an array back to NumPy CPU format."""
    if arr is None:
        return None
    if _CUPY_AVAILABLE and isinstance(arr, cp.ndarray):
        return cp.asnumpy(arr)
    return arr


def slice_volume_gpu(volume: cp.ndarray | np.ndarray, 
                     axis: int, 
                     index: int,
                     keep_on_gpu: bool = False) -> cp.ndarray | np.ndarray:
    """
    Perform efficient slicing on the GPU if volume is a CuPy array.
    
    Args:
        volume: 3D volume array (may be CuPy or NumPy).
        axis: Slicing axis index (0=IL, 1=XL, 2=T).
        index: Integer coordinate position along axis.
        keep_on_gpu: If True and volume is CuPy, returns CuPy array. 
                     If False, explicitly transfers to CPU NumPy.
    """
    if axis == 0:
        sl = volume[index, :, :]
    elif axis == 1:
        sl = volume[:, index, :]
    else:
        sl = volume[:, :, index]
        
    if keep_on_gpu:
        return sl
    return to_cpu(sl)


def apply_colormap_gpu(data: cp.ndarray | np.ndarray, 
                       lut: np.ndarray) -> np.ndarray:
    """
    Perform min-max normalization and LUT lookup entirely on the GPU if possible.
    
    Args:
        data: The 2D seismic data slice (could be CuPy or NumPy).
        lut: The (N, 4) unit8 RGBA lookup table (CPU NumPy).
        
    Returns:
        np.ndarray: Final RGBA CPU image ready for GUI texture upload.
    """
    if not _CUPY_AVAILABLE or not isinstance(data, cp.ndarray):
        # Standard NumPy fallback logic if not on GPU
        xp = np
        dmin, dmax = xp.nanmin(data), xp.nanmax(data)
    else:
        xp = cp
        dmin, dmax = xp.nanmin(data), xp.nanmax(data)

    # 1. Min-Max Normalization
    if dmax == dmin:
        norm = xp.zeros_like(data, dtype=xp.float32)
    else:
        norm = (data - dmin) / (dmax - dmin)
        
    # 2. Convert to LUT indices
    lut_len = len(lut)
    idx = (norm * (lut_len - 1)).astype(xp.int32)
    idx = xp.clip(idx, 0, lut_len - 1)
    
    # 3. Map via LUT
    if xp is cp:
        # Upload LUT to GPU briefly for lightning fast vector lookup
        gpu_lut = cp.asarray(lut)
        rgba_gpu = gpu_lut[idx]
        # Finally, pull small final RGBA image to CPU
        return cp.asnumpy(rgba_gpu)
    else:
        return lut[idx]
