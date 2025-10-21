"""Workflow wizard components for pyama-air GUI."""

from pyama_air.gui.workflow.main_wizard import WorkflowWizard
from pyama_air.gui.workflow.pages import (
    ChannelConfigurationPage,
    ExecutionPage,
    FeatureSelectionPage,
    FileSelectionPage,
    ParameterConfigurationPage,
)

__all__ = [
    "WorkflowWizard",
    "FileSelectionPage",
    "ChannelConfigurationPage",
    "FeatureSelectionPage",
    "ParameterConfigurationPage",
    "ExecutionPage",
]
