import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth import AuthTokenMiddleware
from app.api.system import router as system_router
from app.api.data import router as data_router
from app.services.data_generator import load_static_mock_data, load_real_well_coordinates

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load static mock data on startup so cache is always populated
    load_static_mock_data()
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    load_real_well_coordinates(data_dir=os.path.join(project_root, 'data'))
    yield

app = FastAPI(
    title="GeoViz Engine Backend",
    version="0.1.0",
    description="Python FastAPI backend for geo-viz-engine",
    lifespan=lifespan,
)

app.add_middleware(AuthTokenMiddleware)

is_dev = os.environ.get("GEOVIZ_DEV", "").lower() in ("1", "true", "yes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if is_dev else ["http://localhost:5173", "tauri://localhost", "https://tauri.localhost"],
    allow_credentials=not is_dev,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system_router)
app.include_router(data_router)


if __name__ == "__main__":
    import uvicorn
    from app.services.data_generator import load_static_mock_data
    # Load pre-generated static mock data on startup
    _loaded_count = load_static_mock_data()
    if _loaded_count > 0:
        print(f"[INFO] Loaded {_loaded_count} pre-generated mock wells from static files")
    token = os.environ.get("GEOVIZ_API_TOKEN", "")
    if not token:
        raise RuntimeError("GEOVIZ_API_TOKEN environment variable must be set")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
