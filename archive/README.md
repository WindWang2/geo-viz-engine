# archive/

历史代码与一次性产物归档。本目录内容不参与构建，也不被主应用引用。保留目的仅为方便回溯。

完整 Web 架构（Tauri + React + FastAPI + ECharts 实验）保留在 git tag `v0.1-web`，本目录不再额外拷贝。

## 子目录

### `scripts/`
散落在仓库根目录的一次性调试/验证脚本（`test_*.py`、`debug_*.py`、`check_*.py`、`get_*.py`、`convert_*.py`、`verify_ui.py` 等）。它们不是 `tests/` 中的 pytest 套件，多数针对早期开发阶段的具体问题。

**保留原因**：部分脚本含有未沉淀进正式代码的探索逻辑（坐标系换算、Excel 处理、segyio 用法等），删除前可作为参考。

**注意**：勿在此处新增脚本。新调试代码应进 `scratch/`（gitignore 范围外的临时区），稳定后转入 `tests/` 或 `src/`。

### `misc/`
- `diff.txt` — 早期一次性 `git diff` 转储
- `.coverage` — 历史 pytest 覆盖率二进制产物
