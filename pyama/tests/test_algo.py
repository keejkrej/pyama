#!/usr/bin/env python3
"""
Visual testing script for PyAMA core algorithm functionality.
Shows input and output data explicitly instead of using assertions.
Demonstrates the complete processing pipeline from ND2 file to model fitting.
"""

from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.ndimage import binary_closing, binary_fill_holes, binary_opening, uniform_filter
from scipy.optimize import linear_sum_assignment
from skimage.measure import label, regionprops
from pyama.io import load_microscopy_file, get_microscopy_time_stack
from pyama.apps.modeling.fitting import fit_model
from pyama.apps.modeling.models import get_model


def _segment_frame(frame: np.ndarray) -> np.ndarray:
    frame_f = np.asarray(frame, dtype=np.float32)
    mask_size = 3
    mean = uniform_filter(frame_f, size=mask_size)
    mean_sq = uniform_filter(frame_f * frame_f, size=mask_size)
    var = mean_sq - mean * mean
    logstd = np.zeros_like(frame_f, dtype=np.float32)
    positive = var > 0
    logstd[positive] = 0.5 * np.log(var[positive])
    flat = logstd.ravel()
    counts, edges = np.histogram(flat, bins=200)
    bins = (edges[:-1] + edges[1:]) * 0.5
    hist_max = bins[int(np.argmax(counts))]
    background_vals = flat[flat <= hist_max]
    sigma = np.std(background_vals) if background_vals.size else 0.0
    thresh = float(hist_max + (3.0 * sigma))
    binary = binary_fill_holes(logstd > thresh)
    struct = np.ones((7, 7))
    binary = binary_opening(binary, iterations=3, structure=struct)
    binary = binary_closing(binary, iterations=3, structure=struct)
    return np.asarray(label(binary, connectivity=1), dtype=bool)


def _track_stack(image: np.ndarray, out: np.ndarray, progress_callback=None) -> None:
    image = image.astype(np.uint16, copy=False)
    out = out.astype(np.uint16, copy=False)
    n_frames = image.shape[0]

    regions_all = []
    for t in range(n_frames):
        frame_regions = {}
        for prop in regionprops(image[t]):
            frame_regions[int(prop.label)] = {
                "bbox": tuple(int(v) for v in prop.bbox),
                "coords": prop.coords,
            }
        regions_all.append(frame_regions)

    seed_frame = 0
    while seed_frame < n_frames and not regions_all[seed_frame]:
        seed_frame += 1
    if seed_frame >= n_frames:
        return

    traces = [{seed_frame: label} for label in regions_all[seed_frame]]
    prev_map = {label: idx for idx, label in enumerate(regions_all[seed_frame])}
    prev_regions = regions_all[seed_frame]

    for t in range(seed_frame + 1, n_frames):
        prev_labels = list(prev_map.keys())
        curr_labels = list(regions_all[t].keys())
        if not prev_labels or not curr_labels:
            prev_map = {}
            prev_regions = {}
            continue

        cost = np.ones((len(prev_labels), len(curr_labels)), dtype=float)
        valid = np.zeros_like(cost, dtype=bool)
        for i, prev_label in enumerate(prev_labels):
            ay0, ax0, ay1, ax1 = prev_regions[prev_label]["bbox"]
            for j, curr_label in enumerate(curr_labels):
                by0, bx0, by1, bx1 = regions_all[t][curr_label]["bbox"]
                inter_y0 = max(ay0, by0)
                inter_x0 = max(ax0, bx0)
                inter_y1 = min(ay1, by1)
                inter_x1 = min(ax1, bx1)
                inter_h = inter_y1 - inter_y0
                inter_w = inter_x1 - inter_x0
                if inter_h <= 0 or inter_w <= 0:
                    continue
                inter_area = inter_h * inter_w
                a_area = max(0, (ay1 - ay0) * (ax1 - ax0))
                b_area = max(0, (by1 - by0) * (bx1 - bx0))
                union = a_area + b_area - inter_area
                if union <= 0:
                    continue
                iou = float(inter_area) / float(union)
                if iou >= 0.1:
                    cost[i, j] = 1.0 - iou
                    valid[i, j] = True

        row_ind, col_ind = linear_sum_assignment(cost)
        new_prev_map = {}
        new_prev_regions = {}
        for row, col in zip(row_ind, col_ind):
            if not valid[row, col]:
                continue
            prev_label = prev_labels[row]
            curr_label = curr_labels[col]
            trace_id = prev_map.get(prev_label)
            if trace_id is None:
                continue
            traces[trace_id][t] = curr_label
            new_prev_map[curr_label] = trace_id
            new_prev_regions[curr_label] = regions_all[t][curr_label]
        prev_map = new_prev_map
        prev_regions = new_prev_regions
        if progress_callback is not None:
            progress_callback(t, n_frames, "Tracking")

    out[...] = 0
    for roi_id, trace in enumerate(traces, start=1):
        for frame_idx, roi_label in trace.items():
            region = regions_all[frame_idx].get(roi_label)
            if region is None:
                continue
            ys = region["coords"][:, 0]
            xs = region["coords"][:, 1]
            out[frame_idx, ys, xs] = roi_id


