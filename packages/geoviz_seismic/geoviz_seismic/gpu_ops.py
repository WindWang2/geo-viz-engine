"""GPU computation operations powered by CuPy (fallback to NumPy)."""
from __future__ import annotations

import logging
import numpy as np

logger = logging.getLogger(__name__)

try:
    import cupy as cp
    try:
        from cupyx.scipy.ndimage import map_coordinates as cp_map_coords
    except ImportError:
        cp_map_coords = None
    _CUPY_AVAILABLE = True
    # Verify functional context
    try:
        _ = cp.cuda.Device().id
    except Exception:
        logger.warning("CuPy imported but no active CUDA device detected. Falling back to CPU mode.")
        _CUPY_AVAILABLE = False
except ImportError:
    cp = None
    cp_map_coords = None
    _CUPY_AVAILABLE = False

from scipy.ndimage import map_coordinates as sp_map_coords


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


def sample_arbitrary_slice_gpu(volume: cp.ndarray | np.ndarray,
                               angle_deg: float,
                               offset_px: float,
                               keep_on_gpu: bool = False) -> cp.ndarray | np.ndarray:
    """
    Resamples volume data along an arbitrary vertical plane cutting through the cube.
    Leverages affine grid transforms and bi-linear interpolation for speed.
    
    Args:
        volume: 3D array of shape (n_inlines, n_xlines, n_samples)
        angle_deg: Azimuthal rotation angle in degrees.
        offset_px: Perpendicular pixel/voxel offset from horizontal center.
        keep_on_gpu: Return device reference if possible.
        
    Returns:
        2D array of shape (n_samples, diag_size) containing the resampled plane slice.
    """
    # Detection block
    xp = cp if (_CUPY_AVAILABLE and isinstance(volume, cp.ndarray)) else np
    map_func = cp_map_coords if (xp is cp and cp_map_coords is not None) else sp_map_coords

    ni, nx, nt = volume.shape
    diag = int(np.hypot(ni, nx))
    
    theta = np.radians(angle_deg)
    cos_t = float(np.cos(theta))
    sin_t = float(np.sin(theta))
    
    # Construct coordinate grid for interpolation
    # D is distance along the slice plane, T is sample index (depth)
    d_range = xp.linspace(-diag/2.0, diag/2.0, diag)
    t_range = xp.arange(nt, dtype=xp.float32)
    
    # Meshgrid results in shape (nt, diag), which matches standard 2D layout requirements
    T, D = xp.meshgrid(t_range, d_range, indexing='ij')
    
    # Map coordinates back to original cube indices
    I_idx = (ni / 2.0) + D * cos_t + offset_px * sin_t
    X_idx = (nx / 2.0) + D * sin_t - offset_px * cos_t
    
    # Combine for interpolation engine, expected shape is (3, nt, diag)
    interp_grid = xp.stack([I_idx, X_idx, T])
    
    # Sample. Use constant fill zero for bounds to hide background.
    sampled = map_func(volume, interp_grid, order=1, mode='constant', cval=0.0)
    
    if keep_on_gpu:
        return sampled
    return to_cpu(sampled)


def sample_polyline_slice(volume: np.ndarray,
                          points: list[tuple[float, float]],
                          samples_per_unit: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """
    Resample volume data along a polyline path defined by waypoints on the IL/XL plane.
    
    Args:
        volume: 3D array of shape (n_inlines, n_xlines, n_samples).
        points: List of (inline_idx, xline_idx) waypoints (fractional indices OK).
        samples_per_unit: Number of horizontal samples per voxel unit of distance.
        
    Returns:
        Tuple of (slice_2d, cumulative_distances):
            - slice_2d: shape (n_samples, total_horiz_samples) — the vertical cross-section
            - cumulative_distances: 1D array of cumulative path distance for each horizontal sample
    """
    if len(points) < 2:
        nt = volume.shape[2]
        return np.zeros((nt, 1), dtype=np.float32), np.array([0.0])
    
    xp = np
    map_func = sp_map_coords
    
    # If volume is on GPU, bring it to CPU for this operation
    vol_cpu = to_cpu(volume) if not isinstance(volume, np.ndarray) else volume
    
    # Build the dense sample coordinates along the polyline
    all_il = []
    all_xl = []
    all_dist = []
    cum_dist = 0.0
    
    for seg_idx in range(len(points) - 1):
        i0, x0 = points[seg_idx]
        i1, x1 = points[seg_idx + 1]
        seg_len = float(np.hypot(i1 - i0, x1 - x0))
        
        if seg_len < 0.01:
            continue
        
        n_pts = max(2, int(seg_len * samples_per_unit))
        t_vals = np.linspace(0.0, 1.0, n_pts, endpoint=(seg_idx == len(points) - 2))
        
        for t in t_vals:
            il = i0 + t * (i1 - i0)
            xl = x0 + t * (x1 - x0)
            d = cum_dist + t * seg_len
            all_il.append(il)
            all_xl.append(xl)
            all_dist.append(d)
        
        cum_dist += seg_len
    
    if len(all_il) == 0:
        nt = vol_cpu.shape[2]
        return np.zeros((nt, 1), dtype=np.float32), np.array([0.0])
    
    n_horiz = len(all_il)
    ni, nx, nt = vol_cpu.shape
    
    # Build coordinate grid: (3, nt, n_horiz)
    il_arr = np.array(all_il, dtype=np.float32)
    xl_arr = np.array(all_xl, dtype=np.float32)
    t_range = np.arange(nt, dtype=np.float32)
    
    # Broadcast: IL[h], XL[h] are constant across time; T[t] is constant across horiz
    IL_grid = np.tile(il_arr, (nt, 1))       # (nt, n_horiz)
    XL_grid = np.tile(xl_arr, (nt, 1))       # (nt, n_horiz)
    T_grid = np.tile(t_range[:, np.newaxis], (1, n_horiz))  # (nt, n_horiz)
    
    coords = np.stack([IL_grid, XL_grid, T_grid])  # (3, nt, n_horiz)
    
    sampled = map_func(vol_cpu, coords, order=1, mode='constant', cval=0.0)
    
    return sampled.astype(np.float32), np.array(all_dist, dtype=np.float32)

