# Phase 1: Project Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建 geo-viz-engine 全平台桌面应用的基础项目骨架，包含 Tauri 壳、React 前端、Python 后端、路由、i18n 和合成数据生成器。

**Architecture:** Tauri 2.x (Rust) 作为桌面壳，WebView 渲染 React 前端，Python FastAPI 作为后端数据处理服务。开发时前端和后端独立运行，发布时 PyInstaller 打包 Python 为 Sidecar。通过 Auth Token 保证本地 API 安全。

**Tech Stack:** Tauri 2.x / React 18 / TypeScript 5 / Vite 5 / Zustand 4 / TailwindCSS 3 / React Router 7 / i18next / FastAPI 0.100+ / Pydantic 2 / uvicorn / lasio / pyarrow / pytest / Vitest

---

## Task 1: Python 目录结构 + 环境初始化

- [ ] **1.1** 创建完整目录结构

  ```bash
  mkdir -p src-python/app/api
  mkdir -p src-python/app/services
  mkdir -p src-python/app/models
  mkdir -p src-python/tests
  mkdir -p data/generated
  mkdir -p scripts
  touch data/generated/.gitkeep
  ```

- [ ] **1.2** 创建 `src-python/requirements.txt`

  ```
  fastapi==0.115.0
  uvicorn[standard]==0.30.6
  pydantic==2.9.2
  numpy==2.1.3
  pyarrow==18.0.0
  lasio==0.30
  httpx==0.27.2
  pytest==8.3.3
  pytest-asyncio==0.24.0
  pytest-cov==6.0.0
  ```

- [ ] **1.3** 创建 `src-python/pyproject.toml`

  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  asyncio_mode = "auto"
  filterwarnings = ["ignore::DeprecationWarning"]

  [tool.coverage.run]
  source = ["app"]
  branch = true

  [tool.coverage.report]
  exclude_lines = [
      "pragma: no cover",
      "if __name__ == .__main__.:",
  ]
  ```

- [ ] **1.4** 创建 Python 虚拟环境并安装依赖

  ```bash
  cd src-python
  python -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

  预期输出末尾：`Successfully installed fastapi-0.115.0 ...`

- [ ] **1.5** 创建所有 `__init__.py` 文件

  ```bash
  touch src-python/app/__init__.py
  touch src-python/app/api/__init__.py
  touch src-python/app/services/__init__.py
  touch src-python/app/models/__init__.py
  touch src-python/tests/__init__.py
  ```

- [ ] **1.6** Commit

  ```bash
  git add src-python/ data/generated/.gitkeep scripts/
  git commit -m "feat: initialize Python backend directory structure and venv"
  ```

---

## Task 2: Pydantic 数据模型 (TDD)

- [ ] **2.1** 写测试：`src-python/tests/test_models.py`

  ```python
  from datetime import datetime
  from app.models.common import HealthResponse, ErrorResponse
  from app.models.well_log import CurveData, WellLogData, WellMetadata, GenerateDataRequest, GenerateDataResponse


  def test_health_response_fields():
      h = HealthResponse(
          status="ok",
          version="0.1.0",
          timestamp=datetime.now(),
          backend="geo-viz-engine-python",
      )
      assert h.status == "ok"
      assert h.version == "0.1.0"
      assert h.backend == "geo-viz-engine-python"


  def test_error_response_fields():
      e = ErrorResponse(detail="Unauthorized", code="AUTH_001")
      assert e.detail == "Unauthorized"
      assert e.code == "AUTH_001"


  def test_error_response_code_optional():
      e = ErrorResponse(detail="Not found")
      assert e.code is None


  def test_curve_data_fields():
      c = CurveData(
          name="GR",
          unit="API",
          data=[80.0, 85.0, 90.0],
          depth=[0.0, 0.125, 0.25],
          min_value=80.0,
          max_value=90.0,
          display_range=(0.0, 150.0),
          color="#00AA00",
          line_style="solid",
      )
      assert c.name == "GR"
      assert c.unit == "API"
      assert len(c.data) == 3
      assert c.display_range == (0.0, 150.0)


  def test_well_log_data_fields():
      curve = CurveData(
          name="GR", unit="API", data=[80.0], depth=[0.0],
          min_value=80.0, max_value=80.0, display_range=(0.0, 150.0),
          color="#00AA00", line_style="solid",
      )
      well = WellLogData(
          well_id="WELL-001",
          well_name="Well 1",
          depth_start=0.0,
          depth_end=3000.0,
          depth_step=0.125,
          curves=[curve],
      )
      assert well.well_id == "WELL-001"
      assert well.location is None
      assert len(well.curves) == 1


  def test_well_log_data_with_location():
      well = WellLogData(
          well_id="WELL-002", well_name="Well 2",
          depth_start=0.0, depth_end=3000.0, depth_step=0.125,
          location=(102.5, 38.3), curves=[],
      )
      assert well.location == (102.5, 38.3)


  def test_generate_data_request_defaults():
      req = GenerateDataRequest()
      assert req.count == 10
      assert req.depth_start == 0.0
      assert req.depth_end == 3000.0
      assert req.depth_step == 0.125


  def test_generate_data_request_validation_count_zero():
      import pytest
      from pydantic import ValidationError
      with pytest.raises(ValidationError):
          GenerateDataRequest(count=0)


  def test_generate_data_request_validation_count_too_large():
      import pytest
      from pydantic import ValidationError
      with pytest.raises(ValidationError):
          GenerateDataRequest(count=101)
  ```

- [ ] **2.2** 运行测试 — 预期全部失败（模块不存在）

  ```bash
  cd src-python && source venv/bin/activate && python -m pytest tests/test_models.py -v 2>&1 | head -20
  ```

  预期：`ModuleNotFoundError: No module named 'app.models.common'`

- [ ] **2.3** 实现 `src-python/app/models/common.py`

  ```python
  from datetime import datetime
  from typing import Optional
  from pydantic import BaseModel


  class HealthResponse(BaseModel):
      status: str
      version: str
      timestamp: datetime
      backend: str


  class ErrorResponse(BaseModel):
      detail: str
      code: Optional[str] = None
  ```

- [ ] **2.4** 实现 `src-python/app/models/well_log.py`

  ```python
  from typing import List, Optional, Tuple
  from pydantic import BaseModel, Field


  class CurveData(BaseModel):
      name: str
      unit: str
      data: List[float]
      depth: List[float]
      min_value: float
      max_value: float
      display_range: Tuple[float, float]
      color: str
      line_style: str  # "solid" | "dashed" | "dotted"


  class WellLogData(BaseModel):
      well_id: str
      well_name: str
      depth_start: float
      depth_end: float
      depth_step: float
      location: Optional[Tuple[float, float]] = None
      curves: List[CurveData]


  class WellMetadata(BaseModel):
      well_id: str
      well_name: str
      depth_start: float
      depth_end: float
      curve_names: List[str]


  class GenerateDataRequest(BaseModel):
      count: int = Field(default=10, ge=1, le=100)
      depth_start: float = Field(default=0.0, ge=0.0)
      depth_end: float = Field(default=3000.0, gt=0.0)
      depth_step: float = Field(default=0.125, gt=0.0)


  class GenerateDataResponse(BaseModel):
      wells: List[WellMetadata]
      message: str
      generated_count: int
  ```

- [ ] **2.5** 运行测试 — 预期全部通过

  ```bash
  cd src-python && source venv/bin/activate && python -m pytest tests/test_models.py -v
  ```

  预期：`11 passed`

- [ ] **2.6** Commit

  ```bash
  git add src-python/app/models/ src-python/tests/test_models.py
  git commit -m "feat: add Pydantic data models for well log and system responses"
  ```

---

## Task 3: Auth Token 中间件 (TDD)

- [ ] **3.1** 创建 `src-python/tests/conftest.py`

  此文件必须在所有测试导入 `app` 之前设置环境变量：

  ```python
  import os

  # Must be set before any app module is imported
  TEST_TOKEN = "test-token-for-pytest-32chars-xxx"
  os.environ.setdefault("GEOVIZ_API_TOKEN", TEST_TOKEN)


  import pytest


  @pytest.fixture(scope="session")
  def test_token() -> str:
      return TEST_TOKEN


  @pytest.fixture(scope="session")
  def auth_headers() -> dict:
      return {"X-API-Token": TEST_TOKEN}
  ```

- [ ] **3.2** 写测试：`src-python/tests/test_auth.py`

  ```python
  import os
  import pytest
  from httpx import AsyncClient, ASGITransport
  from fastapi import FastAPI
  from fastapi.responses import JSONResponse
  from app.auth import AuthTokenMiddleware


  def make_test_app(token: str) -> FastAPI:
      """Create a minimal FastAPI app with auth middleware for testing."""
      app = FastAPI()
      app.add_middleware(AuthTokenMiddleware)

      @app.get("/ping")
      async def ping():
          return JSONResponse({"pong": True})

      return app


  async def test_valid_token_passes(test_token):
      app = make_test_app(test_token)
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.get("/ping", headers={"X-API-Token": test_token})
      assert response.status_code == 200
      assert response.json() == {"pong": True}


  async def test_missing_token_returns_401(test_token):
      app = make_test_app(test_token)
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.get("/ping")
      assert response.status_code == 401
      assert "detail" in response.json()


  async def test_wrong_token_returns_401(test_token):
      app = make_test_app(test_token)
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.get("/ping", headers={"X-API-Token": "not-the-right-token"})
      assert response.status_code == 401


  async def test_empty_token_returns_401(test_token):
      app = make_test_app(test_token)
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.get("/ping", headers={"X-API-Token": ""})
      assert response.status_code == 401
  ```

