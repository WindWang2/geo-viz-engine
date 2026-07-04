# Findings & Specifications: Phase 15 — Project File Schema (.gvz)

## 1. Schema Design (`.gvz` JSON Specification)
为了使工程文件易于版本控制、可读性强、易于扩展，我们设计了一个基于 `pydantic` 的 JSON Schema 规范。

```python
from pydantic import BaseModel
from typing import Optional, Any

class ProjectMeta(BaseModel):
    name: str = "New Project"
    version: str = "0.8.0"
    created_at: str
    updated_at: str

class ProjectWell(BaseModel):
    name: str
    latitude: float
    longitude: float
    file_path: Optional[str] = None  # Excel or LAS path (relative or absolute)

class ProjectSeismic(BaseModel):
    file_path: Optional[str] = None  # SEGY path
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    spacing: tuple[float, float, float] = (1.0, 1.0, 1.0)

class ProjectHorizon(BaseModel):
    name: str
    file_path: str  # Horizon CSV/text file path

class ProjectPick(BaseModel):
    well_name: str
    depth: float
    formation: str

class ProjectCorrelation(BaseModel):
    source_well: str
    target_well: str
    source_depth: float
    target_depth: float
    formation: str

class ProjectViewState(BaseModel):
    active_page: int = 0
    seismic_slice_positions: dict[str, int] = {"inline": 0, "crossline": 0, "time": 0}
    seismic_colormap: str = "seismic"
    seismic_render_mode: str = "planes"

class ProjectSchema(BaseModel):
    meta: ProjectMeta
    wells: list[ProjectWell] = []
    seismic: Optional[ProjectSeismic] = None
    horizons: list[ProjectHorizon] = []
    picks: list[ProjectPick] = []
    correlations: list[ProjectCorrelation] = []
    view_state: ProjectViewState = ProjectViewState()
```

## 2. 相对路径算法 (Path Relativization)
为了确保工程文件可在不同的电脑或环境中无缝拷贝共享，所有文件路径（`wells[].file_path`, `seismic.file_path`, `horizons[].file_path`）均使用智能相对化处理：
- **保存时**：如果引用的数据文件位于工程文件所在的目录或其子目录内，则自动转换为相对工程文件的相对路径（例如 `data/HZ25.xlsx`），否则保留绝对路径。
- **加载时**：如果读取的路径是相对路径，则自动将其拼接到工程文件所在的真实目录下，还原为当前运行环境下的绝对路径，从而确保文件加载成功。

## 3. UI 状态集成点 (UI View State Integration Points)
- **DataPage**：展示当前加载的工程名称及多井列表。
- **MainWindow**：在主窗口的 Open / Save 操作中统一协调各个页面（`MapPage`、`WellLogPage` 等）的数据同步与状态恢复。
