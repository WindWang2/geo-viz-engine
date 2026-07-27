from __future__ import annotations

from typing import Any

import numpy as np

from .contracts import PreparedPreview, PreviewKind

PAYLOAD_SCHEMA_VERSION = 3
CACHEABLE_KINDS = frozenset(
    {PreviewKind.XY_SCATTER, PreviewKind.SURFACE, PreviewKind.FORMATION_TOPS}
)


def _formation_top_type():
    """Load the optional cross-well model only for formation-top payloads."""
    from geoviz_cross_well import FormationTop

    return FormationTop


def _dat_payload_types():
    """Load plotting-backed payload classes only when DAT caching is used."""
    from .previews.dat import SurfacePreviewPayload, XYPreviewPayload

    return SurfacePreviewPayload, XYPreviewPayload


def encode_prepared_preview(
    preview: PreparedPreview,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    if preview.kind not in CACHEABLE_KINDS:
        raise ValueError(f"unsupported kind for disk cache: {preview.kind}")
    meta: dict[str, Any] = {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "kind": str(preview.kind),
        "title": preview.title,
        "summary_rows": [list(row) for row in preview.summary_rows],
        "warning": preview.warning,
        "estimated_bytes": preview.estimated_bytes,
    }
    arrays: dict[str, np.ndarray] = {}
    if preview.kind is PreviewKind.XY_SCATTER:
        _, XYPreviewPayload = _dat_payload_types()
        payload = preview.payload
        if not isinstance(payload, XYPreviewPayload):
            raise ValueError("XY_SCATTER payload type mismatch")
        meta["names"] = list(payload.names)
        meta["resource_id"] = payload.resource_id
        meta["record_ids"] = list(payload.record_ids)
        meta["source_rows"] = list(payload.source_rows)
        meta["source_version"] = payload.source_version
        meta["source_crs"] = payload.source_crs
        meta["coordinate_units"] = payload.coordinate_units
        meta["diagnostics"] = {
            "total_records": payload.diagnostics.total_records,
            "valid_records": payload.diagnostics.valid_records,
            "issues": [
                {
                    "source_row": issue.source_row,
                    "reason": issue.reason,
                }
                for issue in payload.diagnostics.issues
            ],
            "omitted_issue_count": (
                payload.diagnostics.omitted_issue_count
            ),
        }
        arrays["x"] = np.asarray(payload.x)
        arrays["y"] = np.asarray(payload.y)
    elif preview.kind is PreviewKind.SURFACE:
        SurfacePreviewPayload, _ = _dat_payload_types()
        payload = preview.payload
        if not isinstance(payload, SurfacePreviewPayload):
            raise ValueError("SURFACE payload type mismatch")
        meta["levels"] = list(payload.levels)
        arrays["grid_x"] = np.asarray(payload.grid_x)
        arrays["grid_y"] = np.asarray(payload.grid_y)
        arrays["grid_z"] = np.asarray(payload.grid_z)
    else:  # FORMATION_TOPS
        FormationTop = _formation_top_type()
        tops = preview.payload
        if not (
            isinstance(tops, tuple) and all(isinstance(t, FormationTop) for t in tops)
        ):
            raise ValueError("FORMATION_TOPS payload type mismatch")
        meta["tops"] = [
            {
                "well_name": t.well_name,
                "formation_name": t.formation_name,
                "depth_m": float(t.depth_m),
                "color": t.color,
            }
            for t in tops
        ]
    return meta, arrays


def decode_prepared_preview(
    meta: dict[str, Any], arrays: dict[str, np.ndarray]
) -> PreparedPreview:
    if int(meta.get("schema_version", -1)) != PAYLOAD_SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    kind = PreviewKind(meta["kind"])
    if kind not in CACHEABLE_KINDS:
        raise ValueError(f"unsupported kind: {kind}")
    summary = tuple((str(a), str(b)) for a, b in meta.get("summary_rows", ()))
    if kind is PreviewKind.XY_SCATTER:
        _, XYPreviewPayload = _dat_payload_types()
        from .previews.dat import PreviewRowIssue, XYPreviewDiagnostics

        diagnostics = meta.get("diagnostics") or {}
        payload = XYPreviewPayload(
            names=tuple(meta["names"]),
            x=np.asarray(arrays["x"]),
            y=np.asarray(arrays["y"]),
            resource_id=str(meta.get("resource_id") or ""),
            record_ids=tuple(int(value) for value in meta.get("record_ids", ())),
            source_rows=tuple(
                int(value) for value in meta.get("source_rows", ())
            ),
            source_version=str(meta.get("source_version") or ""),
            source_crs=str(meta.get("source_crs") or ""),
            coordinate_units=str(meta.get("coordinate_units") or ""),
            diagnostics=XYPreviewDiagnostics(
                total_records=int(
                    diagnostics.get("total_records") or 0
                ),
                valid_records=int(
                    diagnostics.get("valid_records") or 0
                ),
                issues=tuple(
                    PreviewRowIssue(
                        source_row=int(row["source_row"]),
                        reason=str(row["reason"]),
                    )
                    for row in diagnostics.get("issues", ())
                ),
                omitted_issue_count=int(
                    diagnostics.get("omitted_issue_count") or 0
                ),
            ),
        )
    elif kind is PreviewKind.SURFACE:
        SurfacePreviewPayload, _ = _dat_payload_types()
        payload = SurfacePreviewPayload(
            grid_x=np.asarray(arrays["grid_x"]),
            grid_y=np.asarray(arrays["grid_y"]),
            grid_z=np.asarray(arrays["grid_z"]),
            levels=tuple(float(x) for x in meta.get("levels", ())),
        )
    else:
        FormationTop = _formation_top_type()
        payload = tuple(
            FormationTop(
                row["well_name"],
                row["formation_name"],
                float(row["depth_m"]),
                color=str(row.get("color") or ""),
            )
            for row in meta.get("tops", ())
        )
    return PreparedPreview(
        kind=kind,
        title=str(meta.get("title") or ""),
        payload=payload,
        summary_rows=summary,
        warning=str(meta.get("warning") or ""),
        estimated_bytes=int(meta.get("estimated_bytes") or 0),
    )
