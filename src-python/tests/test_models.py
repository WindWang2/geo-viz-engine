from datetime import datetime
from app.models.common import HealthResponse, ErrorResponse
from app.models.well_log import CurveData, WellLogData, WellMetadata, GenerateDataRequest, GenerateDataResponse


def test_health_response_fields():
    h = HealthResponse(
        status="ok",
        version="0.1.0",
        timestamp=datetime.now(),
        backend="geo-viz-engine-python",
    )
    assert h.status == "ok"
    assert h.version == "0.1.0"
    assert h.backend == "geo-viz-engine-python"


def test_error_response_fields():
    e = ErrorResponse(detail="Unauthorized", code="AUTH_001")
    assert e.detail == "Unauthorized"
    assert e.code == "AUTH_001"


def test_error_response_code_optional():
    e = ErrorResponse(detail="Not found")
    assert e.code is None


def test_curve_data_fields():
    c = CurveData(
        name="GR",
        unit="API",
        data=[80.0, 85.0, 90.0],
        depth=[0.0, 0.125, 0.25],
        min_value=80.0,
        max_value=90.0,
        display_range=(0.0, 150.0),
        color="#00AA00",
        line_style="solid",
    )
    assert c.name == "GR"
    assert c.unit == "API"
    assert len(c.data) == 3
    assert c.display_range == (0.0, 150.0)


def test_well_log_data_fields():
    curve = CurveData(
        name="GR", unit="API", data=[80.0], depth=[0.0],
        min_value=80.0, max_value=80.0, display_range=(0.0, 150.0),
        color="#00AA00", line_style="solid",
    )
    well = WellLogData(
        well_id="WELL-001",
        well_name="Well 1",
        depth_start=0.0,
        depth_end=3000.0,
        depth_step=0.125,
        curves=[curve],
    )
    assert well.well_id == "WELL-001"
    assert well.location is None
    assert len(well.curves) == 1


def test_well_log_data_with_location():
    well = WellLogData(
        well_id="WELL-002", well_name="Well 2",
        depth_start=0.0, depth_end=3000.0, depth_step=0.125,
        location=(102.5, 38.3), curves=[],
    )
    assert well.location == (102.5, 38.3)


def test_generate_data_request_defaults():
    req = GenerateDataRequest()
    assert req.count == 10
    assert req.depth_start == 0.0
    assert req.depth_end == 3000.0
    assert req.depth_step == 0.125


def test_generate_data_request_validation_count_zero():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        GenerateDataRequest(count=0)


def test_generate_data_request_validation_count_too_large():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        GenerateDataRequest(count=101)
