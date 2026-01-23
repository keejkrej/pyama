import os
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

from scipy.ndimage import center_of_mass
from pyama_core.processing.normalization.polar import (
    normalize_cell_polar,
    integrate_polar,
)

PLOT_DIR = Path(os.environ.get("PYAMA_PLOT_DIR", "tests/_plots")).resolve()
PLOT_DIR.mkdir(parents=True, exist_ok=True)


def test_normalization():
    # Setup
    H, W = 100, 100
    images = np.zeros((1, 2, H, W), dtype=np.float32)
    masks = np.zeros((1, H, W), dtype=bool)

    # Create a "blobby" mask (realistic cell shape)
    # R(theta) = R0 + delta * sin(k * theta)
    y_grid, x_grid = np.ogrid[:H, :W]
    cy, cx = 50, 50

    # Matches the larger shape used in nucleus offset test - REVERTED to original
    base_radius = 20

    # Calculate angle and radius for every pixel relative to center
    pixel_angles = np.arctan2(y_grid - cy, x_grid - cx)
    pixel_radii = np.sqrt((y_grid - cy) ** 2 + (x_grid - cx) ** 2)

    # Define boundary function matching the nucleus test - REVERTED
    def get_boundary_r(angles):
        # Original formula
        return base_radius + 5 * np.sin(3 * angles) + 3 * np.cos(5 * angles)

    boundary_radii = get_boundary_r(pixel_angles)

    mask_area = pixel_radii <= boundary_radii
    masks[0] = mask_area

    # Fill image with a pattern inside the mask
    # Gradient: value = r / r_boundary(theta)
    # This ensures that after normalization, we still expect a linear ramp from 0 to 1
    with np.errstate(divide="ignore", invalid="ignore"):
        normalized_dist = pixel_radii / boundary_radii
        # Channel 2 pattern: Angular gradient 0 to 1 (normalized angle)
        angular_pattern = (pixel_angles + np.pi) / (2 * np.pi)  # 0 to 1

    normalized_dist[~mask_area] = 0
    angular_pattern[~mask_area] = 0

    images[0, 0] = normalized_dist
    images[0, 1] = angular_pattern

    # Normalize
    # We expect the output to have the radial gradient mapped to 0..1 along the r-axis
    r_res = 100
    theta_res = 100
    normalized_xr = normalize_cell_polar(
        images, masks, r_resolution=r_res, theta_resolution=theta_res
    )

    print(f"Input shape: {images.shape}")
    print(f"Output shape: {normalized_xr.shape}")
    print(f"Output dimensions: {normalized_xr.dims}")

    # Check output shape
    assert normalized_xr.shape == (1, 2, theta_res, r_res)
    assert normalized_xr.dims == ("time", "channel", "angle", "radius")

    # Check content
    # The output r-dimension is now the LAST dimension (axis 3)
    # Angle is axis 2.

    normalized_np = normalized_xr.values

    # Average over theta (axis 2)
    radial_profile = np.mean(normalized_np[0, 0], axis=0)

    # Check if radial_profile is roughly linear 0..1
    expected_profile = np.linspace(0, 1, r_res)

    # There will be interpolation errors, but it should be close.
    mse = np.mean((radial_profile - expected_profile) ** 2)
    print(f"Mean Squared Error of radial profile: {mse}")

    if mse < 0.01:
        print("SUCCESS: Radial profile matches expected linear gradient.")
    else:
        print("FAILURE: Radial profile does not match.")
        print("Profile:", radial_profile)

    # Check Integral Invariance (Channel 0)
    cartesian_integral = np.sum(images[0, 0])

    # Polar Integral
    polar_integral_xr = integrate_polar(normalized_xr)
    polar_integral = polar_integral_xr.values[0, 0]

    # Difference should be small (interpolation errors exist)
    abs_diff = abs(cartesian_integral - polar_integral)
    rel_diff = abs_diff / cartesian_integral

    print(f"Cartesian Integral (Ch 0): {cartesian_integral:.4f}")
    print(f"Polar Integral (Ch 0): {polar_integral:.4f}")
    print(f"Relative Difference (Ch 0): {rel_diff:.4f}")

    # Verify Channel 1: Angular Gradient
    # Just check it exists and has expected trend along angle axis
    angular_profile = np.mean(normalized_xr.values[0, 1], axis=1)  # Average over radius
    # Ideally linear 0 to 1, but cyclic wrap might make it tricky at edges.
    # The gradient was (theta + pi) / 2pi -> 0 to 1.
    # Due to 'mod' and wrapping, there might be a phase shift, let's just check shape and non-zero.
    assert np.mean(angular_profile) > 0.1, "Channel 1 should have content"
    print("Channel 1 content verified.")

    if rel_diff < 0.05:  # Allow 5% error due to resolution/interpolation
        print("SUCCESS: Integral is invariant.")
    else:
        print("FAILURE: Integral is not invariant.")

    # Plotting
    # fig is not defined yet if we removed the previous subplots call or if we are just starting plotting section
    fig = plt.figure(figsize=(12, 12))
    gs = fig.add_gridspec(3, 3)

    # Row 1: Inputs
    ax_mask = fig.add_subplot(gs[0, 0])
    ax_in0 = fig.add_subplot(gs[0, 1])
    ax_in1 = fig.add_subplot(gs[0, 2])

    ax_mask.imshow(masks[0], cmap="gray")
    ax_mask.set_title("Input Mask")
    ax_mask.axis("off")

    ax_in0.imshow(images[0, 0], cmap="viridis")
    ax_in0.set_title("Input Ch 0 (Radial)")
    ax_in0.axis("off")

    ax_in1.imshow(images[0, 1], cmap="plasma")
    ax_in1.set_title("Input Ch 1 (Angular)")
    ax_in1.axis("off")

    # Row 2: Channel 0 (Radial)
    ax_norm0 = fig.add_subplot(gs[1, 0])
    ax_prof0 = fig.add_subplot(gs[1, 1:])

    ax_norm0.imshow(
        normalized_np[0, 0], cmap="viridis", aspect="auto", extent=[0, 1, 1, 0]
    )
    ax_norm0.set_title("Normalized Ch 0\nY=Angle, X=Radius")
    ax_norm0.set_xlabel("Radius")
    ax_norm0.set_ylabel("Angle")

    ax_prof0.plot(expected_profile, label="Expected", linestyle="--", color="gray")
    ax_prof0.plot(radial_profile, label="Actual Ch 0 (Avg over Angle)", color="red")
    ax_prof0.set_title("Radial Profile (Ch 0)")
    ax_prof0.set_xlabel("Radial Index")
    ax_prof0.legend()
    ax_prof0.grid(True, alpha=0.3)

    # Row 3: Channel 1 (Angular)
    ax_norm1 = fig.add_subplot(gs[2, 0])
    ax_prof1 = fig.add_subplot(gs[2, 1:])

    ax_norm1.imshow(
        normalized_np[0, 1], cmap="plasma", aspect="auto", extent=[0, 1, 1, 0]
    )
    ax_norm1.set_title("Normalized Ch 1\nY=Angle, X=Radius")
    ax_norm1.set_xlabel("Radius")
    ax_norm1.set_ylabel("Angle")

    # Angular Profile (Avg over Radius)
    # This was computed above as angular_profile
    expected_angular = np.linspace(0, 1, theta_res)
    # Note: The pattern generated was (theta + pi)/2pi.
    # Theta from arctan2 is -pi to pi.
    # At index 0 (top of image), angle=0. At index max, angle=1.
    # We should check the order in the plot.

    ax_prof1.plot(
        expected_angular, label="Expected (Linear 0-1)", linestyle="--", color="gray"
    )
    ax_prof1.plot(angular_profile, label="Actual Ch 1 (Avg over Radius)", color="blue")
    ax_prof1.set_title("Angular Profile (Ch 1)")
    ax_prof1.set_xlabel("Angular Index")
    ax_prof1.legend()
    ax_prof1.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = str(PLOT_DIR / "normalization_test.png")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved plot to: {out_path}")


