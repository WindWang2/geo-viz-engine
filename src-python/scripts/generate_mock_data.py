"""
Generate mock well log data using app.services.data_generator.

Produces:
  data/generated/well-001.json  — shallow well (0–1500 m)
  data/generated/well-002.json  — deep well   (1500–3000 m)
  data/generated/well-003.json  — full well   (0–3000 m)
  data/generated/index.json     — metadata summary for all three wells

Run from the src-python directory:
  python scripts/generate_mock_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from repo root or from src-python/
_script_dir = Path(__file__).resolve().parent
_src_python = _script_dir.parent
if str(_src_python) not in sys.path:
    sys.path.insert(0, str(_src_python))

from app.models.well_log import WellMetadata
from app.services.data_generator import generate_well_log

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "generated"

WELLS = [
    dict(
        filename="well-001.json",
        well_id="WELL-001",
        well_name="Well 001 (Shallow)",
        depth_start=0.0,
        depth_end=1500.0,
        seed=101,
    ),
    dict(
        filename="well-002.json",
        well_id="WELL-002",
        well_name="Well 002 (Deep)",
        depth_start=1500.0,
        depth_end=3000.0,
        seed=202,
    ),
    dict(
        filename="well-003.json",
        well_id="WELL-003",
        well_name="Well 003 (Full)",
        depth_start=0.0,
        depth_end=3000.0,
        seed=303,
    ),
]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    index_entries: list[dict] = []

    for spec in WELLS:
        filename = spec["filename"]
        well = generate_well_log(
            well_id=spec["well_id"],
            well_name=spec["well_name"],
            depth_start=spec["depth_start"],
            depth_end=spec["depth_end"],
            seed=spec["seed"],
        )

        out_path = OUTPUT_DIR / filename
        out_path.write_text(well.model_dump_json(indent=2), encoding="utf-8")
        print(f"  wrote {out_path.relative_to(OUTPUT_DIR.parents[1])}  "
              f"({out_path.stat().st_size // 1024} KB, "
              f"{len(well.curves[0].data):,} depth samples)")

        meta = WellMetadata(
            well_id=well.well_id,
            well_name=well.well_name,
            depth_start=well.depth_start,
            depth_end=well.depth_end,
            curve_names=[c.name for c in well.curves],
        )
        index_entries.append({
            **meta.model_dump(),
            "file": filename,
        })

    index_path = OUTPUT_DIR / "index.json"
    index_path.write_text(
        json.dumps({"wells": index_entries, "count": len(index_entries)}, indent=2),
        encoding="utf-8",
    )
    print(f"  wrote {index_path.relative_to(OUTPUT_DIR.parents[1])}")
    print(f"\nDone — {len(WELLS)} wells + index written to {OUTPUT_DIR.relative_to(OUTPUT_DIR.parents[1])}/")


if __name__ == "__main__":
    main()
