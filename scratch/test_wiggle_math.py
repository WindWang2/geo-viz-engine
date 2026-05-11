import numpy as np

def get_positive_polygons(trace, y_coords, center_x, scale):
    polys = []
    current_poly = []
    
    n = len(trace)
    
    for i in range(n - 1):
        v1, v2 = trace[i], trace[i+1]
        y1, y2 = y_coords[i], y_coords[i+1]
        
        if v1 >= 0:
            if not current_poly:
                current_poly.append((center_x, y1))
            current_poly.append((center_x + v1 * scale, y1))
            
            if v2 < 0:
                # Crossed from pos to neg
                frac = v1 / (v1 - v2)
                y_c = y1 + frac * (y2 - y1)
                current_poly.append((center_x, y_c))
                polys.append(current_poly)
                current_poly = []
        else:
            if v2 > 0:
                # Crossed from neg to pos
                frac = -v1 / (v2 - v1)
                y_c = y1 + frac * (y2 - y1)
                current_poly = [(center_x, y_c)]
                
    # Handle final sample
    if trace[-1] >= 0:
        if not current_poly:
             current_poly.append((center_x, y_coords[-1]))
        current_poly.append((center_x + trace[-1] * scale, y_coords[-1]))
        current_poly.append((center_x, y_coords[-1]))
        polys.append(current_poly)
    elif current_poly:
        # Closes current open polygon if last is neg but was open (shouldn't happen with logic above but safe)
        current_poly.append((center_x, y_coords[-1]))
        polys.append(current_poly)
        
    return polys

# Test
trace = np.array([-5, 10, 20, -10, -5, 5, -2])
y = np.arange(len(trace))
polygons = get_positive_polygons(trace, y, center_x=100, scale=1.0)
for i, p in enumerate(polygons):
    print(f"Poly {i}:")
    for pt in p:
        print(f"  {pt}")