- [ ] **3.3** 运行测试 — 预期失败

  ```bash
  cd src-python && source venv/bin/activate && python -m pytest tests/test_auth.py -v 2>&1 | head -10
  ```

  预期：`ModuleNotFoundError: No module named 'app.auth'`

- [ ] **3.4** 实现 `src-python/app/auth.py`

  ```python
  import os
  from starlette.middleware.base import BaseHTTPMiddleware
  from starlette.requests import Request
  from starlette.responses import Response, JSONResponse


  class AuthTokenMiddleware(BaseHTTPMiddleware):
      """Validate X-API-Token header against GEOVIZ_API_TOKEN environment variable."""

      async def dispatch(self, request: Request, call_next) -> Response:
          expected_token = os.environ.get("GEOVIZ_API_TOKEN", "")
          if not expected_token:
              # No token configured — deny all to prevent accidental open access
              return JSONResponse(
                  status_code=401,
                  content={"detail": "API token not configured on server"},
              )

          provided_token = request.headers.get("X-API-Token", "")
          if not provided_token or provided_token != expected_token:
              return JSONResponse(
                  status_code=401,
                  content={"detail": "Invalid or missing API token"},
              )

          return await call_next(request)
  ```

- [ ] **3.5** 运行测试 — 预期全部通过

  ```bash
  cd src-python && source venv/bin/activate && python -m pytest tests/test_auth.py -v
  ```

  预期：`4 passed`

- [ ] **3.6** Commit

  ```bash
  git add src-python/app/auth.py src-python/tests/test_auth.py src-python/tests/conftest.py
  git commit -m "feat: add auth token middleware with env-var-based token validation"
  ```

---

## Task 4: System Status API (TDD)

- [ ] **4.1** 写测试：`src-python/tests/test_api_system.py`

  ```python
  from httpx import AsyncClient, ASGITransport


  async def test_system_status_ok(auth_headers):
      from app.main import app
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.get("/api/system/status", headers=auth_headers)
      assert response.status_code == 200
      data = response.json()
      assert data["status"] == "ok"
      assert data["version"] == "0.1.0"
      assert data["backend"] == "geo-viz-engine-python"
      assert "timestamp" in data


  async def test_system_status_missing_token():
      from app.main import app
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.get("/api/system/status")
      assert response.status_code == 401


  async def test_system_status_invalid_token():
      from app.main import app
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.get(
              "/api/system/status",
              headers={"X-API-Token": "completely-wrong-token"},
          )
      assert response.status_code == 401
      assert response.json()["detail"] == "Invalid or missing API token"
  ```

- [ ] **4.2** 运行测试 — 预期失败

  ```bash
  cd src-python && source venv/bin/activate && python -m pytest tests/test_api_system.py -v 2>&1 | head -10
  ```

  预期：`ModuleNotFoundError: No module named 'app.main'`

- [ ] **4.3** 实现 `src-python/app/api/system.py`

  ```python
  from datetime import datetime, timezone
  from fastapi import APIRouter
  from app.models.common import HealthResponse

  router = APIRouter(prefix="/api/system", tags=["system"])

  APP_VERSION = "0.1.0"


  @router.get("/status", response_model=HealthResponse)
  async def get_status() -> HealthResponse:
      return HealthResponse(
          status="ok",
          version=APP_VERSION,
          timestamp=datetime.now(timezone.utc),
          backend="geo-viz-engine-python",
      )
  ```

- [ ] **4.4** 实现最小 `src-python/app/main.py`（仅注册 system router，data router 在 Task 6 添加）

  ```python
  import os
  from fastapi import FastAPI
  from fastapi.middleware.cors import CORSMiddleware
  from app.auth import AuthTokenMiddleware
  from app.api.system import router as system_router

  app = FastAPI(
      title="GeoViz Engine Backend",
      version="0.1.0",
      description="Python FastAPI backend for geo-viz-engine",
  )

  # Auth middleware — validates X-API-Token on every request
  app.add_middleware(AuthTokenMiddleware)

  # CORS — allow Vite dev server and Tauri WebView
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["http://localhost:5173", "tauri://localhost"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )

  app.include_router(system_router)


  if __name__ == "__main__":
      import uvicorn
      token = os.environ.get("GEOVIZ_API_TOKEN", "")
      if not token:
          raise RuntimeError("GEOVIZ_API_TOKEN environment variable must be set")
      uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
  ```

- [ ] **4.5** 运行测试 — 预期全部通过

  ```bash
  cd src-python && source venv/bin/activate && python -m pytest tests/test_api_system.py -v
  ```

  预期：`3 passed`

- [ ] **4.6** Commit

  ```bash
  git add src-python/app/main.py src-python/app/api/system.py src-python/tests/test_api_system.py
  git commit -m "feat: add system status API endpoint with auth middleware"
  ```

---

## Task 5: Synthetic Data Generator Service (TDD)

- [ ] **5.1** 写测试：`src-python/tests/test_data_generator.py`

  ```python
  import pytest
  from app.services.data_generator import generate_well_log, generate_wells
  from app.models.well_log import WellLogData


  def test_generate_single_well_returns_model():
      well = generate_well_log("WELL-001", "Well 1", seed=42)
      assert isinstance(well, WellLogData)
      assert well.well_id == "WELL-001"
      assert well.well_name == "Well 1"


  def test_generated_well_has_four_curves():
      well = generate_well_log("WELL-001", "Well 1", seed=42)
      assert len(well.curves) == 4


  def test_generated_well_curve_names():
      well = generate_well_log("WELL-001", "Well 1", seed=42)
      names = {c.name for c in well.curves}
      assert names == {"GR", "RT", "DEN", "NPHI"}


  def test_generated_well_sample_count():
      # 3000m / 0.125m step = 24000 samples
      well = generate_well_log(
          "WELL-001", "Well 1",
          depth_start=0.0, depth_end=3000.0, depth_step=0.125, seed=42,
      )
      gr = next(c for c in well.curves if c.name == "GR")
      assert len(gr.data) == 24000
      assert len(gr.depth) == 24000


  def test_gr_values_in_physical_range():
      well = generate_well_log("WELL-001", "Well 1", seed=42)
      gr = next(c for c in well.curves if c.name == "GR")
      assert all(5.0 <= v <= 200.0 for v in gr.data), "GR out of physical range"


  def test_rt_values_positive():
      well = generate_well_log("WELL-001", "Well 1", seed=42)
      rt = next(c for c in well.curves if c.name == "RT")
      assert all(v > 0.0 for v in rt.data), "RT must be positive"


  def test_den_values_in_physical_range():
      well = generate_well_log("WELL-001", "Well 1", seed=42)
      den = next(c for c in well.curves if c.name == "DEN")
      assert all(1.0 <= v <= 3.0 for v in den.data), "DEN out of physical range"


  def test_nphi_values_in_physical_range():
      well = generate_well_log("WELL-001", "Well 1", seed=42)
      nphi = next(c for c in well.curves if c.name == "NPHI")
      assert all(0.0 <= v <= 0.6 for v in nphi.data), "NPHI out of physical range"


  def test_gr_display_range_is_standard():
      well = generate_well_log("WELL-001", "Well 1", seed=42)
      gr = next(c for c in well.curves if c.name == "GR")
      assert gr.display_range == (0.0, 150.0)
      assert gr.unit == "API"


  def test_rt_display_range_is_log_scale_friendly():
      well = generate_well_log("WELL-001", "Well 1", seed=42)
      rt = next(c for c in well.curves if c.name == "RT")
      assert rt.display_range == (0.1, 1000.0)
      assert rt.unit == "ohm.m"


  def test_generate_multiple_wells_unique_ids():
      wells = generate_wells(count=10)
      assert len(wells) == 10
      ids = [w.well_id for w in wells]
      assert len(set(ids)) == 10


  def test_different_seeds_produce_different_data():
      well1 = generate_well_log("W1", "W1", seed=1)
      well2 = generate_well_log("W2", "W2", seed=2)
      gr1 = next(c for c in well1.curves if c.name == "GR").data[:100]
      gr2 = next(c for c in well2.curves if c.name == "GR").data[:100]
      assert gr1 != gr2


  def test_well_depth_metadata_correct():
      well = generate_well_log(
          "W1", "W1",
          depth_start=500.0, depth_end=2000.0, depth_step=0.5, seed=0,
      )
      assert well.depth_start == 500.0
      assert abs(well.depth_end - 2000.0) < 1.0
      assert well.depth_step == 0.5
  ```

- [ ] **5.2** 运行测试 — 预期失败

  ```bash
  cd src-python && source venv/bin/activate && python -m pytest tests/test_data_generator.py -v 2>&1 | head -10
  ```

  预期：`ModuleNotFoundError: No module named 'app.services.data_generator'`

