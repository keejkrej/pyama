# AGENTS.md

Repository guidelines for AI agents. PyAMA: `pyama` core library + `pyama-gui` Qt GUI + `pyama-cli`.

## Commands

```bash
uv sync
uv run pyama-gui
uv run pyama-cli --help
uv run pytest
uv run ruff check && uv run ruff format
uv run ty check
```

## Architecture

- **Workflow**: `pyama.apps.processing.service.run_complete_workflow` – Copying → Segmentation → Tracking → Background → ROI → Extraction
- **Config**: canonical internal processing config lives in `pyama.types.pipeline`
- **Qt**: app shell is `pyama_gui.main_window.MainWindow`; tabs live under `pyama_gui.apps.*.{view,view_model}`
- **Binding**: UI→Model only; no model→UI auto-sync

## Conventions

- `@Slot()` on signal handlers; `_build_ui()` / `_connect_signals()` for Qt init
- No artificial timeouts in workflow
- Imports at top of file; use `dict`, `list`, `|` not `typing` generics
- Logging: `logger.info` = user progress, `logger.debug` = diagnostics

## CSV Formats

- **Analysis**: `frame,position,roi,value`; `load_analysis_csv()` returns MultiIndex `(position, roi)`
- **Fitted**: `position,roi,model_type,success,r_squared,{params}`
- **Traces**: `position,roi,frame,is_good,x,y,w,h,{feature}_c{id}`

See [docs/](docs/) for usage, core API, and protocol.
