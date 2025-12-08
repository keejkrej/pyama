import numpy as np
import xarray as xr
from scipy.ndimage import map_coordinates, center_of_mass
from skimage.measure import find_contours
from scipy.interpolate import interp1d


def normalize_cell_polar(
    images: np.ndarray,
    masks: np.ndarray,
    r_resolution: int = 100,
    theta_resolution: int = 100,
    order: int = 1,
) -> xr.DataArray:
    """
    Normalize cell images to a polar coordinate system where the cell boundary is at r=1.

    Args:
        images: Input images with shape (T, C, H, W).
        masks: Boolean masks with shape (T, H, W).
        r_resolution: Number of radial steps (normalized r from 0 to 1).
        theta_resolution: Number of angular steps.
        order: Interpolation order for map_coordinates (0=nearest, 1=linear, etc.).

    Returns:
        xarray.DataArray with shape (T, C, theta_resolution, r_resolution).
        Dimensions: ('time', 'channel', 'angle', 'radius').
        Coordinates:
            angle: 0 to 1 (normalized angle).
            radius: 0 to 1 (normalized radius).
            boundary_radius: (time, angle) - The boundary radius R(theta) for each frame.
    """

    T, C, H, W = images.shape
    if masks.shape != (T, H, W):
        raise ValueError("Masks shape must be (T, H, W) matching images (T, C, H, W).")

    # Output array: (T, C, theta_resolution, r_resolution)
    normalized = np.zeros((T, C, theta_resolution, r_resolution), dtype=images.dtype)

    # Store boundary radius for integral calculation: (T, theta_resolution)
    boundary_radii_store = np.zeros((T, theta_resolution), dtype=np.float32)

    # Pre-compute theta grid in radians for calculation
    calc_thetas = np.linspace(0, 2 * np.pi, theta_resolution, endpoint=False)

    # Pre-compute normalized radius grid for calculation
    # We use endpoint=False to ensure uniform bin width of 1/N_r
    out_rs = np.linspace(0, 1, r_resolution, endpoint=False)

    # Coordinates
    coords_angle = np.linspace(0, 1, theta_resolution, endpoint=False)
    coords_radius = out_rs

    for t in range(T):
        mask = masks[t]
        if not np.any(mask):
            continue

        cy, cx = center_of_mass(mask)

        # Find boundary and R(theta)
        contours = find_contours(mask, 0.5)
        if not contours:
            continue

        contour = max(contours, key=len)

        dy = contour[:, 0] - cy
        dx = contour[:, 1] - cx

        r_contour = np.sqrt(dx**2 + dy**2)
        theta_contour = np.arctan2(dy, dx)
        theta_contour = np.mod(theta_contour, 2 * np.pi)

        # Sort and interpolate
        sorted_idx = np.argsort(theta_contour)
        theta_sorted = theta_contour[sorted_idx]
        r_sorted = r_contour[sorted_idx]

        theta_pad = np.concatenate(
            [
                theta_sorted[-10:] - 2 * np.pi,
                theta_sorted,
                theta_sorted[:10] + 2 * np.pi,
            ]
        )
        r_pad = np.concatenate([r_sorted[-10:], r_sorted, r_sorted[:10]])

        interpolator = interp1d(
            theta_pad,
            r_pad,
            kind="linear",
            bounds_error=False,
            fill_value="extrapolate",
        )
        boundary_r = interpolator(calc_thetas)  # shape (theta_resolution,)

        boundary_radii_store[t] = boundary_r

        # Create sampling coordinates
        boundary_r_grid = np.tile(boundary_r[:, np.newaxis], (1, r_resolution))
        out_rs_grid = np.tile(out_rs[np.newaxis, :], (theta_resolution, 1))

        r_real_grid = out_rs_grid * boundary_r_grid
        theta_grid = np.tile(calc_thetas[:, np.newaxis], (1, r_resolution))

        sample_x = cx + r_real_grid * np.cos(theta_grid)
        sample_y = cy + r_real_grid * np.sin(theta_grid)

        coords = np.stack([sample_y, sample_x])

        for c in range(C):
            normalized[t, c] = map_coordinates(
                images[t, c], coords, order=order, mode="constant", cval=0.0
            )

    # Wrap in xarray
    da = xr.DataArray(
        normalized,
        dims=("time", "channel", "angle", "radius"),
        coords={
            "time": np.arange(T),
            "channel": np.arange(C),
            "angle": coords_angle,
            "radius": coords_radius,
            "boundary_radius": (("time", "angle"), boundary_radii_store),
        },
        attrs={
            "description": "Polar normalized cell images",
            "boundary_r_normalized": 1.0,
            "angle_range": "0-1 (mapped from 0-2pi)",
        },
    )

    return da


