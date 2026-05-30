"""geoviz-well-tie — Well-seismic tie: synthetic seismogram generation and calibration.

Independent package providing reflectivity computation from well logs,
Ricker/Ormsby wavelet generation, synthetic seismogram convolution,
and well-seismic calibration visualization for PySide6.
Works in any project: ``pip install geoviz-well-tie``.
"""

from .wavelet import ricker_wavelet, ormsby_wavelet
from .synthetic import compute_reflectivity, generate_synthetic
from .calibration import WellTieCalibration

__version__ = "0.1.0"

__all__ = [
    "ricker_wavelet",
    "ormsby_wavelet",
    "compute_reflectivity",
    "generate_synthetic",
    "WellTieCalibration",
]