- [ ] **5.3** 实现 `src-python/app/services/data_generator.py`

  ```python
  from __future__ import annotations

  from typing import List

  import numpy as np

  from app.models.well_log import CurveData, WellLogData

  # Module-level in-memory cache: well_id -> WellLogData
  _wells_cache: dict[str, WellLogData] = {}


  def generate_well_log(
      well_id: str,
      well_name: str,
      depth_start: float = 0.0,
      depth_end: float = 3000.0,
      depth_step: float = 0.125,
      seed: int = 42,
  ) -> WellLogData:
      """
      Generate a synthetic well log with GR, RT, DEN, NPHI curves.

      Lithology model (0=shale, 1=sandstone, 2=coal, 3=oil-bearing sand):
        - Shale:   GR~80, RT~2,   DEN~2.55, NPHI~0.25
        - Sand:    GR~30, RT~10,  DEN~2.45, NPHI~0.15
        - Coal:    GR~25, RT~50,  DEN~1.80, NPHI~0.40
        - Oil:     GR~35, RT~200, DEN~2.35, NPHI~0.20
      """
      rng = np.random.default_rng(seed)

      depths = np.arange(depth_start, depth_end, depth_step)
      n = len(depths)

      # Build a layered lithology sequence with ~50-80 layers
      n_boundaries = min(80, n // 100)
      boundary_indices = np.sort(rng.choice(n, size=n_boundaries, replace=False))

      lithology = np.zeros(n, dtype=int)  # default: shale
      prev = 0
      for idx in boundary_indices:
          if idx > prev:
              lithology[prev:idx] = int(rng.integers(0, 4))
          prev = idx
      lithology[prev:] = int(rng.integers(0, 4))

      # --- GR (Natural Gamma Ray, API) ---
      gr_base = np.where(
          lithology == 0, 80.0,
          np.where(lithology == 1, 30.0,
          np.where(lithology == 2, 25.0, 35.0))
      ).astype(float)
      gr = gr_base + rng.normal(0, 6, n)
      gr = np.clip(gr, 5.0, 200.0)

      # --- RT (Resistivity, ohm.m) — log-normal noise ---
      rt_base = np.where(
          lithology == 0, 2.0,
          np.where(lithology == 1, 10.0,
          np.where(lithology == 2, 50.0, 200.0))
      ).astype(float)
      rt = rt_base * np.exp(rng.normal(0, 0.25, n))
      rt = np.clip(rt, 0.1, 1000.0)

      # --- DEN (Bulk Density, g/cc) ---
      den_base = np.where(
          lithology == 0, 2.55,
          np.where(lithology == 1, 2.45,
          np.where(lithology == 2, 1.80, 2.35))
      ).astype(float)
      den = den_base + rng.normal(0, 0.04, n)
      den = np.clip(den, 1.0, 3.0)

      # --- NPHI (Neutron Porosity, v/v) ---
      nphi_base = np.where(
          lithology == 0, 0.25,
          np.where(lithology == 1, 0.15,
          np.where(lithology == 2, 0.40, 0.20))
      ).astype(float)
      nphi = nphi_base + rng.normal(0, 0.015, n)
      nphi = np.clip(nphi, 0.0, 0.6)

      depths_list = depths.tolist()

      curves = [
          CurveData(
              name="GR", unit="API",
              data=gr.tolist(), depth=depths_list,
              min_value=float(gr.min()), max_value=float(gr.max()),
              display_range=(0.0, 150.0), color="#00AA00", line_style="solid",
          ),
          CurveData(
              name="RT", unit="ohm.m",
              data=rt.tolist(), depth=depths_list,
              min_value=float(rt.min()), max_value=float(rt.max()),
              display_range=(0.1, 1000.0), color="#AA0000", line_style="solid",
          ),
          CurveData(
              name="DEN", unit="g/cc",
              data=den.tolist(), depth=depths_list,
              min_value=float(den.min()), max_value=float(den.max()),
              display_range=(1.5, 3.0), color="#0000CC", line_style="solid",
          ),
          CurveData(
              name="NPHI", unit="v/v",
              data=nphi.tolist(), depth=depths_list,
              min_value=float(nphi.min()), max_value=float(nphi.max()),
              display_range=(0.0, 0.6), color="#CC6600", line_style="dashed",
          ),
      ]

      actual_depth_end = float(depths[-1]) + depth_step if n > 0 else depth_end

      return WellLogData(
          well_id=well_id,
          well_name=well_name,
          depth_start=depth_start,
          depth_end=actual_depth_end,
          depth_step=depth_step,
          location=None,
          curves=curves,
      )


  def generate_wells(count: int = 10) -> List[WellLogData]:
      """Generate `count` synthetic wells and cache them in memory."""
      global _wells_cache
      wells: List[WellLogData] = []
      for i in range(count):
          well_id = f"WELL-{i + 1:03d}"
          well_name = f"Well {i + 1}"
          well = generate_well_log(well_id, well_name, seed=i * 42 + 7)
          wells.append(well)
      _wells_cache = {w.well_id: w for w in wells}
      return wells


  def get_cached_wells() -> List[WellLogData]:
      """Return all previously generated wells from the in-memory cache."""
      return list(_wells_cache.values())
  ```

- [ ] **5.4** 运行测试 — 预期全部通过

  ```bash
  cd src-python && source venv/bin/activate && python -m pytest tests/test_data_generator.py -v
  ```

  预期：`13 passed`

- [ ] **5.5** Commit

  ```bash
  git add src-python/app/services/data_generator.py src-python/tests/test_data_generator.py
  git commit -m "feat: add synthetic well log data generator (GR/RT/DEN/NPHI, 10 wells)"
  ```

---

## Task 6: Data Generation API (TDD)

- [ ] **6.1** 写测试：`src-python/tests/test_api_data.py`

  ```python
  from httpx import AsyncClient, ASGITransport


  async def test_generate_data_default_count(auth_headers):
      from app.main import app
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.post("/api/data/generate", headers=auth_headers)
      assert response.status_code == 200
      data = response.json()
      assert data["generated_count"] == 10
      assert len(data["wells"]) == 10
      assert "Generated" in data["message"]


  async def test_generate_data_custom_count(auth_headers):
      from app.main import app
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.post(
              "/api/data/generate",
              json={"count": 3},
              headers=auth_headers,
          )
      assert response.status_code == 200
      assert response.json()["generated_count"] == 3
      assert len(response.json()["wells"]) == 3


  async def test_generate_data_well_metadata_fields(auth_headers):
      from app.main import app
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.post(
              "/api/data/generate",
              json={"count": 1},
              headers=auth_headers,
          )
      assert response.status_code == 200
      well = response.json()["wells"][0]
      assert well["well_id"] == "WELL-001"
      assert well["well_name"] == "Well 1"
      assert well["depth_start"] == 0.0
      assert well["depth_end"] > 0.0
      assert set(well["curve_names"]) == {"GR", "RT", "DEN", "NPHI"}


  async def test_generate_data_no_body_uses_defaults(auth_headers):
      from app.main import app
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.post("/api/data/generate", headers=auth_headers)
      assert response.status_code == 200
      assert response.json()["generated_count"] == 10


  async def test_generate_data_count_zero_rejected(auth_headers):
      from app.main import app
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.post(
              "/api/data/generate",
              json={"count": 0},
              headers=auth_headers,
          )
      assert response.status_code == 422


  async def test_generate_data_count_over_limit_rejected(auth_headers):
      from app.main import app
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.post(
              "/api/data/generate",
              json={"count": 101},
              headers=auth_headers,
          )
      assert response.status_code == 422


  async def test_generate_data_unauthorized():
      from app.main import app
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.post("/api/data/generate")
      assert response.status_code == 401
  ```

- [ ] **6.2** 运行测试 — 预期失败

  ```bash
  cd src-python && source venv/bin/activate && python -m pytest tests/test_api_data.py -v 2>&1 | head -15
  ```

  预期：`404 Not Found` 或 router 未注册的错误

- [ ] **6.3** 实现 `src-python/app/api/data.py`

  ```python
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
  ```

- [ ] **6.4** 将 data router 注册到 `src-python/app/main.py`（在 system router 之后添加一行）

  在 `app.include_router(system_router)` 后追加：

  ```python
  from app.api.data import router as data_router
  # ...
  app.include_router(data_router)
  ```

  完整更新后的 `src-python/app/main.py`：

  ```python
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
  ```

- [ ] **6.5** 运行全量后端测试 — 预期全部通过

  ```bash
  cd src-python && source venv/bin/activate && python -m pytest -v
  ```

  预期：`~31 passed`（models×11 + auth×4 + system×3 + data_generator×13 + data_api×7）

- [ ] **6.6** Commit

  ```bash
  git add src-python/app/api/data.py src-python/app/main.py src-python/tests/test_api_data.py
  git commit -m "feat: add /api/data/generate endpoint wired to synthetic data generator"
  ```

---

## Task 7: Tauri 项目骨架 — Cargo.toml + tauri.conf.json

- [ ] **7.1** 创建 `src-tauri` 目录结构

  ```bash
  mkdir -p src-tauri/src
  mkdir -p src-tauri/capabilities
  mkdir -p src-tauri/binaries
  touch src-tauri/binaries/.gitkeep
  ```

- [ ] **7.2** 创建 `src-tauri/Cargo.toml`

  ```toml
  [package]
  name = "geo-viz-engine"
  version = "0.1.0"
  description = "GeoViz Engine — Geological Data Visualization Desktop App"
  authors = []
  edition = "2021"

  [lib]
  name = "geo_viz_engine_lib"
  crate-type = ["staticlib", "cdylib", "rlib"]

  [build-dependencies]
  tauri-build = { version = "2", features = [] }

  [dependencies]
  tauri = { version = "2", features = [] }
  tauri-plugin-shell = "2"
  serde = { version = "1", features = ["derive"] }
  serde_json = "1"
  rand = "0.8"

  [profile.release]
  codegen-units = 1
  lto = true
  opt-level = "s"
  panic = "abort"
  strip = true
  ```

- [ ] **7.3** 创建 `src-tauri/build.rs`

  ```rust
  fn main() {
      tauri_build::build()
  }
  ```

- [ ] **7.4** 创建 `src-tauri/tauri.conf.json`

  ```json
  {
    "$schema": "https://schema.tauri.app/config/2",
    "productName": "GeoViz Engine",
    "version": "0.1.0",
    "identifier": "com.geoviz.engine",
    "build": {
      "beforeDevCommand": "",
      "devUrl": "http://localhost:5173",
      "beforeBuildCommand": "cd ../src-web && npm run build",
      "frontendDist": "../src-web/dist"
    },
    "bundle": {
      "active": true,
      "targets": "all",
      "externalBin": [
        "binaries/geoviz-backend"
      ],
      "icon": []
    },
    "app": {
      "windows": [
        {
          "title": "GeoViz Engine",
          "width": 1280,
          "height": 800,
          "minWidth": 800,
          "minHeight": 600,
          "resizable": true,
          "fullscreen": false
        }
      ],
      "security": {
        "csp": null
      }
    }
  }
  ```

