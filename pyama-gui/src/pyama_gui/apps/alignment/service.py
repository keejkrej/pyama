"""Alignment facade for GUI-side workflows.

This keeps the thin alignment wrapper on the GUI side instead of exposing it
through ``pyama.apps``. The underlying grid/bbox math still delegates to
``core_py`` while bbox CSV path/loading stays in ``pyama`` processing code.
"""

from core_py import (
    build_bbox_csv,
    clear_excluded_cell_ids,
    collect_edge_cell_ids,
    count_visible_cells,
    create_default_grid,
    merge_excluded_cell_ids,
    minimum_grid_spacing,
    normalize_grid_state,
    set_excluded_cell_ids_for_position,
    toggle_excluded_cell_ids,
)

from pyama.apps.processing.bbox import bbox_csv_path, load_bbox_rows

__all__ = [
    "bbox_csv_path",
    "build_bbox_csv",
    "clear_excluded_cell_ids",
    "collect_edge_cell_ids",
    "count_visible_cells",
    "create_default_grid",
    "load_bbox_rows",
    "merge_excluded_cell_ids",
    "minimum_grid_spacing",
    "normalize_grid_state",
    "set_excluded_cell_ids_for_position",
    "toggle_excluded_cell_ids",
]
