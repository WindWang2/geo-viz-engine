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
                     index: int) -> np.ndarray:
    """
    Perform efficient slicing on the GPU if volume is a CuPy array,
    returning a standard CPU NumPy array optimized for visualization engines.
    
    Args:
        volume: 3D volume array (may be CuPy or NumPy).
        axis: Slicing axis index (0=IL, 1=XL, 2=T).
        index: Integer coordinate position along axis.
    """
    if axis == 0:
        sl = volume[index, :, :]
    elif axis == 1:
        sl = volume[:, index, :]
    else:
        sl = volume[:, :, index]
        
    # Convert explicitly back to numpy for renderers demanding standard memory mapping
    return to_cpu(sl)
