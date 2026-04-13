from fastapi import APIRouter, Body
from app.models.well_log import GenerateDataRequest, GenerateDataResponse, WellMetadata
from app.services.data_generator import generate_wells

router = APIRouter(prefix="/api/data", tags=["data"])


@router.post("/generate", response_model=GenerateDataResponse)
async def generate_data(
    body: GenerateDataRequest = Body(default_factory=GenerateDataRequest),
) -> GenerateDataResponse:
    """
    Generate synthetic well log data and cache in memory.
    Returns metadata only (curve data available via /api/well-log endpoints).
    """
    wells = generate_wells(count=body.count)
    metadata = [
        WellMetadata(
            well_id=w.well_id,
            well_name=w.well_name,
            depth_start=w.depth_start,
            depth_end=w.depth_end,
            curve_names=[c.name for c in w.curves],
        )
        for w in wells
    ]
    return GenerateDataResponse(
        wells=metadata,
        message=f"Generated {len(wells)} synthetic wells successfully",
        generated_count=len(wells),
    )
