"""L5 display controls: polarity / wiggle gain / colormap registry / reset.

Polarity and gain are DISPLAY-ONLY: the stored slice data, the cursor
readout path and picked values keep the survey sign convention. Tests
assert the mapping math (VD index flip), the wiggle geometry factor, the
toolbar contract (full colormap list, reset) and that raw data never
changes.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from geoviz_seismic.colormap import ColormapManager
from geoviz_seismic.profile_vd import ProfileVD
from geoviz_seismic.profile_wiggle import ProfileWiggle
from geoviz_seismic.seismic_view import SeismicView


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _symmetric_volume(n_traces: int = 8, n_samples: int = 32) -> np.ndarray:
    """A section with both strong positive and negative lobes."""
    rng = np.random.default_rng(7)
    t = np.arange(n_samples, dtype=np.float32)
    data = rng.normal(0.0, 0.05, (n_samples, n_traces)).astype(np.float32)
    data[5, 0] = 1.0   # strong positive
    data[5, 1] = -1.0  # strong negative
    return data + 0.0 * t[:, None]


class TestProfileVDPolarity:
    def test_polarity_flips_index_mapping_but_not_data(self, qapp, qtbot):
        vd = ProfileVD()
        qtbot.addWidget(vd)
        data = _symmetric_volume()
        vd.render(data)
        normal_index = vd._indexed.copy()
        raw_before = vd._data.copy()

        vd.set_polarity(normal=False)
        flipped = vd._indexed
        assert flipped is not normal_index

        # The value that indexed HIGH under normal polarity must index LOW
        # under reversed polarity (and vice versa) — sign flip, not reshuffle.
        assert flipped[5, 0] < flipped[5, 1]
        assert normal_index[5, 0] > normal_index[5, 1]
        # The stored data is untouched: polarity is display-only.
        np.testing.assert_array_equal(vd._data, raw_before)

        vd.set_polarity(normal=True)
        np.testing.assert_array_equal(vd._indexed, normal_index)

    def test_clip_cache_survives_polarity_toggle(self, qapp, qtbot):
        vd = ProfileVD()
        qtbot.addWidget(vd)
        vd.render(_symmetric_volume())
        cached = vd._clip_range_cache
        vd.set_polarity(False)
        vd.set_polarity(True)
        assert vd._clip_range_cache == cached  # negation reuses the range


class TestProfileWiggleControls:
    def test_gain_contract(self, qapp, qtbot):
        wiggle = ProfileWiggle()
        qtbot.addWidget(wiggle)
        assert wiggle.gain() == 2.0  # historical default
        wiggle.set_gain(5.0)
        assert wiggle.gain() == 5.0
        with pytest.raises(ValueError):
            wiggle.set_gain(0.0)
        with pytest.raises(ValueError):
            wiggle.set_gain(float("nan"))

    def test_polarity_flag(self, qapp, qtbot):
        wiggle = ProfileWiggle()
        qtbot.addWidget(wiggle)
        assert wiggle.polarity_normal()
        wiggle.set_polarity(False)
        assert not wiggle.polarity_normal()
        wiggle.set_polarity(False)  # idempotent
        assert not wiggle.polarity_normal()

    def test_wiggle_paints_with_gain_and_polarity(self, qapp, qtbot):
        wiggle = ProfileWiggle()
        qtbot.addWidget(wiggle)
        wiggle.resize(400, 300)
        wiggle.show()
        wiggle.render(_symmetric_volume(), trace_step=1)
        wiggle.set_gain(4.0)
        wiggle.set_polarity(False)
        qtbot.waitExposed(wiggle)
        wiggle.repaint()
        assert wiggle._cached_pixmap is None  # display change invalidates cache


class TestSeismicViewToolbar:
    # auto_load=False: the default constructor spawns the synthetic-preview
    # auto-load QThread, which outlives widget teardown in tests and aborts
    # the interpreter at exit ("QThread: Destroyed while thread …").
    def test_colormap_combo_lists_the_full_registry(self, qapp, qtbot):
        view = SeismicView(auto_load=False)
        qtbot.addWidget(view)
        listed = {view._cmap_combo.itemText(i) for i in range(view._cmap_combo.count())}
        assert listed == set(ColormapManager._COLORMAPS)
        assert view._cmap_combo.currentText() == "seismic"

    def test_polarity_and_gain_reach_every_profile_panel(self, qapp, qtbot):
        view = SeismicView(auto_load=False)
        qtbot.addWidget(view)
        panels = [view._profile_il, view._profile_xl, view._profile_t, view._profile_arb]
        view._gain_spin.setValue(3.5)
        assert all(pw.wiggle_gain() == 3.5 for pw in panels)
        view._act_polarity.setChecked(True)
        assert all(not pw.polarity_normal() for pw in panels)

    def test_reset_display_controls_restores_factory_state(self, qapp, qtbot):
        view = SeismicView(auto_load=False)
        qtbot.addWidget(view)
        view._clip_spin.setValue(80.0)
        view._gain_spin.setValue(9.0)
        view._act_polarity.setChecked(True)
        view._cmap_combo.setCurrentText("gray")
        view._mode_combo.setCurrentIndex(1)

        view._reset_display_controls()

        assert view._clip_spin.value() == 99.0
        assert view._gain_spin.value() == 2.0
        assert not view._act_polarity.isChecked()
        assert view._cmap_combo.currentText() == "seismic"
        assert view._mode_combo.currentIndex() == 0
        panels = [view._profile_il, view._profile_xl, view._profile_t, view._profile_arb]
        assert all(pw.polarity_normal() for pw in panels)
        assert all(pw.wiggle_gain() == 2.0 for pw in panels)
