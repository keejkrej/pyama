"""Generate fake sample CSV files for testing the comparison tab.

This script generates realistic-looking maturation traces with noise
in the tidy CSV format expected by load_analysis_csv.

Usage:
    python tests/generate_fake_samples.py [output_dir] [num_samples]

Output format (per load_analysis_csv):
    frame,fov,cell,value
    0,0,0,1.234
    0,0,1,2.345
    ...
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def maturation_curve(
    t: np.ndarray,
    t0: float = 0.5,
    ktl: float = 1000.0,
    km: float = 1.28,
    delta: float = 0.01,
    beta: float = 5.22e-3,
    offset: float = 100.0,
) -> np.ndarray:
    """Generate a maturation curve (simplified model)."""
    dt = t - t0
    bmd = beta - delta

    f1 = np.exp(-(beta + km) * dt) / (bmd + km)
    f2 = -np.exp(-beta * dt) / bmd
    f3 = km / bmd / (bmd + km) * np.exp(-delta * dt)

    result = (f1 + f2 + f3) * ktl
    normalized_result = np.where(dt > 0, result, 0)
    return normalized_result + offset


def generate_sample(
    num_cells: int,
    num_frames: int = 60,
    frame_interval: float = 1 / 6,
    noise_level: float = 0.1,
    rng: np.random.Generator | None = None,
) -> pd.DataFrame:
    """Generate a fake sample with multiple cell traces.

    Args:
        num_cells: Number of cells to generate
        num_frames: Number of time frames
        frame_interval: Time interval per frame in hours
        noise_level: Relative noise level (0.1 = 10% of signal)
        rng: Random number generator

    Returns:
        DataFrame in tidy format with columns: frame, fov, cell, value
    """
    if rng is None:
        rng = np.random.default_rng()

    frames = np.arange(num_frames)
    time = frames * frame_interval

    rows = []
    for cell_id in range(num_cells):
        # Randomize parameters slightly for each cell
        t0 = rng.uniform(0.2, 1.0)
        ktl = rng.uniform(500, 2000)
        delta = rng.uniform(0.005, 0.02)
        offset = rng.uniform(50, 200)

        # Generate base curve
        curve = maturation_curve(time, t0=t0, ktl=ktl, delta=delta, offset=offset)

        # Add noise
        noise = rng.normal(0, noise_level * np.mean(curve), size=len(curve))
        noisy_curve = curve + noise

        # Create rows for this cell (fov=0 for single-FOV samples)
        for frame_idx, value in enumerate(noisy_curve):
            rows.append(
                {
                    "frame": frame_idx,
                    "fov": 0,
                    "cell": cell_id,
                    "value": max(0, value),  # Ensure non-negative
                }
            )

    return pd.DataFrame(rows)


def generate_samples(
    output_dir: Path,
    num_samples: int = 5,
    seed: int = 42,
) -> list[Path]:
    """Generate multiple fake sample files.

    Args:
        output_dir: Directory to save samples
        num_samples: Number of sample files to generate
        seed: Random seed for reproducibility

    Returns:
        List of generated file paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(seed)
    generated_files = []

    for i in range(num_samples):
        # Vary cell count between samples
        num_cells = rng.integers(20, 51)

        # Generate sample data
        df = generate_sample(
            num_cells=num_cells,
            num_frames=60,
            frame_interval=1 / 6,  # 10 min per frame
            noise_level=0.15,
            rng=rng,
        )

        # Save to CSV
        filename = f"sample_{i + 1:02d}.csv"
        filepath = output_dir / filename
        df.to_csv(filepath, index=False)
        generated_files.append(filepath)
        print(f"Generated {filepath} ({num_cells} cells, {len(df)} rows)")

    return generated_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate fake sample CSV files")
    parser.add_argument(
        "output_dir",
        nargs="?",
        default="tests/_fake_samples",
        help="Output directory (default: tests/_fake_samples)",
    )
    parser.add_argument(
        "num_samples",
        nargs="?",
        type=int,
        default=5,
        help="Number of samples to generate (default: 5)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )

    args = parser.parse_args()
    generate_samples(Path(args.output_dir), args.num_samples, args.seed)


if __name__ == "__main__":
    main()
