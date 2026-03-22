"""CSV readers and writers used by internal pyama services."""

from pathlib import Path

import pandas as pd

DEFAULT_ANALYSIS_FRAME_INTERVAL_MINUTES = 10.0
_BASE_TRACE_COLUMNS = {"position", "roi", "frame", "is_good", "x", "y", "w", "h"}


def write_analysis_csv(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df_to_write = df.copy()
    df_to_write.index.name = "frame"
    df_to_write.columns = [str(col) for col in df_to_write.columns]
    df_to_write.to_csv(output_path, index=True, header=True, float_format="%.6f")


def load_analysis_csv(
    csv_path: Path,
    *,
    frame_interval_minutes: float = DEFAULT_ANALYSIS_FRAME_INTERVAL_MINUTES,
) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Analysis CSV file not found: {csv_path}")
    if frame_interval_minutes <= 0:
        raise ValueError("frame_interval_minutes must be > 0")

    df = pd.read_csv(csv_path)

    if "time" in df.columns and "frame" not in df.columns:
        raise ValueError(
            "Legacy time-based analysis CSVs are not supported; expected 'frame' column"
        )

    required_cols = {"frame", "position", "roi", "value"}
    if not required_cols.issubset(df.columns):
        missing = required_cols - set(df.columns)
        raise ValueError(f"CSV missing required columns: {missing}")

    df["frame"] = pd.to_numeric(df["frame"], errors="coerce")
    df["position"] = df["position"].astype(int)
    df["roi"] = df["roi"].astype(int)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    if df["frame"].isna().any():
        raise ValueError(f"CSV contains non-numeric frame values: {csv_path}")
    frame_values = df["frame"].round().astype(int)
    if not ((df["frame"] - frame_values).abs() < 1e-9).all():
        raise ValueError(f"CSV contains non-integer frame values: {csv_path}")
    df["frame"] = frame_values
    df["time_min"] = df["frame"] * float(frame_interval_minutes)

    return df.set_index(["position", "roi"]).sort_index()


def create_analysis_dataframe(
    frame_values: list[int], roi_data: dict[int, list[float]]
) -> pd.DataFrame:
    max_roi_id = max(roi_data.keys()) if roi_data else -1
    expected_roi_ids = list(range(max_roi_id + 1))

    df_data = {}
    for roi_id in expected_roi_ids:
        if roi_id in roi_data:
            df_data[roi_id] = roi_data[roi_id]
        else:
            df_data[roi_id] = [float("nan")] * len(frame_values)

    df = pd.DataFrame(df_data, index=frame_values)
    df.index.name = "frame"
    return df


def get_analysis_stats(df: pd.DataFrame) -> dict:
    time_values = (
        pd.Index(df.index, name="frame").to_series() * DEFAULT_ANALYSIS_FRAME_INTERVAL_MINUTES
    )
    return {
        "frame_points": len(df),
        "roi_count": len(df.columns),
        "duration_min": float(time_values.max() - time_values.min()) if len(df) > 1 else 0,
        "time_interval_min": float(time_values.diff().median()) if len(df) > 1 else 0,
        "missing_values": df.isnull().sum().sum(),
        "complete_traces": (df.isnull().sum() == 0).sum(),
    }


def discover_csv_files(data_path: Path | str) -> list[Path]:
    data_path = Path(data_path)
    csv_files: list[Path] = []

    if data_path.is_file() and data_path.suffix.lower() == ".csv":
        csv_files.append(data_path)
    elif data_path.is_dir():
        csv_files.extend(data_path.glob("*.csv"))

    return [f for f in csv_files if "_fitted" not in f.name and "_traces" not in f.name]


def get_dataframe(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:
        raise ValueError(f"Failed to read CSV file: {exc}") from exc

    if df.empty:
        raise ValueError(f"CSV file is empty: {csv_path}")

    return df


def extract_roi_quality_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if "roi" not in df.columns or "is_good" not in df.columns:
        raise ValueError("DataFrame must contain 'roi' and 'is_good' columns")

    roi_quality = df.groupby("roi")["is_good"].first().reset_index()
    roi_quality["roi"] = roi_quality["roi"].astype(int)
    return roi_quality[["roi", "is_good"]]


def extract_roi_feature_dataframe(df: pd.DataFrame, roi_id: int) -> pd.DataFrame:
    roi_df = df[df["roi"] == roi_id].copy()
    if roi_df.empty:
        raise ValueError(f"ROI ID {roi_id} not found in DataFrame")

    feature_cols = [col for col in df.columns if col not in _BASE_TRACE_COLUMNS]

    roi_df = roi_df.sort_values("frame")
    result_df = pd.DataFrame({"frame": roi_df["frame"]})
    for feature in feature_cols:
        result_df[feature] = roi_df[feature].values
    return result_df


def write_dataframe(df: pd.DataFrame, csv_path: Path, **kwargs) -> None:
    if df.empty:
        raise ValueError("Cannot write empty DataFrame to CSV")

    try:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv_path, index=False, **kwargs)
    except Exception as exc:
        raise ValueError(f"Failed to write CSV file: {exc}") from exc


def update_roi_quality(df: pd.DataFrame, quality_df: pd.DataFrame) -> pd.DataFrame:
    if "roi" not in df.columns or "is_good" not in df.columns:
        raise ValueError("Original DataFrame must contain 'roi' and 'is_good' columns")

    if "roi" not in quality_df.columns or "is_good" not in quality_df.columns:
        raise ValueError("Quality DataFrame must contain 'roi' and 'is_good' columns")

    updated_df = df.copy()
    quality_map = dict(zip(quality_df["roi"], quality_df["is_good"]))
    updated_df["is_good"] = (
        updated_df["roi"]
        .map(quality_map)
        .infer_objects(copy=False)
        .fillna(updated_df["is_good"])
    )
    return updated_df


def extract_roi_position_dataframe(df: pd.DataFrame, roi_id: int) -> pd.DataFrame:
    roi_df = df[df["roi"] == roi_id].copy()
    if roi_df.empty:
        raise ValueError(f"ROI ID {roi_id} not found in DataFrame")

    roi_df = roi_df.sort_values("frame")
    return pd.DataFrame(
        {
            "frame": roi_df["frame"].values,
            "x": roi_df["x"].values,
            "y": roi_df["y"].values,
        }
    )


def extract_all_rois_data(df: pd.DataFrame) -> dict:
    quality_df = extract_roi_quality_dataframe(df)
    roi_ids = quality_df["roi"].unique()

    result = {}
    for roi_id in roi_ids:
        str_id = str(int(roi_id))
        quality = bool(quality_df[quality_df["roi"] == roi_id]["is_good"].iloc[0])

        features_df = extract_roi_feature_dataframe(df, int(roi_id))
        features = {col: features_df[col].values for col in features_df.columns}

        positions_df = extract_roi_position_dataframe(df, int(roi_id))
        positions = {
            "frames": positions_df["frame"].values,
            "x": positions_df["x"].values,
            "y": positions_df["y"].values,
        }

        result[str_id] = {
            "quality": quality,
            "features": features,
            "positions": positions,
        }

    return result


__all__ = [
    "DEFAULT_ANALYSIS_FRAME_INTERVAL_MINUTES",
    "create_analysis_dataframe",
    "discover_csv_files",
    "extract_all_rois_data",
    "extract_roi_feature_dataframe",
    "extract_roi_position_dataframe",
    "extract_roi_quality_dataframe",
    "get_analysis_stats",
    "get_dataframe",
    "load_analysis_csv",
    "update_roi_quality",
    "write_analysis_csv",
    "write_dataframe",
]
