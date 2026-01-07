"""Task registry for mapping task types to task classes."""

from typing import Type

from ..models import TaskType
from .base import BaseTask
from .dummy import DummyTask
from .tokenize import TokenizeTask


class TaskRegistry:
    """
    Registry mapping TaskType to task class implementations.

    To add a new task type:
    1. Create a new task class that inherits from BaseTask
    2. Add it to the _registry dictionary below
    3. Add the TaskType enum value to models.py

    Example:
        from .my_task import MyTask

        class TaskRegistry:
            _registry = {
                TaskType.MY_TASK: MyTask,
                ...
            }
    """

    # Map TaskType enum to task class
    _registry: dict[TaskType, Type[BaseTask]] = {
        TaskType.DUMMY_SHORT: DummyTask,
        TaskType.DUMMY_LONG: DummyTask,
        TaskType.DUMMY_VERY_LONG: DummyTask,
        TaskType.TOKENIZE: TokenizeTask,
    }

    # Default parameters for each task type
    _default_parameters: dict[TaskType, dict] = {
        TaskType.DUMMY_SHORT: {"duration": 5, "steps": 5},
        TaskType.DUMMY_LONG: {"duration": 30, "steps": 10},
        TaskType.DUMMY_VERY_LONG: {"duration": 120, "steps": 20},
        TaskType.TOKENIZE: {"encoding": "cl100k_base", "sleep_duration": 60},
    }

    @classmethod
    def get_task_class(cls, task_type: TaskType) -> Type[BaseTask]:
        """
        Get the task class for a given task type.

        Args:
            task_type: The TaskType enum value

        Returns:
            Task class that inherits from BaseTask

        Raises:
            ValueError: If task type is not registered
        """
        if task_type not in cls._registry:
            raise ValueError(f"Unknown task type: {task_type}")
        return cls._registry[task_type]

    @classmethod
    def get_default_parameters(cls, task_type: TaskType) -> dict:
        """
        Get default parameters for a task type.

        Args:
            task_type: The TaskType enum value

        Returns:
            Dictionary of default parameters
        """
        return cls._default_parameters.get(task_type, {}).copy()

    @classmethod
    def merge_parameters(cls, task_type: TaskType, user_params: dict) -> dict:
        """
        Merge user-provided parameters with defaults.

        Args:
            task_type: The TaskType enum value
            user_params: User-provided parameters

        Returns:
            Merged parameters dictionary (defaults + user overrides)
        """
        defaults = cls.get_default_parameters(task_type)
        defaults.update(user_params)
        return defaults

    @classmethod
    def list_registered_tasks(cls) -> list[TaskType]:
        """
        Get list of all registered task types.

        Returns:
            List of TaskType enum values
        """
        return list(cls._registry.keys())