def _extract_trace_dataframe_local(
    image: np.ndarray,
    seg_labeled: np.ndarray,
    background: np.ndarray,
    progress_callback=None,
    background_weight: float = 1.0,
) -> pd.DataFrame:
    rows = []
    n_frames = image.shape[0]
    for frame_idx in range(n_frames):
        roi_ids = np.unique(seg_labeled[frame_idx])
        roi_ids = roi_ids[roi_ids > 0]
        for roi_id in roi_ids:
            mask = seg_labeled[frame_idx] == roi_id
            ys, xs = np.where(mask)
            if ys.size == 0 or xs.size == 0:
                continue
            rows.append(
                {
                    "cell": int(roi_id),
                    "frame": int(frame_idx),
                    "area": float(np.count_nonzero(mask)),
                    "intensity": float(
                        (
                            image[frame_idx].astype(np.float32)
                            - (float(background_weight) * background[frame_idx].astype(np.float32))
                        )[np.asarray(mask, dtype=bool)].sum()
                    ),
                }
            )
        if progress_callback is not None:
            progress_callback(frame_idx, n_frames, "Extract")

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["time"] = df["frame"].astype(float)
    df.set_index(["cell", "time"], inplace=True)
    return df


def progress_callback(current, total, message):
    """Progress callback for processing functions."""
    if current % 30 == 0:
        print(f"  {message}: {current}/{total}")


def demonstrate_nd2_loading():
    """Demonstrate ND2 file loading and channel extraction."""
    print("=== ND2 File Loading Demo ===")

    # Configuration - update this path to your test ND2 file
    nd2_path = Path("../data/test_sample.nd2")

    if not nd2_path.exists():
        print(f"❌ ND2 file not found: {nd2_path}")
        print("Please update the nd2_path variable to point to your test ND2 file")
        return None, None, None

    try:
        print(f"Loading ND2 file: {nd2_path}")
        img, metadata = load_microscopy_file(nd2_path)

        print("✓ Successfully loaded ND2 file")
        print(f"  Channels: {metadata.n_channels}")
        print(f"  Channel names: {metadata.channel_names}")
        print(f"  Timepoints: {metadata.n_frames}")
        print(f"  Image shape: {img.shape}")

        # Extract phase contrast (typically channel 0) and fluorescence (channel 1)
        if metadata.n_channels < 2:
            print(
                "❌ ND2 file must have at least 2 channels (phase contrast + fluorescence)"
            )
            return None, None, None

        print("Extracting time stacks for channels 0 and 1...")
        phc_data = get_microscopy_time_stack(img, position=0, channel=0)
        fluor_data = get_microscopy_time_stack(img, position=0, channel=1)

        print(f"✓ Phase contrast shape: {phc_data.shape}")
        print(f"✓ Fluorescence shape: {fluor_data.shape}")

        return phc_data, fluor_data, metadata

    except Exception as e:
        print(f"❌ Error loading ND2 file: {e}")
        return None, None, None


def demonstrate_original_images(phc_data, fluor_data, output_dir):
    """Display original images from ND2 file."""
    print("\n=== Original Images Demo ===")

    fig, axs = plt.subplots(1, 2, figsize=(8, 4), constrained_layout=True)
    time_idx = min(100, len(phc_data) - 1)  # Use frame 100 or last available frame

    print(f"Displaying frame {time_idx}")

    axs[0].imshow(phc_data[time_idx], cmap="gray")
    axs[0].set_title("Phase Contrast")
    axs[1].imshow(fluor_data[time_idx], cmap="hot")
    axs[1].set_title("Fluorescence")
    axs[0].axis("off")
    axs[1].axis("off")

    output_path = output_dir / "original_images.png"
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"✓ Saved original images to: {output_path}")


