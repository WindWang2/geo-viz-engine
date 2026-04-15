import pytest
import os
from app.services.well_data_service import WellDataService

def test_get_well_details():
    service = WellDataService()
    well_name = "老龙1"
    
    # This should fail because WellDataService is not yet implemented
    data = service.get_well_details(well_name)
    
    assert data["well_name"] == well_name
    assert "curves" in data
    assert "intervals" in data
    
    # Check curves
    curve_names = [c["name"] for c in data["curves"]]
    assert "AC" in curve_names
    assert "GR" in curve_names
    assert "RT" in curve_names
    assert "RXO" in curve_names
    
    # Check intervals
    assert "formation" in data["intervals"]
    assert "lithology" in data["intervals"]
    assert "facies" in data["intervals"]
    assert "sequence" in data["intervals"]

    # Verify formation structure
    formation = data["intervals"]["formation"]
    assert len(formation) > 0
    assert "top" in formation[0]
    assert "bottom" in formation[0]
    assert "name" in formation[0]
