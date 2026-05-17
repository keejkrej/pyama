# Pyama

Pure-Python desktop port of the Pyama aligner and annotator workflows.

```powershell
uv run aligner
uv run annotator
```

The application reads TIFF/PNG/JPG folder workspaces plus ND2 and CZI sources, then writes Lisca-compatible alignment, ROI, label, and annotation files.