def demonstrate_segmentation(phc_data, output_dir):
    """Demonstrate cell segmentation functionality."""
    print("\n=== Cell Segmentation Demo ===")

    seg_path = output_dir / "segmentation.npy"

    if seg_path.exists():
        print("Loading existing segmentation...")
        seg_data = np.load(seg_path)
        print(f"✓ Loaded segmentation from: {seg_path}")
    else:
        print("Running cell segmentation...")
        seg_data = np.empty_like(phc_data, dtype=bool)
        n_frames = phc_data.shape[0]
        for time_idx, frame in enumerate(phc_data):
            seg_data[time_idx] = _segment_frame(frame)
            progress_callback(time_idx, n_frames, "Segmentation")
        np.save(seg_path, seg_data)
        print(f"✓ Segmentation completed and saved to: {seg_path}")

    # Display segmentation result
    time_idx = min(100, len(phc_data) - 1)
    fig, axs = plt.subplots(1, 2, figsize=(8, 4), constrained_layout=True)
    axs[0].imshow(phc_data[time_idx], cmap="gray")
    axs[0].set_title("Phase Contrast")
    axs[1].imshow(seg_data[time_idx], cmap="gray")
    axs[1].set_title("Segmentation")
    axs[0].axis("off")
    axs[1].axis("off")

    output_path = output_dir / "segmentation.png"
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"✓ Saved segmentation visualization to: {output_path}")

    return seg_data


def demonstrate_cell_tracking(seg_data, output_dir):
    """Demonstrate cell tracking functionality."""
    print("\n=== Cell Tracking Demo ===")

    labeled_path = output_dir / "tracked_segmentation.npy"

    if labeled_path.exists():
        print("Loading existing tracking...")
        tracked_data = np.load(labeled_path)
        print(f"✓ Loaded tracking from: {labeled_path}")
    else:
        print("Running cell tracking...")
        tracked_data = np.zeros_like(seg_data, dtype=np.uint16)
        _track_stack(seg_data, tracked_data, progress_callback=progress_callback)
        np.save(labeled_path, tracked_data)
        print(f"✓ Cell tracking completed and saved to: {labeled_path}")

    # Display tracking result
    fig, axs = plt.subplots(1, 4, figsize=(12, 3), constrained_layout=True)
    time_steps = np.linspace(0, len(tracked_data) - 1, 4, dtype=int)

    for i, t in enumerate(time_steps):
        fr = tracked_data[t]
        # Highlight a few specific cells for visualization
        highlighted = np.where(np.isin(fr, [50, 60, 70]), fr, 0)
        axs[i].imshow(highlighted, cmap="hot")
        axs[i].set_title(f"Frame {t}")
        axs[i].axis("off")

    output_path = output_dir / "cell_tracking.png"
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"✓ Saved tracking visualization to: {output_path}")

    return tracked_data


def demonstrate_feature_extraction(fluorescence_data, tracked_data, output_dir):
    """Demonstrate feature extraction functionality."""
    print("\n=== Feature Extraction Demo ===")

    trace_path = output_dir / "cell_traces.csv"

    if trace_path.exists():
        print("Loading existing traces...")
        df = pd.read_csv(trace_path)
        print(f"✓ Loaded traces from: {trace_path}")
    else:
        print("Running feature extraction...")
        # Create zeros background for test (no background correction in demo)
        test_background = np.zeros_like(fluorescence_data, dtype=np.float32)
        df = _extract_trace_dataframe_local(
            fluorescence_data,
            tracked_data,
            test_background,
            progress_callback,
            background_weight=0.0,
        )
        df.to_csv(trace_path)
        print(f"✓ Feature extraction completed and saved to: {trace_path}")

    print("Extracted features:")
    print(f"  Total traces: {len(df)}")
    print(f"  Unique cells: {df['cell'].nunique()}")
    print(f"  Frame range: {df['frame'].min()} - {df['frame'].max()}")
    print(f"  Available columns: {list(df.columns)}")

    # Display extracted features
    all_cells = df.index.get_level_values("cell").unique()
    sample_cells = all_cells[: min(5, len(all_cells))]  # Show up to 5 cells

    print(f"\nSample traces for cells {sample_cells[:3]}:")
    for cell in sample_cells[:3]:
        cell_data = df.loc[cell]
        print(
            f"  Cell {cell}: {len(cell_data)} timepoints, "
            f"intensity range: {cell_data['intensity'].min():.1f} - {cell_data['intensity'].max():.1f}"
        )

    # Visualize features
    fig, axs = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)

    for c in sample_cells:
        df.loc[c].plot(y="intensity", ax=axs[0], legend=False, color="green", alpha=0.5)
        df.loc[c].plot(y="area", ax=axs[1], legend=False, color="blue", alpha=0.5)

    axs[0].set_title("Intensity Total (Sample Cells)")
    axs[0].set_xlabel("Time [h]")
    axs[0].set_ylim(0, df["intensity"].max() * 1.1)
    axs[1].set_title("Area (Sample Cells)")
    axs[1].set_ylim(0, df["area"].max() * 1.1)
    axs[1].set_xlabel("Time [h]")

    output_path = output_dir / "extracted_features.png"
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"✓ Saved feature visualization to: {output_path}")

    return df


