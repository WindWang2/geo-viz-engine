# How to import LAS data

This guide shows you how to load well log data from industry-standard LAS 2.0 or 3.0 files into NumPy arrays using the GeoViz Engine.

## Prerequisites

- You need a valid `.las` file on your filesystem.
- The `geoviz_well_log` package must be installed in your environment.

## Steps

1. Import the parser function from `geoviz_well_log.las_parser`:

   ```python
   from geoviz_well_log.las_parser import parse_las_file
   ```

2. Call the parse function on your file:

   ```python
   # Reads the file and automatically converts -999.25 to np.nan
   result = parse_las_file("data/my_well.las")
   ```

3. Extract the depth array and your curves of interest:

   ```python
   # The depth array is guaranteed to be extracted if a 'DEPT' or 'DEPTH' column exists
   depths = result.depth
   
   # Other curves are stored in a dictionary mapping column names to 1D arrays
   gamma_ray = result.curves.get("GR")
   resistivity = result.curves.get("ILD")
   
   print(f"Loaded {len(depths)} samples for well {result.well_name}")
   ```

## Verification

To verify the data loaded correctly, you can check the shape of the arrays and the automatic removal of null sentinels:

```python
import numpy as np

# Ensure lengths match
assert len(depths) == len(gamma_ray)

# Verify nulls (-999.25) were converted to NaNs
nan_count = np.isnan(gamma_ray).sum()
print(f"Found {nan_count} invalid/null readings")
```

## Troubleshooting

- **`AttributeError: 'NoneType' object has no attribute 'shape'`**: This occurs if the curve you requested (e.g., `"GR"`) does not exist in the file. Check `list(result.curves.keys())` to see what curves are actually available.
- **Empty Arrays**: If `result.depth` is empty, the parser likely could not find a curve named `DEPT` or `DEPTH`. Check `result.curves.keys()` and look for an alternatively named depth column.

## Related
- [LAS Parser Reference](file:///home/kevin/projects/geo-viz-engine/docs/reference-las-parser.md)
- [Explanation: LAS Null Handling](file:///home/kevin/projects/geo-viz-engine/docs/explanation-las-null-handling.md)
