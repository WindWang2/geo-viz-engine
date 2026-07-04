"""Unit tests for LAS 2.0 / 3.0 file parser."""
import numpy as np
import pytest
from geoviz_well_log.las_parser import parse_las_text

SAMPLE_LAS_CONTENT = """~VERSION INFORMATION
 VERS .                 2.0 : CWLS LOG ASCII STANDARD -VERSION 2.0
 WRAP .                  NO : ONE LINE PER DEPTH STEP
~WELL INFORMATION
 WELL.             WELL-01 : WELL NAME
 STRT.M             2000.00 : START DEPTH
 STOP.M             2005.00 : STOP DEPTH
 STEP.M                1.00 : STEP
 NULL.              -999.25 : NULL VALUE
~CURVE INFORMATION
 DEPT  .M                   : DEPTH
 GR    .API                 : GAMMA RAY
 DT    .US/M                : ACOUSTIC TRANSIT TIME
~ASCII
 2000.00   45.2   220.0
 2001.00   52.1   -999.25
 2002.00   61.8   215.4
 2003.00   -999.25 210.1
 2004.00   75.3   205.0
 2005.00   80.0   200.0
"""

def test_parse_las_text():
    result = parse_las_text(SAMPLE_LAS_CONTENT)
    assert result.well_name == "WELL-01"
    assert len(result.depth) == 6
    assert np.isclose(result.depth[0], 2000.0)
    assert np.isclose(result.depth[-1], 2005.0)

    assert "GR" in result.curves
    assert "DT" in result.curves
    assert result.units["GR"] == "API"
    assert result.units["DT"] == "US/M"

    # NULL sentinel replacement check
    assert np.isnan(result.curves["DT"][1])  # -999.25 replaced by nan
    assert np.isnan(result.curves["GR"][3])  # -999.25 replaced by nan
    assert np.isclose(result.curves["GR"][0], 45.2)
