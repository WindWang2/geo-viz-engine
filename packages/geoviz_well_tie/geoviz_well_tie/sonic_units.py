"""Unit-aware sonic slowness normalization (WL-9 / #406).

The well-tie host previously classified sonic curves with a purely numeric
heuristic (median of |sonic| < 150 => assume µs/ft and multiply by 3.28084),
which misfires on tight carbonates whose typical 140-150 µs/m median falls
exactly inside that guessed µs/ft band — TWT then comes out ~3.3x too large.
Curve unit metadata is already available at parse time (LAS ~C block,
``CurveData.unit``) but was discarded. This module resolves the unit from
the metadata first and only falls back to the numeric heuristic when the
unit is missing or unknown, returning a warning for the caller to surface.
"""

from __future__ import annotations

import numpy as np

#: µs/ft -> µs/m factor (feet per metre).
US_FT_TO_US_M = 3.28084

_US_PER_M = frozenset({"us/m", "usm", "um"})
# "usft"/"usecft"/"microsecft" are separator-less LAS spellings that do not end
# in "/ft". They were recognised by the well-tie host's former private table, so
# they must stay recognised now that this module is the single sonic unit table
# and the host delegates to it (#879).
_US_PER_FT = frozenset(
    {"us/f", "us/ft", "usf", "uf", "usft", "usecft", "microsecft"}
)


def canonical_sonic_unit(unit: str | None) -> str | None:
    """Return ``"us/m"``, ``"us/ft"`` or ``None`` for a LAS curve unit string.

    Handles common case variants and micro-sign spellings (``US/M``,
    ``us/m``, ``µs/m``, ``USF``, ``US/FT``, ...). Empty/unknown strings
    yield ``None``.
    """
    if not unit:
        return None
    u = unit.strip().lower().replace("µ", "u").replace("μ", "u")
    if not u:
        return None
    u = u.replace(" ", "")
    if u in _US_PER_M or u.endswith("/m"):
        return "us/m"
    if u in _US_PER_FT or u.endswith("/f") or u.endswith("/ft"):
        return "us/ft"
    return None


def normalize_sonic_units(
    sonic: np.ndarray,
    unit: str | None = None,
) -> tuple[np.ndarray, str, str | None]:
    """Return ``(sonic in µs/m, resolved unit, warning)``.

    - unit resolves to µs/m: values returned unchanged.
    - unit resolves to µs/ft: values scaled by ``US_FT_TO_US_M``.
    - unit missing/unknown: the legacy numeric heuristic runs (median of
      ``|sonic| < 150`` => treat as µs/ft and scale); the heuristic never
      runs silently — a warning string is returned for the caller to log or
      surface in the UI.

    The returned warning is ``None`` when metadata fully determined the unit.
    """
    sonic = np.asarray(sonic, dtype=np.float64)
    resolved = canonical_sonic_unit(unit)
    if resolved == "us/m":
        return sonic, "us/m", None
    if resolved == "us/ft":
        return sonic * US_FT_TO_US_M, "us/m", None

    finite = sonic[np.isfinite(sonic)]
    if finite.size == 0:
        return sonic, "us/m", (
            f"sonic unit '{unit}' unknown and no finite samples — assumed µs/m"
        )
    median = float(np.nanmedian(np.abs(finite)))
    if median < 150.0:
        return (
            sonic * US_FT_TO_US_M,
            "us/m",
            f"sonic unit '{unit}' unknown; median |sonic| {median:.1f} < 150 "
            f"suggests µs/ft — scaled by {US_FT_TO_US_M:.5f}",
        )
    return sonic, "us/m", (
        f"sonic unit '{unit}' unknown; median |sonic| {median:.1f} >= 150 — "
        "assumed µs/m"
    )
