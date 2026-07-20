"""Datum Transformer for Multi-Well Stratigraphic Section Alignment."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class DatumTransformer:
    """Transforms measured depths to canvas Y-coordinates for multi-well sections.

    Modes:
      - 'absolute': Displays all wells aligned by absolute Measured Depth / Elevation (TVD).
      - 'datum_shift': Aligns all wells by a selected datum horizon, shifting depths so the datum horizon lies on Y_datum.
    """

    mode: str = "absolute"  # 'absolute' or 'datum_shift'
    datum_name: str = ""
    scale_y: float = 1.0  # Pixels per depth unit (e.g. pixels per meter)
    header_height: float = 56.0
    y_datum: float = 150.0  # Target canvas Y for the datum line in datum_shift mode

    # Map of well_id -> depth at datum_name (for datum_shift mode)
    datum_depths: Dict[str, float] = field(default_factory=dict)
    # Global depth bounds for absolute mode
    global_min_depth: float = 0.0
    global_max_depth: float = 1000.0

    def get_depth_y(self, well_id: str, depth: float) -> float:
        """Map measured depth for a specific well to canvas Y-coordinate."""
        if self.mode == "datum_shift" and self.datum_name and well_id in self.datum_depths:
            well_datum_depth = self.datum_depths[well_id]
            return self.y_datum + (depth - well_datum_depth) * self.scale_y
        # Absolute mode
        return self.header_height + (depth - self.global_min_depth) * self.scale_y

    def inverse_y_to_depth(self, well_id: str, y: float) -> float:
        """Map canvas Y-coordinate back to measured depth for a specific well."""
        if self.mode == "datum_shift" and self.datum_name and well_id in self.datum_depths:
            well_datum_depth = self.datum_depths[well_id]
            return well_datum_depth + (y - self.y_datum) / max(1e-6, self.scale_y)
        return self.global_min_depth + (y - self.header_height) / max(1e-6, self.scale_y)