- [ ] **7.5** 创建 `src-tauri/capabilities/default.json`

  ```json
  {
    "$schema": "../gen/schemas/desktop-schema.json",
    "identifier": "default",
    "description": "Default capabilities for GeoViz Engine",
    "windows": ["main"],
    "permissions": [
      "core:default",
      "shell:allow-execute"
    ]
  }
  ```

- [ ] **7.6** 验证 Cargo.toml 语法（`cargo check` 会下载依赖，约1-3分钟）

  ```bash
  cd src-tauri && cargo fetch
  ```

  预期：无错误输出（警告可忽略）

- [ ] **7.7** Commit

  ```bash
  git add src-tauri/
  git commit -m "feat: add Tauri 2.x project scaffold (Cargo.toml, tauri.conf.json, capabilities)"
  ```

---

## Task 8: Rust Token 生成 + Tauri Commands

- [ ] **8.1** 创建 `src-tauri/src/lib.rs`

  ```rust
  use rand::distributions::Alphanumeric;
  use rand::Rng;
  use tauri::Manager;

  /// Application state shared across Tauri commands.
  pub struct AppState {
      /// 32-character random token generated at startup.
      /// Passed to Python backend via environment variable.
      pub api_token: String,
  }

  /// Generate a cryptographically-adequate 32-character alphanumeric token.
  pub fn generate_api_token() -> String {
      rand::thread_rng()
          .sample_iter(&Alphanumeric)
          .take(32)
          .map(char::from)
          .collect()
  }

  /// Tauri command: return the API token to the frontend.
  /// The frontend uses this token in X-API-Token header for backend calls.
  #[tauri::command]
  pub fn get_api_token(app: tauri::AppHandle) -> String {
      app.state::<AppState>().api_token.clone()
  }

  /// Entry point called from main.rs.
  pub fn run() {
      let token = generate_api_token();

      tauri::Builder::default()
          .plugin(tauri_plugin_shell::init())
          .manage(AppState {
              api_token: token.clone(),
          })
          .invoke_handler(tauri::generate_handler![get_api_token])
          .setup(move |app| {
              let mode = std::env::var("GEOVIZ_MODE").unwrap_or_else(|_| "prod".to_string());
              if mode == "prod" {
                  // In production: spawn embedded Python sidecar
                  // The sidecar binary is named geoviz-backend-<target-triple>
                  // and placed in src-tauri/binaries/ at build time.
                  // For Phase 1 (dev only), this branch is a no-op placeholder.
                  let _ = app; // suppress unused warning
              }
              // In dev mode: Python is started separately by dev.sh
              Ok(())
          })
          .run(tauri::generate_context!())
          .expect("error while running Tauri application");
  }
  ```

- [ ] **8.2** 创建 `src-tauri/src/main.rs`

  ```rust
  // Prevents additional console window on Windows in release builds.
  #![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

  fn main() {
      geo_viz_engine_lib::run()
  }
  ```

- [ ] **8.3** 验证 Rust 代码编译

  ```bash
  cd src-tauri && cargo check 2>&1 | tail -5
  ```

  预期末尾：`Finished \`dev\` profile [unoptimized + debuginfo] target(s)` 或仅有 warning，无 error。

- [ ] **8.4** Commit

  ```bash
  git add src-tauri/src/
  git commit -m "feat: add Rust token generation and get_api_token Tauri command"
  ```

---

## Task 9: 前端项目初始化 — package.json + Vite + TypeScript

- [ ] **9.1** 创建 `src-web` 目录结构

  ```bash
  mkdir -p src-web/src/components/common
  mkdir -p src-web/src/components/layout
  mkdir -p src-web/src/pages
  mkdir -p src-web/src/stores
  mkdir -p src-web/src/hooks
  mkdir -p src-web/src/i18n
  mkdir -p src-web/src/__mocks__/@tauri-apps/api
  ```

- [ ] **9.2** 创建 `src-web/package.json`

  ```json
  {
    "name": "geo-viz-engine-web",
    "version": "0.1.0",
    "private": true,
    "type": "module",
    "scripts": {
      "dev": "vite --port 5173",
      "build": "tsc && vite build",
      "preview": "vite preview",
      "test": "vitest run",
      "test:watch": "vitest",
      "test:coverage": "vitest run --coverage"
    },
    "dependencies": {
      "@tauri-apps/api": "^2",
      "i18next": "^23.7.6",
      "lucide-react": "^0.468.0",
      "react": "^18.3.1",
      "react-dom": "^18.3.1",
      "react-i18next": "^14.0.0",
      "react-router-dom": "^7.0.2",
      "zustand": "^4.5.0"
    },
    "devDependencies": {
      "@testing-library/jest-dom": "^6.6.3",
      "@testing-library/react": "^16.0.1",
      "@testing-library/user-event": "^14.5.2",
      "@types/react": "^18.3.12",
      "@types/react-dom": "^18.3.1",
      "@vitejs/plugin-react": "^4.3.3",
      "autoprefixer": "^10.4.20",
      "jsdom": "^25.0.1",
      "postcss": "^8.4.47",
      "tailwindcss": "^3.4.14",
      "typescript": "^5.6.3",
      "vite": "^5.4.10",
      "vitest": "^2.1.6"
    }
  }
  ```

- [ ] **9.3** 安装依赖

  ```bash
  cd src-web && npm install
  ```

  预期：`added XXX packages` 无错误。

- [ ] **9.4** 创建 `src-web/tsconfig.json`

  ```json
  {
    "compilerOptions": {
      "target": "ES2020",
      "useDefineForClassFields": true,
      "lib": ["ES2020", "DOM", "DOM.Iterable"],
      "module": "ESNext",
      "skipLibCheck": true,
      "moduleResolution": "bundler",
      "allowImportingTsExtensions": true,
      "isolatedModules": true,
      "moduleDetection": "force",
      "noEmit": true,
      "jsx": "react-jsx",
      "strict": true,
      "noUnusedLocals": true,
      "noUnusedParameters": true,
      "noFallthroughCasesInSwitch": true
    },
    "include": ["src"]
  }
  ```

- [ ] **9.5** 创建 `src-web/vite.config.ts`

  ```typescript
  import { defineConfig } from "vite";
  import react from "@vitejs/plugin-react";

  export default defineConfig({
    plugins: [react()],
    // Tauri dev: prevent vite from obscuring Rust errors
    clearScreen: false,
    server: {
      port: 5173,
      strictPort: true,
      watch: {
        // Ignore src-tauri to avoid reloads on Rust changes
        ignored: ["**/src-tauri/**"],
      },
    },
    build: {
      // Tauri supports es2021
      target: ["es2021", "chrome100", "safari13"],
      minify: !process.env.TAURI_DEBUG ? "esbuild" : false,
      sourcemap: !!process.env.TAURI_DEBUG,
    },
    envPrefix: ["VITE_", "TAURI_"],
  });
  ```

- [ ] **9.6** 创建 `src-web/vitest.config.ts`

  ```typescript
  import { defineConfig } from "vitest/config";
  import react from "@vitejs/plugin-react";

  export default defineConfig({
    plugins: [react()],
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test-setup.ts"],
      coverage: {
        provider: "v8",
        reporter: ["text", "json"],
      },
    },
  });
  ```

- [ ] **9.7** 创建 `src-web/src/test-setup.ts`

  ```typescript
  import "@testing-library/jest-dom";
  ```

- [ ] **9.8** Commit

  ```bash
  git add src-web/package.json src-web/package-lock.json src-web/tsconfig.json src-web/vite.config.ts src-web/vitest.config.ts src-web/src/test-setup.ts
  git commit -m "feat: initialize React/Vite/TypeScript frontend project"
  ```

---

## Task 10: TailwindCSS + PostCSS + HTML 入口

- [ ] **10.1** 创建 `src-web/tailwind.config.js`

  ```javascript
  /** @type {import('tailwindcss').Config} */
  export default {
    content: [
      "./index.html",
      "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
      extend: {
        colors: {
          // Geological dark theme palette
          "geo-bg":      "#0d1117",
          "geo-surface": "#161b22",
          "geo-border":  "#30363d",
          "geo-text":    "#e6edf3",
          "geo-muted":   "#8b949e",
          "geo-accent":  "#1f6feb",
          "geo-green":   "#3fb950",
          "geo-red":     "#f85149",
        },
      },
    },
    plugins: [],
  };
  ```

- [ ] **10.2** 创建 `src-web/postcss.config.js`

  ```javascript
  export default {
    plugins: {
      tailwindcss: {},
      autoprefixer: {},
    },
  };
  ```

- [ ] **10.3** 创建 `src-web/index.html`

  ```html
  <!doctype html>
  <html lang="zh-CN">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>GeoViz Engine</title>
    </head>
    <body>
      <div id="root"></div>
      <script type="module" src="/src/main.tsx"></script>
    </body>
  </html>
  ```

- [ ] **10.4** 创建全局样式入口 `src-web/src/index.css`

  ```css
  @tailwind base;
  @tailwind components;
  @tailwind utilities;

  @layer base {
    html, body, #root {
      height: 100%;
      margin: 0;
      padding: 0;
    }

    body {
      background-color: #0d1117;
      color: #e6edf3;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    }
  }
  ```

- [ ] **10.5** Commit

  ```bash
  git add src-web/tailwind.config.js src-web/postcss.config.js src-web/index.html src-web/src/index.css
  git commit -m "feat: add TailwindCSS with geological dark theme palette"
  ```

---

## Task 11: i18n 基础配置 (TDD)

