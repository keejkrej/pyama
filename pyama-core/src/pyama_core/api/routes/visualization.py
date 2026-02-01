"""Visualization routes - project loading, trace data, and quality updates."""

import logging
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from pyama_core.io import naming, load_config, get_config_path, serialize_channels_data
from pyama_core.io.processing_csv import (
    get_dataframe,
    extract_all_cells_data,
    update_cell_quality,
    write_dataframe,
)
from pyama_core.io.trace_paths import resolve_trace_path

logger = logging.getLogger(__name__)

router = APIRouter(tags=["visualization"])


# =============================================================================
# REQUEST/RESPONSE SCHEMAS
# =============================================================================


class ProjectLoadRequest(BaseModel):
    """Request to load a visualization project."""

    project_path: str = Field(..., description="Path to the project directory")


class ProjectDataResponse(BaseModel):
    """Response containing project data."""

    project_path: str
    n_fov: int
    fov_data: dict[int, dict[str, str]]  # FOV ID -> {channel_name: file_path}
    channels: dict | None
    base_name: str


class TraceData(BaseModel):
    """Trace data for a single cell."""

    cell_id: str
    quality: bool
    features: dict[str, list[float]]  # feature_name -> [values per frame]
    positions: dict[str, list[float]]  # "frames", "xc", "yc" -> arrays


class TracesResponse(BaseModel):
    """Response containing paginated trace data."""

    traces: list[TraceData]
    total: int
    page: int
    page_size: int
    features: list[str]


class QualityUpdateRequest(BaseModel):
    """Request to update trace quality flags."""

    project_path: str
    fov: int
    updates: dict[str, bool]  # cell_id -> quality


class QualityUpdateResponse(BaseModel):
    """Response from quality update."""

    success: bool
    saved_path: str


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.post("/project/load", response_model=ProjectDataResponse)
async def load_project(request: ProjectLoadRequest) -> ProjectDataResponse:
    """Load project data from a processing output directory.

    Discovers FOVs, loads config if available, and maps available data files.
    Matches the behavior of LoadPanel._load_project() in pyama-qt.
    """
    project_path = Path(request.project_path)

    if not project_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project directory not found: {request.project_path}",
        )

    if not project_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Path is not a directory: {request.project_path}",
        )

    try:
        # Discover FOVs from directory structure
        fovs = naming.discover_fovs(project_path)
        if not fovs:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No FOV directories found in {project_path}. "
                    "Expected directories named fov_000, fov_001, etc."
                ),
            )

        # Load config if available
        cfg_path = get_config_path(project_path)
        channels_config = None
        if cfg_path.exists():
            try:
                config = load_config(cfg_path)
                channels_config = serialize_channels_data(config.channels)
            except Exception as e:
                logger.warning("Failed to load config: %s", e)

        # Build fov_data by discovering files in each FOV directory
        # Matches LoadPanel._load_project() logic
        fov_data: dict[int, dict[str, str]] = {}
        for fov in fovs:
            fov_dir = naming.fov_dir(project_path, fov)
            fov_files: dict[str, str] = {}

            # Discover all NPY files
            for npy_file in fov_dir.glob("*.npy"):
                name = npy_file.stem
                if "_pc_ch_" in name:
                    fov_files["pc"] = str(npy_file)
                elif "_fl_ch_" in name and "_background" not in name:
                    ch_idx = name.split("_fl_ch_")[-1]
                    fov_files[f"fl_ch_{ch_idx}"] = str(npy_file)
                elif "_seg_tracked_ch_" in name:
                    fov_files["seg_tracked"] = str(npy_file)
                elif "_seg_labeled_ch_" in name:
                    fov_files["seg_labeled"] = str(npy_file)
                elif "_seg_ch_" in name:
                    fov_files["seg"] = str(npy_file)
                elif "_fl_background_ch_" in name:
                    ch_idx = name.split("_fl_background_ch_")[-1]
                    fov_files[f"fl_background_ch_{ch_idx}"] = str(npy_file)

            # Discover traces CSV
            traces_files = list(fov_dir.glob("*_traces.csv"))
            if traces_files:
                fov_files["traces"] = str(traces_files[0])

            fov_data[fov] = fov_files

        # Extract base_name from first FOV directory name pattern
        # Assuming format: {base_name}_fov_{fov:03d}_*
        base_name = ""
        if fovs:
            first_fov_dir = naming.fov_dir(project_path, fovs[0])
            first_file = next(first_fov_dir.glob("*_traces.csv"), None)
            if first_file:
                # Extract base_name from filename like "20251209_10x_Ti2_LNP_HuH7_fov_000_traces.csv"
                parts = first_file.stem.split("_fov_")
                if len(parts) >= 2:
                    base_name = parts[0]

        logger.info(
            "Project loaded: %s (fovs=%d)",
            project_path,
            len(fovs),
        )

        return ProjectDataResponse(
            project_path=str(project_path),
            n_fov=len(fovs),
            fov_data=fov_data,
            channels=channels_config,
            base_name=base_name,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to load project: %s", project_path)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load project: {e}",
        ) from e