def demonstrate_model_fitting(df, output_dir):
    """Demonstrate model fitting functionality."""
    print("\n=== Model Fitting Demo ===")

    all_cells = df.index.get_level_values("cell").unique()
    cell_id = all_cells[len(all_cells) // 2]  # Use middle cell

    print(f"Fitting base model to cell {cell_id}")

    y = df.loc[cell_id]["intensity"]
    t = df.loc[cell_id].index.values

    print(f"  Time range: {t.min():.1f} - {t.max():.1f} hours")
    print(f"  Intensity range: {y.min():.1f} - {y.max():.1f}")
    print(f"  Data points: {len(y)}")

    model = get_model("base")
    result = fit_model(
        model,
        t,
        y,
        model.get_fixed_parameters(),
        model.get_fit_parameters(),
    )

    print("✓ Fitting completed:")
    print(f"  R² = {result.r_squared:.3f}")
    print("  Parameters:")
    for param_name, param in result.fitted_params.items():
        print(f"    {param_name} = {param.value:.3g}")

    # Generate fitted curve
    y_pred = model.eval(t, result.fixed_params, result.fitted_params)

    # Visualize fitting result
    fig, axs = plt.subplots(1, 1, figsize=(6, 4), constrained_layout=True)
    axs.plot(t, y, label="data", linewidth=2, marker="o", markersize=3)
    axs.plot(t, y_pred, label="fit", linewidth=2)

    # Add parameter text
    param_text = f"$R^2$ = {result.r_squared:.3f}\n" + "\n".join(
        [f"{k} = {v.value:.3g}" for k, v in result.fitted_params.items()]
    )

    axs.text(
        0.05,
        0.95,
        param_text,
        transform=axs.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
    )

    axs.legend(loc="lower right")
    axs.set_xlabel("Time [h]")
    axs.set_ylabel("Intensity Total")
    axs.set_title(f"Maturation Model Fitting (Cell {cell_id})")

    output_path = output_dir / "model_fitting.png"
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"✓ Saved model fitting visualization to: {output_path}")


def main():
    """Main testing pipeline with clear demonstrations."""
    print("PyAMA Algorithm Testing Pipeline")
    print("===============================")

    # Setup output directory
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Step 1: Load ND2 file
    phc_data, fluor_data, metadata = demonstrate_nd2_loading()
    if phc_data is None:
        print("\n❌ Cannot proceed without valid ND2 file")
        return

    # Step 2: Display original images
    demonstrate_original_images(phc_data, fluor_data, output_dir)

    # Step 3: Segmentation
    seg_data = demonstrate_segmentation(phc_data, output_dir)

    # Step 4: Cell tracking
    tracked_data = demonstrate_cell_tracking(seg_data, output_dir)

    # Step 5: Feature extraction (using raw fluorescence, not background)
    df = demonstrate_feature_extraction(fluor_data, tracked_data, output_dir)

    # Step 6: Model fitting
    demonstrate_model_fitting(df, output_dir)

    print(f"\n{'=' * 50}")
    print("✓ All algorithm tests completed successfully!")
    print(f"Results saved to: {output_dir}")
    print(
        f"Processed {len(df.index.get_level_values('cell').unique())} cells "
        f"across {len(phc_data)} timepoints"
    )
    print("=" * 50)


if __name__ == "__main__":
    main()
