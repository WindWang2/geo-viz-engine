"""Survey corners from SEGY aligned to SeismicLoader volume axes (wayfinder #81/#84).

**Contract (decision A):** Volume shape is ``(n_inline, n_crossline, n_sample)``
from ``SeismicLoader``. ``SurveySpec.n_inlines`` / ``n_crosslines`` match that
assignment (full-grid counts). Preview cubes keep the same axis order;
``VolumeRegistration`` only scales indices for downsampling.

On non-standard SEGY (FieldRecord/CDP as geometry), loader IL numbers are the
text-header **xlines** and loader XL numbers are text **inlines**. Corners are
built in **loader** IL/XL space so survey and cube agree without transposing.
"""

from __future__ import annotations

import re
from pathlib import Path


def survey_corners_from_segy(
    segy_path: Path | str,
) -> tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    dict,
]:
    """Return (p1, p2, p3, meta) for ``survey_from_corners`` in **loader** axes.

    p* = (loader_inline, loader_crossline, x, y) so that
    ``n_inlines == SeismicLoader.n_inlines`` and
    ``n_crosslines == SeismicLoader.n_crosslines``.

    meta includes n_samples, dt_ms, t0_ms, and loader counts.
    """
    path = Path(segy_path)
    if not path.is_file():
        raise FileNotFoundError(str(path))

    import segyio

    loader_meta: dict = {}
    try:
        from geoviz_seismic.loader import SeismicLoader

        loader = SeismicLoader(str(path))
        try:
            m = loader.inspect()
            loader_meta = {
                "loader_n_inlines": m.n_inlines,
                "loader_n_crosslines": m.n_crosslines,
                "loader_iline_start": m.iline_start,
                "loader_iline_step": getattr(m, "iline_step", 1),
                "loader_xline_start": m.xline_start,
                "loader_xline_step": getattr(m, "xline_step", 1),
                "loader_geometry_source": getattr(
                    m, "geometry_source", getattr(loader, "geometry_source", "unknown")
                ),
                "loader_geometry_fields": getattr(
                    m, "geometry_fields", getattr(loader, "geometry_fields", None)
                ),
                "n_samples": m.n_samples,
                "dt_ms": m.dt_ms,
                "t0_ms": m.t0_ms,
            }
        finally:
            loader.close()
    except Exception:
        pass

    with segyio.open(str(path), "r", ignore_geometry=True) as f:
        text = ""
        try:
            text = f.text[0].decode("ascii", errors="replace")
        except Exception:
            text = ""
        n_samples = len(f.samples)
        dt_us = int(f.bin[segyio.BinField.Interval] or 2000)
        dt_ms = dt_us / 1000.0
        t0_ms = float(f.samples[0]) if n_samples else 0.0

        classic = _parse_text_header_classic(text)
        if classic is not None and _corners_match_loader_counts(
            classic, loader_meta
        ):
            # The loader-axes swap is only valid when the loader assigned its
            # "inline" axis from a fast/slow header pair (detected/pseudo).
            # With real INLINE_3D/CROSSLINE_3D geometry the loader inline IS
            # the text inline — swapping would transpose the survey (square
            # grids) or fail the span validation (non-square).
            source = loader_meta.get("loader_geometry_source", "unknown")
            if source != "standard_189_193":
                p1, p2, p3 = _classic_corners_to_loader_axes(*classic)
            else:
                p1, p2, p3 = classic
            meta = {
                "n_samples": loader_meta.get("n_samples", n_samples),
                "dt_ms": loader_meta.get("dt_ms", dt_ms),
                "t0_ms": loader_meta.get("t0_ms", t0_ms),
                "source": "text_header_loader_axes",
                **{k: v for k, v in loader_meta.items() if k.startswith("loader_")},
            }
            return p1, p2, p3, meta

        # Loader counts disagree with the text header (stale header values):
        # scan actual trace headers — the data itself is authoritative over a
        # text header that claims different line ranges.
        return _corners_from_trace_scan(f, n_samples, dt_ms, t0_ms, loader_meta)


def _corners_match_loader_counts(classic, loader_meta: dict) -> bool:
    """Text-header corner spans must agree with the loader's line counts.

    Without loader counts there is nothing to cross-check (legacy path).
    """
    n_il = loader_meta.get("loader_n_inlines")
    n_xl = loader_meta.get("loader_n_crosslines")
    if n_il is None or n_xl is None:
        return True
    il_step = abs(int(loader_meta.get("loader_iline_step") or 1)) or 1
    xl_step = abs(int(loader_meta.get("loader_xline_step") or 1)) or 1
    il0, xl0 = float(classic[0][0]), float(classic[0][1])
    il1, xl1 = float(classic[2][0]), float(classic[2][1])
    span_il = abs(il1 - il0)
    span_xl = abs(xl1 - xl0)
    source = loader_meta.get("loader_geometry_source", "unknown")
    if source == "standard_189_193":
        # Loader inline IS the text inline: compare in text-axis space.
        checks = (
            (span_il, int(n_il), il_step),
            (span_xl, int(n_xl), xl_step),
        )
    else:
        # Detected geometry assigned the loader inline to the FAST header —
        # for classic IL=+Y/XL=+X files that is the text crossline. Compare
        # each text axis against the swapped loader axis counts.
        checks = (
            (span_xl, int(n_il), il_step),
            (span_il, int(n_xl), xl_step),
        )
    return all(
        abs(span - (count - 1) * step) <= 1e-6 for span, count, step in checks
    )


