import pytest
import numpy as np

def test_rdp_simplification():
    from geoviz_paleo_map.lod import rdp_simplify
    
    # A straight line with an intermediate point
    points = np.array([
        [0.0, 0.0],
        [1.0, 1.0],
        [2.0, 2.0]
    ])
    
    # Epsilon = 0.5. The middle point is exactly on the line, so distance=0.
    simplified = rdp_simplify(points, epsilon=0.5)
    
    assert len(simplified) == 2
    assert np.allclose(simplified[0], [0.0, 0.0])
    assert np.allclose(simplified[1], [2.0, 2.0])

def test_rdp_simplification_preserves_corners():
    from geoviz_paleo_map.lod import rdp_simplify
    
    # A V-shape
    points = np.array([
        [0.0, 0.0],
        [1.0, 1.0], # distance to line (0,0)-(2,0) is 1.0
        [2.0, 0.0]
    ])
    
    # Epsilon = 0.5 < 1.0, so the point should be kept
    simplified = rdp_simplify(points, epsilon=0.5)
    assert len(simplified) == 3
    
    # Epsilon = 1.5 > 1.0, so the point should be removed
    simplified2 = rdp_simplify(points, epsilon=1.5)
    assert len(simplified2) == 2