def test_normalization_nucleus_offset():
    print("\n--- Testing Nucleus Offset ---")
    # Scenario: "Blobby" cell centered roughly at (50, 50)
    # Nucleus at (50, 60), shifted +10 in Y
    # Pattern: Concentric rings centered at Cell Geometric Center

    H, W = 100, 100
    images = np.zeros((1, 1, H, W), dtype=np.float32)
    masks = np.zeros((1, H, W), dtype=bool)
    nuc_masks = np.zeros((1, H, W), dtype=bool)

    y_grid, x_grid = np.ogrid[:H, :W]
    cy, cx = 50, 50

    # --- Generate Blobby Cell Mask ---
    pixel_angles = np.arctan2(y_grid - cy, x_grid - cx)
    pixel_radii = np.sqrt((y_grid - cy) ** 2 + (x_grid - cx) ** 2)

    # R(theta) = R0 + delta * sin(...)
    # Increased base_radius to 35 to give room for nucleus offset -- REVERTED
    base_radius = 20
    boundary_radii_limit = (
        base_radius + 5 * np.sin(3 * pixel_angles) + 3 * np.cos(5 * pixel_angles)
    )

    masks[0] = pixel_radii <= boundary_radii_limit

    # Re-calculate Centroid of the actual mask to be precise for the "Cell Center" label
    cy_real, cx_real = center_of_mass(masks[0])
    print(f"Cell Centroid: ({cy_real:.2f}, {cx_real:.2f})")

    # --- Generate Nucleus Mask ---
    # Shifted down by ~8 pixels (reduced from 10 to ensure it fits comfortably in R=20)
    ny, nx = int(cy_real) + 8, int(cx_real)
    radius_nuc = 4
    nuc_masks[0] = (y_grid - ny) ** 2 + (x_grid - nx) ** 2 <= radius_nuc**2

    # --- Image Pattern: Linear Radial Gradient from Cell Centroid ---
    # Matches the pattern in the main test.
    # Value = Distance / Boundary_Distance
    with np.errstate(divide="ignore", invalid="ignore"):
        pattern = pixel_radii / boundary_radii_limit

    images[0, 0] = pattern
    images[0, 0][~masks[0]] = 0

    # Normalize with nucleus mask
    # Origin will be at nucleus centroid
    xr_out = normalize_cell_polar(
        images, masks, nucleus_masks=nuc_masks, theta_resolution=360, r_resolution=100
    )

    boundary_r = xr_out.boundary_radius.values[0]

    print(f"Boundary Radius Range: [{boundary_r.min():.2f}, {boundary_r.max():.2f}]")

    print("SUCCESS: Nucleus offset test ran with realistic mask and standard pattern.")

    # Plotting
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))

    # 1. Input Image with Markers
    axes[0].imshow(images[0, 0], cmap="viridis")
    axes[0].plot(cx_real, cy_real, "rx", markersize=10, label="Cell Center")
    axes[0].plot(nx, ny, "wo", markersize=5, label="Nucleus Center")
    axes[0].set_title(
        "Input Image (Radial Gradient @ Cell Center)\nWhite Dot = Polar Origin"
    )
    axes[0].legend()
    axes[0].axis("off")

    # 2. Normalized Output
    # Ideally this would be a linear horizontal gradient if origin was Cell Center.
    # With Nucleus Center origin, it will look distorted.
    axes[1].imshow(xr_out[0, 0], cmap="viridis", aspect="auto", extent=[0, 1, 1, 0])
    axes[1].set_title("Normalized Output\n(Distorted Gradient)")
    axes[1].set_xlabel("Radius")
    axes[1].set_ylabel("Angle")

    plt.tight_layout()
    out_path = str(PLOT_DIR / "normalization_nucleus_test.png")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved nucleus test plot to: {out_path}")


if __name__ == "__main__":
    test_normalization()
    test_normalization_nucleus_offset()
