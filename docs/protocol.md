# Testing Protocol

Prereqs: `uv sync`, test ND2, output dir.

**Processing**: Launch → Browse ND2 → configure → Start Workflow → Cancel test → Complete → Merge (samples.yaml + processing output folder)

**Visualization**: Load Folder → select channels → Start → navigate traces, toggle good/bad → Save Inspected CSV

**Modeling**: Load CSV → pick model → Start Fitting → quality panel, parameter analysis, Save All Plots
**Statistics**: Load merge_output folder → run AUC/Onset → inspect normalized traces → compare sample distributions

**Cross-tab**: Full flow; tab switching; error handling for invalid files
