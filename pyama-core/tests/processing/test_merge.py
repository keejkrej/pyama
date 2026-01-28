#!/usr/bin/env python3
"""
Test script for PyAMA merge functionality.

This script tests merging processing results from multiple FOVs into tidy CSV files
for analysis. It tests:
- FOV range parsing
- Merge execution with file discovery

Usage:
    python test_merge.py
"""

from pathlib import Path
import pandas as pd
import yaml
from tempfile import TemporaryDirectory

from pyama_core.processing.merge import (
    parse_fov_range,
    run_merge,
)
from pyama_core.io import naming


def test_fov_range_parsing():
    """Test parsing of FOV range strings like "0-2, 4, 6-7"."""
    print("="*60)
    print("Testing FOV Range Parsing")
    print("="*60)

    test_cases = [
        ("0-2, 4, 6-7", [0, 1, 2, 4, 6, 7]),
        ("1,3,5", [1, 3, 5]),
        ("0-5", [0, 1, 2, 3, 4, 5]),
        ("10-12, 15", [10, 11, 12, 15]),
    ]

    print("Test cases:")
    for input_str, expected in test_cases:
        result = parse_fov_range(input_str)
        status = "✓" if result == expected else "❌"
        print(f"   {status} '{input_str}' -> {result}")
        if result != expected:
            print(f"      Expected: {expected}")

    print("\n✓ FOV range parsing tests completed\n")


def test_merge_functionality():
    """Test merging processing results into tidy CSV files."""
    print("="*60)
    print("Testing Merge Functionality")
    print("="*60)

    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_dir = tmp_path / "processed"

        # Create sample configuration YAML
        print("1. Creating sample configuration...")
        samples_yaml = tmp_path / "samples.yaml"
        samples_config = {
            "samples": [
                {
                    "name": "sample",
                    "fovs": "0"
                }
            ]
        }
        with samples_yaml.open("w", encoding="utf-8") as f:
            yaml.safe_dump(samples_config, f, sort_keys=False)

        print(f"   Created: {samples_yaml}")
        print(f"   Content:\n{yaml.dump(samples_config, sort_keys=False)}")

        # Create FOV directory structure with traces CSV
        print("\n2. Creating FOV directory structure...")
        fov_dir = naming.fov_dir(input_dir, 0)
        fov_dir.mkdir(parents=True, exist_ok=True)

        traces_csv = fov_dir / "test_fov_000_traces.csv"
        traces_data = pd.DataFrame({
            "fov": [0, 0],
            "time": [0.0, 1.0],
            "cell": [1, 1],
            "good": [True, True],
            "area_ch_0": [10.0, 12.0],
            "intensity_total_ch_1": [100.0, 110.0],
        })
        traces_data.to_csv(traces_csv, index=False)

        print(f"   Created FOV dir: {fov_dir}")
        print(f"   Created traces: {traces_csv}")
        print(f"   Content:\n{traces_data.to_string()}")

        # Create processing config YAML
        print("\n3. Creating processing config YAML...")
        config_yaml = input_dir / "processing_config.yaml"
        config_data = {
            "channels": {
                "pc": {0: ["area"]},
                "fl": {1: ["intensity_total"]},
            },
            "params": {},
        }
        with config_yaml.open("w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f, sort_keys=False)

        print(f"   Created: {config_yaml}")
        print(f"   Content:\n{yaml.dump(config_data, sort_keys=False)}")

        # Verify FOV discovery
        print("\n4. Verifying FOV discovery...")
        discovered_fovs = naming.discover_fovs(input_dir)
        print(f"   Discovered FOVs: {discovered_fovs}")

        # Run merge
        print("\n5. Running merge...")
        output_dir = tmp_path / "merged"
        message = run_merge(
            sample_yaml=samples_yaml,
            output_dir=output_dir,
            input_dir=input_dir,
        )
        print(f"   Result: {message}")

        # Check outputs
        print("\n6. Checking output files...")
        pc_output = output_dir / "sample_area_ch_0.csv"
        fl_output = output_dir / "sample_intensity_total_ch_1.csv"

        if pc_output.exists():
            print(f"   ✓ Phase contrast output: {pc_output.name}")
            pc_df = pd.read_csv(pc_output, comment="#")
            print(f"     Columns: {list(pc_df.columns)}")
            print("     Expected: ['time', 'fov', 'cell', 'value']")
            print(f"     Data:\n{pc_df.to_string()}")

            expected_columns = ["time", "fov", "cell", "value"]
            if list(pc_df.columns) == expected_columns:
                print("     ✓ Column format correct (tidy format)")
            else:
                print("     ❌ Column format incorrect")
        else:
            print("   ❌ Phase contrast output missing!")

        if fl_output.exists():
            print(f"\n   ✓ Fluorescence output: {fl_output.name}")
            fl_df = pd.read_csv(fl_output, comment="#")
            print(f"     Columns: {list(fl_df.columns)}")
            print("     Expected: ['time', 'fov', 'cell', 'value']")
            print(f"     Data:\n{fl_df.to_string()}")

            expected_columns = ["time", "fov", "cell", "value"]
            if list(fl_df.columns) == expected_columns:
                print("     ✓ Column format correct (tidy format)")
            else:
                print("     ❌ Column format incorrect")
        else:
            print("\n   ❌ Fluorescence output missing!")

        print("\n✓ Merge functionality tests completed\n")


def main():
    """Run all merge functionality tests."""
    print("="*60)
    print("PyAMA Merge Functionality Testing")
    print("="*60)
    print()

    test_fov_range_parsing()
    test_merge_functionality()

    print("="*60)
    print("✓ All merge tests completed successfully!")
    print("="*60)


if __name__ == "__main__":
    main()