def _classic_corners_to_loader_axes(
    p1: tuple, p2: tuple, p3: tuple
) -> tuple[tuple, tuple, tuple]:
    """Map classic text corners (IL=+Y, XL=+X) to loader IL/XL assignment.

    On this SEGY class, SeismicLoader treats text **xline** as volume axis 0
    (inline) and text **inline** as volume axis 1 (crossline). Loader IL runs
    along map +X; loader XL along map +Y.

    Classic::
        p1 (il0, xl0, x0, y0), p2 (il0, xl1, x1, y0), p3 (il1, xl1, x1, y1)

    Loader::
        p1 (xl0, il0, x0, y0), p2 (xl0, il1, x0, y1), p3 (xl1, il1, x1, y1)
    """
    il0, xl0, x0, y0 = (float(v) for v in p1)
    _il0b, xl1, x1, _y0b = (float(v) for v in p2)
    il1, _xl1b, x2, y1 = (float(v) for v in p3)
    lp1 = (xl0, il0, x0, y0)
    lp2 = (xl0, il1, x0, y1)  # same loader IL, +loader XL → +Y
    lp3 = (xl1, il1, x2, y1)  # +loader IL → +X
    return lp1, lp2, lp3


def align_horizon_corners_to_loader_axes(p1, p2, p3, *, swap=None) -> tuple:
    """Remap horizon P1–P3 (classic text IL/XL) to loader axis assignment.

    *swap* follows the SEGY loader geometry: ``True`` (or None, legacy
    default) for the detected fast/slow header fallback, ``False`` when the
    loader read real INLINE_3D/CROSSLINE_3D geometry (text IL already IS the
    loader inline — swapping would transpose the horizon).
    """
    if swap is None or swap:
        return _classic_corners_to_loader_axes(p1, p2, p3)
    return p1, p2, p3


def _parse_text_header_classic(text: str) -> tuple | None:
    """P1–P3 with text Inline along +Y, Crossline along +X (classic az=0)."""
    if not text:
        return None
    m_il = re.search(r"First\s+inline\s*:\s*(\d+)\s+Last\s+inline\s*:\s*(\d+)", text, re.I)
    m_xl = re.search(r"First\s+xline\s*:\s*(\d+)\s+Last\s+xline\s*:\s*(\d+)", text, re.I)
    m_x = re.search(r"xmin\s*:\s*([-\d.]+)\s+xmax\s*:\s*([-\d.]+)", text, re.I)
    m_y = re.search(r"ymin\s*:\s*([-\d.]+)\s+ymax\s*:\s*([-\d.]+)", text, re.I)
    if not (m_il and m_xl and m_x):
        return None
    il0, il1 = float(m_il.group(1)), float(m_il.group(2))
    xl0, xl1 = float(m_xl.group(1)), float(m_xl.group(2))
    x0, x1 = float(m_x.group(1)), float(m_x.group(2))
    if m_y:
        y0, y1 = float(m_y.group(1)), float(m_y.group(2))
        # Text header often duplicates xmax into ymax; recover from IL spacing
        if abs(y1 - x1) < 1.0 and il1 > il0:
            y1 = y0 + (il1 - il0) * 40.014634
    else:
        y0, y1 = 0.0, (il1 - il0) * 40.014634
    p1 = (il0, xl0, x0, y0)
    p2 = (il0, xl1, x1, y0)
    p3 = (il1, xl1, x1, y1)
    return p1, p2, p3


