# Understanding LAS Null Handling

The industry-standard LAS format stores missing or unrecorded well log data as a specific "null" floating point number, typically `-999.25` or `-9999.0`. Failing to handle this properly results in catastrophic visualization errors, such as curves snapping to negative infinity on plots, rendering the entire depth track illegible.

## The problem

When reading ASCII rows from a `.las` file, the values are parsed indiscriminately as floats. If a tool was turned off at the top of the well, the resulting array might look like this:

`[ -999.25, -999.25, 42.1, 44.5, 48.2 ]`

If passed directly to a visualization engine or clustering algorithm, the minimum value is calculated as `-999.25`, forcing the axis to scale out drastically. Furthermore, statistical analysis (like computing averages or convex hulls) becomes polluted by the sentinel values.

## The approach

GeoViz Engine's LAS parser handles this automatically during the file ingestion phase before any downstream rendering or analytics can be affected.

The design relies on NumPy's vectorized masking:

```python
# The parser extracts the null sentinel from the WELL block
null_value = -999.25 # (Default, overridden by WELL.NULL)

# We identify and replace nulls using a tolerance
vals[np.isclose(vals, null_value, atol=1e-3)] = np.nan
vals[vals == -9999.0] = np.nan
```

By substituting these sentinels with `np.nan` (Not a Number):
1. **Plotting**: Matplotlib and QPainter natively skip over `NaN` values, resulting in clean gaps in the curve track rather than giant spikes.
2. **Math**: NumPy functions (like `np.nanmax`, `np.nanmean`) can safely operate on the arrays without skewing the results.
3. **Cross-plots**: Convex hull algorithms and regressions easily drop `NaN` coordinates.

## Trade-offs

We chose implicit normalization to `np.nan` over returning the original raw values and the null sentinel to the user. 

- **Trade-off**: The user loses the ability to distinguish between "missing data" and "exactly -999.25 recorded".
- **Why**: In petrophysics, exactly recording -999.25 as a valid geological measurement is effectively impossible. The burden of manually scrubbing data is high and a frequent source of errors, so GeoViz enforces safety at the parsing layer.

## Alternatives considered

We considered returning a `MaskedArray` instead of standard `ndarray` with `NaN`s. However, `MaskedArray` operations carry a significant performance overhead, and PySide6's `QPainter` integration (where we explicitly iterate over indices or map vertices) is far more ergonomic when dealing with standard float arrays. 
