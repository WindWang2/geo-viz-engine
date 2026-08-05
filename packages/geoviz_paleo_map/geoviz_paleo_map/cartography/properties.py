"""PropertyPanel — sidebar form for the currently-selected free graphic.

Wires ``QFormLayout`` editors (stroke/fill hex, line-width mm, font mm,
text, align, scale-bar denominator) to the selected ``FreeGraphicsItem``.
The window refreshes the panel on ``selectionChanged``; each editor
signal writes back to the item immediately (spec §3.4).

Deviation from the plan: ``refresh_from_selection`` locates the scene
through ``self.window()`` and reloads the first selected free graphic —
the plan's version only cleared the panel, which contradicted its own
test (``refresh_from_selection`` must reflect the scene's selection).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QWidget,
)

from geoviz_paleo_map.cartography.items.free.base import FreeGraphicsItem


class PropertyPanel(QWidget):
    """Form that edits the single selected free graphic."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._item: FreeGraphicsItem | None = None
        form = QFormLayout(self)
        form.setContentsMargins(4, 4, 4, 4)

        self._stroke_edit = QLineEdit()
        form.addRow("描边色", self._stroke_edit)
        self._fill_edit = QLineEdit()
        form.addRow("填充色", self._fill_edit)
        self._width_spin = QDoubleSpinBox()
        self._width_spin.setRange(0.1, 20.0)
        self._width_spin.setSingleStep(0.1)
        self._width_spin.setSuffix(" mm")
        form.addRow("线宽", self._width_spin)
        self._font_spin = QDoubleSpinBox()
        self._font_spin.setRange(1.0, 50.0)
        self._font_spin.setSingleStep(0.5)
        self._font_spin.setSuffix(" mm")
        form.addRow("字号", self._font_spin)
        self._text_edit = QLineEdit()
        form.addRow("文本", self._text_edit)
        self._align_combo = QComboBox()
        self._align_combo.addItems(["left", "center", "right"])
        form.addRow("对齐", self._align_combo)
        self._denom_spin = QDoubleSpinBox()
        self._denom_spin.setRange(1, 10_000_000)
        self._denom_spin.setDecimals(0)
        form.addRow("比例尺分母", self._denom_spin)

        self._stroke_edit.editingFinished.connect(self._apply_stroke)
        self._fill_edit.editingFinished.connect(self._apply_fill)
        self._width_spin.valueChanged.connect(self._apply_width)
        self._font_spin.valueChanged.connect(self._apply_font)
        self._text_edit.editingFinished.connect(self._apply_text)
        self._align_combo.currentIndexChanged.connect(self._apply_align)
        self._denom_spin.valueChanged.connect(self._apply_denominator)
        self.setEnabled(False)

    # -- refresh --------------------------------------------------------

    def refresh_from_selection(self) -> None:
        """Reload the first selected free graphic in the owning window.

        The panel lives in the window's sidebar, so ``self.window()`` is
        the ``CartographyLayoutWindow`` exposing ``_scene``.
        """
        from geoviz_paleo_map.cartography.items.free.base import FreeGraphicsItem
        win = self.window()
        scene = getattr(win, "_scene", None) if win is not None else None
        item = None
        if scene is not None:
            free = [
                it for it in scene.selectedItems()
                if isinstance(it, FreeGraphicsItem)
            ]
            item = free[0] if free else None
        self.set_item(item)

    def set_item(self, item: FreeGraphicsItem | None) -> None:
        self._item = item
        if item is None:
            self.setEnabled(False)
            return
        self.setEnabled(True)
        self._stroke_edit.setText(item.stroke)
        self._fill_edit.setText(item.fill or "")
        self._width_spin.blockSignals(True)
        self._width_spin.setValue(item.width_mm)
        self._width_spin.blockSignals(False)
        self._font_spin.blockSignals(True)
        self._font_spin.setValue(item.font_mm)
        self._font_spin.blockSignals(False)
        text = getattr(item, "text", "")
        self._text_edit.setText(text)
        align = getattr(item, "align", "left")
        idx = self._align_combo.findText(align)
        self._align_combo.blockSignals(True)
        self._align_combo.setCurrentIndex(max(0, idx))
        self._align_combo.blockSignals(False)
        denom = getattr(item, "denominator", 0)
        if denom:
            self._denom_spin.blockSignals(True)
            self._denom_spin.setValue(float(denom))
            self._denom_spin.blockSignals(False)

    # -- write-back -----------------------------------------------------

    def _current_style(self) -> dict:
        item = self._item
        return {
            "stroke": item.stroke,
            "fill": item.fill,
            "width_mm": item.width_mm,
            "font_mm": item.font_mm,
        }

    def _apply_stroke(self) -> None:
        if self._item is None:
            return
        self._item.stroke = self._stroke_edit.text()
        self._item.update()

    def _apply_fill(self) -> None:
        if self._item is None:
            return
        txt = self._fill_edit.text().strip()
        self._item.fill = txt or None
        self._item.update()

    def _apply_width(self) -> None:
        if self._item is None:
            return
        self._item.apply_style({**self._current_style(), "width_mm": self._width_spin.value()})

    def _apply_font(self) -> None:
        if self._item is None:
            return
        self._item.apply_style({**self._current_style(), "font_mm": self._font_spin.value()})

    def _apply_text(self) -> None:
        if self._item is not None and hasattr(self._item, "text"):
            self._item.text = self._text_edit.text()
            if hasattr(self._item, "_reflow"):
                self._item._reflow()
            self._item.update()

    def _apply_align(self) -> None:
        if self._item is not None and hasattr(self._item, "align"):
            self._item.align = self._align_combo.currentText()
            self._item.update()

    def _apply_denominator(self) -> None:
        if self._item is not None and hasattr(self._item, "denominator"):
            self._item.denominator = int(self._denom_spin.value())
            self._item.update()
