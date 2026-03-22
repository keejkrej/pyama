# Testing Protocol

Prereqs: `uv sync`, test ND2, output dir.

**Processing**: Launch → set workspace → Browse ND2/CZI → configure channels and parameters → Start → optional cancel test → complete → Merge (`samples.yaml` + workspace output)

**Visualization**: Load Folder → select channels → Start → navigate traces, toggle good/bad → Save Inspected CSV

**Modeling**: Load CSV → pick model → Start Fitting → quality panel, parameter analysis, Save All Plots
**Statistics**: Load `traces_merged` folder (or a workspace containing it) → run AUC/Onset → inspect normalized traces → compare sample distributions

**Cross-tab**: workspace startup prompt; full flow; tab switching; error handling for invalid files
