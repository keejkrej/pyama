# AGENTS.md

Repository guidelines for AI agents. PyAMA: pyama-core (processing, modeling, statistics, I/O) + pyama-pro (Qt GUI).

## Commands

```bash
uv sync
uv run pyama-pro
uv run pytest
uv run ruff check && uv run ruff format
uv run ty check
```

## Architecture

- **Workflow**: `pyama_core.processing.workflow.run_complete_workflow` – Copying → Segmentation → Correction → Tracking → Extraction
- **Context**: `ProcessingContext` in `pyama_core.types.processing` – channels, results, params
- **Qt**: ProcessingTab, ModelingTab, StatisticsTab, VisualizationTab in `pyama_pro.{processing,modeling,statistics,visualization}.main_tab`
- **Signals**: `operation_started()`, `operation_finished(bool, str)`; workers emit `finished(bool, str|object)`
- **Binding**: UI→Model only; no model→UI auto-sync

## Conventions

- `@Slot()` on signal handlers; `_build_ui()` / `_connect_signals()` for Qt init
- No artificial timeouts in workflow
- Imports at top of file; use `dict`, `list`, `|` not `typing` generics
- Logging: `logger.info` = user progress, `logger.debug` = diagnostics

## CSV Formats

- **Analysis**: `time,fov,cell,value`; `load_analysis_csv()` → MultiIndex `(fov, cell)`
- **Fitted**: `fov,cell,model_type,success,r_squared,{params}`
- **Traces**: `fov,cell,frame,time,good,position_*,bbox_*,{feature}_ch_{id}`

See [docs/](docs/) for usage, core API, and protocol.


