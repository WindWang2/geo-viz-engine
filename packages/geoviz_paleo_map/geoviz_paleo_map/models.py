"""Data models for geoviz_paleo_map."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QBrush, QColor


@dataclass(frozen=True)
class FaciesStyle:
    """Resolved styling for one facies value: base color + optional composite brush."""

    base_color: QColor
    brush: QBrush
    pattern_id: str | None = None