- [ ] **11.1** 写测试：`src-web/src/i18n/i18n.test.ts`

  ```typescript
  import i18n from "./index";

  describe("i18n configuration", () => {
    it("defaults to Chinese (zh)", () => {
      expect(i18n.language).toBe("zh");
    });

    it("translates app title in Chinese", () => {
      i18n.changeLanguage("zh");
      expect(i18n.t("app.title")).toBe("GeoViz Engine");
    });

    it("translates nav.wellLog in Chinese", () => {
      i18n.changeLanguage("zh");
      expect(i18n.t("nav.wellLog")).toBe("测井可视化");
    });

    it("translates nav.home in English after language change", async () => {
      await i18n.changeLanguage("en");
      expect(i18n.t("nav.home")).toBe("Home");
    });

    it("translates nav.wellLog in English", async () => {
      await i18n.changeLanguage("en");
      expect(i18n.t("nav.wellLog")).toBe("Well Log");
    });

    it("translates status.ready in Chinese", async () => {
      await i18n.changeLanguage("zh");
      expect(i18n.t("status.ready")).toBe("就绪");
    });

    it("translates status.ready in English", async () => {
      await i18n.changeLanguage("en");
      expect(i18n.t("status.ready")).toBe("Ready");
    });

    it("translates page.wellLog.generateData in Chinese", async () => {
      await i18n.changeLanguage("zh");
      expect(i18n.t("page.wellLog.generateData")).toBe("生成合成数据");
    });

    afterAll(async () => {
      // Reset to Chinese after tests
      await i18n.changeLanguage("zh");
    });
  });
  ```

- [ ] **11.2** 运行测试 — 预期失败

  ```bash
  cd src-web && npx vitest run src/i18n/i18n.test.ts 2>&1 | tail -10
  ```

  预期：`Cannot find module './index'`

- [ ] **11.3** 创建 `src-web/src/i18n/zh.json`

  ```json
  {
    "app": {
      "title": "GeoViz Engine",
      "version": "版本"
    },
    "nav": {
      "home": "首页",
      "wellLog": "测井可视化",
      "seismic": "地震剖面",
      "contour": "等值线图",
      "threeD": "三维地质"
    },
    "page": {
      "home": {
        "title": "欢迎使用 GeoViz Engine",
        "description": "专业地质数据可视化平台",
        "startWellLog": "开始测井分析"
      },
      "wellLog": {
        "title": "测井可视化",
        "noData": "暂无数据，请生成合成数据开始体验",
        "generateData": "生成合成数据",
        "generating": "生成中..."
      }
    },
    "status": {
      "ready": "就绪",
      "loading": "加载中...",
      "error": "错误",
      "backendConnected": "后端已连接",
      "backendDisconnected": "后端未连接"
    },
    "lang": {
      "zh": "中文",
      "en": "English"
    }
  }
  ```

- [ ] **11.4** 创建 `src-web/src/i18n/en.json`

  ```json
  {
    "app": {
      "title": "GeoViz Engine",
      "version": "Version"
    },
    "nav": {
      "home": "Home",
      "wellLog": "Well Log",
      "seismic": "Seismic",
      "contour": "Contour Map",
      "threeD": "3D Viewer"
    },
    "page": {
      "home": {
        "title": "Welcome to GeoViz Engine",
        "description": "Professional Geological Data Visualization Platform",
        "startWellLog": "Start Well Log Analysis"
      },
      "wellLog": {
        "title": "Well Log Visualization",
        "noData": "No data available. Generate synthetic data to get started.",
        "generateData": "Generate Synthetic Data",
        "generating": "Generating..."
      }
    },
    "status": {
      "ready": "Ready",
      "loading": "Loading...",
      "error": "Error",
      "backendConnected": "Backend Connected",
      "backendDisconnected": "Backend Disconnected"
    },
    "lang": {
      "zh": "中文",
      "en": "English"
    }
  }
  ```

- [ ] **11.5** 创建 `src-web/src/i18n/index.ts`

  ```typescript
  import i18n from "i18next";
  import { initReactI18next } from "react-i18next";
  import zh from "./zh.json";
  import en from "./en.json";

  i18n
    .use(initReactI18next)
    .init({
      resources: {
        zh: { translation: zh },
        en: { translation: en },
      },
      lng: "zh",
      fallbackLng: "en",
      interpolation: {
        escapeValue: false, // React already escapes
      },
    });

  export default i18n;
  ```

- [ ] **11.6** 运行测试 — 预期全部通过

  ```bash
  cd src-web && npx vitest run src/i18n/i18n.test.ts
  ```

  预期：`9 passed`

- [ ] **11.7** Commit

  ```bash
  git add src-web/src/i18n/
  git commit -m "feat: add i18n configuration with Chinese/English translations"
  ```

---

## Task 12: Zustand Stores (TDD)

- [ ] **12.1** 写测试：`src-web/src/stores/stores.test.ts`

  ```typescript
  import { act, renderHook } from "@testing-library/react";
  import { useSettingsStore } from "./useSettingsStore";
  import { useWellStore } from "./useWellStore";

  // Reset Zustand store state between tests
  beforeEach(() => {
    useSettingsStore.setState({ language: "zh" });
    useWellStore.setState({ wells: [], isLoading: false, error: null });
  });

  describe("useSettingsStore", () => {
    it("defaults language to zh", () => {
      const { result } = renderHook(() => useSettingsStore());
      expect(result.current.language).toBe("zh");
    });

    it("setLanguage updates language to en", () => {
      const { result } = renderHook(() => useSettingsStore());
      act(() => result.current.setLanguage("en"));
      expect(result.current.language).toBe("en");
    });

    it("setLanguage updates language back to zh", () => {
      const { result } = renderHook(() => useSettingsStore());
      act(() => result.current.setLanguage("en"));
      act(() => result.current.setLanguage("zh"));
      expect(result.current.language).toBe("zh");
    });
  });

  describe("useWellStore", () => {
    const mockWell = {
      well_id: "WELL-001",
      well_name: "Well 1",
      depth_start: 0,
      depth_end: 3000,
      curve_names: ["GR", "RT", "DEN", "NPHI"],
    };

    it("initial state has empty wells array", () => {
      const { result } = renderHook(() => useWellStore());
      expect(result.current.wells).toEqual([]);
    });

    it("initial isLoading is false", () => {
      const { result } = renderHook(() => useWellStore());
      expect(result.current.isLoading).toBe(false);
    });

    it("setWells stores well metadata", () => {
      const { result } = renderHook(() => useWellStore());
      act(() => result.current.setWells([mockWell]));
      expect(result.current.wells).toHaveLength(1);
      expect(result.current.wells[0].well_id).toBe("WELL-001");
    });

    it("clearWells empties the array", () => {
      const { result } = renderHook(() => useWellStore());
      act(() => result.current.setWells([mockWell]));
      act(() => result.current.clearWells());
      expect(result.current.wells).toHaveLength(0);
    });

    it("setLoading toggles loading state", () => {
      const { result } = renderHook(() => useWellStore());
      act(() => result.current.setLoading(true));
      expect(result.current.isLoading).toBe(true);
      act(() => result.current.setLoading(false));
      expect(result.current.isLoading).toBe(false);
    });

    it("setError stores error message", () => {
      const { result } = renderHook(() => useWellStore());
      act(() => result.current.setError("Network error"));
      expect(result.current.error).toBe("Network error");
    });

    it("setError null clears error", () => {
      const { result } = renderHook(() => useWellStore());
      act(() => result.current.setError("error"));
      act(() => result.current.setError(null));
      expect(result.current.error).toBeNull();
    });
  });
  ```

- [ ] **12.2** 运行测试 — 预期失败

  ```bash
  cd src-web && npx vitest run src/stores/stores.test.ts 2>&1 | tail -5
  ```

  预期：`Cannot find module './useSettingsStore'`

- [ ] **12.3** 创建 `src-web/src/stores/useSettingsStore.ts`

  ```typescript
  import { create } from "zustand";
  import i18n from "../i18n";

  type Language = "zh" | "en";

  interface SettingsState {
    language: Language;
    setLanguage: (lang: Language) => void;
  }

  export const useSettingsStore = create<SettingsState>((set) => ({
    language: "zh",
    setLanguage: (lang) => {
      i18n.changeLanguage(lang);
      set({ language: lang });
    },
  }));
  ```

- [ ] **12.4** 创建 `src-web/src/stores/useWellStore.ts`

  ```typescript
  import { create } from "zustand";

  export interface WellMetadata {
    well_id: string;
    well_name: string;
    depth_start: number;
    depth_end: number;
    curve_names: string[];
  }

  interface WellState {
    wells: WellMetadata[];
    isLoading: boolean;
    error: string | null;
    setWells: (wells: WellMetadata[]) => void;
    clearWells: () => void;
    setLoading: (loading: boolean) => void;
    setError: (error: string | null) => void;
  }

  export const useWellStore = create<WellState>((set) => ({
    wells: [],
    isLoading: false,
    error: null,
    setWells: (wells) => set({ wells }),
    clearWells: () => set({ wells: [] }),
    setLoading: (isLoading) => set({ isLoading }),
    setError: (error) => set({ error }),
  }));
  ```

- [ ] **12.5** 运行测试 — 预期全部通过

  ```bash
  cd src-web && npx vitest run src/stores/stores.test.ts
  ```

  预期：`10 passed`

- [ ] **12.6** Commit

  ```bash
  git add src-web/src/stores/
  git commit -m "feat: add Zustand stores for settings (language) and well metadata"
  ```

---

## Task 13: useApi Hook (TDD)

- [ ] **13.1** 创建 Tauri API mock：`src-web/src/__mocks__/@tauri-apps/api/core.ts`

  ```typescript
  import { vi } from "vitest";

  export const invoke = vi.fn();
  ```

