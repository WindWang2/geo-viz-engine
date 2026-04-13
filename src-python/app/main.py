import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth import AuthTokenMiddleware
from app.api.system import router as system_router
from app.api.data import router as data_router

app = FastAPI(
    title="GeoViz Engine Backend",
    version="0.1.0",
    description="Python FastAPI backend for geo-viz-engine",
)

app.add_middleware(AuthTokenMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "tauri://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system_router)
app.include_router(data_router)


if __name__ == "__main__":
    import uvicorn
    token = os.environ.get("GEOVIZ_API_TOKEN", "")
    if not token:
        raise RuntimeError("GEOVIZ_API_TOKEN environment variable must be set")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
