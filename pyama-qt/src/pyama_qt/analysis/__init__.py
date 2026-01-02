"""Analysis module components for data fitting and parameter analysis.

This module provides the comparison tab for multi-sample analysis,
standalone analysis windows, and sub-components for loading trace data,
performing model fitting, and analyzing parameter distributions.
"""

# =============================================================================
# IMPORTS
# =============================================================================

from pyama_qt.analysis.analysis_window import AnalysisWindow
from pyama_qt.analysis.comparison import ComparisonPanel
from pyama_qt.analysis.data import DataPanel
from pyama_qt.analysis.main_tab import AnalysisTab
from pyama_qt.analysis.parameter import ParameterPanel
from pyama_qt.analysis.quality import QualityPanel

__all__ = [
    "AnalysisTab",
    "AnalysisWindow",
    "ComparisonPanel",
    "DataPanel",
    "ParameterPanel",
    "QualityPanel",
]
