import pytest
from geoviz_cross_well.auto_section_planner import (
    _extract_coords,
    plan_section,
    plan_section_pca,
    plan_section_nearest_neighbor,
)
from src.data.models import WellCoordinates

class CustomWell:
    def __init__(self, name, lng, lat):
        self.name = name
        self.lng = lng
        self.lat = lat

def test_extract_coords_tuple():
    """Verify coord extraction from raw tuples."""
    assert _extract_coords(("W1", 120.5, 31.2)) == ("W1", 120.5, 31.2)
    assert _extract_coords(("W2", (120.5, 31.2))) == ("W2", 120.5, 31.2)

def test_extract_coords_dict():
    """Verify coord extraction from dicts with various keys."""
    assert _extract_coords({"name": "W1", "longitude": 120.5, "latitude": 31.2}) == ("W1", 120.5, 31.2)
    assert _extract_coords({"well_name": "W2", "lng": 120.5, "lat": 31.2}) == ("W2", 120.5, 31.2)
    assert _extract_coords({"id": "W3", "x": 120.5, "y": 31.2}) == ("W3", 120.5, 31.2)

def test_extract_coords_objects():
    """Verify coord extraction from standard Pydantic models and custom classes."""
    pydantic_well = WellCoordinates(name="W1", longitude=120.5, latitude=31.2)
    assert _extract_coords(pydantic_well) == ("W1", 120.5, 31.2)
    
    custom_well = CustomWell("W2", 120.5, 31.2)
    assert _extract_coords(custom_well) == ("W2", 120.5, 31.2)

def test_pca_planning_basic():
    """Verify that PCA sorting correctly orders collinear horizontal wells."""
    w1 = {"name": "W1", "lng": 100.0, "lat": 30.0}
    w2 = {"name": "W2", "lng": 105.0, "lat": 30.0}
    w3 = {"name": "W3", "lng": 102.0, "lat": 30.0}
    
    sorted_wells = plan_section([w1, w2, w3], method="pca")
    names = [w["name"] for w in sorted_wells]
    
    # Can be left-to-right or right-to-left
    assert names == ["W1", "W3", "W2"] or names == ["W2", "W3", "W1"]

def test_pca_planning_diagonal():
    """Verify that PCA sorting handles diagonal layouts correctly."""
    w1 = {"name": "W1", "lng": 10.0, "lat": 10.0}
    w2 = {"name": "W2", "lng": 20.0, "lat": 20.0}
    w3 = {"name": "W3", "lng": 15.0, "lat": 15.0}
    
    sorted_wells = plan_section([w1, w2, w3], method="pca")
    names = [w["name"] for w in sorted_wells]
    assert names == ["W1", "W3", "W2"] or names == ["W2", "W3", "W1"]

def test_nearest_neighbor_dog_leg():
    """Verify that Nearest Neighbor (TSP) handles a winding dog-leg section where PCA fails."""
    # A V-shape layout:
    # W1 at (0, 0)
    # W2 at (1, 1)
    # W3 at (2, 0)
    # PCA projection axis might project W1 and W3 close to each other.
    # W1 to W2 is distance sqrt(2) ~ 1.41
    # W1 to W3 is distance 2.0
    w1 = {"name": "W1", "lng": 0.0, "lat": 0.0}
    w2 = {"name": "W2", "lng": 1.0, "lat": 1.0}
    w3 = {"name": "W3", "lng": 2.0, "lat": 0.0}
    
    # Run Nearest Neighbor path
    sorted_wells = plan_section([w1, w2, w3], method="nearest_neighbor")
    names = [w["name"] for w in sorted_wells]
    
    # Path starting at an extreme endpoint (W1 or W3) should flow sequentially:
    # W1 -> W2 -> W3  OR  W3 -> W2 -> W1
    assert names == ["W1", "W2", "W3"] or names == ["W3", "W2", "W1"]

def test_planning_invalid_method():
    """Verify that plan_section raises ValueError for invalid sorting method names."""
    w1 = ("W1", 0.0, 0.0)
    w2 = ("W2", 1.0, 1.0)
    
    with pytest.raises(ValueError, match="Unknown planning method"):
        plan_section([w1, w2], method="invalid_method")

def test_planning_trivial_lists():
    """Verify that lists with <= 2 wells are returned unchanged."""
    w1 = ("W1", 0.0, 0.0)
    assert plan_section([w1]) == [w1]
    assert plan_section([]) == []
