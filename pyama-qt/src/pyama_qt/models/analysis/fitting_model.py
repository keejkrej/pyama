"""Fitting model for analysis configuration and status."""

from typing import Dict
from PySide6.QtCore import QObject, Signal


class FittingModel(QObject):
    """Model for fitting configuration and status."""

    isFittingChanged = Signal(bool)
    statusMessageChanged = Signal(str)
    errorMessageChanged = Signal(str)
    modelTypeChanged = Signal(str)
    modelParamsChanged = Signal(dict)
    modelBoundsChanged = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._is_fitting: bool = False
        self._status_message: str = ""
        self._error_message: str = ""
        self._model_type: str = "trivial"
        self._model_params: Dict[str, float] = {}
        self._model_bounds: Dict[str, tuple[float, float]] = {}

    def is_fitting(self) -> bool:
        return self._is_fitting

    def set_is_fitting(self, value: bool) -> None:
        if self._is_fitting == value:
            return
        self._is_fitting = value
        self.isFittingChanged.emit(value)

    def status_message(self) -> str:
        return self._status_message

    def set_status_message(self, message: str) -> None:
        if self._status_message == message:
            return
        self._status_message = message
        self.statusMessageChanged.emit(message)

    def error_message(self) -> str:
        return self._error_message

    def set_error_message(self, message: str) -> None:
        if self._error_message == message:
            return
        self._error_message = message
        self.errorMessageChanged.emit(message)

    def model_type(self) -> str:
        return self._model_type

    def set_model_type(self, model_type: str) -> None:
        if self._model_type == model_type:
            return
        self._model_type = model_type
        self.modelTypeChanged.emit(model_type)

    def model_params(self) -> Dict[str, float]:
        return self._model_params

    def set_model_params(self, params: Dict[str, float]) -> None:
        if self._model_params == params:
            return
        self._model_params = params
        self.modelParamsChanged.emit(params)

    def model_bounds(self) -> Dict[str, tuple[float, float]]:
        return self._model_bounds

    def set_model_bounds(self, bounds: Dict[str, tuple[float, float]]) -> None:
        if self._model_bounds == bounds:
            return
        self._model_bounds = bounds
        self.modelBoundsChanged.emit(bounds)
