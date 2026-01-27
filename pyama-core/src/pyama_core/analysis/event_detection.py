"""
Event detection for sudden changes in fluorescence traces (e.g., caspase, PI signals).

Implements CUSUM (Cumulative Sum Control Chart) for robust single-event detection.
"""

import numpy as np

from pyama_core.types.analysis import EventResult


def detect_event_cusum(
    t_data: np.ndarray,
    y_data: np.ndarray,
    threshold: float | None = None,
) -> EventResult:
    """Detect single event using an offline CUSUM (argmax of cumulative sum).

    We compute the cumulative sum of demeaned data S_t = sum_{i<=t}(y_i - mean(y)).
    For a single mean shift, |S_t| typically attains its maximum at the change time.
    This avoids arbitrary threshold-crossing latency and pinpoints the step.

    Args:
        t_data: Time array (seconds or frames)
        y_data: Fluorescence intensity array
        threshold: Optional significance threshold on the standardized CUSUM
                   statistic max|S|/(sigma*sqrt(N)). If None, uses 2.0.

    Returns:
        EventResult with event time, magnitude, confidence, and diagnostics
    """
    # Clean data
    mask = ~(np.isnan(t_data) | np.isnan(y_data))
    t_clean = t_data[mask].astype(np.float64)
    y_clean = y_data[mask].astype(np.float64)

    n = len(y_clean)
    if n < 10:
        return EventResult(
            event_detected=False,
            event_time=None,
            event_magnitude=None,
            confidence=0.0,
            event_index=None,
        )

    # Demean and compute cumulative sum
    y_mean = float(np.mean(y_clean))
    y_demean = y_clean - y_mean
    S = np.cumsum(y_demean)

    # Standard deviation for confidence/statistic
    sigma = float(np.std(y_clean))
    if sigma < 1e-12:
        return EventResult(
            event_detected=False,
            event_time=None,
            event_magnitude=None,
            confidence=0.0,
            event_index=None,
        )

    # Avoid edges when picking the maximum
    margin = max(3, int(0.05 * n))
    idx_range = slice(margin, n - margin)
    absS = np.abs(S[idx_range])
    if absS.size == 0:
        return EventResult(
            event_detected=False,
            event_time=None,
            event_magnitude=None,
            confidence=0.0,
            event_index=None,
        )
    rel_idx = int(np.argmax(absS))
    event_idx = rel_idx + margin

    # Magnitude estimate: difference of means after vs before
    magnitude = float(np.mean(y_clean[event_idx:]) - np.mean(y_clean[:event_idx]))

    # Standardized CUSUM statistic
    max_absS = float(np.max(absS))
    stat = max_absS / (sigma * np.sqrt(n))
    # Start with a practical base threshold (<=2.0), then scale with sqrt(n/50)
    base_thr = 2.0 if threshold is None else float(min(2.0, threshold))
    thr = float(base_thr * np.sqrt(n / 50.0))
    thr = float(min(2.0, max(0.8, thr)))  # keep within [0.8, 2.0]

    if stat < thr:
        return EventResult(
            event_detected=False,
            event_time=None,
            event_magnitude=None,
            confidence=float(stat / thr),
            event_index=None,
            cusum_pos_peak=None,
            cusum_neg_peak=None,
        )

    event_time = float(t_clean[event_idx])
    confidence = float(min(1.0, stat / 5.0))

    # Penalize monotonic trends: detrend and recompute standardized statistic
    try:
        p = np.polyfit(t_clean, y_clean, deg=1)
        trend = np.polyval(p, t_clean)
        resid = y_clean - trend
        resid_sigma = float(np.std(resid))
        if resid_sigma < 1e-12 and abs(p[0]) > 1e-12:
            # Pure trend with essentially zero residuals -> not a true step
            confidence = float(min(confidence, 0.3))
        else:
            # Only penalize if linear trend explains most variance
            if sigma > 0 and (resid_sigma / sigma) < 0.2:
                S_d = np.cumsum(resid - np.mean(resid))
                max_absS_d = float(np.max(np.abs(S_d[margin:n - margin]))) if n - margin > margin else 0.0
                stat_d = max_absS_d / (resid_sigma * np.sqrt(n)) if resid_sigma > 1e-12 else 0.0
                confidence = float(min(confidence, min(1.0, stat_d / 5.0)))
    except Exception:
        pass

    return EventResult(
        event_detected=True,
        event_time=event_time,
        event_magnitude=magnitude,
        confidence=confidence,
        event_index=event_idx,
        cusum_pos_peak=None,
        cusum_neg_peak=None,
    )