def _corners_from_trace_scan(f, n_samples: int, dt_ms: float, t0_ms: float, loader_meta: dict):
    """Fallback when text header is missing: scan line headers + SourceX/Y.

    The header pair scanned matches how the loader established geometry:
    real INLINE_3D/CROSSLINE_3D for standard files, FieldRecord/CDP for the
    detected fast/slow fallback. Block scans follow the file's trace sorting.
    """
    import segyio

    TF = segyio.TraceField
    n = f.tracecount
    if n <= 0:
        raise ValueError("SEGY has no traces")
    fields = loader_meta.get("loader_geometry_fields")
    if fields and len(fields) == 2:
        # Read the SAME header pair the loader established geometry with;
        # guessing (FieldRecord/CDP) inverts the axes on detected files.
        try:
            il_field, xl_field = TF(int(fields[0])), TF(int(fields[1]))
        except ValueError:
            il_field, xl_field = TF.FieldRecord, TF.CDP
    else:
        source = loader_meta.get("loader_geometry_source", "unknown")
        if source == "standard_189_193":
            il_field, xl_field = TF.INLINE_3D, TF.CROSSLINE_3D
        else:
            il_field, xl_field = TF.FieldRecord, TF.CDP
    h0 = f.header[0]
    h1 = f.header[n - 1]
    # Prefer loader starts when available (same axis order the loader uses)
    if loader_meta.get("loader_iline_start") is not None:
        il0 = float(loader_meta["loader_iline_start"])
        xl0 = float(loader_meta["loader_xline_start"])
    else:
        il0 = float(h0[il_field] or 0)
        xl0 = float(h0[xl_field] or 0)
    x0 = float(h0[TF.SourceX] or 0)
    y0 = float(h0[TF.SourceY] or 0)
    il1 = float(h1[il_field] or il0)
    xl1 = float(h1[xl_field] or xl0)
    x1 = float(h1[TF.SourceX] or x0)
    y1 = float(h1[TF.SourceY] or y0)

    first_il = int(il0)
    last_xl = int(xl1)
    x_at_p2, y_at_p2 = x0, y0
    x_at_p3, y_at_p3 = x1, y1
    # With loader counts known, scan the exact trace blocks of the first and
    # last line. Blocks follow the file's sorting: inline-major keeps one
    # inline contiguous (n_xl traces); crossline-major keeps one crossline
    # contiguous (n_il traces) and the first inline is a strided walk.
    n_xl = loader_meta.get("loader_n_crosslines")
    n_il = loader_meta.get("loader_n_inlines")
    # f.sorting is None on the ignore_geometry handle used here; infer the
    # layout from header runs instead. One loader-inline contiguous means
    # inline-major; the run belongs to whichever field is constant.
    def _run_length(field) -> int:
        first = None
        run = 0
        for i in range(min(n, max(int(n_xl or 1), int(n_il or 1)) + 1)):
            value = int(f.header[i][field] or 0)
            if first is None:
                first = value
            if value == first:
                run += 1
            else:
                break
        return run

    try:
        crossline_sorted = False
        if n_xl and n_il:
            il_run = _run_length(il_field)
            xl_run = _run_length(xl_field)
            if il_run == int(n_xl) and int(n_xl) > 1:
                crossline_sorted = False
            elif xl_run == int(n_il) and int(n_il) > 1:
                crossline_sorted = True
    except Exception:
        crossline_sorted = False

    def _header_at(i):
        h = f.header[i]
        return (
            int(h[il_field] or 0),
            int(h[xl_field] or 0),
            float(h[TF.SourceX] or 0),
            float(h[TF.SourceY] or 0),
        )

    if n_xl and not crossline_sorted:
        first_block = range(0, min(n, int(n_xl)))
        last_block = range(max(0, n - int(n_xl)), n)
    elif n_il and crossline_sorted:
        first_block = range(0, n, int(n_il))
        last_block = range(n_il - 1, n, int(n_il))
    else:
        first_block = None
        last_block = None

    if first_block is not None:
        for i in first_block:
            il, xl, sx, sy = _header_at(i)
            if il == first_il and xl >= last_xl:
                last_xl = xl
                x_at_p2, y_at_p2 = sx, sy
    else:
        for i in range(0, min(n, 5000), max(1, n // 2000)):
            il, xl, sx, sy = _header_at(i)
            if il == first_il and xl >= last_xl:
                last_xl = xl
                x_at_p2, y_at_p2 = sx, sy
    last_il = int(il1)
    if last_block is not None:
        for i in reversed(list(last_block)):
            il, xl, sx, sy = _header_at(i)
            if xl == last_xl and il >= last_il:
                last_il = il
                x_at_p3, y_at_p3 = sx, sy
                break
    else:
        for i in range(max(0, n - 5000), n, max(1, n // 2000)):
            il, xl, sx, sy = _header_at(i)
            if xl == last_xl and il >= last_il:
                last_il = il
                x_at_p3, y_at_p3 = sx, sy
    p1 = (float(first_il), float(xl0), x0, y0)
    p2 = (float(first_il), float(last_xl), x_at_p2, y_at_p2)
    p3 = (float(last_il), float(last_xl), x_at_p3, y_at_p3)
    meta = {
        "n_samples": loader_meta.get("n_samples", n_samples),
        "dt_ms": loader_meta.get("dt_ms", dt_ms),
        "t0_ms": loader_meta.get("t0_ms", t0_ms),
        "source": "trace_scan",
        **{k: v for k, v in loader_meta.items() if k.startswith("loader_")},
    }
    return p1, p2, p3, meta


def horizon_corners_from_dat(path: Path | str) -> tuple | None:
    """Parse P1/P2/P3 from SMI horizon header (inline, crossline, x, y)."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    pts = {}
    for label in ("P1", "P2", "P3"):
        m = re.search(
            rf"#\s*{label}:\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)",
            text,
        )
        if m:
            pts[label] = (
                float(m.group(1)),
                float(m.group(2)),
                float(m.group(3)),
                float(m.group(4)),
            )
    if len(pts) == 3:
        return pts["P1"], pts["P2"], pts["P3"]
    return None
