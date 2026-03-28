"""JSON codec for the pyama RPC protocol."""

from dataclasses import fields, is_dataclass
from enum import Enum
import importlib
from pathlib import Path
from typing import Any


def to_wire(value: Any) -> Any:
    """Convert a Python object into a JSON-safe RPC payload."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Path):
        return {"__pyama_path__": str(value)}
    if isinstance(value, Enum):
        return {
            "__pyama_enum__": f"{value.__class__.__module__}:{value.__class__.__name__}",
            "name": value.name,
        }
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "__pyama_dataclass__": (
                f"{value.__class__.__module__}:{value.__class__.__name__}"
            ),
            "data": {
                field.name: to_wire(getattr(value, field.name))
                for field in fields(value)
            },
        }
    if isinstance(value, tuple):
        return {"__pyama_tuple__": [to_wire(item) for item in value]}
    if isinstance(value, list):
        return [to_wire(item) for item in value]
    if isinstance(value, dict):
        return {
            "__pyama_dict__": [
                [to_wire(key), to_wire(item)] for key, item in value.items()
            ]
        }
    raise TypeError(f"Unsupported RPC value: {type(value)!r}")


def from_wire(value: Any) -> Any:
    """Decode an RPC payload back into Python objects."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list):
        return [from_wire(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "__pyama_path__" in value:
        return Path(str(value["__pyama_path__"]))
    if "__pyama_tuple__" in value:
        return tuple(from_wire(item) for item in value["__pyama_tuple__"])
    if "__pyama_dict__" in value:
        return {
            from_wire(key): from_wire(item)
            for key, item in value["__pyama_dict__"]
        }
    if "__pyama_enum__" in value:
        module_name, class_name = str(value["__pyama_enum__"]).split(":", maxsplit=1)
        module = importlib.import_module(module_name)
        enum_cls = getattr(module, class_name)
        return enum_cls[str(value["name"])]
    if "__pyama_dataclass__" in value:
        module_name, class_name = str(value["__pyama_dataclass__"]).split(
            ":",
            maxsplit=1,
        )
        module = importlib.import_module(module_name)
        dataclass_type = getattr(module, class_name)
        payload = {
            str(key): from_wire(item)
            for key, item in dict(value["data"]).items()
        }
        return dataclass_type(**payload)
    return {str(key): from_wire(item) for key, item in value.items()}


__all__ = ["from_wire", "to_wire"]
