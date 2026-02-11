# Plugins

Plugins go in `~/.pyama/plugins/` by type: `features/phase_contrast/`, `features/fluorescence/`, `fitting/`.

**Install**: File → Install Plugin... in PyAMA-Pro, or copy `.py` to `~/.pyama/plugins/` and restart.

**Features**: `extract_{name}(ctx: ExtractionContext) -> float`; register in `PHASE_FEATURES` or `FLUORESCENCE_FEATURES`, or `register_plugin_feature()`. See `examples/plugins/features/`.

**Models**: `Params`, `Bounds`, `DEFAULTS`, `BOUNDS`, `eval(t, params)`. Add to `MODELS` or `register_plugin_model()`. See `maturation.py`, `examples/plugins/fitting/exponential_decay.py`.