@router.get("/traces", response_model=TracesResponse)
async def get_traces(
    project_path: str = Query(..., description="Path to project directory"),
    fov: int = Query(..., description="FOV index"),
    page: int = Query(0, ge=0, description="Page number (0-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Traces per page"),
) -> TracesResponse:
    """Load paginated trace data for a specific FOV.

    Matches TracePanel._load_data_from_csv() and extract_all_cells_data() behavior.
    """
    project_dir = Path(project_path)

    if not project_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project directory not found: {project_path}",
        )

    try:
        # Get FOV directory
        fov_dir = naming.fov_dir(project_dir, fov)
        if not fov_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"FOV {fov} directory not found: {fov_dir}",
            )

        # Find traces CSV
        traces_files = list(fov_dir.glob("*_traces.csv"))
        if not traces_files:
            raise HTTPException(
                status_code=404,
                detail=f"No traces CSV found in FOV {fov}",
            )

        traces_path = Path(traces_files[0])
        resolved_path = resolve_trace_path(traces_path)

        if resolved_path is None or not resolved_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Traces CSV not found: {traces_path}",
            )

        # Load and extract data
        df = get_dataframe(resolved_path)
        cells_data = extract_all_cells_data(df)

        # Extract features list from first cell
        features: list[str] = []
        if cells_data:
            first_cell = next(iter(cells_data.values()))
            features = [
                k
                for k in first_cell["features"].keys()
                if k != "frame"
            ]

        # Convert to TraceData format
        all_traces: list[TraceData] = []
        for cell_id, data in cells_data.items():
            all_traces.append(
                TraceData(
                    cell_id=cell_id,
                    quality=data["quality"],
                    features={
                        k: v.tolist() if hasattr(v, "tolist") else list(v)
                        for k, v in data["features"].items()
                        # Include frame in features (used as x-axis in plots)
                    },
                    positions={
                        "frames": data["positions"]["frames"].tolist()
                        if hasattr(data["positions"]["frames"], "tolist")
                        else list(data["positions"]["frames"]),
                        "xc": data["positions"]["xc"].tolist()
                        if hasattr(data["positions"]["xc"], "tolist")
                        else list(data["positions"]["xc"]),
                        "yc": data["positions"]["yc"].tolist()
                        if hasattr(data["positions"]["yc"], "tolist")
                        else list(data["positions"]["yc"]),
                    },
                )
            )

        # Sort by cell_id (as integer)
        all_traces.sort(key=lambda t: int(t.cell_id))

        # Paginate
        total = len(all_traces)
        start_idx = page * page_size
        end_idx = start_idx + page_size
        paginated_traces = all_traces[start_idx:end_idx]

        logger.info(
            "Loaded traces for FOV %d: %d total, page %d (%d traces)",
            fov,
            total,
            page,
            len(paginated_traces),
        )

        return TracesResponse(
            traces=paginated_traces,
            total=total,
            page=page,
            page_size=page_size,
            features=sorted(features),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to load traces for FOV %d: %s", fov, e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load traces: {e}",
        ) from e


@router.get("/traces/features", response_model=dict[str, list[str]])
async def get_trace_features(
    project_path: str = Query(..., description="Path to project directory"),
    fov: int = Query(..., description="FOV index"),
) -> dict[str, list[str]]:
    """Get list of available feature columns from traces CSV."""
    project_dir = Path(project_path)

    if not project_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project directory not found: {project_path}",
        )

    try:
        fov_dir = naming.fov_dir(project_dir, fov)
        if not fov_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"FOV {fov} directory not found",
            )

        traces_files = list(fov_dir.glob("*_traces.csv"))
        if not traces_files:
            raise HTTPException(
                status_code=404,
                detail=f"No traces CSV found in FOV {fov}",
            )

        traces_path = Path(traces_files[0])
        resolved_path = resolve_trace_path(traces_path)

        if resolved_path is None or not resolved_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Traces CSV not found: {traces_path}",
            )

        df = get_dataframe(resolved_path)
        cells_data = extract_all_cells_data(df)

        features: list[str] = []
        if cells_data:
            first_cell = next(iter(cells_data.values()))
            features = [
                k
                for k in first_cell["features"].keys()
                if k != "frame"
            ]

        return {"features": sorted(features)}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get features for FOV %d: %s", fov, e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get features: {e}",
        ) from e


@router.post("/traces/quality", response_model=QualityUpdateResponse)
async def update_trace_quality(
    request: QualityUpdateRequest,
) -> QualityUpdateResponse:
    """Update quality flags for traces and save to inspected CSV.

    Matches TracePanel._on_save_clicked() behavior.
    """
    project_dir = Path(request.project_path)

    if not project_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project directory not found: {request.project_path}",
        )

    try:
        fov_dir = naming.fov_dir(project_dir, request.fov)
        if not fov_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"FOV {request.fov} directory not found",
            )

        # Find original traces CSV
        traces_files = list(fov_dir.glob("*_traces.csv"))
        if not traces_files:
            raise HTTPException(
                status_code=404,
                detail=f"No traces CSV found in FOV {request.fov}",
            )

        traces_path = Path(traces_files[0])
        resolved_path = resolve_trace_path(traces_path)

        if resolved_path is None or not resolved_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Traces CSV not found: {traces_path}",
            )

        # Load dataframe
        df = get_dataframe(resolved_path)

        # Create quality update dataframe
        quality_updates = pd.DataFrame(
            [
                {"cell": int(cell_id), "good": quality}
                for cell_id, quality in request.updates.items()
            ],
            columns=["cell", "good"],
        )

        # Update quality
        updated_df = update_cell_quality(df, quality_updates)

        # Determine save path (prefer inspected if original was inspected)
        if resolved_path.name.endswith("_inspected.csv"):
            save_path = resolved_path
        else:
            save_path = traces_path.with_name(
                f"{traces_path.stem}_inspected.csv"
            )

        # Write updated dataframe
        write_dataframe(updated_df, save_path)

        logger.info(
            "Updated quality for %d traces in FOV %d, saved to %s",
            len(request.updates),
            request.fov,
            save_path,
        )

        return QualityUpdateResponse(
            success=True,
            saved_path=str(save_path),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update trace quality: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update quality: {e}",
        ) from e


visualization_router = router