- [ ] **13.2** 写测试：`src-web/src/hooks/useApi.test.ts`

  ```typescript
  import { renderHook, act, waitFor } from "@testing-library/react";
  import { vi, beforeEach, afterEach } from "vitest";
  import { useApi } from "./useApi";

  // Mock fetch globally
  const mockFetch = vi.fn();
  global.fetch = mockFetch;

  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubEnv("VITE_DEV_API_TOKEN", "test-vite-token");
    vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  describe("useApi", () => {
    it("starts with loading=false and error=null", () => {
      const { result } = renderHook(() => useApi());
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it("sets loading=true during request", async () => {
      mockFetch.mockImplementationOnce(
        () => new Promise((resolve) => setTimeout(() => resolve({
          ok: true,
          json: async () => ({ status: "ok" }),
        }), 50))
      );

      const { result } = renderHook(() => useApi());
      act(() => { result.current.request("/api/system/status"); });
      expect(result.current.loading).toBe(true);
    });

    it("sends X-API-Token header", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: "ok" }),
      });

      const { result } = renderHook(() => useApi());
      await act(async () => { await result.current.request("/api/system/status"); });

      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = options.headers as Record<string, string>;
      expect(headers["X-API-Token"]).toBeDefined();
    });

    it("returns parsed JSON on success", async () => {
      const payload = { status: "ok", version: "0.1.0" };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => payload,
      });

      const { result } = renderHook(() => useApi());
      let data: unknown;
      await act(async () => {
        data = await result.current.request("/api/system/status");
      });
      expect(data).toEqual(payload);
    });

    it("sets error state on HTTP error", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
      });

      const { result } = renderHook(() => useApi());
      await act(async () => {
        try { await result.current.request("/api/system/status"); }
        catch { /* expected */ }
      });
      await waitFor(() => expect(result.current.error).toContain("401"));
    });

    it("sets loading=false after request completes", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      const { result } = renderHook(() => useApi());
      await act(async () => { await result.current.request("/path"); });
      expect(result.current.loading).toBe(false);
    });
  });
  ```

- [ ] **13.3** 运行测试 — 预期失败

  ```bash
  cd src-web && npx vitest run src/hooks/useApi.test.ts 2>&1 | tail -5
  ```

  预期：`Cannot find module './useApi'`

- [ ] **13.4** 创建 `src-web/src/hooks/useApi.ts`

  ```typescript
  import { useState, useCallback } from "react";

  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
  const DEV_TOKEN = import.meta.env.VITE_DEV_API_TOKEN ?? "dev-token-local-development-32x";

  /**
   * Detect whether we are running inside a Tauri WebView.
   * In Tauri, __TAURI_INTERNALS__ is injected by the Tauri runtime.
   */
  function isTauriEnv(): boolean {
    return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
  }

  /**
   * Get the API token:
   * - In Tauri (production): call get_api_token Rust command
   * - In browser (dev/test): use VITE_DEV_API_TOKEN env variable
   */
  async function getToken(): Promise<string> {
    if (isTauriEnv()) {
      const { invoke } = await import("@tauri-apps/api/core");
      return invoke<string>("get_api_token");
    }
    return DEV_TOKEN;
  }

  interface UseApiReturn {
    request: <T>(path: string, options?: RequestInit) => Promise<T>;
    loading: boolean;
    error: string | null;
  }

  export function useApi(): UseApiReturn {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const request = useCallback(async <T>(
      path: string,
      options: RequestInit = {},
    ): Promise<T> => {
      setLoading(true);
      setError(null);
      try {
        const token = await getToken();
        const response = await fetch(`${API_BASE_URL}${path}`, {
          ...options,
          headers: {
            "Content-Type": "application/json",
            "X-API-Token": token,
            ...(options.headers as Record<string, string> ?? {}),
          },
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return (await response.json()) as T;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Unknown error";
        setError(msg);
        throw err;
      } finally {
        setLoading(false);
      }
    }, []);

    return { request, loading, error };
  }
  ```

- [ ] **13.5** 运行测试 — 预期全部通过

  ```bash
  cd src-web && npx vitest run src/hooks/useApi.test.ts
  ```

  预期：`6 passed`

- [ ] **13.6** 创建 `src-web/.env.development`

  ```env
  VITE_DEV_API_TOKEN=dev-token-local-development-32x
  VITE_API_BASE_URL=http://localhost:8000
  ```

- [ ] **13.7** Commit

  ```bash
  git add src-web/src/hooks/ src-web/src/__mocks__/ src-web/.env.development
  git commit -m "feat: add useApi hook with Tauri/browser token injection"
  ```

---

## Task 14: Layout 组件 (TDD)

- [ ] **14.1** 写测试：`src-web/src/components/common/Sidebar.test.tsx`

  ```typescript
  import { render, screen } from "@testing-library/react";
  import { MemoryRouter } from "react-router-dom";
  import { I18nextProvider } from "react-i18next";
  import i18n from "../../i18n";
  import Sidebar from "./Sidebar";

  function renderSidebar(path = "/") {
    return render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={[path]}>
          <Sidebar />
        </MemoryRouter>
      </I18nextProvider>
    );
  }

  describe("Sidebar", () => {
    beforeAll(() => i18n.changeLanguage("zh"));

    it("renders Home nav link", () => {
      renderSidebar();
      expect(screen.getByText("首页")).toBeInTheDocument();
    });

    it("renders Well Log nav link", () => {
      renderSidebar();
      expect(screen.getByText("测井可视化")).toBeInTheDocument();
    });

    it("home link points to /", () => {
      renderSidebar();
      expect(screen.getByText("首页").closest("a")).toHaveAttribute("href", "/");
    });

    it("well-log link points to /well-log", () => {
      renderSidebar();
      expect(screen.getByText("测井可视化").closest("a")).toHaveAttribute("href", "/well-log");
    });
  });
  ```

- [ ] **14.2** 写测试：`src-web/src/components/common/StatusBar.test.tsx`

  ```typescript
  import { render, screen } from "@testing-library/react";
  import { I18nextProvider } from "react-i18next";
  import i18n from "../../i18n";
  import StatusBar from "./StatusBar";

  describe("StatusBar", () => {
    beforeAll(() => i18n.changeLanguage("zh"));

    it("renders ready status text", () => {
      render(
        <I18nextProvider i18n={i18n}>
          <StatusBar />
        </I18nextProvider>
      );
      expect(screen.getByText("就绪")).toBeInTheDocument();
    });

    it("renders version string", () => {
      render(
        <I18nextProvider i18n={i18n}>
          <StatusBar />
        </I18nextProvider>
      );
      expect(screen.getByText(/v0\.1\.0/)).toBeInTheDocument();
    });
  });
  ```

- [ ] **14.3** 写测试：`src-web/src/components/common/Toolbar.test.tsx`

  ```typescript
  import { render, screen, fireEvent } from "@testing-library/react";
  import { I18nextProvider } from "react-i18next";
  import i18n from "../../i18n";
  import Toolbar from "./Toolbar";

  describe("Toolbar", () => {
    beforeEach(() => i18n.changeLanguage("zh"));

    it("renders app title", () => {
      render(
        <I18nextProvider i18n={i18n}>
          <Toolbar />
        </I18nextProvider>
      );
      expect(screen.getByText("GeoViz Engine")).toBeInTheDocument();
    });

    it("renders language toggle button", () => {
      render(
        <I18nextProvider i18n={i18n}>
          <Toolbar />
        </I18nextProvider>
      );
      // Button should show the OTHER language (click to switch to it)
      expect(screen.getByRole("button", { name: /English/i })).toBeInTheDocument();
    });

    it("clicking language button switches to English", () => {
      render(
        <I18nextProvider i18n={i18n}>
          <Toolbar />
        </I18nextProvider>
      );
      const langBtn = screen.getByRole("button", { name: /English/i });
      fireEvent.click(langBtn);
      expect(i18n.language).toBe("en");
    });
  });
  ```

- [ ] **14.4** 运行 component 测试 — 预期失败

  ```bash
  cd src-web && npx vitest run src/components/common/ 2>&1 | tail -5
  ```

  预期：`Cannot find module './Sidebar'` 等

