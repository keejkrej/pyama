"""Progress tracking utilities for tests."""

from tqdm import tqdm


def create_progress_callback(pbar: tqdm):
    """Create a progress callback function that updates a tqdm progress bar.
    
    This helper creates a callback function compatible with PyAMA's progress
    callback signature: ``(current: int, total: int, message: str) -> None``.
    
    The callback tracks the last reported position to avoid duplicate updates
    when the same frame is reported multiple times (e.g., during tracking
    where region extraction and tracking phases both report progress).
    
    Args:
        pbar: tqdm progress bar instance to update.
        
    Returns:
        Callback function with signature (current, total, message).
        
    Example:
        >>> from tqdm import tqdm
        >>> with tqdm(total=100, desc="Processing") as pbar:
        ...     callback = create_progress_callback(pbar)
        ...     callback(50, 100, "Halfway done")
    """
    last_current = -1
    
    def callback(current: int, total: int, message: str) -> None:
        nonlocal last_current
        # Update progress bar to the current position
        if current > last_current:
            pbar.update(current - last_current)
            last_current = current
        pbar.set_postfix_str(message)
    return callback
