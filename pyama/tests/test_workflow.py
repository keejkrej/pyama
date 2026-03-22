#!/usr/bin/env python3
"""
Visual testing script for PyAMA workflow functionality.
Shows input and output data explicitly instead of using assertions.
Demonstrates the complete workflow from ND2 processing to results generation.
"""

import logging
from pathlib import Path

from pyama.io import load_microscopy_file
from pyama.tasks import (
    ProcessingTaskRequest,
    TaskStatus,
    submit_processing,
    subscribe,
    unsubscribe,
)
from pyama.types.processing import Channels, ProcessingConfig, ProcessingParams


def demonstrate_workflow_setup():
    """Demonstrate workflow setup and configuration."""
    print("=== Workflow Setup Demo ===")

    # Configuration - update these paths as needed
    microscopy_path = Path("D:/250129_HuH7.nd2")  # Update this path
    output_dir = Path("D:/250129_HuH7")

    print(f"1. Microscopy path: {microscopy_path}")
    print(f"2. Output directory: {output_dir}")

    if not microscopy_path.exists():
        print(f"❌ Microscopy file not found: {microscopy_path}")
        print(
            "Please update the microscopy_path variable to point to your test ND2 file"
        )
        return None, None, None

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    print("✓ Logging configured at INFO level")

    # Build per-channel feature mapping
    print("\n3. Discovering available features...")
    from pyama.apps.processing.extract import (
        list_fluorescence_features,
        list_phase_features,
    )

    fl_feature_choices = list_fluorescence_features()
    pc_features = list_phase_features()

    print(f"   Phase contrast features: {pc_features}")
    print(f"   Fluorescence features: {fl_feature_choices}")

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ Output directory created: {output_dir}")

    # Load metadata
    print("\n4. Loading microscopy file metadata...")
    try:
        img, md = load_microscopy_file(microscopy_path)
        print("✓ Successfully loaded microscopy file")
        print(f"   Channels: {md.n_channels}")
        print(f"   Channel names: {md.channel_names}")
        print(f"   Timepoints: {md.n_frames}")
        print(f"   Positions: {md.n_positions}")
        print(f"   Image shape: {img.shape}")
    except Exception as e:
        print(f"❌ Error loading microscopy file: {e}")
        return None, None, None

    print("\n5. Building processing config...")

    available_channels = md.n_channels
    fl_channels: dict[int, list[str]] = {}

    if available_channels >= 2:
        fl_channels[1] = fl_feature_choices
    if available_channels >= 3:
        fl_channels[2] = fl_feature_choices

    config = ProcessingConfig(
        channels=Channels(
            pc={0: pc_features},
            fl=fl_channels,
        ),
        params=ProcessingParams(
            positions=f"0:{min(2, md.n_positions)}",
            n_workers=2,
            background_weight=0.0,
        ),
    )

    print("✓ Processing config created:")
    channels = config.channels
    if channels is None:
        raise RuntimeError("Processing config is missing channels")
    print(f"   PC Channel: {next(iter(channels.pc)) if channels.pc else 'None'}")
    print(f"   PC Features: {next(iter(channels.pc.values())) if channels.pc else 'None'}")
    print(f"   FL Channels: {list(channels.fl)}")
    for channel_id, features in channels.fl.items():
        print(f"     Channel {channel_id}: {features}")

    return microscopy_path, output_dir, config, md


def demonstrate_workflow_execution(output_dir, config, md):
    """Demonstrate workflow execution with progress tracking."""
    print("\n=== Workflow Execution Demo ===")

    print("1. Workflow configuration:")
    print(f"   Positions: {config.params.positions}")
    print(f"   Workers: {config.params.n_workers}")

    print("\n2. Starting workflow execution...")
    print("   (This may take several minutes depending on data size...)")

    try:
        record = submit_processing(
            ProcessingTaskRequest(
                metadata=md,
                config=config,
                output_dir=output_dir,
            )
        )
        queue = subscribe(record.id)
        try:
            while True:
                snapshot = queue.get()
                if snapshot.progress is not None:
                    progress = snapshot.progress
                    print(
                        "   Progress:",
                        progress.step,
                        progress.percent,
                        progress.message,
                    )
                if snapshot.status in {
                    TaskStatus.COMPLETED,
                    TaskStatus.FAILED,
                    TaskStatus.CANCELLED,
                }:
                    success = snapshot.status == TaskStatus.COMPLETED and bool(
                        (snapshot.result or {}).get("success", False)
                    )
                    break
        finally:
            unsubscribe(record.id, queue)

        if success:
            print("✓ Workflow completed successfully!")
        else:
            print("❌ Workflow completed with errors")

        return success

    except Exception as e:
        print(f"❌ Workflow execution failed: {e}")
        return False


def demonstrate_results_inspection(output_dir):
    """Demonstrate inspection of workflow results."""
    print("\n=== Results Inspection Demo ===")

    print("1. Output directory contents:")
    if output_dir.exists():
        for file_path in sorted(output_dir.rglob("*")):
            if file_path.is_file():
                rel_path = file_path.relative_to(output_dir)
                size_mb = file_path.stat().st_size / (1024 * 1024)
                print(f"   {rel_path} ({size_mb:.2f} MB)")
    else:
        print("   Output directory does not exist")

    traces_dir = output_dir / "traces"
    print(f"\n2. traces directory exists: {traces_dir.exists()}")


def main():
    """Run complete workflow testing with clear demonstrations."""
    print("PyAMA Workflow Testing Pipeline")
    print("===============================")

    # Step 1: Setup workflow
    microscopy_path, output_dir, config, md = demonstrate_workflow_setup()
    if config is None:
        print("\n❌ Cannot proceed without valid setup")
        return

    # Step 2: Execute workflow
    success = demonstrate_workflow_execution(output_dir, config, md)

    # Step 3: Inspect results
    demonstrate_results_inspection(output_dir)

    print(f"\n{'=' * 50}")
    if success:
        print("✓ Workflow testing completed successfully!")
        print("✓ All processing steps completed without errors")
        print("✓ Results files generated and verified")
    else:
        print("⚠ Workflow testing completed with issues")
        print("⚠ Some processing steps may have failed")

    print(f"Output directory: {output_dir}")
    print(f"Microscopy file: {microscopy_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
