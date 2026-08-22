"""TimeSliceMap2D shows ActiveTimeSlice pierce points."""

from __future__ import annotations

import numpy as np

from geoviz_well_seismic_3d import (
    InMemoryVolumeAccess,
    JointWellId,
    TimeDepthTable,
    WellHead,
    WellSeismicScene,
)
from geoviz_well_seismic_3d.time_map_2d import TimeSliceMap2D

P1 = (1315, 4165, 0.0, 0.0)
P2 = (1315, 4805, 12793.0, 0.0)
P3 = (1725, 4805, 12793.0, 16406.0)


def test_time_map_records_pierce_hits(qtbot):
    scene = WellSeismicScene()
    scene.set_survey_from_corners(P1, P2, P3, n_samples=21, dt_ms=10.0)
    data = np.zeros((6, 8, 21), dtype=np.float32)
    data[2, 3, :] = 1.0
    scene.set_volume_access(InMemoryVolumeAccess(data))
    scene.set_wells(
        [
            WellHead(
                "A1", 1000, 2000, 1000, 2000, 2000, id=JointWellId("source:a1")
            )
        ],
        td_tables={
            "A1": TimeDepthTable(
                well_name="A1",
                time_ms=np.array([0.0, 200.0], dtype=np.float64),
                md_m=np.array([0.0, 2000.0], dtype=np.float64),
            )
        },
    )
    scene.update_time_slice(scene.orthogonal_slice_state.active_time_ms, 100.0)
    widget = TimeSliceMap2D()
    qtbot.addWidget(widget)
    widget.resize(400, 240)
    widget.set_scene(scene)
    ids = {well_id for _px, _py, well_id in widget._hits}
    assert "source:a1" in ids
    assert widget._image is not None
    assert widget._caption.startswith("Time 平面")
