from fastapi import APIRouter, Body, HTTPException
from app.models.well_log import (
    GenerateDataRequest,
    GenerateDataResponse,
    WellLogData,
    WellMetadata,
    WellDetailData,
)
from app.services import data_generator
from app.services.well_data_service import WellDataService

router = APIRouter(prefix="/api/data", tags=["data"])
_well_data_service = WellDataService()


@router.get("/list", response_model=list[WellMetadata])
async def list_wells() -> list[WellMetadata]:
    """
    List metadata for all cached wells (including statically loaded mock data).
    """
    wells = data_generator.get_cached_wells()
    metadata = [
        WellMetadata(
            well_id=w.well_id,
            well_name=w.well_name,
            depth_start=w.depth_start,
            depth_end=w.depth_end,
            curve_names=[c.name for c in w.curves],
            longitude=w.longitude,
            latitude=w.latitude,
        )
        for w in wells
    ]
    return metadata


@router.get("/wells", response_model=list[dict])
async def list_wells_location():
    """
    Returns lightweight list of wells with coordinates, for map markers and table.
    """
    wells = data_generator.get_cached_wells()
    return [
        {
            "well_id": w.well_id,
            "well_name": w.well_name,
            "longitude": w.longitude,
            "latitude": w.latitude,
        }
        for w in wells
    ]


@router.post("/generate", response_model=GenerateDataResponse)
async def generate_data(
    body: GenerateDataRequest = Body(default_factory=GenerateDataRequest),
) -> GenerateDataResponse:
    """
    Generate synthetic well log data and cache in memory.
    Returns metadata only (curve data available via /api/well-log endpoints).
    """
    wells = data_generator.generate_wells(
        count=body.count,
        depth_start=body.depth_start,
        depth_end=body.depth_end,
        depth_step=body.depth_step,
    )
    metadata = [
        WellMetadata(
            well_id=w.well_id,
            well_name=w.well_name,
            depth_start=w.depth_start,
            depth_end=w.depth_end,
            curve_names=[c.name for c in w.curves],
            longitude=w.longitude,
            latitude=w.latitude,
        )
        for w in wells
    ]
    return GenerateDataResponse(
        wells=metadata,
        message=f"Generated {len(wells)} synthetic wells successfully",
        generated_count=len(wells),
    )


@router.get("/well/{well_id}", response_model=WellLogData)
async def get_well_data(well_id: str) -> WellLogData:
    """
    Get full well log data including all curve values for a generated well.
    Data is retrieved from the in-memory cache.
    """
    well = data_generator._wells_cache.get(well_id)
    if well is None:
        raise HTTPException(
            status_code=404,
            detail=f"Well '{well_id}' not found. Generate data first via /api/data/generate.",
        )
    return well

@router.get("/well-detail/{well_name}", response_model=WellDetailData)
async def get_well_detail(well_name: str) -> WellDetailData:
    """
    Get comprehensive well data from Excel (aligned intervals and curves).
    """
    try:
        data = _well_data_service.get_well_details(well_name)
        return WellDetailData(**data)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
