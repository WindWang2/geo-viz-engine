"""geoviz-well-tie — Well-seismic tie: synthetic seismogram generation and calibration.

Independent package providing reflectivity computation from well logs,
Ricker/Ormsby wavelet generation, synthetic seismogram convolution,
and well-seismic calibration visualization for PySide6.
Works in any project: ``pip install geoviz-well-tie``.
"""

from .wavelet import ricker_wavelet, ormsby_wavelet
from .synthetic import (
    compute_reflectivity,
    generate_synthetic,
    generate_synthetic_twt,
    synthetic_from_logs,
)
from .calibration import WellTieCalibration, resample_to_seismic_grid, shift_depths
from .auto_tie import auto_tie_with_quality, correlate_synthetic_to_trace
from .sonic_units import (
    US_FT_TO_US_M,
    canonical_sonic_unit,
    normalize_sonic_units,
)

__version__ = "0.1.0"

__all__ = [
    "ricker_wavelet",
    "ormsby_wavelet",
    "compute_reflectivity",
    "generate_synthetic",
    "generate_synthetic_twt",
    "synthetic_from_logs",
    "WellTieCalibration",
    "resample_to_seismic_grid",
    "shift_depths",
    "auto_tie_with_quality",
    "correlate_synthetic_to_trace",
    "US_FT_TO_US_M",
    "canonical_sonic_unit",
    "normalize_sonic_units",
]
