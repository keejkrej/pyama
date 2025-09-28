"""
Analysis CSV format definitions for PyAMA sample data.

This module defines simple utilities for handling CSV files consumed by the
analysis module. The format uses time as index and cells as columns.

Format: time (hours) as index, cell IDs (0,1,2,3...) as columns
"""

import pandas as pd
from pathlib import Path


def write_analysis_csv(
    df: pd.DataFrame, output_path: Path, time_units: str | None = None
) -> None:
    """
    Write sample data to analysis CSV format.

    Args:
        df: DataFrame with time as index and cell IDs as columns
        output_path: Path where to save the CSV file
        time_units: Optional time units to include as comment header
    """
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Prepare DataFrame for writing
    df_to_write = df.copy()
    df_to_write.index.name = "time"
    df_to_write.columns = [str(col) for col in df_to_write.columns]

    # Write CSV
    with open(output_path, "w", newline="") as f:
        if time_units:
            f.write(f"# Time units: {time_units}\n")
        df_to_write.to_csv(f, index=True, header=True, float_format="%.6f")


def load_analysis_csv(csv_path: Path) -> pd.DataFrame:
    """
    Load an existing analysis CSV file.

    Args:
        csv_path: Path to the analysis CSV file

    Returns:
        DataFrame with analysis data
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Analysis CSV file not found: {csv_path}")

    # Read time units from comment header
    time_units = None
    with open(csv_path, "r") as f:
        first_line = f.readline().strip()
        if first_line.startswith("# Time units:"):
            time_units = first_line.split(":", 1)[1].strip().lower()

    # Load CSV
    df = pd.read_csv(csv_path, index_col=0, comment="#")

    # Basic cleanup
    df.index = pd.to_numeric(df.index, errors="coerce")
    df.index.name = "time"

    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df.columns = [str(col) for col in df.columns]

    # Convert time to hours if needed
    if time_units:
        conversion_factors = {
            "seconds": 1 / 3600,
            "sec": 1 / 3600,
            "s": 1 / 3600,
            "minutes": 1 / 60,
            "min": 1 / 60,
            "m": 1 / 60,
            "hours": 1,
            "hour": 1,
            "h": 1,
            "hr": 1,
            "hrs": 1,
        }
        if time_units in conversion_factors:
            factor = conversion_factors[time_units]
            if factor != 1:
                df.index = df.index * factor

    return df


def create_analysis_dataframe(
    time_values: list[float], cell_data: dict[int, list[float]]
) -> pd.DataFrame:
    """
    Create a properly formatted analysis DataFrame.

    Args:
        time_values: List of time points in hours
        cell_data: Dictionary mapping cell IDs to values

    Returns:
        DataFrame formatted for analysis CSV
    """
    # Ensure cell IDs are sequential starting from 0
    max_cell_id = max(cell_data.keys()) if cell_data else -1
    expected_cell_ids = list(range(max_cell_id + 1))

    # Create DataFrame with time as index
    df_data = {}
    for cell_id in expected_cell_ids:
        if cell_id in cell_data:
            df_data[cell_id] = cell_data[cell_id]
        else:
            df_data[cell_id] = [float("nan")] * len(time_values)

    df = pd.DataFrame(df_data, index=time_values)
    df.index.name = "time"

    return df


def get_analysis_stats(df: pd.DataFrame) -> dict:
    """
    Extract statistics from an analysis DataFrame.

    Args:
        df: Analysis DataFrame

    Returns:
        Dictionary with sample statistics
    """
    return {
        "time_points": len(df),
        "cell_count": len(df.columns),
        "duration_hours": df.index.max() - df.index.min() if len(df) > 1 else 0,
        "time_interval": df.index.to_series().diff().median() if len(df) > 1 else 0,
        "missing_values": df.isnull().sum().sum(),
        "complete_traces": (df.isnull().sum() == 0).sum(),
    }


def discover_csv_files(data_path: Path | str) -> list[Path]:
    """
    Discover CSV files for analysis.

    Args:
        data_path: Path to a CSV file or directory containing CSV files

    Returns:
        List of CSV file paths
    """
    data_path = Path(data_path)
    csv_files = []

    if data_path.is_file() and data_path.suffix.lower() == ".csv":
        csv_files.append(data_path)
    elif data_path.is_dir():
        csv_files.extend(data_path.glob("*.csv"))

    return [f for f in csv_files if "_fitted" not in f.name and "_traces" not in f.name]
