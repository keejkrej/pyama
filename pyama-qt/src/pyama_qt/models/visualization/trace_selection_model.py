"""Trace selection model for visualization."""

from PySide6.QtCore import QObject, Signal


class TraceSelectionModel(QObject):
    """Model for managing trace selection state."""

    selectionChanged = Signal(list)  # list of selected trace IDs
    activeTraceChanged = Signal(str)  # active trace ID

    def __init__(self) -> None:
        super().__init__()
        self._selected_traces: list[str] = []
        self._active_trace: str | None = None

    def selected_traces(self) -> list[str]:
        return self._selected_traces

    def active_trace(self) -> str | None:
        return self._active_trace

    def set_selected_traces(self, trace_ids: list[str]) -> None:
        if self._selected_traces == trace_ids:
            return
        self._selected_traces = trace_ids
        self.selectionChanged.emit(trace_ids)

    def set_active_trace(self, trace_id: str | None) -> None:
        if self._active_trace == trace_id:
            return
        self._active_trace = trace_id
        self.activeTraceChanged.emit(trace_id)

    def add_trace_to_selection(self, trace_id: str) -> None:
        """Add a trace to the selection."""
        if trace_id not in self._selected_traces:
            self._selected_traces.append(trace_id)
            self.selectionChanged.emit(self._selected_traces)

    def remove_trace_from_selection(self, trace_id: str) -> None:
        """Remove a trace from the selection."""
        if trace_id in self._selected_traces:
            self._selected_traces.remove(trace_id)
            self.selectionChanged.emit(self._selected_traces)

    def clear_selection(self) -> None:
        """Clear all selected traces."""
        if self._selected_traces:
            self._selected_traces.clear()
            self.selectionChanged.emit([])

    def is_trace_selected(self, trace_id: str) -> bool:
        """Check if a trace is selected."""
        return trace_id in self._selected_traces
