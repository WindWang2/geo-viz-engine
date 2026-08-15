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
        if classic is not None:
            p1, p2, p3 = _classic_corners_to_loader_axes(*classic)
            meta = {
                "n_samples": loader_meta.get("n_samples", n_samples),
                "dt_ms": loader_meta.get("dt_ms", dt_ms),
                "t0_ms": loader_meta.get("t0_ms", t0_ms),
                "source": "text_header_loader_axes",
                **{k: v for k, v in loader_meta.items() if k.startswith("loader_")},
            }
            return p1, p2, p3, meta

        # Fallback: FieldRecord≈loader-related, CDP≈loader-related (same as loader)
        return _corners_from_trace_scan(f, n_samples, dt_ms, t0_ms, loader_meta)


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


def align_horizon_corners_to_loader_axes(p1, p2, p3) -> tuple:
    """Remap horizon P1–P3 (classic text IL/XL) to loader axis assignment."""
    return _classic_corners_to_loader_axes(p1, p2, p3)


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
    """Fallback when text header is missing: scan FieldRecord/CDP + SourceX/Y."""
    import segyio

    TF = segyio.TraceField
    n = f.tracecount
    if n <= 0:
        raise ValueError("SEGY has no traces")
    h0 = f.header[0]
    h1 = f.header[n - 1]
    # Prefer loader starts when available (already FieldRecord/CDP order)
    if loader_meta.get("loader_iline_start") is not None:
        il0 = float(loader_meta["loader_iline_start"])
        xl0 = float(loader_meta["loader_xline_start"])
    else:
        il0 = float(h0[TF.FieldRecord] or 0)
        xl0 = float(h0[TF.CDP] or 0)
    x0 = float(h0[TF.SourceX] or 0)
    y0 = float(h0[TF.SourceY] or 0)
    il1 = float(h1[TF.FieldRecord] or il0)
    xl1 = float(h1[TF.CDP] or xl0)
    x1 = float(h1[TF.SourceX] or x0)
    y1 = float(h1[TF.SourceY] or y0)

    first_il = int(il0)
    last_xl = int(xl1)
    x_at_p2, y_at_p2 = x0, y0
    x_at_p3, y_at_p3 = x1, y1
    # When loader counts are known, traces are iline-major sorted: the first
    # inline occupies traces [0, n_xl) and the last inline the final block.
    # Scanning those blocks exactly beats the old strided sample, which could
    # step over the last crossline and collapse P2 onto P1 (zero-length XL
    # edge → zero bin spacing).
    n_xl = loader_meta.get("loader_n_crosslines")
    first_block = range(0, min(n, int(n_xl))) if n_xl else None
    last_block = (
        range(max(0, n - int(n_xl)), n) if n_xl else None
    )
    if first_block is not None:
        for i in first_block:
            h = f.header[i]
            xl = int(h[TF.CDP] or 0)
            sx, sy = float(h[TF.SourceX] or 0), float(h[TF.SourceY] or 0)
            if xl >= last_xl:
                last_xl = xl
                x_at_p2, y_at_p2 = sx, sy
        # The last crossline of the first inline is p2; p3 shares it.
        for i in first_block:
            h = f.header[i]
            if int(h[TF.CDP] or 0) == last_xl:
                x_at_p2, y_at_p2 = (
                    float(h[TF.SourceX] or 0),
                    float(h[TF.SourceY] or 0),
                )
                break
    else:
        for i in range(0, min(n, 5000), max(1, n // 2000)):
            h = f.header[i]
            il = int(h[TF.FieldRecord] or 0)
            xl = int(h[TF.CDP] or 0)
            sx, sy = float(h[TF.SourceX] or 0), float(h[TF.SourceY] or 0)
            if il == first_il and xl >= last_xl:
                last_xl = xl
                x_at_p2, y_at_p2 = sx, sy
    last_il = int(il1)
    if last_block is not None:
        for i in reversed(list(last_block)):
            h = f.header[i]
            il = int(h[TF.FieldRecord] or 0)
            if il >= last_il:
                last_il = il
                x_at_p3, y_at_p3 = (
                    float(h[TF.SourceX] or 0),
                    float(h[TF.SourceY] or 0),
                )
                break
    else:
        for i in range(max(0, n - 5000), n, max(1, n // 2000)):
            h = f.header[i]
            il = int(h[TF.FieldRecord] or 0)
            xl = int(h[TF.CDP] or 0)
            sx, sy = float(h[TF.SourceX] or 0), float(h[TF.SourceY] or 0)
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