- [ ] **14.5** 创建 `src-web/src/components/common/Sidebar.tsx`

  ```typescript
  import { NavLink } from "react-router-dom";
  import { useTranslation } from "react-i18next";
  import { Home, Activity } from "lucide-react";

  interface NavItem {
    to: string;
    icon: React.ReactNode;
    labelKey: string;
  }

  const navItems: NavItem[] = [
    { to: "/",         icon: <Home size={18} />,     labelKey: "nav.home" },
    { to: "/well-log", icon: <Activity size={18} />, labelKey: "nav.wellLog" },
  ];

  export default function Sidebar() {
    const { t } = useTranslation();

    return (
      <nav className="w-48 flex-shrink-0 bg-geo-surface border-r border-geo-border flex flex-col py-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-2 px-4 py-2.5 text-sm transition-colors ${
                isActive
                  ? "bg-geo-accent/20 text-geo-accent border-r-2 border-geo-accent"
                  : "text-geo-muted hover:text-geo-text hover:bg-white/5"
              }`
            }
          >
            {item.icon}
            <span>{t(item.labelKey)}</span>
          </NavLink>
        ))}
      </nav>
    );
  }
  ```

- [ ] **14.6** 创建 `src-web/src/components/common/StatusBar.tsx`

  ```typescript
  import { useTranslation } from "react-i18next";

  const APP_VERSION = "0.1.0";

  export default function StatusBar() {
    const { t } = useTranslation();

    return (
      <footer className="h-6 bg-geo-surface border-t border-geo-border flex items-center justify-between px-3 text-xs text-geo-muted flex-shrink-0">
        <span>{t("status.ready")}</span>
        <span>GeoViz Engine v{APP_VERSION}</span>
      </footer>
    );
  }
  ```

- [ ] **14.7** 创建 `src-web/src/components/common/Toolbar.tsx`

  ```typescript
  import { useTranslation } from "react-i18next";
  import { useSettingsStore } from "../../stores/useSettingsStore";

  export default function Toolbar() {
    const { t } = useTranslation();
    const { language, setLanguage } = useSettingsStore();

    const otherLang = language === "zh" ? "en" : "zh";
    const otherLangLabel = t(`lang.${otherLang}`);

    return (
      <header className="h-9 bg-geo-surface border-b border-geo-border flex items-center justify-between px-4 flex-shrink-0">
        <span className="text-sm font-medium text-geo-text tracking-wide">
          {t("app.title")}
        </span>
        <button
          onClick={() => setLanguage(otherLang)}
          className="text-xs text-geo-muted hover:text-geo-text transition-colors px-2 py-1 rounded hover:bg-white/5"
        >
          {otherLangLabel}
        </button>
      </header>
    );
  }
  ```

- [ ] **14.8** 创建 `src-web/src/components/layout/AppLayout.tsx`

  ```typescript
  import { Outlet } from "react-router-dom";
  import Toolbar from "../common/Toolbar";
  import Sidebar from "../common/Sidebar";
  import StatusBar from "../common/StatusBar";

  export default function AppLayout() {
    return (
      <div className="flex flex-col h-full bg-geo-bg text-geo-text">
        <Toolbar />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
          <main className="flex-1 overflow-auto">
            <Outlet />
          </main>
        </div>
        <StatusBar />
      </div>
    );
  }
  ```

- [ ] **14.9** 运行 layout 测试 — 预期全部通过

  ```bash
  cd src-web && npx vitest run src/components/
  ```

  预期：`9 passed`

- [ ] **14.10** Commit

  ```bash
  git add src-web/src/components/
  git commit -m "feat: add Sidebar, Toolbar, StatusBar, AppLayout components"
  ```

---

## Task 15: Pages (TDD)

- [ ] **15.1** 写测试：`src-web/src/pages/HomePage.test.tsx`

  ```typescript
  import { render, screen } from "@testing-library/react";
  import { MemoryRouter } from "react-router-dom";
  import { I18nextProvider } from "react-i18next";
  import i18n from "../i18n";
  import HomePage from "./HomePage";

  function renderPage() {
    return render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>
      </I18nextProvider>
    );
  }

  describe("HomePage", () => {
    beforeAll(() => i18n.changeLanguage("zh"));

    it("renders welcome heading", () => {
      renderPage();
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });

    it("renders description text", () => {
      renderPage();
      expect(screen.getByText("专业地质数据可视化平台")).toBeInTheDocument();
    });

    it("renders link to well-log page", () => {
      renderPage();
      const link = screen.getByText("开始测井分析").closest("a");
      expect(link).toHaveAttribute("href", "/well-log");
    });
  });
  ```

- [ ] **15.2** 写测试：`src-web/src/pages/WellLogPage.test.tsx`

  ```typescript
  import { render, screen, waitFor } from "@testing-library/react";
  import { MemoryRouter } from "react-router-dom";
  import { I18nextProvider } from "react-i18next";
  import { vi } from "vitest";
  import i18n from "../i18n";
  import WellLogPage from "./WellLogPage";

  // Mock useApi
  vi.mock("../hooks/useApi", () => ({
    useApi: () => ({
      request: vi.fn().mockResolvedValue({
        generated_count: 3,
        wells: [
          { well_id: "WELL-001", well_name: "Well 1", depth_start: 0, depth_end: 3000, curve_names: ["GR"] },
          { well_id: "WELL-002", well_name: "Well 2", depth_start: 0, depth_end: 3000, curve_names: ["GR"] },
          { well_id: "WELL-003", well_name: "Well 3", depth_start: 0, depth_end: 3000, curve_names: ["GR"] },
        ],
        message: "Generated 3 synthetic wells",
      }),
      loading: false,
      error: null,
    }),
  }));

  function renderPage() {
    return render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter>
          <WellLogPage />
        </MemoryRouter>
      </I18nextProvider>
    );
  }

  describe("WellLogPage", () => {
    beforeAll(() => i18n.changeLanguage("zh"));

    it("renders page title", () => {
      renderPage();
      expect(screen.getByRole("heading", { name: /测井可视化/i })).toBeInTheDocument();
    });

    it("renders generate data button", () => {
      renderPage();
      expect(screen.getByRole("button", { name: /生成合成数据/i })).toBeInTheDocument();
    });

    it("shows no-data message initially when wells store is empty", () => {
      renderPage();
      expect(screen.getByText(/暂无数据/i)).toBeInTheDocument();
    });
  });
  ```

- [ ] **15.3** 运行测试 — 预期失败

  ```bash
  cd src-web && npx vitest run src/pages/ 2>&1 | tail -5
  ```

  预期：`Cannot find module './HomePage'`

- [ ] **15.4** 创建 `src-web/src/pages/HomePage.tsx`

  ```typescript
  import { Link } from "react-router-dom";
  import { useTranslation } from "react-i18next";
  import { Activity } from "lucide-react";

  export default function HomePage() {
    const { t } = useTranslation();

    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center">
        <div className="max-w-lg">
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 bg-geo-accent/20 rounded-2xl flex items-center justify-center">
              <Activity size={32} className="text-geo-accent" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-geo-text mb-3">
            {t("page.home.title")}
          </h1>
          <p className="text-geo-muted mb-8">
            {t("page.home.description")}
          </p>
          <Link
            to="/well-log"
            className="inline-flex items-center gap-2 bg-geo-accent hover:bg-geo-accent/80 text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            <Activity size={16} />
            {t("page.home.startWellLog")}
          </Link>
        </div>
      </div>
    );
  }
  ```

- [ ] **15.5** 创建 `src-web/src/pages/WellLogPage.tsx`

  ```typescript
  import { useTranslation } from "react-i18next";
  import { useWellStore } from "../stores/useWellStore";
  import { useApi } from "../hooks/useApi";

  interface GenerateDataResponse {
    wells: Array<{
      well_id: string;
      well_name: string;
      depth_start: number;
      depth_end: number;
      curve_names: string[];
    }>;
    generated_count: number;
    message: string;
  }

  export default function WellLogPage() {
    const { t } = useTranslation();
    const { wells, setWells, isLoading, setLoading, error, setError } = useWellStore();
    const { request } = useApi();

    async function handleGenerate() {
      setLoading(true);
      setError(null);
      try {
        const data = await request<GenerateDataResponse>("/api/data/generate", {
          method: "POST",
        });
        setWells(data.wells);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to generate data");
      } finally {
        setLoading(false);
      }
    }

    return (
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-semibold text-geo-text">
            {t("page.wellLog.title")}
          </h1>
          <button
            onClick={handleGenerate}
            disabled={isLoading}
            className="inline-flex items-center gap-2 bg-geo-accent hover:bg-geo-accent/80 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {isLoading ? t("page.wellLog.generating") : t("page.wellLog.generateData")}
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-geo-red/10 border border-geo-red/30 rounded-lg text-geo-red text-sm">
            {error}
          </div>
        )}

        {wells.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-geo-muted">
            <p className="text-sm">{t("page.wellLog.noData")}</p>
          </div>
        ) : (
          <ul className="space-y-2">
            {wells.map((well) => (
              <li
                key={well.well_id}
                className="p-3 bg-geo-surface border border-geo-border rounded-lg text-sm"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-geo-text">{well.well_name}</span>
                  <span className="text-geo-muted text-xs">{well.well_id}</span>
                </div>
                <div className="text-geo-muted text-xs mt-1">
                  {well.depth_start}m – {well.depth_end.toFixed(0)}m &middot;{" "}
                  {well.curve_names.join(", ")}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }
  ```

- [ ] **15.6** 运行页面测试 — 预期全部通过

  ```bash
  cd src-web && npx vitest run src/pages/
  ```

  预期：`6 passed`

- [ ] **15.7** Commit

  ```bash
  git add src-web/src/pages/
  git commit -m "feat: add HomePage and WellLogPage with synthetic data generation UI"
  ```

---

## Task 16: router.tsx + App.tsx + main.tsx

- [ ] **16.1** 创建 `src-web/src/router.tsx`

  ```typescript
  import { createBrowserRouter } from "react-router-dom";
  import AppLayout from "./components/layout/AppLayout";
  import HomePage from "./pages/HomePage";
  import WellLogPage from "./pages/WellLogPage";

  const router = createBrowserRouter([
    {
      path: "/",
      element: <AppLayout />,
      children: [
        { index: true, element: <HomePage /> },
        { path: "well-log", element: <WellLogPage /> },
      ],
    },
  ]);

  export default router;
  ```

- [ ] **16.2** 创建 `src-web/src/App.tsx`

  ```typescript
  import { RouterProvider } from "react-router-dom";
  import router from "./router";
  // Initialize i18n on import (side effect)
  import "./i18n";

  export default function App() {
    return <RouterProvider router={router} />;
  }
  ```

- [ ] **16.3** 创建 `src-web/src/main.tsx`

  ```typescript
  import React from "react";
  import ReactDOM from "react-dom/client";
  import App from "./App";
  import "./index.css";

  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
  ```

- [ ] **16.4** 运行全量前端测试验证无回归

  ```bash
  cd src-web && npx vitest run
  ```

  预期：`~31 passed`（i18n×9 + stores×10 + useApi×6 + components×9 + pages×6）

- [ ] **16.5** 验证 TypeScript 编译无错误

  ```bash
  cd src-web && npx tsc --noEmit
  ```

  预期：无任何输出（无错误）

- [ ] **16.6** Commit

  ```bash
  git add src-web/src/router.tsx src-web/src/App.tsx src-web/src/main.tsx
  git commit -m "feat: wire up React Router 7 with AppLayout + HomePage + WellLogPage"
  ```

---

## Task 17: dev.sh + build.sh + 最终集成

- [ ] **17.1** 创建 `scripts/dev.sh`

  ```bash
  #!/usr/bin/env bash
  set -euo pipefail

  ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

  # Dev-mode fixed token (matches .env.development VITE_DEV_API_TOKEN)
  export GEOVIZ_API_TOKEN="dev-token-local-development-32x"

  echo "[geo-viz] Starting Python backend on :8000 ..."
  cd "$ROOT_DIR/src-python"
  source venv/bin/activate
  uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
  PYTHON_PID=$!

  echo "[geo-viz] Starting Vite frontend on :5173 ..."
  cd "$ROOT_DIR/src-web"
  npm run dev &
  VITE_PID=$!

  # Wait for Python backend to be healthy (max 30 seconds)
  echo "[geo-viz] Waiting for backend ..."
  for i in $(seq 1 30); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
      -H "X-API-Token: $GEOVIZ_API_TOKEN" \
      http://127.0.0.1:8000/api/system/status 2>/dev/null || echo "000")
    if [ "$STATUS" = "200" ]; then
      echo "[geo-viz] Backend ready."
      break
    fi
    sleep 1
  done

  echo "[geo-viz] Starting Tauri dev ..."
  cd "$ROOT_DIR/src-tauri"
  GEOVIZ_MODE=dev cargo tauri dev

  # Cleanup background processes on exit
  kill "$PYTHON_PID" "$VITE_PID" 2>/dev/null || true
  ```

- [ ] **17.2** 创建 `scripts/build.sh`

  ```bash
  #!/usr/bin/env bash
  set -euo pipefail

  ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

  echo "[geo-viz] Building Python backend with PyInstaller ..."
  cd "$ROOT_DIR/src-python"
  source venv/bin/activate
  pip install pyinstaller --quiet
  pyinstaller --onefile --name geoviz-backend app/main.py \
    --distpath "$ROOT_DIR/src-tauri/binaries"

  # Rename binary to match Tauri target-triple naming convention.
  # Example for Linux x86_64:
  TARGET_TRIPLE=$(rustc -Vv | grep 'host:' | awk '{print $2}')
  BINARY="$ROOT_DIR/src-tauri/binaries/geoviz-backend"
  if [[ "$OSTYPE" == "msys"* || "$OSTYPE" == "win"* ]]; then
    mv "$BINARY.exe" "${BINARY}-${TARGET_TRIPLE}.exe"
  else
    mv "$BINARY" "${BINARY}-${TARGET_TRIPLE}"
  fi
  echo "[geo-viz] Python binary -> geoviz-backend-${TARGET_TRIPLE}"

  echo "[geo-viz] Building Vite frontend ..."
  cd "$ROOT_DIR/src-web"
  npm run build

  echo "[geo-viz] Building Tauri app ..."
  cd "$ROOT_DIR/src-tauri"
  GEOVIZ_MODE=prod cargo tauri build

  echo "[geo-viz] Build complete. Artifacts in src-tauri/target/release/bundle/"
  ```

- [ ] **17.3** 赋予脚本执行权限

  ```bash
  chmod +x scripts/dev.sh scripts/build.sh
  ```

- [ ] **17.4** 手动冒烟测试 Python 后端（在独立终端执行）

  ```bash
  cd src-python
  source venv/bin/activate
  export GEOVIZ_API_TOKEN="dev-token-local-development-32x"
  uvicorn app.main:app --port 8000 &

  # 验证健康检查
  curl -s -H "X-API-Token: dev-token-local-development-32x" \
    http://127.0.0.1:8000/api/system/status | python3 -m json.tool
  # 预期: {"status": "ok", "version": "0.1.0", ...}

  # 验证数据生成
  curl -s -X POST -H "Content-Type: application/json" \
    -H "X-API-Token: dev-token-local-development-32x" \
    -d '{"count": 3}' \
    http://127.0.0.1:8000/api/data/generate | python3 -m json.tool
  # 预期: {"wells": [...3 wells...], "generated_count": 3, ...}

  kill %1  # 停止后台 uvicorn
  ```

- [ ] **17.5** 运行全量后端测试最终验证

  ```bash
  cd src-python && source venv/bin/activate && python -m pytest -v --tb=short
  ```

  预期：`~31 passed, 0 failed`

- [ ] **17.6** 运行全量前端测试最终验证

  ```bash
  cd src-web && npx vitest run
  ```

  预期：`~31 passed, 0 failed`

- [ ] **17.7** Commit

  ```bash
  git add scripts/
  git commit -m "feat: add dev.sh and build.sh scripts for development and production workflows"
  ```

---

## Task 18: 最终整合 Commit

- [ ] **18.1** 确认所有文件已跟踪

  ```bash
  git status
  ```

  预期：仅有 `node_modules/`（已在 .gitignore）和 `src-python/venv/`（已在 .gitignore）显示为未跟踪。

- [ ] **18.2** 确认 `.gitignore` 包含必要条目（在项目根目录追加，若不存在则创建）

  ```gitignore
  # Python
  src-python/venv/
  src-python/__pycache__/
  src-python/.pytest_cache/
  src-python/app/__pycache__/
  src-python/app/**/__pycache__/
  src-python/tests/__pycache__/
  *.pyc

  # Node
  src-web/node_modules/
  src-web/dist/

  # Rust
  src-tauri/target/

  # Build artifacts
  src-tauri/binaries/geoviz-backend
  src-tauri/binaries/geoviz-backend-*
  *.spec

  # Env
  .env.local
  ```

- [ ] **18.3** 最终 commit

  ```bash
  git add .gitignore
  git commit -m "chore: update .gitignore for Python/Node/Rust build artifacts"
  ```

---

## Phase 1 完成验收标准

完成所有 Task 后，验证以下条件均满足：

| 验收项 | 验证命令 | 预期结果 |
|--------|----------|----------|
| Python 后端测试全绿 | `cd src-python && source venv/bin/activate && python -m pytest` | `~31 passed` |
| 前端测试全绿 | `cd src-web && npx vitest run` | `~31 passed` |
| TypeScript 无编译错误 | `cd src-web && npx tsc --noEmit` | 无输出 |
| Rust 代码编译 | `cd src-tauri && cargo check` | `Finished dev profile` |
| 健康检查 API 响应 | `curl -H "X-API-Token: ..." http://localhost:8000/api/system/status` | `{"status":"ok"}` |
| 数据生成 API 响应 | POST `/api/data/generate` with `{"count":10}` | 10 口井的元数据 |
| i18n 中英切换 | 前端点击语言按钮 | 文字立即切换 |
| 路由导航 | 点击侧边栏"测井可视化" | 路由切换至 `/well-log` |

## 目录结构最终确认

```
geo-viz-engine/
├── src-tauri/
│   ├── src/
│   │   ├── main.rs           ✓
│   │   └── lib.rs            ✓
│   ├── capabilities/
│   │   └── default.json      ✓
│   ├── binaries/
│   │   └── .gitkeep          ✓
│   ├── build.rs              ✓
│   ├── Cargo.toml            ✓
│   └── tauri.conf.json       ✓
├── src-web/
│   ├── src/
│   │   ├── components/
│   │   │   ├── common/       (Toolbar.tsx, StatusBar.tsx, Sidebar.tsx + tests) ✓
│   │   │   └── layout/       (AppLayout.tsx) ✓
│   │   ├── pages/            (HomePage.tsx, WellLogPage.tsx + tests) ✓
│   │   ├── stores/           (useSettingsStore.ts, useWellStore.ts + tests) ✓
│   │   ├── hooks/            (useApi.ts + tests) ✓
│   │   ├── i18n/             (index.ts, zh.json, en.json + tests) ✓
│   │   ├── __mocks__/        (@tauri-apps/api/core.ts) ✓
│   │   ├── router.tsx        ✓
│   │   ├── App.tsx           ✓
│   │   ├── main.tsx          ✓
│   │   ├── index.css         ✓
│   │   └── test-setup.ts     ✓
│   ├── index.html            ✓
│   ├── package.json          ✓
│   ├── vite.config.ts        ✓
│   ├── vitest.config.ts      ✓
│   ├── tsconfig.json         ✓
│   ├── tailwind.config.js    ✓
│   ├── postcss.config.js     ✓
│   └── .env.development      ✓
├── src-python/
│   ├── app/
│   │   ├── __init__.py       ✓
│   │   ├── main.py           ✓
│   │   ├── auth.py           ✓
│   │   ├── api/
│   │   │   ├── __init__.py   ✓
│   │   │   ├── system.py     ✓
│   │   │   └── data.py       ✓
│   │   ├── services/
│   │   │   ├── __init__.py   ✓
│   │   │   └── data_generator.py ✓
│   │   └── models/
│   │       ├── __init__.py   ✓
│   │       ├── well_log.py   ✓
│   │       └── common.py     ✓
│   ├── tests/
│   │   ├── __init__.py       ✓
│   │   ├── conftest.py       ✓
│   │   ├── test_models.py    ✓
│   │   ├── test_auth.py      ✓
│   │   ├── test_api_system.py ✓
│   │   ├── test_api_data.py  ✓
│   │   └── test_data_generator.py ✓
│   ├── requirements.txt      ✓
│   └── pyproject.toml        ✓
├── data/
│   └── generated/
│       └── .gitkeep          ✓
├── scripts/
│   ├── dev.sh                ✓
│   └── build.sh              ✓
└── .gitignore                ✓ (updated)
```
