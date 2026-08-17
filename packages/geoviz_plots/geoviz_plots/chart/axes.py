"""Coordinate axes ticks and nice number calculations."""
import math

def nice_number(value: float, round_flag: bool) -> float:
    """Return a nice rounded number near value.
    
    If round_flag is True, rounds to the nearest nice number (1, 2, 5, 10).
    If False, ceils to the next nice number.
    """
    if value == 0.0:
        return 0.0

    sign = -1 if value < 0 else 1
    value = abs(value)
    exponent = math.floor(math.log10(value))
    fraction = value / (10 ** exponent)
    
    if round_flag:
        if fraction < 1.5:
            nice_fraction = 1.0
        elif fraction < 3.0:
            nice_fraction = 2.0
        elif fraction < 7.0:
            nice_fraction = 5.0
        else:
            nice_fraction = 10.0
    else:
        if fraction <= 1.0:
            nice_fraction = 1.0
        elif fraction <= 2.0:
            nice_fraction = 2.0
        elif fraction <= 5.0:
            nice_fraction = 5.0
        else:
            nice_fraction = 10.0
            
    return sign * nice_fraction * (10 ** exponent)

def calculate_ticks(vmin: float, vmax: float, max_ticks: int) -> tuple[list[float], float]:
    """Calculate nice tick intervals and a list of ticks for a given range.
    
    Returns:
        (ticks, step_size)
    """
    if max_ticks <= 1:
        return [vmin], 1.0

    if not (math.isfinite(vmin) and math.isfinite(vmax)):
        return [], 1.0
        
    if vmin > vmax:
        vmin, vmax = vmax, vmin
        
    if vmin == vmax:
        if vmin == 0.0:
            return [0.0], 1.0
        step = nice_number(abs(vmin) * 0.1, True)
        if step == 0.0:
            step = 1.0
        return [vmin], step
        
    range_val = nice_number(vmax - vmin, False)
    step = nice_number(range_val / (max_ticks - 1), True)
    if step == 0.0:
        step = 1.0
        
    nice_min = math.floor(vmin / step) * step
    nice_max = math.ceil(vmax / step) * step
    
    ticks = []
    current = nice_min
    
    # Use epsilon buffer to prevent floating point comparison errors
    eps = 1e-9
    while current <= nice_max + 0.5 * step:
        # Round to avoid float representation issues like 0.30000000000000004
        rounded_val = round(current / step) * step
        # Format and parse to match precision of step to completely kill float slop
        precision = max(0, -math.floor(math.log10(step))) if step > 0 else 0
        rounded_val = round(rounded_val, precision + 2)
        ticks.append(rounded_val)
        current += step
        
    return ticks, step


def format_tick(value: float, step: float) -> str:
    """Format a tick or hover value with decimals matching ``step``.

    ``calculate_ticks`` already chooses a step that distinguishes adjacent
    ticks; labels must use that precision so a 0.001–0.004 window does not
    collapse to identical ``0.00`` strings.
    """
    if not math.isfinite(value):
        return str(value)
    if not math.isfinite(step) or step <= 0.0:
        step = abs(value) if value != 0.0 else 1.0
    decimals = min(12, max(0, -math.floor(math.log10(step))))
    return f"{value:.{decimals}f}"