def integrate_polar(da: xr.DataArray) -> xr.DataArray:
    """
    Compute the intensity integral over the cell area in a coordinate-invariant way.

    The integral in Cartesian coordinates is sum(I(x,y) dx dy).
    In polar coordinates (r', theta'), the Jacobian determinant is J = 2*pi * r' * R(theta)^2.

    Args:
        da: xarray.DataArray output from normalize_cell_polar.

    Returns:
        xarray.DataArray of shape (time, channel) containing the integrated intensity.
    """
    # Verify required coordinates exist
    if "boundary_radius" not in da.coords:
        raise ValueError(
            "DataArray must have 'boundary_radius' coordinate for integration."
        )

    # Get coordinates
    radius = da.radius  # normalized radius r'
    # angle = da.angle # normalized angle theta'
    boundary_r = da.boundary_radius  # R(theta)

    # Dimensions
    # da is (time, channel, angle, radius)
    # radius is (radius,) or (radius) dim
    # boundary_r is (time, angle)

    # We need to broadcast everything to (time, channel, angle, radius)

    # Jacobian: J(r', theta) = 2 * pi * r' * R(theta)^2
    # Note: This Jacobian is for the coordinate change.

    # Area element integration:
    # Integral = sum( I(r', theta') * J(r', theta') * delta_r' * delta_theta' )

    # delta_theta' = 1 / N_theta (since angle is 0 to 1)
    # delta_r' = 1 / N_r (since radius is 0 to 1)
    # But strictly speaking we should use gradient or spacing if non-uniform.
    # Here we assume uniform spacing as generated by normalize_cell_polar.

    n_theta = da.sizes["angle"]
    n_r = da.sizes["radius"]

    delta_theta = 1.0 / n_theta
    delta_r = 1.0 / n_r

    # R(theta)^2 -> (time, angle)
    R_sq = boundary_r**2

    # r' -> (radius)
    r_prime = radius

    # Jacobian factor (excluding 2pi which comes from d_theta = 2pi * d_theta')
    # Wait, my coordinate transformation was:
    # theta = 2 * pi * theta'
    # r = r' * R(theta)
    # So d_theta = 2 * pi * d_theta'
    # d_r = ... (jacobian handled by determinant)
    # J = det( d(x,y)/d(r', theta') ) = 2 * pi * r' * R(theta)^2

    # So Area Element dA = 2 * pi * r' * R^2 * dr' * dtheta'

    # We can compute this term broadcasting
    # r_prime needs to broadcast over time, channel, angle

    # Compute integral
    # We sum over angle and radius axes

    # Weighted Sum = Sum( I * (2 * pi * r' * R^2) * (1/Nr) * (1/Ntheta) )

    # Let's construct the weight array
    # R_sq is (time, angle). Broadcast to (time, channel, angle, radius)
    # r_prime is (radius). Broadcast to ...

    factor = 2 * np.pi * delta_theta * delta_r

    # We can do this efficiently using xarray
    # (time, angle) * (radius) -> (time, angle, radius)
    jacobian_term = R_sq * r_prime

    weighted_image = da * jacobian_term

    integral = weighted_image.sum(dim=["angle", "radius"]) * factor

    return integral
